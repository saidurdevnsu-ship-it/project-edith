# Project EDITH - Memory & Persistent Context (`memory.md`)

*Last Updated: 2026-11-15*  
*Project Root: `d:\python proj\project edith`*

---

## 1. System Identity & Mission

**Project EDITH** is a dual-platform (**Desktop App** & **Web Browser**) AI Assistant and Multi-Agent Orchestration Hub.  
It operates directly on top of locally hosted LLMs via Ollama, ensuring 100% data privacy, zero API costs for local triage, and low-latency interaction.

---

## 2. Hardware Environment Profile

* **CPU**: AMD Ryzen 7 8840HS (8 Cores, 16 Threads, Zen 4, AVX-512 support)
* **RAM**: 32 GB DDR5 (~13–16 GB free)
* **GPU**: Integrated AMD Radeon 780M (Vulkan / ROCm iGPU)
* **Storage**: Primary project drive `D:\` with > 700 GB free space
* **Local Service Ports**:
  * Ollama daemon: `http://127.0.0.1:11434`
  * Django EDITH server: `http://127.0.0.1:8000`

---

## 3. Installed Local Model Suite & Roles

| Model | Size | Primary Role & Specialization |
| :--- | :--- | :--- |
| **`qwen3:8b`** | **5.2 GB** | **Next-Gen Flagship Local Model**: Advanced dual-mode thinking architecture, high-tier code synthesis, multilingual understanding. |
| **`qwen2.5:1.5b`** | **986 MB** | **Ultra-Fast Intent Classifier & Router**: Sub-200ms task classification, parameter extraction, quick scripts. |
| **`deepseek-r1:1.5b`** | **1.1 GB** | **Reasoning & Planning Specialist**: Chain-of-thought (CoT) math, logic puzzles, algorithm verification. |
| **`llama3.1:8b`** | **4.9 GB** | **Core Local Synthesizer / Default Assistant**: High parameter capacity for rich, long-form conversation and synthesis. |
| **`nomic-embed-text`** | **274 MB** | **Local RAG Embedder**: Generating vector embeddings for local documents and code context. |

---

## 4. Multi-Agent Ecosystem Architecture

EDITH orchestrates a specialized agent team:
1. **👑 Hermes**: Main Manager / Supervisor — Coordinates execution plans, delegates sub-tasks, and aggregates final deliverables.
2. **🔬 Grok**: Research Specialist — Handles live web search, technical papers, repository analysis, and real-time news.
3. **💻 Claude Code**: Developer Specialist — Handles production-grade code synthesis, architecture refactoring, and automated testing.
4. **🧠 Local LLM (Qwen 2.5 / DeepSeek R1)**: Lightweight classifier & local triage — Fast classification, zero cost, local privacy gatekeeper.
5. **⚙️ n8n**: Workflow Automation — Webhook listeners, scheduled cron triggers, email/database notifications.

---

## 5. Core Features & Capabilities Implemented

* **1-Click Turnkey Launchers**:
  * `start_desktop.bat` / `run_desktop.py`: Double-click launcher that checks if Ollama daemon is active, automatically spins up `ollama serve` silently in background if needed, boots Django, and opens the native PyWebView window.
  * `start_web.bat` / `run_web.py`: Double-click launcher that auto-ensures Ollama is live, runs Django, and opens the default browser to `http://127.0.0.1:8000`.
* **API Key Management & External Integration (`/v1/models` & `/v1/chat/completions`)**:
  * **Interactive Key Modal**: UI button `🔑 API Keys` in the top navbar allows generating named secret keys (`edith_sk_...`), viewing prefixes, copying with 1-click, and revoking keys.
  * **OpenAI-Compatible Authenticated Endpoint**: External agents (such as **Hermes Agent**, **n8n**, **Claude Code**, or Open-WebUI) can connect directly via:
    * `GET /v1/models` (listing local models `qwen3:8b`, `deepseek-r1:1.5b`, `llama3.1:8b`, `qwen2.5:1.5b` with CORS and OPTIONS support)
    * `POST /v1/chat/completions` (supporting SSE streaming chunks and full non-streaming completions)
    * Flexible auth: Supports `Authorization: Bearer edith_sk_...` or local localhost direct connections.
  * **Hashed Storage**: Secret keys are hashed with SHA-256 in the database for safety and only displayed once upon generation.
