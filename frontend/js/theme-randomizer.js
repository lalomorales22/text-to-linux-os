/**
 * Theme randomizer with clickable color pickers
 */

const themeElements = {
    randomizeBtn: null,
    previewPrimary: null,
    previewSecondary: null,
    previewAccent: null,
    previewBackground: null,
    colorPrimary: null,
    colorSecondary: null,
    colorAccent: null,
    colorBackground: null
};

/**
 * Initialize theme randomizer
 */
function initThemeRandomizer() {
    // Get elements
    themeElements.randomizeBtn = document.getElementById('randomizeThemeBtn');
    themeElements.previewPrimary = document.getElementById('previewPrimary');
    themeElements.previewSecondary = document.getElementById('previewSecondary');
    themeElements.previewAccent = document.getElementById('previewAccent');
    themeElements.previewBackground = document.getElementById('previewBackground');
    themeElements.colorPrimary = document.getElementById('colorPrimary');
    themeElements.colorSecondary = document.getElementById('colorSecondary');
    themeElements.colorAccent = document.getElementById('colorAccent');
    themeElements.colorBackground = document.getElementById('colorBackground');

    // Randomize button
    if (themeElements.randomizeBtn) {
        themeElements.randomizeBtn.addEventListener('click', randomizeTheme);
    }

    // Color picker listeners - clicking preview opens native picker
    setupColorPicker('Primary', 'primary');
    setupColorPicker('Secondary', 'secondary');
    setupColorPicker('Accent', 'accent');
    setupColorPicker('Background', 'background');

    // Generate initial theme
    randomizeTheme();
}

/**
 * Setup a color picker with click-to-edit
 */
function setupColorPicker(name, key) {
    const preview = themeElements[`preview${name}`];
    const input = themeElements[`color${name}`];

    if (!preview || !input) return;

    // Clicking preview opens color picker
    preview.addEventListener('click', () => {
        input.click();
    });

    // Color input change
    input.addEventListener('input', (e) => {
        const color = e.target.value;
        preview.style.backgroundColor = color;
        
        // Update theme state
        if (AppState.currentTheme && AppState.currentTheme.base_colors) {
            AppState.currentTheme.base_colors[key] = color;
            updateCompleteTheme();
        }
    });
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
    animateColorChange(themeElements.previewPrimary, themeElements.colorPrimary, colors.primary);
    animateColorChange(themeElements.previewSecondary, themeElements.colorSecondary, colors.secondary);
    animateColorChange(themeElements.previewAccent, themeElements.colorAccent, colors.accent);
    animateColorChange(themeElements.previewBackground, themeElements.colorBackground, colors.background);
}

/**
 * Animate color change
 */
function animateColorChange(preview, input, color) {
    if (!preview) return;

    // Add animation
    preview.style.transform = 'scale(0.95)';
    preview.style.opacity = '0.7';

    setTimeout(() => {
        preview.style.backgroundColor = color;
        if (input) input.value = color;
        preview.style.transform = 'scale(1)';
        preview.style.opacity = '1';
        preview.style.transition = 'all 0.2s ease';
    }, 100);
}

/**
 * Generate fallback theme (client-side)
 */
function generateFallbackTheme() {
    const randomColor = () => {
        return '#' + Math.floor(Math.random() * 16777215).toString(16).padStart(6, '0');
    };

    // Generate a cohesive color palette
    const hue = Math.floor(Math.random() * 360);
    const primary = hslToHex(hue, 70, 50);
    const secondary = hslToHex((hue + 30) % 360, 60, 45);
    const accent = hslToHex((hue + 180) % 360, 80, 55);
    const background = hslToHex(hue, 20, 15);

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
 * Update complete theme from current colors
 */
function updateCompleteTheme() {
    if (!AppState.currentTheme || !AppState.currentTheme.base_colors) return;
    
    const colors = AppState.currentTheme.base_colors;
    
    AppState.currentTheme = {
        ...AppState.currentTheme,
        ...generateThemeFromColors(colors)
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
            background: darken(colors.background, 0.7),
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
 * HSL to Hex conversion
 */
function hslToHex(h, s, l) {
    s /= 100;
    l /= 100;
    const a = s * Math.min(l, 1 - l);
    const f = n => {
        const k = (n + h / 30) % 12;
        const color = l - a * Math.max(Math.min(k - 3, 9 - k, 1), -1);
        return Math.round(255 * color).toString(16).padStart(2, '0');
    };
    return `#${f(0)}${f(8)}${f(4)}`;
}

/**
 * Darken a hex color
 */
function darken(hex, factor) {
    if (!hex) return '#000000';
    hex = hex.replace('#', '');

    let r = parseInt(hex.substring(0, 2), 16);
    let g = parseInt(hex.substring(2, 4), 16);
    let b = parseInt(hex.substring(4, 6), 16);

    r = Math.floor(r * factor);
    g = Math.floor(g * factor);
    b = Math.floor(b * factor);

    return '#' + [r, g, b].map(x => {
        const hex = x.toString(16);
        return hex.length === 1 ? '0' + hex : hex;
    }).join('');
}

/**
 * Lighten a hex color
 */
function lighten(hex, factor) {
    if (!hex) return '#ffffff';
    hex = hex.replace('#', '');

    let r = parseInt(hex.substring(0, 2), 16);
    let g = parseInt(hex.substring(2, 4), 16);
    let b = parseInt(hex.substring(4, 6), 16);

    r = Math.min(255, Math.floor(r + (255 - r) * factor));
    g = Math.min(255, Math.floor(g + (255 - g) * factor));
    b = Math.min(255, Math.floor(b + (255 - b) * factor));

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
