/**
 * Theme randomizer functionality
 */

const themeElements = {
    randomizeBtn: document.getElementById('randomizeThemeBtn'),
    previewPrimary: document.getElementById('previewPrimary'),
    previewSecondary: document.getElementById('previewSecondary'),
    previewAccent: document.getElementById('previewAccent'),
    previewBackground: document.getElementById('previewBackground')
};

/**
 * Initialize theme randomizer
 */
function initThemeRandomizer() {
    if (themeElements.randomizeBtn) {
        themeElements.randomizeBtn.addEventListener('click', randomizeTheme);
    }

    // Generate initial theme
    randomizeTheme();
}

/**
 * Randomize theme colors
 */
async function randomizeTheme() {
    try {
        // Call API to generate random theme
        const theme = await API.post('/api/projects/theme/randomize', {});

        // Store in app state
        AppState.currentTheme = theme;

        // Update preview
        updateThemePreview(theme);

        console.log('Theme randomized:', theme);

    } catch (error) {
        console.error('Failed to randomize theme:', error);

        // Fallback to client-side random theme
        const fallbackTheme = generateFallbackTheme();
        AppState.currentTheme = fallbackTheme;
        updateThemePreview(fallbackTheme);
    }
}

/**
 * Update theme preview
 */
function updateThemePreview(theme) {
    if (!theme.base_colors) return;

    const colors = theme.base_colors;

    // Update color previews with animation
    animateColorChange(themeElements.previewPrimary, colors.primary);
    animateColorChange(themeElements.previewSecondary, colors.secondary);
    animateColorChange(themeElements.previewAccent, colors.accent);
    animateColorChange(themeElements.previewBackground, colors.background);
}

/**
 * Animate color change
 */
function animateColorChange(element, color) {
    if (!element) return;

    // Add animation class
    element.style.transform = 'scale(0.9)';
    element.style.opacity = '0.5';

    setTimeout(() => {
        element.style.backgroundColor = color;
        element.style.transform = 'scale(1)';
        element.style.opacity = '1';
        element.style.transition = 'all 0.3s ease';
    }, 150);
}

/**
 * Generate fallback theme (client-side)
 */
function generateFallbackTheme() {
    const randomColor = () => {
        return '#' + Math.floor(Math.random() * 16777215).toString(16).padStart(6, '0');
    };

    const primary = randomColor();
    const secondary = randomColor();
    const accent = randomColor();
    const background = randomColor();

    return {
        base_colors: {
            primary: primary,
            secondary: secondary,
            accent: accent,
            background: background
        },
        openbox: {
            window_active_border_color: primary,
            window_inactive_border_color: secondary
        },
        terminal: {
            background: background,
            foreground: '#e0e0e0',
            cursor: accent
        },
        panel: {
            panel_background_color: background,
            taskbar_active_background_color: accent
        },
        grub: {
            background_color: background,
            selected_color: primary
        },
        wallpaper: {
            type: 'solid',
            color: background
        }
    };
}

/**
 * Get current theme
 */
function getCurrentTheme() {
    return AppState.currentTheme;
}

/**
 * Apply custom colors
 */
function applyCustomColors(colors) {
    const theme = {
        base_colors: colors,
        ...generateThemeFromColors(colors)
    };

    AppState.currentTheme = theme;
    updateThemePreview(theme);
}

/**
 * Generate complete theme from base colors
 */
function generateThemeFromColors(colors) {
    return {
        openbox: {
            window_active_border_color: colors.primary,
            window_inactive_border_color: colors.secondary,
            window_active_title_bg: colors.primary,
            window_inactive_title_bg: darken(colors.primary, 0.3)
        },
        terminal: {
            background: darken(colors.primary, 0.85),
            foreground: '#e0e0e0',
            cursor: colors.accent,
            color4: colors.primary,
            color12: colors.accent
        },
        panel: {
            panel_background_color: darken(colors.background, 0.7),
            taskbar_active_background_color: colors.accent,
            taskbar_background_color: darken(colors.background, 0.7)
        },
        grub: {
            background_color: darken(colors.background, 0.8),
            selected_color: colors.primary,
            border_color: colors.primary
        },
        wallpaper: {
            type: 'solid',
            color: colors.background
        }
    };
}

/**
 * Darken a hex color
 */
function darken(hex, factor) {
    // Remove # if present
    hex = hex.replace('#', '');

    // Convert to RGB
    let r = parseInt(hex.substring(0, 2), 16);
    let g = parseInt(hex.substring(2, 4), 16);
    let b = parseInt(hex.substring(4, 6), 16);

    // Darken
    r = Math.floor(r * factor);
    g = Math.floor(g * factor);
    b = Math.floor(b * factor);

    // Convert back to hex
    return '#' + [r, g, b].map(x => {
        const hex = x.toString(16);
        return hex.length === 1 ? '0' + hex : hex;
    }).join('');
}

/**
 * Lighten a hex color
 */
function lighten(hex, factor) {
    hex = hex.replace('#', '');

    let r = parseInt(hex.substring(0, 2), 16);
    let g = parseInt(hex.substring(2, 4), 16);
    let b = parseInt(hex.substring(4, 6), 16);

    r = Math.min(255, Math.floor(r * factor));
    g = Math.min(255, Math.floor(g * factor));
    b = Math.min(255, Math.floor(b * factor));

    return '#' + [r, g, b].map(x => {
        const hex = x.toString(16);
        return hex.length === 1 ? '0' + hex : hex;
    }).join('');
}

// Export functions
window.initThemeRandomizer = initThemeRandomizer;
window.randomizeTheme = randomizeTheme;
window.getCurrentTheme = getCurrentTheme;
window.applyCustomColors = applyCustomColors;
