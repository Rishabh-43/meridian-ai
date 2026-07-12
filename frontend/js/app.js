// ===================================================
// Configuration
// ===================================================

const CONFIG = {
  // Local dev: talk to the FastAPI dev server directly.
  // Deployed: same-origin ('') — set this to your deployed backend's
  // origin (e.g. a Render URL) once the frontend and backend are hosted
  // separately, or leave it '' if they're served from the same origin.
  API_BASE_URL:
    window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
      ? 'http://localhost:8000'
      : '',

  ACCEPTED_EXTENSIONS: ['.pdf', '.docx', '.txt'],
  MAX_FILE_SIZE_BYTES: 10 * 1024 * 1024, // 10MB

  HEALTH_TIMEOUT_MS: 5000,
  UPLOAD_TIMEOUT_MS: 30000,
  QUERY_TIMEOUT_MS: 30000,

  DEFAULT_TOP_K: 5,

  TOAST_DURATION_MS: 3200,
  TOAST_EXIT_ANIMATION_MS: 200,

  SUGGESTED_QUESTIONS: [
    'What is this document about?',
    'Summarize the key points',
    'What are the main conclusions?'
  ]
};


// ===================================================
// DOM References
// ===================================================

const dom = {
  // Upload hero
  uploadHero: document.getElementById('upload-hero'),
  uploadForm: document.getElementById('upload-form'),
  uploadDropzone: document.getElementById('upload-dropzone'),
  browseFilesButton: document.getElementById('browse-files-button'),
  uploadFileInput: document.getElementById('upload-file-input'),

  // Document bar
  documentBar: document.getElementById('document-bar'),
  documentBarIcon: document.getElementById('document-bar-icon'),
  documentBarFilename: document.getElementById('document-bar-filename'),
  documentBarStatusLabel: document.getElementById('document-bar-status-label'),
  replaceDocumentButton: document.getElementById('replace-document-button'),
  newChatButton: document.getElementById('new-chat-button'),

  // Empty chat state
  emptyChatState: document.getElementById('empty-chat-state'),
  suggestedQuestions: document.getElementById('suggested-questions'),

  // Conversation
  conversationContainer: document.getElementById('conversation-container'),

  // Input bar
  questionForm: document.getElementById('question-form'),
  questionInput: document.getElementById('question-input'),
  sendQuestionButton: document.getElementById('send-question-button')
};

// BUG FIX (Phase 3A -> 3B): the dropzone used to be restored by resetting
// uploadDropzone.innerHTML back to a cached HTML string. That destroys and
// recreates every child node (including the file input), which left the
// cached dom.uploadFileInput reference pointing at a detached element after
// the first upload cycle.
//
// Fix: never destroy the original dropzone children. Capture them once,
// toggle their visibility with the existing `.is-hidden` utility class
// while uploading, and append/remove a separate progress element instead.
// The original nodes (and their listeners/references) are never recreated.
const dropzoneOriginalChildren = Array.from(dom.uploadDropzone.children);


// ===================================================
// Application State
// ===================================================

const appState = {
  isBackendAvailable: true, // set from GET /health at init
  document: null,           // { documentId, filename, extension, chunkCount, status }
  messages: [],              // { id, role: 'user' | 'assistant', text, excerpts }
  isUploading: false,
  isThinking: false,
  lastQuestionText: null     // used to support "Try again" on a failed query
};


// ===================================================
// Helper Functions
// ===================================================

function getFileExtension(filename) {
  const lastDot = filename.lastIndexOf('.');
  if (lastDot === -1) return '';
  return filename.slice(lastDot).toLowerCase();
}

function isAcceptedFileType(filename) {
  return CONFIG.ACCEPTED_EXTENSIONS.includes(getFileExtension(filename));
}

function isWithinSizeLimit(sizeBytes) {
  return sizeBytes <= CONFIG.MAX_FILE_SIZE_BYTES;
}

function generateId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function scrollConversationToBottom() {
  window.scrollTo({
    top: document.documentElement.scrollHeight,
    behavior: 'smooth'
  });
}

// --- Backend request helpers -----------------------------------------

