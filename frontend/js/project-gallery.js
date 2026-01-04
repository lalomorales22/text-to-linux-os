/**
 * Project gallery with sidebar and rename functionality
 */

let galleryElements = {};
let currentSelectedProject = null;

/**
 * Initialize project gallery
 */
function initProjectGallery() {
    galleryElements = {
        projectsList: document.getElementById('projectsList'),
        emptyState: document.getElementById('emptyState'),
        projectView: document.getElementById('projectView'),
        projectName: document.getElementById('projectName'),
        projectStatus: document.getElementById('projectStatus'),
        projectVersion: document.getElementById('projectVersion'),
        projectCreated: document.getElementById('projectCreated'),
        projectUpdated: document.getElementById('projectUpdated'),
        projectVersionCount: document.getElementById('projectVersionCount'),
        projectSize: document.getElementById('projectSize'),
        projectThemeColors: document.getElementById('projectThemeColors'),
        renameBtn: document.getElementById('renameBtn'),
        renameForm: document.getElementById('renameForm'),
        renameInput: document.getElementById('renameInput'),
        saveRenameBtn: document.getElementById('saveRenameBtn'),
        cancelRenameBtn: document.getElementById('cancelRenameBtn'),
        viewDownloadBtn: document.getElementById('viewDownloadBtn'),
        viewContinueBtn: document.getElementById('viewContinueBtn'),
        viewRetryBtn: document.getElementById('viewRetryBtn'),
        viewDeleteBtn: document.getElementById('viewDeleteBtn'),
        createFirstProject: document.getElementById('createFirstProject')
    };

    // Setup rename functionality
    if (galleryElements.renameBtn) {
        galleryElements.renameBtn.addEventListener('click', showRenameForm);
    }
    if (galleryElements.saveRenameBtn) {
        galleryElements.saveRenameBtn.addEventListener('click', saveRename);
    }
    if (galleryElements.cancelRenameBtn) {
        galleryElements.cancelRenameBtn.addEventListener('click', hideRenameForm);
    }
    if (galleryElements.renameInput) {
        galleryElements.renameInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') saveRename();
            if (e.key === 'Escape') hideRenameForm();
        });
    }

    // Setup action buttons
    if (galleryElements.viewDownloadBtn) {
        galleryElements.viewDownloadBtn.addEventListener('click', () => {
            if (currentSelectedProject) downloadProject(currentSelectedProject);
        });
    }
    if (galleryElements.viewContinueBtn) {
        galleryElements.viewContinueBtn.addEventListener('click', () => {
            if (currentSelectedProject) editProject(currentSelectedProject);
        });
    }
    if (galleryElements.viewRetryBtn) {
        galleryElements.viewRetryBtn.addEventListener('click', () => {
            if (currentSelectedProject) retryBuild(currentSelectedProject);
        });
    }
    if (galleryElements.viewDeleteBtn) {
        galleryElements.viewDeleteBtn.addEventListener('click', () => {
            if (currentSelectedProject) deleteProject(currentSelectedProject);
        });
    }

    console.log('Project gallery initialized');
}

/**
 * Load and display project gallery
 */
async function loadGallery() {
    showScreen('gallery');
    setActiveTab('gallery');
    await loadProjectGallery();
}

/**
 * Load project gallery
 */
async function loadProjectGallery() {
    try {
        const projects = await API.get('/api/projects/list');

        if (projects.length === 0) {
            galleryElements.projectsList.innerHTML = `
                <div class="empty-sidebar-message">
                    <p>No projects yet</p>
                </div>
            `;
            showEmptyState();
        } else {
            renderProjectsList(projects);
            
            // If we had a selected project, re-select it
            if (currentSelectedProject) {
                const updatedProject = projects.find(p => p.id === currentSelectedProject.id);
                if (updatedProject) {
                    selectProject(updatedProject);
                } else {
                    showEmptyState();
                }
            } else {
                showEmptyState();
            }
        }

    } catch (error) {
        showError('Failed to load projects: ' + error.message);
    }
}

/**
 * Show empty state
 */
