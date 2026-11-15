import json
import logging
import time
import uuid
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, StreamingHttpResponse, HttpResponseBadRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .models import Conversation, ChatMessage, EdithAPIKey
from .services import ollama_service
from .agents import evaluate_model_recommendation
from django.conf import settings

logger = logging.getLogger(__name__)


def get_edith_system_prompt() -> str:
    """Load persistent context from memory.md into EDITH's working memory."""
    memory_path = settings.BASE_DIR / 'memory.md'
    memory_snippet = ""
    if memory_path.exists():
        try:
            full_text = memory_path.read_text(encoding='utf-8')
            # Extract key sections to keep context window compact
            memory_snippet = full_text[:3500]
        except Exception as e:
            logger.warning("Could not read memory.md: %s", e)

    prompt = (
        "You are EDITH, a high-performance local AI assistant and multi-agent orchestrator.\n"
        "You maintain chain-of-thought awareness of your hardware, local model suite, and user preferences.\n"
        "Be insightful, precise, technically sound, and concise.\n"
    )
    if memory_snippet:
        prompt += f"\n--- PERSISTENT MEMORY (memory.md) ---\n{memory_snippet}\n------------------------------------\n"
    return prompt


def index(request):
    """Render the primary single-page chat interface (works for web and desktop)."""
    return render(request, 'assistant/index.html')


def api_ollama_status(request):
    """Return health check and available models from local Ollama."""
    health = ollama_service.check_health()
    models = ollama_service.get_models()
    # Filter out embedding models from the generation dropdown
    generative_models = [
        m for m in models
        if not any(sub in m['name'].lower() for sub in ['embed', 'bge', 'nomic'])
    ]
    return JsonResponse({
        'health': health,
        'models': generative_models,
        'default_model': ollama_service.default_model,
    })


@csrf_exempt
@require_http_methods(["GET", "POST"])
def api_keys_view(request):
    """List all API keys (GET) or generate a new secret API key (POST)."""
    if request.method == 'GET':
        keys = EdithAPIKey.objects.all()
        data = [
            {
                'id': str(k.id),
                'name': k.name,
                'prefix': k.prefix,
                'created_at': k.created_at.strftime('%Y-%m-%d %H:%M'),
                'last_used_at': k.last_used_at.strftime('%Y-%m-%d %H:%M') if k.last_used_at else 'Never',
                'is_active': k.is_active,
            }
            for k in keys
        ]
        return JsonResponse({'keys': data})

    if request.method == 'POST':
        try:
            body = json.loads(request.body.decode('utf-8')) if request.body else {}
        except json.JSONDecodeError:
            body = {}

        key_name = (body.get('name') or 'Default Key').strip()[:100]
        key_obj, raw_key = EdithAPIKey.generate(name=key_name)
        return JsonResponse({
            'success': True,
            'id': str(key_obj.id),
            'name': key_obj.name,
            'prefix': key_obj.prefix,
            'raw_key': raw_key,  # Returned only once!
            'created_at': key_obj.created_at.strftime('%Y-%m-%d %H:%M'),
            'message': 'API Key generated successfully. Please copy it now.'
        }, status=201)


@csrf_exempt
@require_http_methods(["DELETE"])
def api_key_delete_view(request, key_id):
    """Delete or revoke an API key."""
    key_obj = get_object_or_404(EdithAPIKey, id=key_id)
    key_obj.delete()
    return JsonResponse({'success': True, 'id': str(key_id)})