function fetchWithTimeout(url, options, timeoutMs) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  return fetch(url, { ...options, signal: controller.signal }).finally(() => {
    clearTimeout(timeoutId);
  });
}

async function parseErrorDetail(response) {
  try {
    const data = await response.json();
    return data && data.detail ? data.detail : null;
  } catch (err) {
    return null;
  }
}

function getUploadErrorMessageForStatus(status) {
  switch (status) {
    case 415:
      return 'Unsupported file type. Please upload a PDF, DOCX, or TXT file.';
    case 413:
      return 'File is too large. Maximum size is 10MB.';
    case 400:
      return 'This document could not be processed.';
    default:
      return 'Something went wrong while uploading. Please try again.';
  }
}

function getQueryErrorMessageForStatus(status) {
  switch (status) {
    case 400:
      return 'Could not retrieve relevant content for that question.';
    case 500:
      return 'The AI failed to generate an answer. Please try again.';
    default:
      return 'Something went wrong answering that question.';
  }
}

async function checkBackendHealth() {
  try {
    const response = await fetchWithTimeout(
      `${CONFIG.API_BASE_URL}/health`,
      { method: 'GET' },
      CONFIG.HEALTH_TIMEOUT_MS
    );
    if (!response.ok) return false;
    const data = await response.json();
    return data.status === 'healthy';
  } catch (err) {
    return false;
  }
}


// ===================================================
// UI Rendering
// ===================================================

function renderDocumentBar() {
  if (!appState.document) return;
  dom.documentBarFilename.textContent = appState.document.filename;

  const statusLabel = appState.document.status === 'processed'
    ? 'Ready'
    : (appState.document.status || 'Ready');
  dom.documentBarStatusLabel.textContent = statusLabel.charAt(0).toUpperCase() + statusLabel.slice(1);

  dom.documentBar.hidden = false;
  dom.documentBar.classList.add('is-entering');
}

function showUploadHero() {
  dom.uploadHero.hidden = false;
  dom.documentBar.hidden = true;
  dom.emptyChatState.hidden = true;
}

function showPostUploadUI() {
  dom.uploadHero.hidden = true;
  renderDocumentBar();
  if (appState.messages.length === 0) {
    dom.emptyChatState.hidden = false;
  }
  
  // BUG FIX: Explicitly enable chat input and focus it to ensure
  // the UI state is properly reflected after upload succeeds.
  // This forces the browser to remove the disabled attribute and
  // repaint the DOM, making the input visibly enabled.
  dom.questionInput.disabled = false;
  dom.sendQuestionButton.disabled = false;
  setChatEnabled(true);
  dom.questionInput.focus();
}

function setChatEnabled(enabled) {
  dom.questionInput.disabled = !enabled;
  dom.sendQuestionButton.disabled = !enabled;
}

function disableUploadUI() {
  dom.browseFilesButton.disabled = true;
  dom.uploadFileInput.disabled = true;
  dom.uploadDropzone.setAttribute('aria-disabled', 'true');
}

function renderUploadingState(filename) {
  dom.uploadDropzone.classList.add('upload-dropzone--uploading');
  dropzoneOriginalChildren.forEach((child) => child.classList.add('is-hidden'));

  const progress = document.createElement('div');
  progress.className = 'upload-progress';
  progress.id = 'upload-progress-indicator';
  progress.innerHTML = `
    <span class="upload-progress__filename">${escapeHtml(filename)}</span>
    <div class="upload-progress__track">
      <div class="upload-progress__bar"></div>
    </div>
    <span class="upload-progress__label">Preparing your document&hellip;</span>
  `;
  dom.uploadDropzone.appendChild(progress);
}

function resetDropzone() {
  dom.uploadDropzone.classList.remove('upload-dropzone--uploading', 'upload-dropzone--drag-active');

  const progress = document.getElementById('upload-progress-indicator');
  if (progress) progress.remove();

  dropzoneOriginalChildren.forEach((child) => child.classList.remove('is-hidden'));
  dom.uploadFileInput.value = '';
}

function createUserMessageElement(text) {
  const wrapper = document.createElement('div');
  wrapper.className = 'conversation-message conversation-message--user is-entering';

  const bubble = document.createElement('div');
  bubble.className = 'conversation-message__bubble';
  bubble.textContent = text;

  wrapper.appendChild(bubble);
  return wrapper;
}

