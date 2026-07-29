"""Real Debian package validation.

Downloads and caches the actual Debian package index (Packages.gz for each
archive area), so package existence, sizes, and suggestions come from the real
repository instead of guesses. Also exposes an apt dry-run when running inside
a Debian environment (the Docker container), which surfaces dependency
conflicts in seconds instead of 40 minutes into a build.
"""
import asyncio
import difflib
import gzip
import logging
import re
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from backend.config import get_settings
from backend.database.db import MetaDB, PackageDB

logger = logging.getLogger(__name__)

INDEX_SYNCED_KEY = "package_index_synced_at"

# Packages every ISO gets regardless of user selection.
ESSENTIAL_PACKAGES = [
    "linux-image-amd64",
    "live-boot",
    "systemd-sysv",
    "network-manager",
    "sudo",
    "locales",
    "keyboard-configuration",
]

DESKTOP_PACKAGES = [
    "xserver-xorg", "xinit", "openbox", "tint2", "pcmanfm", "lxterminal",
    "lightdm", "feh", "fonts-dejavu",
]

# Common wrong names -> real Debian packages.
KNOWN_ALIASES: dict[str, list[str]] = {
    "chrome": ["chromium", "firefox-esr"],
    "google-chrome": ["chromium"],
    "vscode": ["codium", "vim", "neovim"],
    "code": ["codium"],
    "code-oss": ["codium"],
    "python": ["python3"],
    "pip": ["python3-pip"],
    "node": ["nodejs"],
    "docker": ["docker.io"],
    "docker-ce": ["docker.io"],
    "openjdk": ["default-jdk"],
    "java": ["default-jre"],
    "gcc-full": ["build-essential"],
    "spotify": ["vlc"],
    "slack": ["firefox-esr"],
}

# Size model constants (documented heuristics applied to REAL installed sizes):
# squashfs compresses the root filesystem to roughly 45% of installed size, and
# dependency closure typically adds ~35% over the top-level package list.
BASE_SYSTEM_MB = 350
SQUASHFS_RATIO = 0.45
DEPENDENCY_FACTOR = 1.35

_sync_lock = asyncio.Lock()


async def sync_index(force: bool = False) -> dict:
    """Download and cache the Debian package index. Safe to call repeatedly."""
    settings = get_settings()
    async with _sync_lock:
        if not force and not index_is_stale():
            return {"synced": False, "packages": PackageDB.count()}

        rows: dict[str, tuple] = {}
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
            for area in settings.debian_areas:
                url = (f"{settings.debian_mirror}/dists/{settings.debian_suite}"
                       f"/{area.strip()}/binary-amd64/Packages.gz")
                logger.info("Fetching package index: %s", url)
                resp = await client.get(url)
                resp.raise_for_status()
                text = gzip.decompress(resp.content).decode("utf-8", errors="replace")
                for row in _parse_packages_file(text):
                    rows[row[0]] = row  # later areas override duplicates

        PackageDB.replace_all(list(rows.values()))
        MetaDB.set(INDEX_SYNCED_KEY, datetime.now(timezone.utc).isoformat())
        logger.info("Package index synced: %d packages", len(rows))
        return {"synced": True, "packages": len(rows)}


def index_is_stale() -> bool:
    if PackageDB.count() == 0:
        return True
    synced_at = MetaDB.get(INDEX_SYNCED_KEY)
    if not synced_at:
        return True
    age = datetime.now(timezone.utc) - datetime.fromisoformat(synced_at)
    return age > timedelta(hours=get_settings().package_index_max_age_hours)


def _parse_packages_file(text: str):
    """Yield (name, version, installed_size_kb, download_size_bytes, section, description)."""
    current: dict[str, str] = {}
    for line in text.splitlines():
        if not line:
            if "Package" in current:
                yield (
                    current["Package"],
                    current.get("Version", ""),
                    int(current.get("Installed-Size", "0") or 0),
                    int(current.get("Size", "0") or 0),
                    current.get("Section", ""),
                    current.get("Description", "")[:200],
                )
            current = {}
        elif line[0] not in (" ", "\t") and ":" in line:
            key, _, value = line.partition(":")
            current[key] = value.strip()
    if "Package" in current:
        yield (
            current["Package"],
            current.get("Version", ""),
            int(current.get("Installed-Size", "0") or 0),
            int(current.get("Size", "0") or 0),
            current.get("Section", ""),
            current.get("Description", "")[:200],
        )