function showEmptyState() {
    currentSelectedProject = null;
    if (galleryElements.emptyState) galleryElements.emptyState.classList.remove('hidden');
    if (galleryElements.projectView) galleryElements.projectView.classList.add('hidden');
}

/**
 * Render projects in sidebar
 */
function renderProjectsList(projects) {
    galleryElements.projectsList.innerHTML = '';

    projects.forEach(project => {
        const item = createProjectItem(project);
        galleryElements.projectsList.appendChild(item);
    });
}

/**
 * Create project sidebar item
 */
function createProjectItem(project) {
    const item = document.createElement('div');
    item.className = 'project-item';
    item.dataset.projectId = project.id;

    if (currentSelectedProject && currentSelectedProject.id === project.id) {
        item.classList.add('active');
    }

    item.innerHTML = `
        <span class="project-dot ${project.status}"></span>
        <div class="project-info">
            <div class="project-item-name">${escapeHtml(project.name)}</div>
            <div class="project-item-meta">v${project.current_version} · ${formatDate(project.updated_at)}</div>
        </div>
    `;

    item.addEventListener('click', () => selectProject(project));

    return item;
}

/**
 * Select a project and show details
 */
async function selectProject(project) {
    currentSelectedProject = project;
    AppState.selectedProjectId = project.id;

    // Update sidebar active state
    document.querySelectorAll('.project-item').forEach(item => {
        item.classList.remove('active');
        if (item.dataset.projectId === project.id) {
            item.classList.add('active');
        }
    });

    // Show project view
    if (galleryElements.emptyState) galleryElements.emptyState.classList.add('hidden');
    if (galleryElements.projectView) galleryElements.projectView.classList.remove('hidden');

    // Populate project details
    galleryElements.projectName.textContent = project.name;
    galleryElements.projectStatus.textContent = project.status;
    galleryElements.projectStatus.className = `status-badge ${project.status}`;
    galleryElements.projectVersion.textContent = `v${project.current_version}`;
    galleryElements.projectCreated.textContent = formatDate(project.created_at);
    galleryElements.projectUpdated.textContent = formatDate(project.updated_at);
    galleryElements.projectVersionCount.textContent = project.version_count || 1;

    // ISO Size
    if (project.latest_version && project.latest_version.iso_size) {
        galleryElements.projectSize.textContent = formatFileSize(project.latest_version.iso_size);
    } else {
        galleryElements.projectSize.textContent = '—';
    }

    // Theme colors
    if (project.latest_version && project.latest_version.theme_preview) {
        const colors = project.latest_version.theme_preview;
        galleryElements.projectThemeColors.innerHTML = `
            <div class="color-swatch" style="background-color: ${colors.primary}" title="Primary"></div>
            <div class="color-swatch" style="background-color: ${colors.secondary}" title="Secondary"></div>
            <div class="color-swatch" style="background-color: ${colors.accent}" title="Accent"></div>
            <div class="color-swatch" style="background-color: ${colors.background}" title="Background"></div>
        `;
    } else {
        galleryElements.projectThemeColors.innerHTML = '<span style="color: var(--text-muted)">No theme set</span>';
    }

    // Update action buttons visibility
    const hasIso = project.latest_version && project.latest_version.iso_path;
    galleryElements.viewDownloadBtn.style.display = hasIso ? 'flex' : 'none';
    galleryElements.viewRetryBtn.classList.toggle('hidden', project.status !== 'failed');
    galleryElements.viewContinueBtn.textContent = project.status === 'completed' ? 'View Details' : 'Continue Editing';
}

/**
 * Show rename form
 */
function showRenameForm() {
    if (!currentSelectedProject) return;
    
    galleryElements.renameInput.value = currentSelectedProject.name;
    galleryElements.renameForm.classList.remove('hidden');
    galleryElements.projectName.parentElement.style.display = 'none';
    galleryElements.renameInput.focus();
    galleryElements.renameInput.select();
}

/**
 * Hide rename form
 */
function hideRenameForm() {
    galleryElements.renameForm.classList.add('hidden');
    galleryElements.projectName.parentElement.style.display = 'flex';
}

