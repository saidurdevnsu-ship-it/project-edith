// Project EDITH - Frontend Application Logic

let currentConversationId = null;
let isStreaming = false;
let currentAbortController = null;
let activeAssistantBubble = null;
let activeCursor = null;

// DOM Elements
const sidebar = document.getElementById('sidebar');
const toggleSidebarBtn = document.getElementById('toggleSidebarBtn');
const closeSidebarBtn = document.getElementById('closeSidebarBtn');
const newChatBtn = document.getElementById('newChatBtn');
const conversationsList = document.getElementById('conversationsList');
const modelSelect = document.getElementById('modelSelect');
const smartSuggestToggle = document.getElementById('smartSuggestToggle');
const statusDot = document.getElementById('statusDot');
const statusTitle = document.getElementById('statusTitle');
const statusSubtitle = document.getElementById('statusSubtitle');
const refreshStatusBtn = document.getElementById('refreshStatusBtn');
const currentChatTitle = document.getElementById('currentChatTitle');
const currentModelTag = document.getElementById('currentModelTag');
const clientModeBadge = document.getElementById('clientModeBadge');
const clearChatBtn = document.getElementById('clearChatBtn');
const messagesContainer = document.getElementById('messagesContainer');
const welcomeHero = document.getElementById('welcomeHero');
const messagesList = document.getElementById('messagesList');
const chatForm = document.getElementById('chatForm');
const chatInput = document.getElementById('chatInput');
const sendBtn = document.getElementById('sendBtn');
const sendIcon = document.getElementById('sendIcon');
const sendSpinner = document.getElementById('sendSpinner');

// Stop Generating Elements
const stopContainer = document.getElementById('stopContainer');
const floatingStopBtn = document.getElementById('floatingStopBtn');
const stopActionBtn = document.getElementById('stopActionBtn');

// Model Switch Permission Modal Elements
const modelPermissionCard = document.getElementById('modelPermissionCard');
const permissionDesc = document.getElementById('permissionDesc');
const confirmSwitchBtn = document.getElementById('confirmSwitchBtn');
const cancelSwitchBtn = document.getElementById('cancelSwitchBtn');

// API Key Management Elements
const openApiKeysBtn = document.getElementById('openApiKeysBtn');
const apiKeysModal = document.getElementById('apiKeysModal');
const closeApiKeysModalBtn = document.getElementById('closeApiKeysModalBtn');
const createKeyForm = document.getElementById('createKeyForm');
const keyNameInput = document.getElementById('keyNameInput');
const generateKeyBtn = document.getElementById('generateKeyBtn');
const newKeyBanner = document.getElementById('newKeyBanner');
const rawKeyDisplay = document.getElementById('rawKeyDisplay');
const copyRawKeyBtn = document.getElementById('copyRawKeyBtn');
const keysTableBody = document.getElementById('keysTableBody');

// Setup marked.js options
if (window.marked) {
  marked.setOptions({
    breaks: true,
    highlight: function(code, lang) {
      if (window.hljs) {
        const language = hljs.getLanguage(lang) ? lang : 'plaintext';
        return hljs.highlight(code, { language }).value;
      }
      return code;
    }
  });
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
  initClientMode();
  checkOllamaStatus();
  loadConversations();
  setupEventListeners();
  autoResizeTextarea();
});

// Detect Desktop App vs Web Browser
function initClientMode() {
  if (window.pywebview) {
    clientModeBadge.textContent = 'Desktop App';
    clientModeBadge.style.color = '#10b981';
    clientModeBadge.style.borderColor = 'rgba(16, 185, 129, 0.4)';
    clientModeBadge.style.background = 'rgba(16, 185, 129, 0.12)';
  } else {
    clientModeBadge.textContent = 'Web Browser';
  }
}