def suggest_alternatives(name: str, all_names: list[str] | None = None) -> list[str]:
    lowered = name.lower()
    if lowered in KNOWN_ALIASES:
        return KNOWN_ALIASES[lowered]
    # Fuzzy match against packages that share a prefix or contain the name,
    # then rank with difflib. Progressively shorter prefixes keep typos like
    # "dockerr" matchable while the candidate pool stays small and fast.
    candidates: list[str] = []
    for query in (lowered, lowered[:5], lowered[:4], lowered[:3]):
        if len(query) < 3:
            break
        candidates = [p["name"] for p in PackageDB.search(query, limit=300)]
        if candidates:
            break
    return difflib.get_close_matches(lowered, candidates, n=3, cutoff=0.6)


def validate_packages(packages: list[str]) -> dict:
    """Check each package against the real index. Returns detailed results."""
    unique = list(dict.fromkeys(p.strip() for p in packages if p.strip()))
    name_pattern = re.compile(r"^[a-z0-9][a-z0-9+.\-]+$")
    found = PackageDB.get_many(unique)

    results = []
    all_valid = True
    for name in unique:
        if not name_pattern.match(name):
            results.append({"name": name, "exists": False, "error": "invalid package name",
                            "suggestions": suggest_alternatives(name)})
            all_valid = False
        elif name in found:
            pkg = found[name]
            results.append({
                "name": name, "exists": True,
                "version": pkg["version"],
                "installed_size_kb": pkg["installed_size_kb"],
                "description": pkg["description"],
            })
        else:
            results.append({"name": name, "exists": False,
                            "suggestions": suggest_alternatives(name)})
            all_valid = False

    return {
        "all_valid": all_valid,
        "index_packages": PackageDB.count(),
        "results": results,
        "size_estimate_mb": estimate_iso_size_mb(unique),
    }


def estimate_iso_size_mb(packages: list[str]) -> int:
    """Estimate final ISO size from real installed sizes."""
    names = list(dict.fromkeys([*ESSENTIAL_PACKAGES, *DESKTOP_PACKAGES, *packages]))
    found = PackageDB.get_many(names)
    installed_kb = sum(p["installed_size_kb"] or 0 for p in found.values())
    # Unknown packages get a modest default so the estimate doesn't collapse.
    unknown = len(names) - len(found)
    installed_kb += unknown * 5000
    compressed_mb = (installed_kb / 1024) * DEPENDENCY_FACTOR * SQUASHFS_RATIO
    return int(BASE_SYSTEM_MB + compressed_mb)


def apt_available() -> bool:
    return shutil.which("apt-get") is not None and Path("/etc/debian_version").exists()


async def apt_dry_run(packages: list[str]) -> dict:
    """Simulate the apt install inside the container to catch dependency
    conflicts before a real build. Only available in a Debian environment."""
    if not apt_available():
        return {"available": False,
                "message": "apt dry-run requires the Debian build container"}
    names = list(dict.fromkeys([*ESSENTIAL_PACKAGES, *packages]))
    proc = await asyncio.create_subprocess_exec(
        "apt-get", "--simulate", "--quiet", "install", "--no-install-recommends", *names,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
    except asyncio.TimeoutError:
        proc.kill()
        return {"available": True, "ok": False, "errors": ["apt simulation timed out"]}

    out = stdout.decode(errors="replace")
    err = stderr.decode(errors="replace")
    errors = [ln for ln in (out + "\n" + err).splitlines()
              if ln.startswith("E:") or "is not going to be installed" in ln
              or "Unable to locate" in ln]
    install_count = len(re.findall(r"^Inst ", out, flags=re.MULTILINE))
    return {
        "available": True,
        "ok": proc.returncode == 0 and not errors,
        "packages_to_install": install_count,
        "errors": errors[:20],
    }
