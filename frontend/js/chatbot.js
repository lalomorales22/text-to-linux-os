/**
 * Chatbot functionality
 */

let currentProjectId = null;
let currentConfig = null;
let isWaitingForResponse = false;

const chatElements = {
    messages: document.getElementById('chatMessages'),
    input: document.getElementById('chatInput'),
    sendBtn: document.getElementById('sendBtn'),
    buildBtn: document.getElementById('buildBtn'),
    sizeEstimate: document.getElementById('sizeEstimate'),
    sizeBar: document.getElementById('sizeBar')
};

/**
 * Initialize chatbot
 */
function initChatbot() {
    chatElements.sendBtn.addEventListener('click', sendMessage);
    chatElements.input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    chatElements.buildBtn.addEventListener('click', startBuild);
}

/**
 * Start a new chat session
 */
function startNewChat() {
    // Clear previous chat
    chatElements.messages.innerHTML = '';
    currentProjectId = null;
    currentConfig = null;
    chatElements.buildBtn.disabled = true;

    // Show welcome message
    addMessage('assistant',
        "Hello! I'm here to help you create your custom Linux ISO. " +
        "Let's start by understanding your needs.\n\n" +
        "First, tell me about your hardware:\n" +
        "- How much RAM do you have?\n" +
        "- What's your CPU like (modern/older)?\n" +
        "- What type of storage (SSD/HDD)?"
    );
}

/**
 * Send a message to the chatbot
 */
async function sendMessage() {
    const message = chatElements.input.value.trim();
    if (!message || isWaitingForResponse) return;

    // Add user message to UI
    addMessage('user', message);

    // Clear input
    chatElements.input.value = '';

    // Show typing indicator
    isWaitingForResponse = true;
    const typingId = showTypingIndicator();

    try {
        // Send message to API
        const response = await API.post('/api/chat/message', {
            project_id: currentProjectId,
            message: message
        });

        // Update project ID
        if (response.project_id) {
            currentProjectId = response.project_id;
            AppState.currentProject = currentProjectId;
        }

        // Remove typing indicator
        removeTypingIndicator(typingId);

        // Add assistant response
        addMessage('assistant', response.message);

        // Check if ready to build
        if (response.ready_to_build && response.config) {
            currentConfig = response.config;
            chatElements.buildBtn.disabled = false;
            updateSizeEstimate(response.config.size_estimate_mb);

            // Show build ready message
            showSuccess('Configuration complete! You can now build your ISO.');
        }

    } catch (error) {
        removeTypingIndicator(typingId);
        showError('Failed to send message: ' + error.message);
    } finally {
        isWaitingForResponse = false;
    }
}

/**
 * Add a message to the chat
 */
function addMessage(role, content) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message-enter ${role}-message`;

    // Simple markdown-like formatting
    const formattedContent = formatMessageContent(content);
    messageDiv.innerHTML = formattedContent;

    chatElements.messages.appendChild(messageDiv);

    // Scroll to bottom
    chatElements.messages.scrollTop = chatElements.messages.scrollHeight;
}

/**
 * Format message content (simple markdown support)
 */
function formatMessageContent(content) {
    // Escape HTML
    let formatted = content
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');

    // Code blocks
    formatted = formatted.replace(/```(\w+)?\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>');

    // Inline code
    formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>');

    // Bold
    formatted = formatted.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

    // Lists
    formatted = formatted.replace(/^- (.+)$/gm, '• $1');

    // Line breaks
    formatted = formatted.replace(/\n/g, '<br>');

    return formatted;
}

/**
 * Show typing indicator
 */
function showTypingIndicator() {
    const typingDiv = document.createElement('div');
    typingDiv.className = 'assistant-message typing-indicator';
    typingDiv.innerHTML = '<span></span><span></span><span></span>';

    const id = 'typing-' + Date.now();
    typingDiv.id = id;

    chatElements.messages.appendChild(typingDiv);
    chatElements.messages.scrollTop = chatElements.messages.scrollHeight;

    return id;
}

/**
 * Remove typing indicator
 */
function removeTypingIndicator(id) {
    const indicator = document.getElementById(id);
    if (indicator) {
        indicator.remove();
    }
}

