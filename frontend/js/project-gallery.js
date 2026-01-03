/**
 * Project gallery functionality
 */

const galleryElements = {
    grid: document.getElementById('projectsGrid'),
    empty: document.getElementById('emptyGallery')
};

/**
 * Initialize project gallery
 */
function initProjectGallery() {
    console.log('Project gallery initialized');
}

/**
 * Load and display project gallery
 */
async function loadGallery() {
    showScreen('gallery');
    await loadProjectGallery();
}

/**
 * Load project gallery
 */
async function loadProjectGallery() {
    try {
        const projects = await API.get('/api/projects/list');

        if (projects.length === 0) {
            galleryElements.grid.classList.add('hidden');
            galleryElements.empty.classList.remove('hidden');
        } else {
            galleryElements.empty.classList.add('hidden');
            galleryElements.grid.classList.remove('hidden');
            renderProjects(projects);
        }

    } catch (error) {
        showError('Failed to load projects: ' + error.message);
    }
}

/**
 * Render projects in gallery
 */
function renderProjects(projects) {
    galleryElements.grid.innerHTML = '';

    projects.forEach(project => {
        const card = createProjectCard(project);
        galleryElements.grid.appendChild(card);
    });
}

/**
 * Create project card element
 */
function createProjectCard(project) {
    const card = document.createElement('div');
    card.className = 'project-card bg-gray-800 border border-gray-700 rounded-lg p-6 cursor-pointer';

    // Theme preview colors
    let themePreview = '';
    if (project.latest_version && project.latest_version.theme_preview) {
        const colors = project.latest_version.theme_preview;
        themePreview = `
            <div class="flex gap-2 mb-4">
                <div class="w-6 h-6 rounded border border-gray-600 theme-color-preview"
                     style="background-color: ${colors.primary}"></div>
                <div class="w-6 h-6 rounded border border-gray-600 theme-color-preview"
                     style="background-color: ${colors.secondary}"></div>
                <div class="w-6 h-6 rounded border border-gray-600 theme-color-preview"
                     style="background-color: ${colors.accent}"></div>
            </div>
        `;
    }

    // Status badge
    const statusColor = {
        'draft': 'bg-gray-600',
        'configuring': 'bg-blue-600',
        'building': 'bg-yellow-600',
        'completed': 'bg-green-600',
        'failed': 'bg-red-600'
    }[project.status] || 'bg-gray-600';

    // ISO size
    let sizeInfo = '';
    if (project.latest_version && project.latest_version.iso_size) {
        sizeInfo = `<p class="text-sm text-gray-400">Size: ${formatFileSize(project.latest_version.iso_size)}</p>`;
    }

    card.innerHTML = `
        ${themePreview}

        <h3 class="text-xl font-bold mb-2">${escapeHtml(project.name)}</h3>

        <div class="mb-3">
            <span class="inline-block ${statusColor} text-xs px-2 py-1 rounded-full">
                ${project.status}
            </span>
            <span class="text-xs text-gray-400 ml-2">
                v${project.current_version}
            </span>
        </div>

        ${sizeInfo}

        <p class="text-sm text-gray-400 mb-4">
            ${project.version_count} version${project.version_count !== 1 ? 's' : ''}
        </p>

        <p class="text-xs text-gray-500">
            Updated: ${formatDate(project.updated_at)}
        </p>

        <div class="mt-4 flex gap-2">
            ${project.latest_version && project.latest_version.iso_path ? `
                <button class="download-btn flex-1 bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded text-sm font-medium transition">
                    Download
                </button>
            ` : ''}
            <button class="edit-btn flex-1 bg-gray-600 hover:bg-gray-500 px-4 py-2 rounded text-sm font-medium transition">
                ${project.status === 'completed' ? 'View' : 'Continue'}
            </button>
            <button class="delete-btn bg-red-600 hover:bg-red-700 px-4 py-2 rounded text-sm font-medium transition">
                Delete
            </button>
        </div>
    `;

    // Add event listeners
    const downloadBtn = card.querySelector('.download-btn');
    if (downloadBtn) {
        downloadBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            downloadProject(project);
        });
    }

    const editBtn = card.querySelector('.edit-btn');
    editBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        editProject(project);
    });

    const deleteBtn = card.querySelector('.delete-btn');
    deleteBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        deleteProject(project);
    });

    return card;
}

/**
 * Download project ISO
 */
function downloadProject(project) {
    if (project.latest_version && project.latest_version.version_number) {
        const url = `/api/projects/download/${project.id}/v${project.latest_version.version_number}`;
        window.location.href = url;
        showSuccess('Downloading ISO...');
    } else {
        showError('No ISO file available for download');
    }
}

/**
 * Edit/continue project
 */
async function editProject(project) {
    try {
        // Load project details
        const details = await API.get(`/api/projects/${project.id}`);

        // Set current project
        AppState.currentProject = project.id;
        currentProjectId = project.id;

        if (project.status === 'completed') {
            // Show project details/history
            showProjectDetails(details);
        } else {
            // Continue configuration
            showScreen('chat');

            // Load conversation history
            chatElements.messages.innerHTML = '';
            if (details.conversations) {
                details.conversations.forEach(msg => {
                    addMessage(msg.role, msg.message);
                });
            }

            // Load config if available
            if (details.versions && details.versions.length > 0) {
                const latestVersion = details.versions[0];
                currentConfig = latestVersion.config;

                if (latestVersion.theme_config) {
                    AppState.currentTheme = latestVersion.theme_config;
                    updateThemePreview(latestVersion.theme_config);
                }

                if (currentConfig.size_estimate_mb) {
                    updateSizeEstimate(currentConfig.size_estimate_mb);
                }

                chatElements.buildBtn.disabled = false;
            }
        }

    } catch (error) {
        showError('Failed to load project: ' + error.message);
    }
}

/**
 * Show project details
 */
function showProjectDetails(project) {
    // For now, just show a simple view
    // In a full implementation, this would show version history, etc.
    showScreen('chat');

    chatElements.messages.innerHTML = `
        <div class="assistant-message">
            <strong>${escapeHtml(project.name)}</strong><br><br>
            Status: ${project.status}<br>
            Versions: ${project.versions.length}<br>
            Created: ${formatDate(project.created_at)}<br>
            <br>
            This project is completed. You can download the ISO from the gallery
            or start a new version by continuing the conversation.
        </div>
    `;
}

/**
 * Delete project
 */
async function deleteProject(project) {
    if (!confirm(`Are you sure you want to delete "${project.name}"? This cannot be undone.`)) {
        return;
    }

    try {
        await API.delete(`/api/projects/${project.id}`);
        showSuccess('Project deleted');
        loadProjectGallery();
    } catch (error) {
        showError('Failed to delete project: ' + error.message);
    }
}

/**
 * Escape HTML for safety
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Export functions
window.initProjectGallery = initProjectGallery;
window.loadProjectGallery = loadProjectGallery;
window.loadGallery = loadGallery;
