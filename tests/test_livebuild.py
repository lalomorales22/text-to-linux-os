from pathlib import Path

from backend.services import livebuild, themes


CONFIG = {
    "hostname": "My Custom Box!",
    "username": "Dev User",
    "use_case": "development",
    "hardware": {"ram_gb": 8, "cpu": "modern", "storage": "ssd", "boot": "uefi"},
    "packages": ["htop", "git"],
}


def test_sanitize_name():
    assert livebuild.sanitize_name("My Cool OS!") == "My-Cool-OS"
    assert livebuild.sanitize_name("///") == "project"
    assert len(livebuild.sanitize_name("x" * 200)) <= 60


def test_generate_config_tree(tmp_path):
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    config_dir = livebuild.generate_config_tree(CONFIG, themes.generate_random_theme(), build_dir)

    auto = (build_dir / "auto" / "config").read_text()
    assert "--bootloaders \"grub-efi\"" in auto          # uefi-only boot mode
    assert "hostname=my-custom-box" in auto              # sanitized, lowercased
    assert "username=devuser" in auto

    pkg_list = (config_dir / "package-lists" / "main.list.chroot").read_text()
    assert "linux-image-amd64" in pkg_list
    assert "htop" in pkg_list and "git" in pkg_list

    hook = config_dir / "hooks" / "live" / "0010-setup.hook.chroot"
    assert hook.exists()
    assert hook.stat().st_mode & 0o111                   # executable
    assert "autologin-user=devuser" in hook.read_text()

    assert (config_dir / "includes.chroot" / "etc" / "hostname").read_text().strip() == "my-custom-box"
    # theme files landed in the tree
    assert (config_dir / "includes.chroot" / "usr/share/themes/TextToLinux/openbox-3/themerc").exists()
    assert (config_dir / "includes.chroot" / "etc/xdg/tint2/tint2rc").exists()


def test_boot_mode_both(tmp_path):
    build_dir = tmp_path / "b2"
    build_dir.mkdir()
    config = {**CONFIG, "hardware": {**CONFIG["hardware"], "boot": "both"}}
    livebuild.generate_config_tree(config, None, build_dir)
    assert "syslinux,grub-efi" in (build_dir / "auto" / "config").read_text()
