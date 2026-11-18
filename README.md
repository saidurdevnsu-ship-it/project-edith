# Project EDITH - AI Assistant

A Python Django application designed for both **Desktop** and **Web Browser** usage, directly integrated with your locally running **Llama** model via Ollama.
free tokens for your claude code or hermes agent to integrate edith and njoy the power of multiple local llm models all runing from your local machine , behind a single api key of project edith.
---

## 🚀 Key Features

- **Dual-Mode Operation**:
  - **Desktop App Mode**: Native desktop window powered by `pywebview` (clean framing, no browser tabs or URL bars).
  - **Web Browser Mode**: Accessible in any browser on `http://127.0.0.1:8000` or across your local network.
- **Direct Local Llama Integration**:
  - Connects to your local Ollama instance (`http://127.0.0.1:11434`).
  - Pre-configured for `llama3.1:8b` (auto-detects all installed models on startup).
  - Real-time token streaming using Server-Sent Events (SSE).
  - 100% offline & private: Zero data leaves your computer.
- **Chat Management**:
  - Multi-conversation history stored in SQLite.
  - Markdown rendering with code syntax highlighting & one-click code copy.
  - Live model selection and Ollama connection status monitoring.
- **API Key Management & External Integration**:
  - Built-in API Key Generator (`edith_sk_...`) directly from the UI.
  - OpenAI-compatible endpoint at `/v1/chat/completions` authenticated via `Authorization: Bearer <KEY>`.
  - Ready to connect with **n8n**, **Hermes**, **Claude Code**, or external scripts.

---

## 📁 Project Structure

```text
project edith/
│
├── edith_core/               # Django root project settings & URLs
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
│
├── assistant/                # Main AI assistant application
│   ├── models.py             # Conversation & ChatMessage models
│   ├── views.py              # Views & SSE streaming endpoints
│   ├── urls.py               # API and page routing
│   ├── tests.py              # Unit & integration tests
│   ├── services/
│   │   └── ollama_service.py # Local Ollama HTTP API client & streamer
│   ├── templates/
│   │   └── assistant/
│   │       └── index.html    # Responsive single-page interface
│   └── static/
│       └── assistant/
│           ├── css/style.css # Dark theme modern UI styling
│           └── js/app.js     # Real-time streaming & chat controller
│
├── run_desktop.py            # Desktop launcher (Native PyWebView window)
├── run_web.py                # Web launcher (Runs server & opens browser)
├── manage.py                 # Standard Django management script
├── requirements.txt          # Python dependencies
├── .env                      # Local configuration file
└── .env.example              # Configuration template
```

---

## 🛠️ Quick Start

### 1. Prerequisites
Ensure your local Llama instance is running in Ollama:
```bash
ollama run llama3.1:8b
```
*(Ollama listens on `http://127.0.0.1:11434` by default)*

### 2. Environment & Dependencies
Virtual environment is already configured in `venv/`. If reinstalling:
```bash
python -m venv venv
.\venv\Scripts\pip install -r requirements.txt
```

### 3. How to Launch (1-Click or Terminal)

#### Option A: Standalone Desktop App (Native Window)
* **1-Click**: Double-click `start_desktop.bat` in the project folder.
* **Or via Terminal**:
  ```powershell
  .\venv\Scripts\python run_desktop.py
  ```
> **Auto-Start**: Automatically launches Ollama (`ollama serve`) in the background if it's not already running, starts Django, and opens the native desktop app.

#### Option B: Web Browser Mode
* **1-Click**: Double-click `start_web.bat` in the project folder.
* **Or via Terminal**:
  ```powershell
  .\venv\Scripts\python run_web.py
  ```
> Automatically ensures local models are running, starts the server on `http://127.0.0.1:8000`, and opens your default browser.

---

## ⚙️ Configuration (`.env`)

You can modify settings in `.env`:
```env
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_DEFAULT_MODEL=llama3.1:8b
OLLAMA_REQUEST_TIMEOUT=120
DEBUG=True
ALLOWED_HOSTS=*
```

---

## 🧪 Testing

To run the automated test suite:
```bash
.\venv\Scripts\python manage.py test
```