function createAssistantMessageElement(text, excerpts) {
  const wrapper = document.createElement('div');
  wrapper.className = 'conversation-message conversation-message--assistant is-entering';

  const bubble = document.createElement('div');
  bubble.className = 'conversation-message__bubble';

  const textEl = document.createElement('div');
  textEl.className = 'conversation-message__text';
  textEl.textContent = text;
  bubble.appendChild(textEl);

  if (excerpts && excerpts.length > 0) {
    const disclosure = document.createElement('details');
    disclosure.className = 'context-disclosure';

    const summary = document.createElement('summary');
    summary.className = 'context-disclosure__toggle';
    summary.innerHTML = `<span class="context-disclosure__icon" aria-hidden="true">&#9662;</span> Supporting excerpts`;
    disclosure.appendChild(summary);

    const panel = document.createElement('div');
    panel.className = 'context-disclosure__panel';

    excerpts.forEach((excerpt) => {
      const card = document.createElement('div');
      card.className = 'excerpt-card';

      const label = document.createElement('span');
      label.className = 'excerpt-card__label';
      label.textContent = excerpt.label;

      const excerptText = document.createElement('p');
      excerptText.className = 'excerpt-card__text';
      excerptText.textContent = excerpt.text;

      card.appendChild(label);
      card.appendChild(excerptText);
      panel.appendChild(card);
    });

    disclosure.appendChild(panel);
    bubble.appendChild(disclosure);
  }

  wrapper.appendChild(bubble);
  return wrapper;
}

function createThinkingIndicatorElement() {
  const wrapper = document.createElement('div');
  wrapper.className = 'conversation-message conversation-message--assistant is-entering';
  wrapper.id = 'thinking-indicator-message';

  const bubble = document.createElement('div');
  bubble.className = 'conversation-message__bubble thinking-indicator';
  bubble.innerHTML = `
    <span class="thinking-indicator__label">Thinking</span>
    <span class="thinking-indicator__dots" aria-hidden="true">
      <span></span><span></span><span></span>
    </span>
  `;

  wrapper.appendChild(bubble);
  return wrapper;
}

function createErrorMessageElement(message, retryQuestionText) {
  const wrapper = document.createElement('div');
  wrapper.className = 'conversation-message conversation-message--error is-entering';

  const bubble = document.createElement('div');
  bubble.className = 'conversation-message__bubble';

  const messageEl = document.createElement('span');
  messageEl.textContent = message;
  bubble.appendChild(messageEl);

  if (retryQuestionText) {
    const retryButton = document.createElement('button');
    retryButton.type = 'button';
    retryButton.className = 'conversation-message__retry';
    retryButton.textContent = 'Try again';
    retryButton.addEventListener('click', () => {
      wrapper.remove();
      sendQuestion(retryQuestionText);
    });
    bubble.appendChild(retryButton);
  }

  wrapper.appendChild(bubble);
  return wrapper;
}

function appendMessageToConversation(element) {
  dom.conversationContainer.appendChild(element);
  scrollConversationToBottom();
}

function clearConversation() {
  dom.conversationContainer.innerHTML = '';
  appState.messages = [];
}

function showToast(message, type = 'success') {
  const toast = document.createElement('div');
  toast.className = `toast toast--${type}`;
  toast.setAttribute('role', 'status');
  toast.textContent = message;

  document.body.appendChild(toast);

  setTimeout(() => {
    toast.classList.add('toast--exiting');
    setTimeout(() => {
      toast.remove();
    }, CONFIG.TOAST_EXIT_ANIMATION_MS);
  }, CONFIG.TOAST_DURATION_MS);
}


// ===================================================
// Upload Logic
// ===================================================

function validateFile(file) {
  if (!isAcceptedFileType(file.name)) {
    return 'Unsupported file type. Please upload a PDF, DOCX, or TXT file.';
  }
  if (!isWithinSizeLimit(file.size)) {
    return 'File is too large. Maximum size is 10MB.';
  }
  return null;
}

