"""
Live-build configuration generator
"""
import os
import shutil
from typing import Dict, Any, List
from backend.utils.validators import ESSENTIAL_PACKAGES


def generate_package_lists(packages: List[str], config_dir: str):
    """Generate package list files for live-build"""
    os.makedirs(f"{config_dir}/package-lists", exist_ok=True)

    # Combine essential packages with user packages
    all_packages = list(set(ESSENTIAL_PACKAGES + packages))

    # Write main package list
    with open(f"{config_dir}/package-lists/main.list.chroot", 'w') as f:
        f.write("# Essential packages\n")
        for pkg in ESSENTIAL_PACKAGES:
            f.write(f"{pkg}\n")

        f.write("\n# Desktop environment\n")
        desktop_pkgs = [p for p in all_packages if p in [
            'xorg', 'openbox', 'tint2', 'pcmanfm', 'lxterminal',
            'lightdm', 'xfce4-power-manager'
        ]]
        for pkg in desktop_pkgs:
            f.write(f"{pkg}\n")

        f.write("\n# Applications\n")
        app_pkgs = [p for p in all_packages if p not in ESSENTIAL_PACKAGES and p not in desktop_pkgs]
        for pkg in app_pkgs:
            f.write(f"{pkg}\n")


def generate_live_build_config(config: Dict[str, Any], build_dir: str) -> str:
    """
    Generate complete live-build configuration
    Returns the config directory path
    """
    config_dir = f"{build_dir}/config"

    # Create base directories
    os.makedirs(config_dir, exist_ok=True)
    os.makedirs(f"{config_dir}/hooks", exist_ok=True)
    os.makedirs(f"{config_dir}/includes.chroot", exist_ok=True)
    os.makedirs(f"{config_dir}/includes.chroot/etc/skel", exist_ok=True)
    os.makedirs(f"{config_dir}/includes.chroot/usr/local/bin", exist_ok=True)

    # Generate package lists
    generate_package_lists(config.get('packages', []), config_dir)

    # Generate hooks
    generate_hooks(config, config_dir)

    # Generate boot configuration
    generate_boot_config(config, config_dir)

    # Create auto config
    generate_auto_config(config, build_dir)

    return config_dir


def generate_auto_config(config: Dict[str, Any], build_dir: str):
    """Generate auto/config script for live-build"""
    os.makedirs(f"{build_dir}/auto", exist_ok=True)

    hardware = config.get('hardware', {})
    arch = hardware.get('architecture', 'amd64')

    auto_config = f"""#!/bin/sh

set -e

lb config noauto \\
    --distribution bookworm \\
    --architectures {arch} \\
    --archive-areas "main contrib non-free non-free-firmware" \\
    --debian-installer false \\
    --bootappend-live "boot=live components quiet splash" \\
    --mode debian \\
    --system live \\
    --binary-images iso-hybrid \\
    --memtest none \\
    --bootloaders "syslinux,grub-efi" \\
    --linux-packages linux-image \\
    --security true \\
    --updates true \\
    "${{@}}"
"""

    with open(f"{build_dir}/auto/config", 'w') as f:
        f.write(auto_config)

    os.chmod(f"{build_dir}/auto/config", 0o755)