// Format clean display name for models
function formatModelDisplayName(modelName) {
  if (!modelName) return 'Llama 3.1';
  if (modelName === 'auto') return 'Auto Router';
  if (modelName.includes('qwen3')) return 'Qwen 3 8B';
  if (modelName.includes('qwen')) return 'Qwen 2.5';
  if (modelName.includes('deepseek')) return 'DeepSeek R1';
  if (modelName.includes('llama')) return 'Llama 3.1';
  const clean = modelName.split(':')[0];
  return clean.charAt(0).toUpperCase() + clean.slice(1);
}

// Update all UI model indicators synchronously
function updateActiveModelDisplay(modelName) {
  const chosen = modelName || modelSelect.value || 'llama3.1:8b';
  const displayName = formatModelDisplayName(chosen);

  // 1. Update top navbar model badge
  if (currentModelTag) {
    currentModelTag.textContent = chosen;
  }

  // 2. Update sidebar status title (e.g. "Qwen 2.5 Online", "DeepSeek R1 Online")
  if (statusTitle && statusDot.classList.contains('online')) {
    statusTitle.textContent = `${displayName} Online`;
  }

  // 3. Update chat input placeholder
  if (chatInput) {
    if (chosen === 'auto') {
      chatInput.placeholder = 'Message EDITH (Auto Smart Routing)...';
    } else {
      chatInput.placeholder = `Message EDITH (${chosen})...`;
    }
  }
}

// Event Listeners
function setupEventListeners() {
  toggleSidebarBtn.addEventListener('click', () => sidebar.classList.toggle('open'));
  closeSidebarBtn.addEventListener('click', () => sidebar.classList.remove('open'));
  newChatBtn.addEventListener('click', startNewChat);
  refreshStatusBtn.addEventListener('click', checkOllamaStatus);
  clearChatBtn.addEventListener('click', clearCurrentChat);
  modelSelect.addEventListener('change', (e) => {
    updateActiveModelDisplay(e.target.value);
  });

  // Prompt chips
  document.querySelectorAll('.prompt-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const prompt = chip.getAttribute('data-prompt');
      chatInput.value = prompt;
      submitUserMessage();
    });
  });

  // API Keys Modal
  if (openApiKeysBtn) openApiKeysBtn.addEventListener('click', openApiKeysModal);
  if (closeApiKeysModalBtn) closeApiKeysModalBtn.addEventListener('click', closeApiKeysModal);
  if (apiKeysModal) apiKeysModal.addEventListener('click', (e) => {
    if (e.target === apiKeysModal) closeApiKeysModal();
  });
  if (createKeyForm) createKeyForm.addEventListener('submit', handleCreateKey);
  if (copyRawKeyBtn) copyRawKeyBtn.addEventListener('click', copyRawKey);

  // Stop buttons
  if (floatingStopBtn) floatingStopBtn.addEventListener('click', stopGeneration);
  if (stopActionBtn) stopActionBtn.addEventListener('click', stopGeneration);

  // Chat input handling
  chatInput.addEventListener('input', autoResizeTextarea);
  chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!isStreaming && chatInput.value.trim()) {
        submitUserMessage();
      }
    }
  });

  chatForm.addEventListener('submit', (e) => {
    e.preventDefault();
    if (!isStreaming && chatInput.value.trim()) {
      submitUserMessage();
    }
  });
}

function autoResizeTextarea() {
  chatInput.style.height = 'auto';
  chatInput.style.height = Math.min(chatInput.scrollHeight, 180) + 'px';
}

