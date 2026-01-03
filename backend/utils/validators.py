"""
Validators for package names, configs, and user inputs
"""
import re
from typing import List, Dict, Any, Tuple


# Common Debian package patterns
PACKAGE_NAME_PATTERN = re.compile(r'^[a-z0-9][a-z0-9+.-]+$')

# Known essential packages that should always be included
ESSENTIAL_PACKAGES = [
    "linux-image-amd64",
    "live-boot",
    "systemd",
    "network-manager",
]

# Known conflicting package pairs
PACKAGE_CONFLICTS = {
    "vim": ["nano"],
    "nano": ["vim"],
}

# Package size estimates (in MB)
PACKAGE_SIZES = {
    # Base system
    "linux-image-amd64": 50,
    "live-boot": 5,
    "systemd": 10,
    "network-manager": 8,

    # Desktop
    "xorg": 100,
    "openbox": 2,
    "tint2": 1,
    "pcmanfm": 3,
    "lxterminal": 2,

    # Browsers
    "firefox-esr": 100,
    "chromium": 120,

    # Development
    "build-essential": 50,
    "python3": 15,
    "python3-pip": 10,
    "nodejs": 30,
    "npm": 20,
    "git": 15,

    # Editors
    "vim": 5,
    "nano": 1,
    "code-oss": 200,

    # Utilities
    "curl": 1,
    "wget": 1,
    "bash-completion": 1,
    "sudo": 2,

    # Firmware
    "firmware-linux-free": 20,
    "firmware-linux-nonfree": 50,
}

DEFAULT_PACKAGE_SIZE = 5  # Default size for unknown packages


def validate_package_name(package_name: str) -> bool:
    """Validate Debian package name format"""
    return bool(PACKAGE_NAME_PATTERN.match(package_name))


def validate_package_list(packages: List[str]) -> Tuple[bool, List[str]]:
    """
    Validate list of package names
    Returns (is_valid, error_messages)
    """
    errors = []

    for package in packages:
        if not validate_package_name(package):
            errors.append(f"Invalid package name: {package}")

    return len(errors) == 0, errors


def check_package_conflicts(packages: List[str]) -> List[str]:
    """Check for conflicting packages"""
    conflicts = []

    for package in packages:
        if package in PACKAGE_CONFLICTS:
            conflicting = PACKAGE_CONFLICTS[package]
            for conflict in conflicting:
                if conflict in packages:
                    conflicts.append(f"{package} conflicts with {conflict}")

    return conflicts


def estimate_iso_size(packages: List[str], include_base: bool = True) -> int:
    """
    Estimate ISO size in MB based on packages
    """
    total_size = 0

    # Base ISO overhead (bootloader, live-boot system, etc.)
    if include_base:
        total_size += 300  # Base overhead

    # Add package sizes
    for package in packages:
        total_size += PACKAGE_SIZES.get(package, DEFAULT_PACKAGE_SIZE)

    # Add 20% overhead for dependencies and metadata
    total_size = int(total_size * 1.2)

    return total_size


def validate_iso_config(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate complete ISO configuration
    Returns (is_valid, error_messages)
    """
    errors = []

    # Check required fields
    required_fields = ['hardware', 'use_case', 'packages']
    for field in required_fields:
        if field not in config:
            errors.append(f"Missing required field: {field}")

    if 'packages' in config:
        # Validate packages
        is_valid, package_errors = validate_package_list(config['packages'])
        errors.extend(package_errors)

        # Check conflicts
        conflicts = check_package_conflicts(config['packages'])
        errors.extend(conflicts)

        # Check size
        size_mb = estimate_iso_size(config['packages'])
        max_size_gb = int(os.getenv('MAX_ISO_SIZE_GB', '3'))
        if size_mb > max_size_gb * 1024:
            errors.append(
                f"ISO size ({size_mb}MB) exceeds maximum ({max_size_gb}GB). "
                "Please remove some packages."
            )

    return len(errors) == 0, errors


def sanitize_project_name(name: str) -> str:
    """Sanitize project name for filesystem safety"""
    # Remove or replace unsafe characters
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
    # Limit length
    safe_name = safe_name[:100]
    return safe_name


def validate_wallpaper_upload(filename: str, max_size_mb: int = 10) -> Tuple[bool, str]:
    """Validate wallpaper file upload"""
    allowed_extensions = ['.jpg', '.jpeg', '.png', '.bmp']

    ext = os.path.splitext(filename)[1].lower()
    if ext not in allowed_extensions:
        return False, f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"

    return True, ""


import os
