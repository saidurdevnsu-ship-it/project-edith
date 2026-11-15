from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('api/status/', views.api_ollama_status, name='api_status'),
    path('api/check-suggestion/', views.api_check_model_suggestion, name='api_check_model_suggestion'),
    path('api/conversations/', views.api_conversations, name='api_conversations'),
    path('api/conversations/<uuid:conversation_id>/', views.api_conversation_detail, name='api_conversation_detail'),
    path('api/chat/stream/', views.api_chat_stream, name='api_chat_stream'),
    path('api/keys/', views.api_keys_view, name='api_keys'),
    path('api/keys/<uuid:key_id>/', views.api_key_delete_view, name='api_key_delete'),
    # OpenAI compatible endpoints (Hermes, n8n, Claude Code, Open-WebUI)
    path('v1/models', views.api_v1_models, name='v1_models'),
    path('v1/models/', views.api_v1_models, name='v1_models_slash'),
    path('v1/chat/completions', views.api_v1_chat_completions, name='v1_chat_completions'),
    path('v1/chat/completions/', views.api_v1_chat_completions, name='v1_chat_completions_slash'),

    # Handle cases where client appends /v1 to base URL ending in /v1
    path('v1/v1/models', views.api_v1_models, name='v1_v1_models'),
    path('v1/v1/models/', views.api_v1_models, name='v1_v1_models_slash'),
    path('v1/v1/chat/completions', views.api_v1_chat_completions, name='v1_v1_chat_completions'),
    path('v1/v1/chat/completions/', views.api_v1_chat_completions, name='v1_v1_chat_completions_slash'),
]
