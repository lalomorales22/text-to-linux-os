import re

from backend.services import themes

HEX = re.compile(r"^#[0-9a-f]{6}$")


def test_random_theme_structure():
    theme = themes.generate_random_theme()
    for key in ("primary", "secondary", "accent", "background", "surface", "foreground"):
        assert HEX.match(theme[key]), f"{key} is not a hex color: {theme[key]}"
    assert len(theme["terminal"]) >= 18
    for value in theme["terminal"].values():
        assert HEX.match(value)


def test_background_is_dark():
    for _ in range(20):
        bg = themes.generate_random_theme()["background"]
        r, g, b = (int(bg[i:i + 2], 16) for i in (1, 3, 5))
        assert r + g + b < 300, f"background too bright: {bg}"


def test_normalize_fills_missing_keys():
    partial = {"primary": "#ff0000", "background": "#000011"}
    merged = themes.normalize_theme(partial)
    assert merged["primary"] == "#ff0000"
    assert merged["terminal"]["color4"] == "#ff0000"
    assert merged["terminal"]["background"] == "#000011"
    assert HEX.match(merged["accent"])


def test_apply_writes_files(tmp_path):
    themes.apply_theme_to_config(themes.generate_random_theme(), tmp_path)
    chroot = tmp_path / "includes.chroot"
    themerc = chroot / "usr/share/themes/TextToLinux/openbox-3/themerc"
    assert "window.active.border.color" in themerc.read_text()
    assert "panel_items" in (chroot / "etc/xdg/tint2/tint2rc").read_text()
    assert "palette_color_15" in (chroot / "etc/skel/.config/lxterminal/lxterminal.conf").read_text()
    assert "BACKGROUND=" in (chroot / "etc/text-to-linux/theme.conf").read_text()