* **Django 6 Backend**: SQLite persistence for `Conversation` and `ChatMessage` models with UUID keys.
* **Real-time SSE Streaming**: `StreamingHttpResponse` emitting `start`, `token`, `done`, and `error` events.
* **Dual-Mode Launchers**:
  * `run_web.py`: Runs Django server and launches default web browser.
  * `run_desktop.py`: Launches standalone desktop window via `pywebview` with zero browser chrome.
* **Adaptive Model Selection with User Permission**:
  * **Dynamic UI Sync**: Whenever the user switches the active model (or EDITH switches with permission), the bottom sidebar status badge dynamically updates (e.g. `Llama 3.1 Online`, `Qwen 2.5 Online`, `DeepSeek R1 Online`, `Auto Router Online`), alongside the top navbar tag and input placeholder.
  * **Default Respect**: By default, EDITH strictly runs with whatever model the user has manually selected.
  * **Permission Banner**: When a prompt would be significantly better handled by another model (e.g. math/logic -> DeepSeek R1), EDITH displays an interactive recommendation card asking the user: `[✨ Switch & Run]` or `[Keep Current]`.
  * **Auto Route Mode**: An optional `⚡ Auto (EDITH Smart Route)` dropdown option for automated delegation.
* **Instant Stop Generation**:
  * Dual controls: A floating `⏹ Stop Generating` pill and an in-card red square stop button.
  * Powered by `AbortController` signal to immediately terminate HTTP streaming and release resources.

---

## 6. Chain-of-Thought (CoT) History & Resolutions

1. **Ollama Command Not Recognized**:
   * *Problem*: `ollama` CLI failed in PowerShell due to missing PATH entry.
   * *Resolution*: Located `ollama.exe` in `$env:LOCALAPPDATA\Programs\Ollama\ollama.exe` and added the directory permanently to Windows User `PATH`.
2. **Connection Refused (`WinError 10061`)**:
   * *Problem*: Port `11434` connection refused when background Ollama process stopped after terminal closure.
   * *Resolution*: Created background daemon process for Ollama serve, verified health endpoint `http://127.0.0.1:11434/api/tags`, and added automatic reconnection handling.
3. **Lightweight Model Curation**:
   * *Decision*: Selected lightweight high-efficiency models (`qwen2.5:1.5b`, `deepseek-r1:1.5b`, `nomic-embed-text`) tailored specifically for the laptop's Ryzen 7 CPU and RAM budget without GPU memory bottlenecks.
5. **Self-Healing Local Model Lifecycle**:
   * *Problem*: If Ollama stopped or laptop restarted, EDITH showed `🔴 Ollama Offline` with an empty model dropdown.
   * *Resolution*: Implemented 3-layer auto-recovery:
     1. `OllamaService.ensure_running()` auto-spawns `ollama serve` silently whenever any Django view (`/api/status/`, `/api/chat/stream/`) is hit.
     2. `models_cache.json` persists installed models so the UI dropdown is never blank even while the daemon wakes up.
     3. Frontend auto-retries status check every 2 seconds until the status dot turns green.
6. **User Control Priority**:
   * *Rule*: Never auto-switch models without user consent when the user has explicitly selected a preferred model. Always ask for permission with clear justification.
7. **Hermes Agent OpenAI-Compatible Integration (`/v1/models` & `/v1/chat/completions`)**:
   * *Problem*: Hermes Agent encountered HTTP 404 when connecting to `http://127.0.0.1:8000/` because `/v1/models` route was missing.
   * *Resolution*: Implemented `api_v1_models` view, registered routes for `/v1/models` and `/v1/chat/completions` (including trailing slash & `/v1/v1/` fallbacks), enabled CORS and SSE streaming. Verified live and working with Hermes Agent.
8. **GitHub Version Control & Deployment**:
   * Configured `.gitignore` (safeguarding virtual environment `venv/`, database `db.sqlite3`, secrets `.env`, and caches).
   * Linked remote `origin` to `https://github.com/saidurdevnsu-ship-it/project-edith.git`.
   * Successfully pushed initial commit to branch `main`.

---

## 7. Active Roadmap

- [ ] **Phase 1**: Agent Dispatcher implementation (Connecting Hermes, Claude Code, Grok adapters).
- [ ] **Phase 2**: n8n Webhook Endpoint & trigger runner inside EDITH.
- [ ] **Phase 3**: Local RAG pipeline using `nomic-embed-text` and local vector store (ChromaDB / SQLite VSS).
- [ ] **Phase 4**: Long-term memory recall linking `memory.md` directly into EDITH's system prompt context.
