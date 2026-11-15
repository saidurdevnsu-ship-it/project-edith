import os
import json
import logging
from typing import Dict, Any, Optional
from ..services.ollama_service import ollama_service, _get_setting

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are EDITH's fast Intent Classifier and Router.
Classify the user's input into exactly ONE of the following categories:
- CODE: Programming, debugging, architecture, writing code, Git, refactoring.
- RESEARCH: Latest news, deep research, web search, factual inquiries, technology documentation.
- AUTOMATION: Scheduled tasks, workflows, webhooks, notifications, external integrations.
- REASONING: Math, complex multi-step logic, puzzle, algorithm analysis, theorem proving.
- GENERAL: Casual chat, quick translation, local file summary, creative writing, general assistance.

Output ONLY a valid JSON object matching this schema:
{
  "category": "CODE" | "RESEARCH" | "AUTOMATION" | "REASONING" | "GENERAL",
  "confidence": 0.0 to 1.0,
  "summary": "Short 1-sentence summary of the task"
}
Do not include any explanation or extra text outside the JSON.
"""


def classify_user_intent(user_text: str, model: Optional[str] = None) -> Dict[str, Any]:
    """
    Uses the lightweight local model (Qwen 2.5 1.5B) to classify the user's intent in < 200ms.
    """
    classifier_model = model or _get_setting('OLLAMA_CLASSIFIER_MODEL', 'qwen2.5:1.5b')
    prompt = f"User Request: {user_text}\nJSON Output:"

    try:
        tokens = []
        for chunk in ollama_service.stream_chat(
            messages=[{'role': 'user', 'content': prompt}],
            model=classifier_model,
            system_prompt=SYSTEM_PROMPT,
            options={'temperature': 0.1}
        ):
            if chunk.get('token'):
                tokens.append(chunk['token'])
            if chunk.get('error'):
                logger.error("Classifier error from Ollama: %s", chunk['error'])

        raw_output = "".join(tokens).strip()

        if "```json" in raw_output:
            raw_output = raw_output.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_output:
            raw_output = raw_output.split("```")[1].split("```")[0].strip()

        data = json.loads(raw_output)
        return data

    except Exception as e:
        logger.warning("Classifier fallback: %s", e)
        text_lower = user_text.lower()
        if any(w in text_lower for w in ['code', 'python', 'django', 'bug', 'function', 'class', 'fix', 'error', 'git', 'script']):
            return {"category": "CODE", "confidence": 0.8, "summary": user_text[:60]}
        elif any(w in text_lower for w in ['search', 'latest', 'news', 'research', 'what is', 'paper', 'who is', 'market']):
            return {"category": "RESEARCH", "confidence": 0.8, "summary": user_text[:60]}
        elif any(w in text_lower for w in ['workflow', 'automate', 'schedule', 'n8n', 'webhook', 'cron', 'email']):
            return {"category": "AUTOMATION", "confidence": 0.8, "summary": user_text[:60]}
        elif any(w in text_lower for w in ['calculate', 'prove', 'logic', 'puzzle', 'solve', 'math', 'equation']):
            return {"category": "REASONING", "confidence": 0.8, "summary": user_text[:60]}
        return {"category": "GENERAL", "confidence": 0.6, "summary": user_text[:60]}


def evaluate_model_recommendation(user_text: str, current_model: str) -> Dict[str, Any]:
    """
    Evaluates whether an alternative installed local model would perform significantly better
    for the user's task, and prepares a permission request for the user.
    """
    classification = classify_user_intent(user_text)
    category = classification.get('category', 'GENERAL')
    confidence = float(classification.get('confidence', 0.5))

    # Optimal Model Mapping for Local Hardware
    model_mapping = {
        'REASONING': {
            'model': 'deepseek-r1:1.5b',
            'agent': 'DeepSeek R1',
            'reason': 'This task involves multi-step logic and mathematical reasoning. DeepSeek-R1 (1.5B) produces dedicated chain-of-thought solutions.'
        },
        'CODE': {
            'model': 'qwen3:8b',
            'agent': 'Qwen 3 (8B) Developer',
            'reason': 'This task is coding/engineering. Qwen 3 (8B) provides state-of-the-art dual-mode coding and technical reasoning.'
        },
        'AUTOMATION': {
            'model': 'qwen2.5:1.5b',
            'agent': 'n8n & Fast Classifier',
            'reason': 'This task requires structured workflow parameters and trigger parsing.'
        },
        'RESEARCH': {
            'model': 'llama3.1:8b',
            'agent': 'Llama 3.1 8B / Grok',
            'reason': 'Research synthesis benefits from the larger 8B parameter capacity and deeper context.'
        },
        'GENERAL': {
            'model': 'llama3.1:8b',
            'agent': 'Llama 3.1 8B',
            'reason': 'General conversational requests excel with Llama 3.1 8B.'
        }
    }

    target = model_mapping.get(category, model_mapping['GENERAL'])
    suggested_model = target['model']

    # Determine if a switch is recommended
    # Only suggest if the suggested model is different from the current model and confidence is high
    is_auto = (current_model or '').lower() in ['auto', 'auto-smart']
    is_different = (suggested_model.lower() != (current_model or '').lower())
    switch_recommended = is_auto or (is_different and confidence >= 0.75)

    return {
        'category': category,
        'confidence': confidence,
        'current_model': current_model,
        'suggested_model': suggested_model,
        'recommended_agent': target['agent'],
        'reason': target['reason'],
        'switch_recommended': switch_recommended,
        'summary': classification.get('summary', user_text[:60])
    }
