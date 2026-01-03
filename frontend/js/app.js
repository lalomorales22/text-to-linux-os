/**
 * Main application controller
 */

// Application state
const AppState = {
    currentScreen: 'welcome',
    currentProject: null,
    currentBuild: null,
    currentTheme: null
};

// DOM Elements
const screens = {
    welcome: document.getElementById('welcomeScreen'),
    chat: document.getElementById('chatInterface'),
    build: document.getElementById('buildScreen'),
    gallery: document.getElementById('galleryScreen')
};

const buttons = {
    newProject: document.getElementById('newProjectBtn'),
    gallery: document.getElementById('galleryBtn'),
    startChat: document.getElementById('startChatBtn'),
    build: document.getElementById('buildBtn'),
    backToGallery: document.getElementById('backToGalleryBtn'),
    createFirstProject: document.getElementById('createFirstProject')
};

/**
 * Initialize application
 */
function init() {
    console.log('Initializing Text-to-Linux-OS Builder...');

    // Set up event listeners
    buttons.newProject.addEventListener('click', () => showScreen('chat'));
    buttons.gallery.addEventListener('click', loadGallery);
    buttons.startChat.addEventListener('click', () => showScreen('chat'));
    buttons.backToGallery.addEventListener('click', loadGallery);

    if (buttons.createFirstProject) {
        buttons.createFirstProject.addEventListener('click', () => showScreen('chat'));
    }

    // Initialize sub-modules
    initChatbot();
    initThemeRandomizer();
    initProjectGallery();

    // Show welcome screen
    showScreen('welcome');
}

/**
 * Show specific screen
 */
function showScreen(screenName) {
    console.log(`Switching to screen: ${screenName}`);

    // Hide all screens
    Object.values(screens).forEach(screen => {
        if (screen) screen.classList.add('hidden');
    });

    // Show requested screen
    if (screens[screenName]) {
        screens[screenName].classList.remove('hidden');
        AppState.currentScreen = screenName;
    }

    // Screen-specific initialization
    if (screenName === 'chat') {
        startNewChat();
    } else if (screenName === 'gallery') {
        loadProjectGallery();
    }
}

/**
 * Show notification
 */
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `fixed top-4 right-4 px-6 py-4 rounded-lg shadow-lg z-50 ${
        type === 'error' ? 'error-message' :
        type === 'success' ? 'success-message' :
        'bg-blue-600 text-white'
    }`;
    notification.textContent = message;

    document.body.appendChild(notification);

    setTimeout(() => {
        notification.style.opacity = '0';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

/**
 * Show error message
 */
function showError(message) {
    showNotification(message, 'error');
}

/**
 * Show success message
 */
function showSuccess(message) {
    showNotification(message, 'success');
}

/**
 * Format file size
 */
function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
    if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
    return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
}

/**
 * Format date
 */
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
}

/**
 * API helper functions
 */
const API = {
    async request(endpoint, options = {}) {
        try {
            const response = await fetch(endpoint, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });

            if (!response.ok) {
                const error = await response.json().catch(() => ({ detail: 'Request failed' }));
                throw new Error(error.detail || 'Request failed');
            }

            return await response.json();
        } catch (error) {
            console.error('API request failed:', error);
            throw error;
        }
    },

    async get(endpoint) {
        return this.request(endpoint);
    },

    async post(endpoint, data) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    async put(endpoint, data) {
        return this.request(endpoint, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },

    async delete(endpoint) {
        return this.request(endpoint, {
            method: 'DELETE'
        });
    }
};

// Initialize app when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}

// Export for use in other modules
window.AppState = AppState;
window.showScreen = showScreen;
window.showNotification = showNotification;
window.showError = showError;
window.showSuccess = showSuccess;
window.formatFileSize = formatFileSize;
window.formatDate = formatDate;
window.API = API;