// Ollama Connection Check & Model Population
async function checkOllamaStatus() {
  statusDot.className = 'status-dot';
  statusTitle.textContent = 'Checking Ollama...';
  
  try {
    const res = await fetch('/api/status/');
    const data = await res.json();
    
    // Populate models list whenever available
    if (data.models && data.models.length > 0) {
      const currentVal = modelSelect.value || 'llama3.1:8b';
      modelSelect.innerHTML = '';

      // Add Auto Smart Option first
      const autoOpt = document.createElement('option');
      autoOpt.value = 'auto';
      autoOpt.textContent = '⚡ Auto (EDITH Smart Route)';
      modelSelect.appendChild(autoOpt);

      data.models.forEach(m => {
        const opt = document.createElement('option');
        opt.value = m.name;
        const sizeGB = m.size ? (m.size / (1024 * 1024 * 1024)).toFixed(1) + ' GB' : 'Ready';
        opt.textContent = `${m.name} (${sizeGB})`;
        modelSelect.appendChild(opt);
      });

      if ([...modelSelect.options].some(o => o.value === currentVal)) {
        modelSelect.value = currentVal;
      } else {
        modelSelect.value = 'llama3.1:8b';
      }
      updateActiveModelDisplay(modelSelect.value);
    }

    if (data.health && data.health.status === 'connected') {
      statusDot.className = 'status-dot online';
      statusSubtitle.textContent = `v${data.health.version} • 127.0.0.1:11434`;
      updateActiveModelDisplay(modelSelect.value);
    } else {
      statusDot.className = 'status-dot ping-dot';
      statusTitle.textContent = 'Auto-Starting Models...';
      statusSubtitle.textContent = 'Waking Ollama daemon...';
      // Auto-retry connection in 2 seconds
      setTimeout(checkOllamaStatus, 2000);
    }
  } catch (err) {
    statusDot.className = 'status-dot ping-dot';
    statusTitle.textContent = 'Auto-Starting Models...';
    statusSubtitle.textContent = 'Waiting for background service...';
    setTimeout(checkOllamaStatus, 2500);
  }
}

// Load Conversation Threads
async function loadConversations() {
  try {
    const res = await fetch('/api/conversations/');
    const data = await res.json();
    renderConversationsList(data.conversations || []);
  } catch (err) {
    console.error('Failed to load conversations:', err);
  }
}

function renderConversationsList(conversations) {
  conversationsList.innerHTML = '';
  if (conversations.length === 0) {
    conversationsList.innerHTML = '<div style="padding: 12px; font-size: 0.8rem; color: var(--text-muted); text-align: center;">No conversations yet</div>';
    return;
  }

  conversations.forEach(c => {
    const item = document.createElement('div');
    item.className = `conv-item ${c.id === currentConversationId ? 'active' : ''}`;
    item.dataset.id = c.id;

    item.innerHTML = `
      <span class="conv-title">${escapeHtml(c.title)}</span>
      <button class="conv-delete-btn" title="Delete conversation" data-id="${c.id}">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="3 6 5 6 21 6"></polyline>
          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
        </svg>
      </button>
    `;

    item.addEventListener('click', (e) => {
      if (e.target.closest('.conv-delete-btn')) {
        e.stopPropagation();
        deleteConversation(c.id);
        return;
      }
      selectConversation(c.id);
    });

    conversationsList.appendChild(item);
  });
}

// Select Conversation
async function selectConversation(id) {
  if (isStreaming) return;
  currentConversationId = id;
  
  document.querySelectorAll('.conv-item').forEach(el => {
    el.classList.toggle('active', el.dataset.id === id);
  });

  try {
    const res = await fetch(`/api/conversations/${id}/`);
    const data = await res.json();
    currentChatTitle.textContent = data.title;
    
    welcomeHero.classList.add('hidden');
    messagesList.innerHTML = '';

    data.messages.forEach(msg => {
      appendMessageUI(msg.role, msg.content, msg.model);
    });

    scrollToBottom();
    sidebar.classList.remove('open');
  } catch (err) {
    console.error('Failed to load conversation details:', err);
  }
}

// Start New Chat
function startNewChat() {
  if (isStreaming) return;
  currentConversationId = null;
  currentChatTitle.textContent = 'New Chat';
  messagesList.innerHTML = '';
  welcomeHero.classList.remove('hidden');
  document.querySelectorAll('.conv-item').forEach(el => el.classList.remove('active'));
  chatInput.value = '';
  autoResizeTextarea();
  chatInput.focus();
  sidebar.classList.remove('open');
  hidePermissionCard();
}

// Delete Conversation
async function deleteConversation(id) {
  if (!confirm('Are you sure you want to delete this conversation?')) return;
  try {
    const res = await fetch(`/api/conversations/${id}/`, { method: 'DELETE' });
    if (res.ok) {
      if (currentConversationId === id) {
        startNewChat();
      }
      loadConversations();
    }
  } catch (err) {
    console.error('Error deleting conversation:', err);
  }
}