/**
 * Save rename
 */
async function saveRename() {
    if (!currentSelectedProject) return;
    
    const newName = galleryElements.renameInput.value.trim();
    if (!newName) {
        showError('Project name cannot be empty');
        return;
    }

    if (newName === currentSelectedProject.name) {
        hideRenameForm();
        return;
    }

    try {
        await API.put(`/api/projects/${currentSelectedProject.id}`, { name: newName });
        
        currentSelectedProject.name = newName;
        galleryElements.projectName.textContent = newName;
        
        hideRenameForm();
        showSuccess('Project renamed');
        
        // Reload sidebar to update name there too
        await loadProjectGallery();
        
    } catch (error) {
        showError('Failed to rename project: ' + error.message);
    }
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

        // Switch to chat screen
        setActiveTab('newProject');
        showScreen('chat');

        // Get chat elements
        const chatMessages = document.getElementById('chatMessages');
        const chatInput = document.getElementById('chatInput');
        const buildBtn = document.getElementById('buildBtn');

        // Clear and load conversation history
        chatMessages.innerHTML = '';
        
        if (details.conversations && details.conversations.length > 0) {
            details.conversations.forEach(msg => {
                addMessage(msg.role, msg.message);
            });
        } else {
            // Show welcome if no conversation
            addMessage('assistant',
                `Continuing project: ${project.name}\n\n` +
                "Let's continue configuring your Linux ISO. What would you like to adjust?"
            );
        }

        // Load config if available
        if (details.versions && details.versions.length > 0) {
            const latestVersion = details.versions[0];
            
            if (latestVersion.theme_config) {
                AppState.currentTheme = latestVersion.theme_config;
                if (typeof updateThemePreview === 'function') {
                    updateThemePreview(latestVersion.theme_config);
                }
            }

            if (latestVersion.config && latestVersion.config.size_estimate_mb) {
                updateSizeEstimate(latestVersion.config.size_estimate_mb);
            }

            buildBtn.disabled = false;
        }

    } catch (error) {
        showError('Failed to load project: ' + error.message);
    }
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
        currentSelectedProject = null;
        await loadProjectGallery();
    } catch (error) {
        showError('Failed to delete project: ' + error.message);
    }
}

/**
 * Retry failed build
 */
async function retryBuild(project) {
    if (!confirm(`Retry building "${project.name}"?`)) {
        return;
    }

    try {
        showSuccess('Starting build retry...');
        const response = await API.post(`/api/build/retry/${project.id}`, {});

        // Update UI to show building status
        await loadProjectGallery();

        // Start polling for build status
        if (response.build_id) {
            pollBuildStatusForGallery(response.build_id);
        }

    } catch (error) {
        showError('Failed to retry build: ' + error.message);
    }
}

/**
 * Poll build status and update gallery when complete
 */
function pollBuildStatusForGallery(buildId) {
    const pollInterval = setInterval(async () => {
        try {
            const status = await API.get(`/api/build/status/${buildId}`);

            if (status.status === 'completed') {
                clearInterval(pollInterval);
                showSuccess('Build completed successfully!');
                await loadProjectGallery();
            } else if (status.status === 'failed') {
                clearInterval(pollInterval);
                showError('Build failed: ' + (status.error || 'Unknown error'));
                await loadProjectGallery();
            }

        } catch (error) {
            console.error('Error polling build status:', error);
        }
    }, 3000);
}

/**
 * Update size estimate display
 */
function updateSizeEstimate(sizeMb) {
    const sizeEstimate = document.getElementById('sizeEstimate');
    const sizeBar = document.getElementById('sizeBar');
    
    if (sizeEstimate) {
        sizeEstimate.textContent = `~${sizeMb} MB`;
    }
    
    if (sizeBar) {
        const percentage = Math.min((sizeMb / 3000) * 100, 100);
        sizeBar.style.width = `${percentage}%`;
    }
}

// Export functions
window.initProjectGallery = initProjectGallery;
window.loadProjectGallery = loadProjectGallery;
window.loadGallery = loadGallery;
window.updateSizeEstimate = updateSizeEstimate;