async function handleFileSelected(file) {
  if (!appState.isBackendAvailable) {
    showToast('Backend is unavailable right now. Please try again later.', 'error');
    return;
  }

  const validationError = validateFile(file);
  if (validationError) {
    showToast(validationError, 'error');
    return;
  }

  appState.isUploading = true;
  renderUploadingState(file.name);

  try {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetchWithTimeout(
      `${CONFIG.API_BASE_URL}/upload/`,
      { method: 'POST', body: formData },
      CONFIG.UPLOAD_TIMEOUT_MS
    );

    if (!response.ok) {
      const detail = await parseErrorDetail(response);
      throw new Error(detail || getUploadErrorMessageForStatus(response.status));
    }

    const data = await response.json(); // { success, document, preview }
    const metadata = data.document;

    appState.isUploading = false;
    appState.document = {
      documentId: metadata.document_id,
      filename: metadata.filename,
      extension: metadata.extension,
      chunkCount: metadata.chunk_count,
      status: metadata.status
    };

    resetDropzone();
    showPostUploadUI();
    showToast(`${metadata.filename} is ready to chat about.`, 'success');
  } catch (error) {
    appState.isUploading = false;
    resetDropzone();

    const message = error.name === 'AbortError'
      ? 'Upload timed out. Please try again.'
      : (error.message || 'Something went wrong while uploading. Please try again.');

    showToast(message, 'error');
  }
}

function handleReplaceDocument() {
  appState.document = null;
  clearConversation();
  setChatEnabled(false);
  resetQuestionInput();
  showUploadHero();
  showToast('Document removed. Upload a new one to continue.', 'success');
}

function handleNewChat() {
  clearConversation();
  if (appState.document) {
    dom.emptyChatState.hidden = false;
  }
  resetQuestionInput();
}


// ===================================================
// Chat Logic
// ===================================================

function resetQuestionInput() {
  dom.questionInput.value = '';
  autoGrowTextarea();
}

function autoGrowTextarea() {
  dom.questionInput.style.height = 'auto';
  dom.questionInput.style.height = `${dom.questionInput.scrollHeight}px`;
}

async function sendQuestion(rawText) {
  const text = rawText.trim();
  if (!text || appState.isThinking || !appState.document) return;

  if (!appState.isBackendAvailable) {
    showToast('Backend is unavailable right now. Please try again later.', 'error');
    return;
  }

  // Hide empty state once the conversation begins.
  dom.emptyChatState.hidden = true;

  const userMessage = { id: generateId(), role: 'user', text };
  appState.messages.push(userMessage);
  appendMessageToConversation(createUserMessageElement(text));
  appState.lastQuestionText = text;

  resetQuestionInput();

  appState.isThinking = true;
  setChatEnabled(false);
  const thinkingEl = createThinkingIndicatorElement();
  appendMessageToConversation(thinkingEl);

  try {
    const response = await fetchWithTimeout(
      `${CONFIG.API_BASE_URL}/query`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: text, top_k: CONFIG.DEFAULT_TOP_K })
      },
      CONFIG.QUERY_TIMEOUT_MS
    );

    if (!response.ok) {
      const detail = await parseErrorDetail(response);
      throw new Error(detail || getQueryErrorMessageForStatus(response.status));
    }

    const data = await response.json(); // { answer, context, retrieved_chunks }

    thinkingEl.remove();

    const excerpts = data.context
      ? [{
          label: `Retrieved context (${data.retrieved_chunks} chunk${data.retrieved_chunks === 1 ? '' : 's'})`,
          text: data.context
        }]
      : [];

    const assistantMessage = { id: generateId(), role: 'assistant', text: data.answer, excerpts };
    appState.messages.push(assistantMessage);
    appendMessageToConversation(createAssistantMessageElement(data.answer, excerpts));

    appState.isThinking = false;
    setChatEnabled(true);
    dom.questionInput.focus();
  } catch (error) {
    thinkingEl.remove();

    const message = error.name === 'AbortError'
      ? 'The request timed out. Please try again.'
      : (error.message || 'Something went wrong answering that question.');

    appendMessageToConversation(createErrorMessageElement(message, text));

    appState.isThinking = false;
    setChatEnabled(true);
  }
}