// Clear Current Chat
function clearCurrentChat() {
  if (currentConversationId) {
    deleteConversation(currentConversationId);
  } else {
    startNewChat();
  }
}

// Append Message UI
function appendMessageUI(role, content = '', model = '') {
  welcomeHero.classList.add('hidden');

  const row = document.createElement('div');
  row.className = `message-row ${role === 'user' ? 'user-row' : 'assistant-row'}`;

  const avatar = document.createElement('div');
  avatar.className = 'message-avatar';
  avatar.textContent = role === 'user' ? 'U' : 'E';

  const wrapper = document.createElement('div');
  wrapper.className = 'message-content-wrapper';

  const header = document.createElement('div');
  header.className = 'message-header';
  
  const author = document.createElement('span');
  author.className = 'message-author';
  const displayModel = model || modelSelect.value;
  author.textContent = role === 'user' ? 'You' : `EDITH (${displayModel})`;

  header.appendChild(author);

  const bubble = document.createElement('div');
  bubble.className = 'message-bubble';
  if (content) {
    bubble.innerHTML = renderMarkdown(content);
  }

  wrapper.appendChild(header);
  wrapper.appendChild(bubble);
  row.appendChild(avatar);
  row.appendChild(wrapper);

  messagesList.appendChild(row);
  scrollToBottom();
  return bubble;
}

// Handle User Message Submission with Smart Routing & Permission
async function submitUserMessage() {
  const text = chatInput.value.trim();
  if (!text || isStreaming) return;

  hidePermissionCard();

  const chosenModel = modelSelect.value;
  const isAuto = chosenModel === 'auto';
  const askPermission = smartSuggestToggle && smartSuggestToggle.checked;

  // If user selected a specific model AND asked for permission before switching
  if (!isAuto && askPermission) {
    try {
      const checkRes = await fetch('/api/check-suggestion/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, current_model: chosenModel })
      });
      const data = await checkRes.json();

      if (data.switch_recommended && data.suggested_model && data.suggested_model.toLowerCase() !== chosenModel.toLowerCase()) {
        showPermissionCard(data, text, chosenModel);
        return;
      }
    } catch (e) {
      console.warn('Suggestion check failed, using default model:', e);
    }
  }

  // Execute directly with current choice
  executeStream(text, chosenModel);
}

function showPermissionCard(data, text, chosenModel) {
  permissionDesc.innerHTML = `
    This task is classified as <b>[${escapeHtml(data.category)}]</b>: ${escapeHtml(data.reason)}<br>
    Switch from <b>${escapeHtml(chosenModel)}</b> to <b>${escapeHtml(data.suggested_model)}</b>?
  `;
  modelPermissionCard.classList.remove('hidden');

  confirmSwitchBtn.onclick = () => {
    hidePermissionCard();
    modelSelect.value = data.suggested_model;
    updateActiveModelDisplay(data.suggested_model);
    executeStream(text, data.suggested_model);
  };

  cancelSwitchBtn.onclick = () => {
    hidePermissionCard();
    // Respects user's original default choice
    executeStream(text, chosenModel);
  };
}

function hidePermissionCard() {
  modelPermissionCard.classList.add('hidden');
}

// Stop Current Response Generation
function stopGeneration() {
  if (currentAbortController) {
    try {
      currentAbortController.abort();
    } catch (e) {
      console.warn('Abort error:', e);
    }
    currentAbortController = null;
  }

  if (activeCursor) {
    activeCursor.remove();
    activeCursor = null;
  }

  if (activeAssistantBubble) {
    const stopNote = document.createElement('div');
    stopNote.style.cssText = 'font-size: 0.76rem; color: var(--text-muted); margin-top: 6px; font-style: italic;';
    stopNote.textContent = '⏹ Generation stopped by user';
    activeAssistantBubble.appendChild(stopNote);
    attachCodeCopyButtons(activeAssistantBubble);
    activeAssistantBubble = null;
  }

  setStreamingState(false);
  scrollToBottom();
}

