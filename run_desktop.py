import os
import sys
import time
import socket
import shutil
import threading
import subprocess
import webview
from pathlib import Path

HOST = '127.0.0.1'
PORT = 8000
OLLAMA_HOST = '127.0.0.1'
OLLAMA_PORT = 11434

BASE_DIR = Path(__file__).resolve().parent
PYTHON_EXE = sys.executable
CREATE_NO_WINDOW = 0x08000000 if os.name == 'nt' else 0


def is_port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def wait_for_server(host: str, port: int, timeout: int = 15) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        if is_port_in_use(host, port):
            time.sleep(0.3)
            return True
        time.sleep(0.3)
    return False


def find_ollama_executable() -> str:
    path_exe = shutil.which('ollama')
    if path_exe:
        return path_exe
    local_app_data = os.environ.get('LOCALAPPDATA', '')
    if local_app_data:
        candidate = Path(local_app_data) / 'Programs' / 'Ollama' / 'ollama.exe'
        if candidate.exists():
            return str(candidate)
    return 'ollama'


def ensure_ollama_running():
    """Check if local Ollama daemon is running. If not, auto-start in background."""
    if is_port_in_use(OLLAMA_HOST, OLLAMA_PORT):
        print(f"[EDITH] Ollama is already active on http://{OLLAMA_HOST}:{OLLAMA_PORT}")
        return None

    ollama_exe = find_ollama_executable()
    print(f"[EDITH] Starting local Ollama server in background ({ollama_exe} serve)...")
    try:
        proc = subprocess.Popen(
            [ollama_exe, 'serve'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW
        )
        ready = wait_for_server(OLLAMA_HOST, OLLAMA_PORT, timeout=12)
        if ready:
            print("[EDITH] Local Ollama service is ready.")
        else:
            print("[EDITH Warning] Ollama process launched, waiting for response...")
        return proc
    except Exception as e:
        print(f"[EDITH Error] Could not auto-start Ollama: {e}")
        return None


def start_django_server():
    cmd = [PYTHON_EXE, str(BASE_DIR / 'manage.py'), 'runserver', f'{HOST}:{PORT}', '--noreload']
    print(f"[EDITH] Starting background Django server: {' '.join(cmd)}")
    process = subprocess.Popen(
        cmd,
        cwd=str(BASE_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=CREATE_NO_WINDOW
    )
    return process


def main():
    print("=" * 65)
    print("  PROJECT EDITH - Launching Desktop Mode")
    print("=" * 65)

    # 1. Auto-start local Ollama models service if not running
    ollama_proc = ensure_ollama_running()

    # 2. Auto-start Django backend server if not running
    django_proc = None
    if not is_port_in_use(HOST, PORT):
        django_proc = start_django_server()
        ready = wait_for_server(HOST, PORT, timeout=15)
        if not ready:
            print("[EDITH Error] Django server failed to start within timeout.")
            if django_proc:
                django_proc.terminate()
            sys.exit(1)
        print("[EDITH] Django server is live.")
    else:
        print(f"[EDITH] Reusing existing server at http://{HOST}:{PORT}")

    url = f"http://{HOST}:{PORT}"

    try:
        # 3. Create native desktop window
        print("[EDITH] Opening Desktop Window...")
        window = webview.create_window(
            title='Project EDITH - AI Assistant',
            url=url,
            width=1240,
            height=820,
            min_size=(800, 600),
            text_select=True,
            confirm_close=False
        )
        webview.start(debug=False)
    finally:
        if django_proc:
            print("[EDITH] Window closed. Shutting down local Django server...")
            django_proc.terminate()
            django_proc.wait(timeout=5)
            print("[EDITH] Django stopped cleanly.")


if __name__ == '__main__':
    main()