function handleSuggestedQuestionClick(questionText) {
  dom.questionInput.value = questionText;
  autoGrowTextarea();
  dom.questionInput.focus();
}


// ===================================================
// Event Listeners
// ===================================================

function attachDragAndDropListeners() {
  let dragCounter = 0;

  dom.uploadDropzone.addEventListener('dragenter', (event) => {
    event.preventDefault();
    if (appState.isUploading || !appState.isBackendAvailable) return;
    dragCounter += 1;
    dom.uploadDropzone.classList.add('upload-dropzone--drag-active');
  });

  dom.uploadDropzone.addEventListener('dragover', (event) => {
    event.preventDefault();
  });

  dom.uploadDropzone.addEventListener('dragleave', (event) => {
    event.preventDefault();
    if (appState.isUploading || !appState.isBackendAvailable) return;
    dragCounter = Math.max(0, dragCounter - 1);
    if (dragCounter === 0) {
      dom.uploadDropzone.classList.remove('upload-dropzone--drag-active');
    }
  });

  dom.uploadDropzone.addEventListener('drop', (event) => {
    event.preventDefault();
    dragCounter = 0;
    dom.uploadDropzone.classList.remove('upload-dropzone--drag-active');

    if (appState.isUploading || !appState.isBackendAvailable) return;

    const file = event.dataTransfer.files && event.dataTransfer.files[0];
    if (file) {
      handleFileSelected(file);
    }
  });

  // Allow the dropzone to be activated via keyboard (it has role="button").
  dom.uploadDropzone.addEventListener('keydown', (event) => {
    if ((event.key === 'Enter' || event.key === ' ') && !appState.isUploading && appState.isBackendAvailable) {
      event.preventDefault();
      dom.uploadFileInput.click();
    }
  });

  // Clicking the dropzone itself also opens the file picker,
  // except when the click originated from the Browse button
  // (which already triggers the input) to avoid double-firing.
  dom.uploadDropzone.addEventListener('click', (event) => {
    if (appState.isUploading || !appState.isBackendAvailable) return;
    if (event.target.closest('#browse-files-button')) return;
    dom.uploadFileInput.click();
  });
}

function attachUploadListeners() {
  dom.browseFilesButton.addEventListener('click', (event) => {
    event.stopPropagation();
    if (appState.isUploading || !appState.isBackendAvailable) return;
    dom.uploadFileInput.click();
  });

  dom.uploadFileInput.addEventListener('change', (event) => {
    const file = event.target.files && event.target.files[0];
    if (file) {
      handleFileSelected(file);
    }
  });

  dom.uploadForm.addEventListener('submit', (event) => {
    event.preventDefault();
  });
}

function attachDocumentBarListeners() {
  dom.replaceDocumentButton.addEventListener('click', handleReplaceDocument);
  dom.newChatButton.addEventListener('click', handleNewChat);
}

function attachSuggestedQuestionListeners() {
  const buttons = dom.suggestedQuestions.querySelectorAll('[data-suggested-question]');
  buttons.forEach((button) => {
    button.addEventListener('click', () => {
      handleSuggestedQuestionClick(button.textContent.trim());
    });
  });
}

function attachChatInputListeners() {
  dom.questionInput.addEventListener('input', autoGrowTextarea);

  dom.questionInput.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      sendQuestion(dom.questionInput.value);
    }
    // Shift+Enter falls through to default behavior (new line).
  });

  dom.questionForm.addEventListener('submit', (event) => {
    event.preventDefault();
    sendQuestion(dom.questionInput.value);
  });
}


// ===================================================
// Initialization
// ===================================================

async function init() {
  attachDragAndDropListeners();
  attachUploadListeners();
  attachDocumentBarListeners();
  attachSuggestedQuestionListeners();
  attachChatInputListeners();

  setChatEnabled(false);
  autoGrowTextarea();

  const healthy = await checkBackendHealth();
  appState.isBackendAvailable = healthy;

  if (!healthy) {
    disableUploadUI();
    showToast('Backend is unavailable right now. Please try again later.', 'error');
  }
}

document.addEventListener('DOMContentLoaded', init);