// Execute Stream
async function executeStream(text, targetModel) {
  chatInput.value = '';
  autoResizeTextarea();
  setStreamingState(true);

  // Initialize new AbortController
  currentAbortController = new AbortController();

  // Render user bubble
  appendMessageUI('user', text);

  // Assistant bubble placeholder
  const assistantBubble = appendMessageUI('assistant', '', targetModel);
  activeAssistantBubble = assistantBubble;
  const cursor = document.createElement('span');
  cursor.className = 'streaming-cursor';
  activeCursor = cursor;
  assistantBubble.appendChild(cursor);

  let fullReply = '';

  try {
    const payload = {
      conversation_id: currentConversationId,
      message: text,
      model: targetModel
    };

    const response = await fetch('/api/chat/stream/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: currentAbortController.signal
    });

    if (!response.ok) {
      throw new Error(`HTTP error ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n\n');
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const dataStr = line.replace('data: ', '').trim();
        if (!dataStr) continue;

        try {
          const eventData = JSON.parse(dataStr);

          if (eventData.event === 'start') {
            if (!currentConversationId) {
              currentConversationId = eventData.conversation_id;
              currentChatTitle.textContent = eventData.title;
              loadConversations();
            }
            if (eventData.model) {
              updateActiveModelDisplay(eventData.model);
            }
          } else if (eventData.event === 'token') {
            fullReply += eventData.token;
            assistantBubble.innerHTML = renderMarkdown(fullReply);
            assistantBubble.appendChild(cursor);
            scrollToBottom();
          } else if (eventData.event === 'done') {
            cursor.remove();
            activeCursor = null;
            activeAssistantBubble = null;
            assistantBubble.innerHTML = renderMarkdown(fullReply);
            attachCodeCopyButtons(assistantBubble);
            loadConversations();
          } else if (eventData.event === 'error') {
            cursor.remove();
            activeCursor = null;
            activeAssistantBubble = null;
            assistantBubble.innerHTML = `<span style="color: var(--danger)">⚠️ Error: ${escapeHtml(eventData.error)}</span>`;
          }
        } catch (err) {
          console.warn('JSON parse error from stream chunk:', err);
        }
      }
    }
  } catch (err) {
    if (err.name === 'AbortError') {
      // Intentionally aborted by user Stop button
      console.log('Stream stopped by user.');
    } else {
      if (activeCursor) activeCursor.remove();
      assistantBubble.innerHTML = `<span style="color: var(--danger)">⚠️ Connection failed: Could not reach local Ollama LLM.</span>`;
    }
  } finally {
    currentAbortController = null;
    activeCursor = null;
    activeAssistantBubble = null;
    setStreamingState(false);
    scrollToBottom();
  }
}

function setStreamingState(streaming) {
  isStreaming = streaming;
  
  if (streaming) {
    sendBtn.classList.add('hidden');
    if (stopActionBtn) stopActionBtn.classList.remove('hidden');
    if (stopContainer) stopContainer.classList.remove('hidden');
  } else {
    sendBtn.classList.remove('hidden');
    if (stopActionBtn) stopActionBtn.classList.add('hidden');
    if (stopContainer) stopContainer.classList.add('hidden');
    sendBtn.disabled = false;
    sendIcon.classList.remove('hidden');
    sendSpinner.classList.add('hidden');
    chatInput.focus();
  }
}

function scrollToBottom() {
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function renderMarkdown(content) {
  if (window.marked) {
    return marked.parse(content);
  }
  return escapeHtml(content).replace(/\n/g, '<br>');
}

function attachCodeCopyButtons(container) {
  const codeBlocks = container.querySelectorAll('pre');
  codeBlocks.forEach(block => {
    if (block.querySelector('.copy-btn')) return;
    const btn = document.createElement('button');
    btn.className = 'copy-btn';
    btn.textContent = 'Copy';
    btn.style.cssText = `
      position: absolute;
      top: 8px;
      right: 8px;
      background: rgba(255,255,255,0.1);
      border: 1px solid rgba(255,255,255,0.15);
      color: #cbd5e1;
      padding: 3px 8px;
      border-radius: 4px;
      font-size: 0.72rem;
      cursor: pointer;
    `;
    btn.addEventListener('click', () => {
      const code = block.querySelector('code')?.innerText || block.innerText;
      navigator.clipboard.writeText(code).then(() => {
        btn.textContent = 'Copied!';
        setTimeout(() => btn.textContent = 'Copy', 1500);
      });
    });
    block.appendChild(btn);
  });
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// ==========================================
// API Key Management Logic
// ==========================================
function openApiKeysModal() {
  if (apiKeysModal) {
    apiKeysModal.classList.remove('hidden');
    newKeyBanner.classList.add('hidden');
    loadApiKeysTable();
    if (keyNameInput) {
      keyNameInput.value = '';
      keyNameInput.focus();
    }
  }
}

function closeApiKeysModal() {
  if (apiKeysModal) {
    apiKeysModal.classList.add('hidden');
    newKeyBanner.classList.add('hidden');
  }
}

async function loadApiKeysTable() {
  if (!keysTableBody) return;
  keysTableBody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 16px;">Loading keys...</td></tr>';

  try {
    const res = await fetch('/api/keys/');
    const data = await res.json();
    renderKeysTable(data.keys || []);
  } catch (err) {
    keysTableBody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--danger); padding: 16px;">Failed to load API keys</td></tr>';
  }
}

function renderKeysTable(keys) {
  if (!keysTableBody) return;
  keysTableBody.innerHTML = '';

  if (keys.length === 0) {
    keysTableBody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 16px;">No API keys generated yet</td></tr>';
    return;
  }

  keys.forEach(k => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><b>${escapeHtml(k.name)}</b></td>
      <td><span class="key-prefix-badge">${escapeHtml(k.prefix)}</span></td>
      <td>${escapeHtml(k.created_at)}</td>
      <td>${escapeHtml(k.last_used_at)}</td>
      <td>
        <button class="btn-revoke-key" data-id="${k.id}" title="Revoke this key">Revoke</button>
      </td>
    `;

    tr.querySelector('.btn-revoke-key').addEventListener('click', () => {
      revokeApiKey(k.id, k.name);
    });

    keysTableBody.appendChild(tr);
  });
}

