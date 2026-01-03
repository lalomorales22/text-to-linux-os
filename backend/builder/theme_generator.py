"""
Theme generator for OpenBox, terminal, panel, and GRUB
"""
import random
from typing import Dict, Any, Tuple


def random_rgb() -> Tuple[int, int, int]:
    """Generate random RGB color"""
    return (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))


def rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    """Convert RGB to hex color"""
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def generate_complementary_color(base_rgb: Tuple[int, int, int]) -> Tuple[int, int, int]:
    """Generate a complementary color"""
    return (255 - base_rgb[0], 255 - base_rgb[1], 255 - base_rgb[2])


def generate_darker_shade(rgb: Tuple[int, int, int], factor: float = 0.7) -> Tuple[int, int, int]:
    """Generate darker shade of a color"""
    return (
        int(rgb[0] * factor),
        int(rgb[1] * factor),
        int(rgb[2] * factor)
    )


def generate_lighter_shade(rgb: Tuple[int, int, int], factor: float = 1.3) -> Tuple[int, int, int]:
    """Generate lighter shade of a color"""
    return (
        min(255, int(rgb[0] * factor)),
        min(255, int(rgb[1] * factor)),
        min(255, int(rgb[2] * factor))
    )


def generate_openbox_theme(primary: Tuple[int, int, int], secondary: Tuple[int, int, int]) -> Dict[str, Any]:
    """Generate OpenBox window manager theme configuration"""
    primary_hex = rgb_to_hex(primary)
    secondary_hex = rgb_to_hex(secondary)
    dark_shade = rgb_to_hex(generate_darker_shade(primary))
    light_shade = rgb_to_hex(generate_lighter_shade(primary))

    return {
        "border_width": 2,
        "title_height": 24,
        "padding_width": 3,
        "padding_height": 3,
        "window_active_border_color": primary_hex,
        "window_inactive_border_color": secondary_hex,
        "window_active_title_bg": primary_hex,
        "window_inactive_title_bg": dark_shade,
        "window_active_title_text": "#ffffff",
        "window_inactive_title_text": "#aaaaaa",
        "window_active_button_bg": light_shade,
        "window_inactive_button_bg": secondary_hex,
        "menu_bg": primary_hex,
        "menu_text": "#ffffff",
        "menu_selected_bg": light_shade,
        "menu_selected_text": "#ffffff"
    }


def generate_terminal_colors(primary: Tuple[int, int, int], accent: Tuple[int, int, int]) -> Dict[str, Any]:
    """Generate terminal color scheme"""
    return {
        "background": rgb_to_hex(generate_darker_shade(primary, 0.15)),
        "foreground": "#e0e0e0",
        "cursor": rgb_to_hex(accent),
        "color0": "#2e3436",  # Black
        "color1": "#cc0000",  # Red
        "color2": "#4e9a06",  # Green
        "color3": "#c4a000",  # Yellow
        "color4": rgb_to_hex(primary),  # Blue (themed)
        "color5": "#75507b",  # Magenta
        "color6": "#06989a",  # Cyan
        "color7": "#d3d7cf",  # White
        "color8": "#555753",  # Bright Black
        "color9": "#ef2929",  # Bright Red
        "color10": "#8ae234",  # Bright Green
        "color11": "#fce94f",  # Bright Yellow
        "color12": rgb_to_hex(accent),  # Bright Blue (themed)
        "color13": "#ad7fa8",  # Bright Magenta
        "color14": "#34e2e2",  # Bright Cyan
        "color15": "#eeeeec",  # Bright White
    }


def generate_panel_config(background: Tuple[int, int, int], accent: Tuple[int, int, int]) -> Dict[str, Any]:
    """Generate tint2 panel configuration"""
    bg_hex = rgb_to_hex(generate_darker_shade(background, 0.3))
    accent_hex = rgb_to_hex(accent)

    return {
        "panel_position": "bottom center horizontal",
        "panel_size": "100% 32",
        "panel_background_color": bg_hex,
        "panel_background_alpha": 90,
        "taskbar_background_color": bg_hex,
        "taskbar_active_background_color": accent_hex,
        "taskbar_text_color": "#ffffff",
        "taskbar_active_text_color": "#ffffff",
        "clock_background_color": bg_hex,
        "clock_text_color": "#ffffff",
        "systray_background_color": bg_hex,
        "panel_padding": "5 2 5",
        "taskbar_padding": "2 2 2"
    }


def generate_grub_theme(primary: Tuple[int, int, int], background: Tuple[int, int, int]) -> Dict[str, Any]:
    """Generate GRUB bootloader theme"""
    return {
        "background_color": rgb_to_hex(generate_darker_shade(background, 0.2)),
        "text_color": "#e0e0e0",
        "selected_color": rgb_to_hex(primary),
        "border_color": rgb_to_hex(primary),
        "title_text": "TEXT-TO-LINUX-OS",
        "title_color": rgb_to_hex(generate_lighter_shade(primary)),
        "font": "DejaVu Sans Mono 14",
        "show_ascii_art": True
    }


