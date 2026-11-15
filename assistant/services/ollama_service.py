import os
import json
import time
import shutil
import socket
import logging
import subprocess
from pathlib import Path
from typing import Generator, List, Dict, Any, Optional
import requests

logger = logging.getLogger(__name__)

CREATE_NO_WINDOW = 0x08000000 if os.name == 'nt' else 0


def _get_setting(name: str, default: Any) -> Any:
    """Retrieve setting from Django settings if configured, else environment variable."""
    try:
        from django.conf import settings
        if settings.configured:
            return getattr(settings, name, default)
    except Exception:
        pass
    return os.getenv(name, default)


def _get_base_dir() -> Path:
    try:
        from django.conf import settings
        if settings.configured:
            return Path(settings.BASE_DIR)
    except Exception:
        pass
    return Path(__file__).resolve().parent.parent.parent


class OllamaService:
    def __init__(self, base_url: Optional[str] = None):
        configured_url = base_url or _get_setting('OLLAMA_BASE_URL', 'http://127.0.0.1:11434')
        self.base_url = str(configured_url).rstrip('/')
        self.timeout = int(_get_setting('OLLAMA_REQUEST_TIMEOUT', 120))
        self.default_model = str(_get_setting('OLLAMA_DEFAULT_MODEL', 'llama3.1:8b'))
        self.base_dir = _get_base_dir()
        self.cache_file = self.base_dir / 'models_cache.json'

    def find_executable(self) -> str:
        """Find local ollama executable from PATH or common Windows install locations."""
        path_exe = shutil.which('ollama')
        if path_exe:
            return path_exe
        local_app_data = os.environ.get('LOCALAPPDATA', '')
        if local_app_data:
            candidate = Path(local_app_data) / 'Programs' / 'Ollama' / 'ollama.exe'
            if candidate.exists():
                return str(candidate)
        return 'ollama'

    def is_port_listening(self) -> bool:
        """Check if 127.0.0.1:11434 is listening."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                return s.connect_ex(('127.0.0.1', 11434)) == 0
        except Exception:
            return False

    def ensure_running(self) -> bool:
        """Auto-start the local Ollama daemon silently if it's not currently running."""
        if self.is_port_listening():
            return True

        ollama_exe = self.find_executable()
        logger.info("Ollama is offline. Auto-starting background daemon via: %s serve", ollama_exe)
        try:
            subprocess.Popen(
                [ollama_exe, 'serve'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW
            )
            # Wait up to 5 seconds for port to open
            start = time.time()
            while time.time() - start < 5.0:
                if self.is_port_listening():
                    logger.info("Ollama auto-started successfully on port 11434.")
                    return True
                time.sleep(0.3)
        except Exception as e:
            logger.error("Failed to auto-spawn Ollama daemon: %s", e)
        return self.is_port_listening()

    def _save_models_cache(self, models: List[Dict[str, Any]]):
        try:
            self.cache_file.write_text(json.dumps(models, indent=2), encoding='utf-8')
        except Exception as e:
            logger.warning("Could not write models cache: %s", e)

    def _load_models_cache(self) -> List[Dict[str, Any]]:
        if self.cache_file.exists():
            try:
                return json.loads(self.cache_file.read_text(encoding='utf-8'))
            except Exception as e:
                logger.warning("Could not read models cache: %s", e)
        # Fallback default known installed models
        return [
            {'name': 'llama3.1:8b', 'model': 'llama3.1:8b', 'size': 4920753328, 'family': 'llama'},
            {'name': 'qwen2.5:1.5b', 'model': 'qwen2.5:1.5b', 'size': 986000000, 'family': 'qwen2'},
            {'name': 'deepseek-r1:1.5b', 'model': 'deepseek-r1:1.5b', 'size': 1100000000, 'family': 'qwen2'},
        ]

    def check_health(self) -> Dict[str, Any]:
        """Check if local Ollama instance is accessible. Auto-starts if down."""
        try:
            resp = requests.get(f"{self.base_url}/api/version", timeout=2)
            if resp.status_code == 200:
                return {
                    'status': 'connected',
                    'base_url': self.base_url,
                    'version': resp.json().get('version', '0.40.16'),
                    'error': None
                }
        except requests.RequestException:
            pass

        # Try to auto-start
        if self.ensure_running():
            try:
                resp = requests.get(f"{self.base_url}/api/version", timeout=3)
                if resp.status_code == 200:
                    return {
                        'status': 'connected',
                        'base_url': self.base_url,
                        'version': resp.json().get('version', '0.40.16'),
                        'error': None
                    }
            except requests.RequestException:
                pass

        return {
            'status': 'disconnected',
            'base_url': self.base_url,
            'version': None,
            'error': 'Ollama daemon is offline. Starting automatically...'
        }

    def get_models(self) -> List[Dict[str, Any]]:
        """Retrieve list of locally installed models from Ollama, with cache fallback."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=3)
            if resp.status_code == 200:
                data = resp.json()
                models = []
                for item in data.get('models', []):
                    models.append({
                        'name': item.get('name'),
                        'model': item.get('model'),
                        'size': item.get('size', 0),
                        'modified_at': item.get('modified_at'),
                        'family': item.get('details', {}).get('family', 'llama')
                    })
                if models:
                    self._save_models_cache(models)
                return models
        except requests.RequestException:
            pass

        # Try auto-recovery
        if self.ensure_running():
            try:
                resp = requests.get(f"{self.base_url}/api/tags", timeout=3)
                if resp.status_code == 200:
                    data = resp.json()
                    models = []
                    for item in data.get('models', []):
                        models.append({
                            'name': item.get('name'),
                            'model': item.get('model'),
                            'size': item.get('size', 0),
                            'modified_at': item.get('modified_at'),
                            'family': item.get('details', {}).get('family', 'llama')
                        })
                    if models:
                        self._save_models_cache(models)
                    return models
            except requests.RequestException:
                pass

        # Return cached models so UI is NEVER empty
        return self._load_models_cache()

    def stream_chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Stream chat completion tokens from Ollama /api/chat.
        Auto-starts Ollama if offline.
        """
        # Ensure daemon is live before streaming
        self.ensure_running()

        model_name = model or self.default_model
        payload_messages = []

        if system_prompt:
            payload_messages.append({
                'role': 'system',
                'content': system_prompt
            })

        for msg in messages:
            payload_messages.append({
                'role': msg.get('role', 'user'),
                'content': msg.get('content', '')
            })

        payload = {
            'model': model_name,
            'messages': payload_messages,
            'stream': True
        }
        if options:
            payload['options'] = options

        try:
            with requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                stream=True,
                timeout=self.timeout
            ) as response:
                if response.status_code != 200:
                    yield {
                        'error': f"Ollama error ({response.status_code}): {response.text}",
                        'done': True
                    }
                    return

                for line in response.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                        msg_chunk = chunk.get('message', {})
                        token = msg_chunk.get('content', '')
                        done = chunk.get('done', False)
                        yield {
                            'token': token,
                            'done': done,
                            'model': model_name,
                            'error': None
                        }
                    except json.JSONDecodeError:
                        continue
        except requests.RequestException as e:
            yield {
                'error': f"Failed to connect to local Ollama instance: {str(e)}",
                'done': True
            }


# Singleton service instance
ollama_service = OllamaService()