def generate_hooks(config: Dict[str, Any], config_dir: str):
    """Generate post-installation hooks"""

    # Create startup script for OpenBox
    startup_hook = """#!/bin/bash
# Post-installation hook for Text-to-Linux-OS

# Set up auto-login for live user
if [ ! -f /etc/lightdm/lightdm.conf ]; then
    mkdir -p /etc/lightdm
    cat > /etc/lightdm/lightdm.conf << 'EOF'
[Seat:*]
autologin-user=user
autologin-user-timeout=0
user-session=openbox
EOF
fi

# Create default user if not exists
if ! id -u user > /dev/null 2>&1; then
    useradd -m -s /bin/bash user
    echo "user:live" | chpasswd
    usermod -aG sudo user
fi

# Set up OpenBox autostart
mkdir -p /etc/skel/.config/openbox
cat > /etc/skel/.config/openbox/autostart << 'EOF'
# Start panel
tint2 &

# Start file manager in daemon mode
pcmanfm --desktop &

# Set wallpaper (if custom wallpaper exists)
if [ -f ~/wallpaper.jpg ]; then
    feh --bg-scale ~/wallpaper.jpg
elif [ -f ~/wallpaper.png ]; then
    feh --bg-scale ~/wallpaper.png
fi
EOF

chmod +x /etc/skel/.config/openbox/autostart

# Copy skel to existing user directory
cp -r /etc/skel/.config /home/user/ 2>/dev/null || true
chown -R user:user /home/user/.config 2>/dev/null || true

echo "Text-to-Linux-OS setup complete!"
"""

    with open(f"{config_dir}/hooks/live/0010-setup.hook.chroot", 'w') as f:
        f.write(startup_hook)

    os.chmod(f"{config_dir}/hooks/live/0010-setup.hook.chroot", 0o755)

    # Install custom tools if specified
    custom_tools = config.get('custom_tools', [])
    if custom_tools:
        tools_hook = """#!/bin/bash
# Install custom tools

set -e

"""
        if 'claude-code' in custom_tools:
            tools_hook += """
# Install Claude Code (if not already in repos)
echo "Installing claude-code..."
# This would require custom installation script
# For now, we'll create a placeholder
"""

        if 'gemini-cli' in custom_tools:
            tools_hook += """
# Install Gemini CLI
echo "Installing gemini-cli..."
# This would require custom installation script
"""

        with open(f"{config_dir}/hooks/live/0020-custom-tools.hook.chroot", 'w') as f:
            f.write(tools_hook)

        os.chmod(f"{config_dir}/hooks/live/0020-custom-tools.hook.chroot", 0o755)


def generate_boot_config(config: Dict[str, Any], config_dir: str):
    """Generate boot configuration (GRUB, Plymouth)"""

    # Create GRUB config
    os.makedirs(f"{config_dir}/includes.chroot/etc/default", exist_ok=True)

    grub_config = """# GRUB configuration for Text-to-Linux-OS
GRUB_DEFAULT=0
GRUB_TIMEOUT=5
GRUB_DISTRIBUTOR="Text-to-Linux-OS"
GRUB_CMDLINE_LINUX_DEFAULT="quiet splash"
GRUB_CMDLINE_LINUX=""
"""

    with open(f"{config_dir}/includes.chroot/etc/default/grub", 'w') as f:
        f.write(grub_config)


def copy_templates_to_config(config_dir: str, templates_dir: str = "./templates"):
    """Copy template files to configuration"""

    # Copy OpenBox templates
    if os.path.exists(f"{templates_dir}/openbox"):
        shutil.copytree(
            f"{templates_dir}/openbox",
            f"{config_dir}/includes.chroot/etc/xdg/openbox",
            dirs_exist_ok=True
        )

    # Copy Plymouth templates
    if os.path.exists(f"{templates_dir}/plymouth-ascii"):
        shutil.copytree(
            f"{templates_dir}/plymouth-ascii",
            f"{config_dir}/includes.chroot/usr/share/plymouth/themes/text-to-linux",
            dirs_exist_ok=True
        )

    # Copy GRUB templates
    if os.path.exists(f"{templates_dir}/grub"):
        shutil.copytree(
            f"{templates_dir}/grub",
            f"{config_dir}/includes.chroot/boot/grub/themes/text-to-linux",
            dirs_exist_ok=True
        )


def create_build_directory(project_name: str, version: int) -> str:
    """Create and return build directory path"""
    build_dir = f"./builds/{project_name}_v{version}"
    os.makedirs(build_dir, exist_ok=True)
    return build_dir
