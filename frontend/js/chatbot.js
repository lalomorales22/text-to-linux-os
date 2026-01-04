/**
 * Chatbot functionality - Terminal Style
 */

let currentProjectId = null;
let currentConfig = null;
let isWaitingForResponse = false;

const chatElements = {
    messages: null,
    input: null,
    sendBtn: null,
    buildBtn: null,
    sizeEstimate: null,
    sizeBar: null
};

/**
 * Initialize chatbot
 */
function initChatbot() {
    chatElements.messages = document.getElementById('chatMessages');
    chatElements.input = document.getElementById('chatInput');
    chatElements.sendBtn = document.getElementById('sendBtn');
    chatElements.buildBtn = document.getElementById('buildBtn');
    chatElements.sizeEstimate = document.getElementById('sizeEstimate');
    chatElements.sizeBar = document.getElementById('sizeBar');

    if (chatElements.sendBtn) {
        chatElements.sendBtn.addEventListener('click', sendMessage);
    }

    if (chatElements.input) {
        chatElements.input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
    }

    if (chatElements.buildBtn) {
        chatElements.buildBtn.addEventListener('click', startBuild);
    }
}

/**
 * Start a new chat session
 */
function startNewChat() {
    // Clear previous chat
    if (chatElements.messages) {
        chatElements.messages.innerHTML = '';
    }
    currentProjectId = null;
    currentConfig = null;
    
    if (chatElements.buildBtn) {
        chatElements.buildBtn.disabled = true;
    }

    // Show welcome message in terminal style
    addMessage('assistant',
        "System initialized.\n\n" +
        "I'm your Linux ISO configuration assistant. Let's build something great.\n\n" +
        "To get started, tell me about your system:\n" +
        "• RAM size (e.g., 4GB, 8GB, 16GB)\n" +
        "• CPU type (Intel/AMD, modern/older)\n" +
        "• Primary use case (development, browsing, server, etc.)"
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
            showSuccess('Configuration complete! Ready to build.');
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
    // Escape HTML first
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

    // Lists with bullet points
    formatted = formatted.replace(/^[•\-] (.+)$/gm, '<span class="list-item">• $1</span>');

    // Line breaks
    formatted = formatted.replace(/\n/g, '<br>');

    return formatted;
}

/**
 * Show typing indicator
 */
function showTypingIndicator() {
    const typingDiv = document.createElement('div');
    typingDiv.className = 'typing-indicator';
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
    if (chatElements.sizeEstimate) {
        chatElements.sizeEstimate.textContent = `~${Math.round(sizeMb)} MB`;
    }

    if (chatElements.sizeBar) {
        const percentage = Math.min((sizeMb / 3072) * 100, 100);
        chatElements.sizeBar.style.width = percentage + '%';
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
            if (progressBar) progressBar.style.width = status.progress + '%';
            if (progressText) progressText.textContent = status.progress + '%';
            if (stepText) stepText.textContent = status.current_step;

            // Update logs
            if (status.logs && logsContainer) {
                logsContainer.innerHTML = formatBuildLogs(status.logs);
                logsContainer.scrollTop = logsContainer.scrollHeight;
            }

            // Check if complete or failed
            if (status.status === 'completed') {
                clearInterval(pollInterval);
                if (downloadSection) downloadSection.classList.remove('hidden');

                // Set download button
                const downloadBtn = document.getElementById('downloadBtn');
                if (downloadBtn) {
                    downloadBtn.onclick = () => {
                        window.location.href = status.iso_path.replace('./builds', '/api/projects/download');
                    };
                }

                showSuccess('Build completed successfully!');
            } else if (status.status === 'failed') {
                clearInterval(pollInterval);
                showError('Build failed: ' + (status.error || 'Unknown error'));
            }

        } catch (error) {
            console.error('Error polling build status:', error);
        }
    }, 2000);
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

// Export functions
window.initChatbot = initChatbot;
window.startNewChat = startNewChat;
window.addMessage = addMessage;
window.currentProjectId = currentProjectId;