def generate_random_theme() -> Dict[str, Any]:
    """Generate a complete random theme"""
    # Generate base colors
    primary = random_rgb()
    secondary = random_rgb()
    accent = random_rgb()
    background = random_rgb()

    # Ensure background is relatively dark
    if sum(background) > 400:  # If too bright
        background = generate_darker_shade(background, 0.4)

    return {
        "openbox": generate_openbox_theme(primary, secondary),
        "terminal": generate_terminal_colors(primary, accent),
        "panel": generate_panel_config(background, accent),
        "grub": generate_grub_theme(primary, background),
        "wallpaper": {
            "type": "solid",  # or "image"
            "color": rgb_to_hex(background),
            "path": None
        },
        "base_colors": {
            "primary": rgb_to_hex(primary),
            "secondary": rgb_to_hex(secondary),
            "accent": rgb_to_hex(accent),
            "background": rgb_to_hex(background)
        }
    }


def apply_theme_to_config(theme: Dict[str, Any], config_dir: str):
    """
    Apply theme to live-build configuration files
    This generates the actual configuration files in the build directory
    """
    import os
    from jinja2 import Template

    # Create theme directories
    os.makedirs(f"{config_dir}/includes.chroot/etc/xdg/openbox", exist_ok=True)
    os.makedirs(f"{config_dir}/includes.chroot/etc/xdg/tint2", exist_ok=True)
    os.makedirs(f"{config_dir}/includes.chroot/root/.config/lxterminal", exist_ok=True)

    # Write OpenBox theme
    openbox_rc = generate_openbox_rc_xml(theme['openbox'])
    with open(f"{config_dir}/includes.chroot/etc/xdg/openbox/rc.xml", 'w') as f:
        f.write(openbox_rc)

    # Write tint2 panel config
    tint2_conf = generate_tint2_config(theme['panel'])
    with open(f"{config_dir}/includes.chroot/etc/xdg/tint2/tint2rc", 'w') as f:
        f.write(tint2_conf)

    # Write terminal config
    terminal_conf = generate_lxterminal_config(theme['terminal'])
    with open(f"{config_dir}/includes.chroot/root/.config/lxterminal/lxterminal.conf", 'w') as f:
        f.write(terminal_conf)

    return True


def generate_openbox_rc_xml(theme: Dict[str, Any]) -> str:
    """Generate OpenBox rc.xml configuration"""
    # This is a simplified version - full OpenBox config is much larger
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<openbox_config xmlns="http://openbox.org/3.4/rc">
  <theme>
    <name>Custom</name>
    <titleLayout>NLIMC</titleLayout>
    <keepBorder>yes</keepBorder>
    <animateIconify>yes</animateIconify>
  </theme>
  <desktops>
    <number>4</number>
    <firstdesk>1</firstdesk>
  </desktops>
</openbox_config>
"""


def generate_tint2_config(theme: Dict[str, Any]) -> str:
    """Generate tint2 panel configuration"""
    return f"""# Tint2 config - Generated by Text-to-Linux-OS
panel_items = LTSC
panel_position = {theme['panel_position']}
panel_size = {theme['panel_size']}
panel_background_id = 1
panel_monitor = all

background_color = {theme['panel_background_color']} {theme['panel_background_alpha']}
border_width = 0

taskbar_mode = single_desktop
taskbar_padding = {theme['taskbar_padding']}
taskbar_background_id = 1

task_background_id = 1
task_active_background_id = 2
task_text = 1
task_centered = 1

time1_format = %H:%M
time1_font = sans 10
clock_font_color = {theme['clock_text_color']} 100
clock_padding = 5 2
clock_background_id = 1

# Background definitions
background_color = {theme['taskbar_background_color']} 100
border_color = {theme['taskbar_background_color']} 100

# Active task background
background_color = {theme['taskbar_active_background_color']} 100
border_color = {theme['taskbar_active_background_color']} 100
"""


def generate_lxterminal_config(theme: Dict[str, Any]) -> str:
    """Generate LXTerminal configuration"""
    return f"""[general]
fontname=Monospace 10
selchars=-A-Za-z0-9,./?%&#:_
scrollback=1000
bgcolor={theme['background']}
fgcolor={theme['foreground']}
palette_color_0={theme['color0']}
palette_color_1={theme['color1']}
palette_color_2={theme['color2']}
palette_color_3={theme['color3']}
palette_color_4={theme['color4']}
palette_color_5={theme['color5']}
palette_color_6={theme['color6']}
palette_color_7={theme['color7']}
palette_color_8={theme['color8']}
palette_color_9={theme['color9']}
palette_color_10={theme['color10']}
palette_color_11={theme['color11']}
palette_color_12={theme['color12']}
palette_color_13={theme['color13']}
palette_color_14={theme['color14']}
palette_color_15={theme['color15']}
color_preset=Custom
disallowbold=false
cursorblinks=false
cursorunderline=false
audiblebell=false
tabpos=top
hidescrollbar=false
hidemenubar=false
hideclosebtn=false
disablef10=false
disablealt=false
"""