@csrf_exempt
def api_v1_models(request):
    """
    OpenAI-compatible /v1/models endpoint for Hermes Agent and external clients.
    """
    if request.method == "OPTIONS":
        response = HttpResponse()
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return response

    models = ollama_service.get_models()
    generative_models = [
        m for m in models
        if not any(sub in m['name'].lower() for sub in ['embed', 'bge', 'nomic'])
    ]

    current_ts = int(time.time())
    data = []
    for m in generative_models:
        data.append({
            "id": m['name'],
            "object": "model",
            "created": current_ts,
            "owned_by": "edith-local",
            "permission": [],
            "root": m['name'],
            "parent": None
        })

    response = JsonResponse({
        "object": "list",
        "data": data
    })
    response["Access-Control-Allow-Origin"] = "*"
    response["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response


@csrf_exempt
def api_v1_chat_completions(request):
    """
    OpenAI-compatible chat completions endpoint authenticated via 'Authorization: Bearer edith_sk_...'
    Supports both non-streaming and streaming responses for Hermes, n8n, Claude Code, and custom scripts.
    """
    if request.method == "OPTIONS":
        response = HttpResponse()
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return response

    if request.method != "POST":
        return HttpResponseBadRequest("Only POST method allowed")

    # Optional / Flexible auth for local tools like Hermes and external callers
    auth_header = request.headers.get('Authorization', '')
    authenticated_as = "Local Client"

    if auth_header.startswith('Bearer '):
        raw_token = auth_header.split('Bearer ', 1)[1].strip()
        key_obj = EdithAPIKey.verify(raw_token)
        if key_obj:
            authenticated_as = key_obj.name
        else:
            return JsonResponse({'error': 'Invalid or inactive EDITH API Key.'}, status=401)

    try:
        body = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")

    messages = body.get('messages', [])
    model = body.get('model') or ollama_service.default_model
    stream = bool(body.get('stream', False))

    if not messages:
        return HttpResponseBadRequest("Messages list cannot be empty")

    request_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    created_ts = int(time.time())

    # Streaming mode (SSE with OpenAI chunk structure)
    if stream:
        def stream_generator():
            try:
                for chunk in ollama_service.stream_chat(messages=messages, model=model):
                    if chunk.get('error'):
                        yield f"data: {json.dumps({'error': chunk['error']})}\n\n"
                        break

                    token = chunk.get('token', '')
                    if token:
                        chunk_payload = {
                            "id": request_id,
                            "object": "chat.completion.chunk",
                            "created": created_ts,
                            "model": model,
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {"content": token},
                                    "finish_reason": None
                                }
                            ]
                        }
                        yield f"data: {json.dumps(chunk_payload)}\n\n"

                    if chunk.get('done'):
                        end_payload = {
                            "id": request_id,
                            "object": "chat.completion.chunk",
                            "created": created_ts,
                            "model": model,
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {},
                                    "finish_reason": "stop"
                                }
                            ]
                        }
                        yield f"data: {json.dumps(end_payload)}\n\n"
                        yield "data: [DONE]\n\n"
                        break
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        response = StreamingHttpResponse(stream_generator(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        response["Access-Control-Allow-Origin"] = "*"
        return response

    # Non-streaming mode
    tokens = []
    for chunk in ollama_service.stream_chat(messages=messages, model=model):
        if chunk.get('token'):
            tokens.append(chunk['token'])
        if chunk.get('error'):
            return JsonResponse({'error': chunk['error']}, status=500)

    content = "".join(tokens)
    response = JsonResponse({
        'id': request_id,
        'object': 'chat.completion',
        'created': created_ts,
        'model': model,
        'authenticated_as': authenticated_as,
        'choices': [
            {
                'index': 0,
                'message': {
                    'role': 'assistant',
                    'content': content
                },
                'finish_reason': 'stop'
            }
        ],
        'usage': {
            'prompt_tokens': max(1, len(str(messages)) // 4),
            'completion_tokens': max(1, len(content) // 4),
            'total_tokens': max(2, (len(str(messages)) + len(content)) // 4)
        }
    })
    response["Access-Control-Allow-Origin"] = "*"
    return response


@csrf_exempt
@require_http_methods(["POST"])
def api_check_model_suggestion(request):
    """
    Evaluates whether the user's task would be better handled by an alternative model.
    Returns recommendation details so EDITH can ask permission from the user.
    """
    try:
        body = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")

    message = (body.get('message') or '').strip()
    current_model = body.get('current_model') or ollama_service.default_model

    if not message:
        return JsonResponse({'switch_recommended': False})

    recommendation = evaluate_model_recommendation(message, current_model)
    return JsonResponse(recommendation)


@require_http_methods(["GET", "POST"])
@csrf_exempt
def api_conversations(request):
    """List all conversations or create a new one."""
    if request.method == 'GET':
        conversations = Conversation.objects.all().prefetch_related('messages')
        data = []
        for c in conversations:
            first_msg = c.messages.first()
            preview = first_msg.content[:60] if first_msg else ""
            data.append({
                'id': str(c.id),
                'title': c.title,
                'created_at': c.created_at.isoformat(),
                'updated_at': c.updated_at.isoformat(),
                'preview': preview,
                'message_count': c.messages.count(),
            })
        return JsonResponse({'conversations': data})

    if request.method == 'POST':
        try:
            body = json.loads(request.body.decode('utf-8')) if request.body else {}
        except json.JSONDecodeError:
            body = {}
        title = body.get('title', 'New Conversation')
        conv = Conversation.objects.create(title=title)
        return JsonResponse({
            'id': str(conv.id),
            'title': conv.title,
            'created_at': conv.created_at.isoformat(),
            'updated_at': conv.updated_at.isoformat(),
        }, status=201)


@require_http_methods(["GET", "DELETE", "PATCH"])
@csrf_exempt
def api_conversation_detail(request, conversation_id):
    """Get, delete, or rename a specific conversation."""
    conv = get_object_or_404(Conversation, id=conversation_id)

    if request.method == 'GET':
        messages = [
            {
                'id': m.id,
                'role': m.role,
                'content': m.content,
                'model': m.model,
                'created_at': m.created_at.isoformat(),
            }
            for m in conv.messages.all()
        ]
        return JsonResponse({
            'id': str(conv.id),
            'title': conv.title,
            'created_at': conv.created_at.isoformat(),
            'updated_at': conv.updated_at.isoformat(),
            'messages': messages,
        })

    if request.method == 'DELETE':
        conv.delete()
        return JsonResponse({'success': True, 'id': str(conversation_id)})

    if request.method == 'PATCH':
        try:
            body = json.loads(request.body.decode('utf-8'))
        except json.JSONDecodeError:
            return HttpResponseBadRequest("Invalid JSON")
        new_title = body.get('title')
        if new_title:
            conv.title = new_title.strip()[:255]
            conv.save(update_fields=['title', 'updated_at'])
        return JsonResponse({'id': str(conv.id), 'title': conv.title})


@csrf_exempt
@require_http_methods(["POST"])
def api_chat_stream(request):
    """
    Accepts user message, streams local LLM tokens using Server-Sent Events,
    and persists both user and assistant messages in the database.
    """
    try:
        body = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON payload")

    user_text = (body.get('message') or '').strip()
    if not user_text:
        return HttpResponseBadRequest("Message cannot be empty")

    conversation_id = body.get('conversation_id')
    raw_model = body.get('model') or ollama_service.default_model
    system_prompt = body.get('system_prompt') or get_edith_system_prompt()

    # If user selected Auto routing, automatically resolve the best model
    if raw_model.lower() in ['auto', 'auto-smart']:
        recommendation = evaluate_model_recommendation(user_text, 'auto')
        selected_model = recommendation['suggested_model']
        model_routed_reason = recommendation['reason']
    else:
        # User specified model: respect default as requested
        selected_model = raw_model
        model_routed_reason = None

    # Get or create conversation
    if conversation_id:
        conversation = get_object_or_404(Conversation, id=conversation_id)
    else:
        title = user_text[:35] + ('...' if len(user_text) > 35 else '')
        conversation = Conversation.objects.create(title=title)

    # Save User message
    ChatMessage.objects.create(
        conversation=conversation,
        role='user',
        content=user_text,
        model=selected_model
    )

    # Gather conversation history for context
    history_records = conversation.messages.all().order_by('created_at')
    formatted_messages = [
        {'role': m.role, 'content': m.content}
        for m in history_records
    ]

    def event_stream():
        yield f"data: {json.dumps({'event': 'start', 'conversation_id': str(conversation.id), 'title': conversation.title, 'model': selected_model, 'note': model_routed_reason})}\n\n"

        assistant_full_reply = []

        try:
            for chunk in ollama_service.stream_chat(
                messages=formatted_messages,
                model=selected_model,
                system_prompt=system_prompt
            ):
                if chunk.get('error'):
                    yield f"data: {json.dumps({'event': 'error', 'error': chunk['error']})}\n\n"
                    break

                token = chunk.get('token', '')
                if token:
                    assistant_full_reply.append(token)
                    yield f"data: {json.dumps({'event': 'token', 'token': token})}\n\n"

                if chunk.get('done'):
                    full_content = "".join(assistant_full_reply)
                    saved_msg = ChatMessage.objects.create(
                        conversation=conversation,
                        role='assistant',
                        content=full_content,
                        model=selected_model
                    )
                    conversation.save(update_fields=['updated_at'])
                    yield f"data: {json.dumps({'event': 'done', 'message_id': saved_msg.id, 'conversation_id': str(conversation.id)})}\n\n"
                    break
        except Exception as e:
            logger.exception("Error during LLM streaming")
            yield f"data: {json.dumps({'event': 'error', 'error': str(e)})}\n\n"

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response
