import json
from unittest.mock import patch
from django.test import TestCase, Client
from django.urls import reverse
from .models import Conversation, ChatMessage


class AssistantAPITests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_index_page_loads(self):
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'EDITH')

    def test_check_model_suggestion(self):
        payload = {
            'message': 'Solve 15 * 24 - 8 step by step',
            'current_model': 'llama3.1:8b'
        }
        response = self.client.post(
            reverse('api_check_model_suggestion'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('category', data)
        self.assertIn('suggested_model', data)
        self.assertIn('switch_recommended', data)

    def test_create_and_list_conversations(self):
        # Create
        create_resp = self.client.post(
            reverse('api_conversations'),
            data=json.dumps({'title': 'Test Chat'}),
            content_type='application/json'
        )
        self.assertEqual(create_resp.status_code, 201)
        conv_id = create_resp.json()['id']

        # List
        list_resp = self.client.get(reverse('api_conversations'))
        self.assertEqual(list_resp.status_code, 200)
        convs = list_resp.json()['conversations']
        self.assertTrue(any(c['id'] == conv_id for c in convs))

        # Detail
        detail_resp = self.client.get(reverse('api_conversation_detail', args=[conv_id]))
        self.assertEqual(detail_resp.status_code, 200)
        self.assertEqual(detail_resp.json()['title'], 'Test Chat')

        # Delete
        del_resp = self.client.delete(reverse('api_conversation_detail', args=[conv_id]))
        self.assertEqual(del_resp.status_code, 200)
        self.assertEqual(Conversation.objects.count(), 0)

    @patch('assistant.views.ollama_service.stream_chat')
    def test_chat_stream_mock(self, mock_stream):
        mock_stream.return_value = iter([
            {'token': 'Hello', 'done': False},
            {'token': ' World', 'done': True}
        ])

        payload = {
            'message': 'Hi there',
            'model': 'llama3.1:8b'
        }
        response = self.client.post(
            reverse('api_chat_stream'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        content = b''.join(response.streaming_content).decode('utf-8')
        self.assertIn('event', content)
        self.assertIn('Hello', content)

        # Check conversation and messages were created in DB
        self.assertEqual(Conversation.objects.count(), 1)
        self.assertEqual(ChatMessage.objects.count(), 2)

    def test_api_key_generation_and_verification(self):
        # 1. Create key
        create_resp = self.client.post(
            reverse('api_keys'),
            data=json.dumps({'name': 'n8n-bot'}),
            content_type='application/json'
        )
        self.assertEqual(create_resp.status_code, 201)
        data = create_resp.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['raw_key'].startswith('edith_sk_'))
        key_id = data['id']
        raw_key = data['raw_key']

        # 2. List keys
        list_resp = self.client.get(reverse('api_keys'))
        self.assertEqual(list_resp.status_code, 200)
        keys = list_resp.json()['keys']
        self.assertEqual(len(keys), 1)
        self.assertEqual(keys[0]['name'], 'n8n-bot')

        # 3. Test v1 chat completions with invalid bearer key
        unauth_resp = self.client.post(
            reverse('v1_chat_completions'),
            data=json.dumps({'messages': [{'role': 'user', 'content': 'test'}]}),
            content_type='application/json',
            HTTP_AUTHORIZATION="Bearer edith_sk_invalidtoken123"
        )
        self.assertEqual(unauth_resp.status_code, 401)

        # 4. Test v1 chat completions authorized
        with patch('assistant.views.ollama_service.stream_chat') as mock_stream:
            mock_stream.return_value = iter([{'token': 'Response from EDITH', 'done': True}])
            auth_resp = self.client.post(
                reverse('v1_chat_completions'),
                data=json.dumps({'messages': [{'role': 'user', 'content': 'hello'}]}),
                content_type='application/json',
                HTTP_AUTHORIZATION=f"Bearer {raw_key}"
            )
            self.assertEqual(auth_resp.status_code, 200)
            self.assertIn('Response from EDITH', auth_resp.json()['choices'][0]['message']['content'])

        # 5. Revoke key
        del_resp = self.client.delete(reverse('api_key_delete', args=[key_id]))
        self.assertEqual(del_resp.status_code, 200)
        self.assertEqual(self.client.get(reverse('api_keys')).json()['keys'], [])

    def test_v1_models_endpoint(self):
        resp = self.client.get(reverse('v1_models'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get('object'), 'list')
        self.assertIsInstance(data.get('data'), list)
        model_ids = [m['id'] for m in data['data']]
        self.assertIn('llama3.1:8b', model_ids)