async function handleCreateKey(e) {
  e.preventDefault();
  const name = (keyNameInput.value || '').trim();
  if (!name) return;

  generateKeyBtn.disabled = true;
  generateKeyBtn.textContent = 'Generating...';

  try {
    const res = await fetch('/api/keys/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    });
    const data = await res.json();

    if (res.ok && data.raw_key) {
      rawKeyDisplay.textContent = data.raw_key;
      newKeyBanner.classList.remove('hidden');
      keyNameInput.value = '';
      loadApiKeysTable();
    } else {
      alert('Failed to generate key: ' + (data.error || 'Unknown error'));
    }
  } catch (err) {
    alert('Failed to generate key: ' + err.message);
  } finally {
    generateKeyBtn.disabled = false;
    generateKeyBtn.innerHTML = '<span>+ Generate Key</span>';
  }
}

function copyRawKey() {
  const text = rawKeyDisplay.textContent;
  if (!text) return;
  navigator.clipboard.writeText(text).then(() => {
    copyRawKeyBtn.textContent = 'Copied!';
    setTimeout(() => {
      copyRawKeyBtn.textContent = '📋 Copy';
    }, 1500);
  });
}

async function revokeApiKey(keyId, keyName) {
  if (!confirm(`Are you sure you want to revoke the key "${keyName}"? External services using it will stop working.`)) return;

  try {
    const res = await fetch(`/api/keys/${keyId}/`, { method: 'DELETE' });
    if (res.ok) {
      loadApiKeysTable();
    }
  } catch (err) {
    alert('Failed to revoke key: ' + err.message);
  }
}