/**
 * Update size estimate display
 */
function updateSizeEstimate(sizeMb) {
    chatElements.sizeEstimate.textContent = `~${Math.round(sizeMb)} MB`;

    const percentage = Math.min((sizeMb / 3072) * 100, 100);
    chatElements.sizeBar.style.width = percentage + '%';

    // Color coding
    if (sizeMb > 3072) {
        chatElements.sizeBar.classList.remove('bg-blue-500', 'bg-yellow-500');
        chatElements.sizeBar.classList.add('bg-red-500');
        chatElements.sizeEstimate.classList.add('size-danger');
    } else if (sizeMb > 2500) {
        chatElements.sizeBar.classList.remove('bg-blue-500', 'bg-red-500');
        chatElements.sizeBar.classList.add('bg-yellow-500');
        chatElements.sizeEstimate.classList.add('size-warning');
    } else {
        chatElements.sizeBar.classList.remove('bg-yellow-500', 'bg-red-500');
        chatElements.sizeBar.classList.add('bg-blue-500');
        chatElements.sizeEstimate.classList.remove('size-warning', 'size-danger');
    }
}

/**
 * Start building the ISO
 */
async function startBuild() {
    if (!currentProjectId || !currentConfig) {
        showError('No configuration available');
        return;
    }

    try {
        // Apply current theme if selected
        if (AppState.currentTheme) {
            await API.post(`/api/projects/${currentProjectId}/theme/apply`, AppState.currentTheme);
        }

        // Start build
        const response = await API.post('/api/build/start', {
            project_id: currentProjectId
        });

        AppState.currentBuild = response.build_id;

        // Switch to build screen
        showScreen('build');

        // Start monitoring build progress
        monitorBuildProgress(response.build_id);

        showSuccess('Build started!');

    } catch (error) {
        showError('Failed to start build: ' + error.message);
    }
}

/**
 * Monitor build progress
 */
async function monitorBuildProgress(buildId) {
    const progressBar = document.getElementById('buildProgressBar');
    const progressText = document.getElementById('buildProgress');
    const stepText = document.getElementById('buildStep');
    const logsContainer = document.getElementById('buildLogs');
    const downloadSection = document.getElementById('downloadSection');

    const pollInterval = setInterval(async () => {
        try {
            const status = await API.get(`/api/build/status/${buildId}`);

            // Update progress
            progressBar.style.width = status.progress + '%';
            progressText.textContent = status.progress + '%';
            stepText.textContent = status.current_step;

            // Update logs
            if (status.logs) {
                logsContainer.innerHTML = formatBuildLogs(status.logs);
                logsContainer.scrollTop = logsContainer.scrollHeight;
            }

            // Check if complete or failed
            if (status.status === 'completed') {
                clearInterval(pollInterval);
                downloadSection.classList.remove('hidden');

                // Set download button
                const downloadBtn = document.getElementById('downloadBtn');
                downloadBtn.onclick = () => {
                    window.location.href = status.iso_path.replace('./builds', '/api/projects/download');
                };

                showSuccess('Build completed successfully!');
            } else if (status.status === 'failed') {
                clearInterval(pollInterval);
                showError('Build failed: ' + (status.error || 'Unknown error'));
            }

        } catch (error) {
            console.error('Error polling build status:', error);
            // Don't stop polling on temporary errors
        }
    }, 2000); // Poll every 2 seconds
}

/**
 * Format build logs with color coding
 */
function formatBuildLogs(logs) {
    return logs.split('\n').map(line => {
        let className = 'log-entry';

        if (line.includes('ERROR') || line.includes('FATAL') || line.includes('Failed')) {
            className += ' error';
        } else if (line.includes('WARNING') || line.includes('WARN')) {
            className += ' warning';
        } else if (line.includes('✓') || line.includes('SUCCESS') || line.includes('completed')) {
            className += ' success';
        }

        return `<div class="${className}">${escapeHtml(line)}</div>`;
    }).join('');
}

/**
 * Escape HTML
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Export functions
window.initChatbot = initChatbot;
window.startNewChat = startNewChat;
