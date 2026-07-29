"""Application settings, loaded from environment / .env once at import time."""
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings:
    def __init__(self) -> None:
        self.anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
        self.chat_model: str = os.getenv("CHAT_MODEL", "claude-opus-5")

        self.data_dir: Path = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
        self.builds_dir: Path = Path(os.getenv("BUILDS_DIR", BASE_DIR / "builds"))
        self.cache_dir: Path = Path(os.getenv("CACHE_DIR", BASE_DIR / "cache"))
        self.templates_dir: Path = Path(os.getenv("TEMPLATES_DIR", BASE_DIR / "templates"))
        self.frontend_dir: Path = Path(os.getenv("FRONTEND_DIR", BASE_DIR / "frontend"))

        db_url = os.getenv("DATABASE_URL", "")
        if db_url.startswith("sqlite:///"):
            self.database_path: Path = Path(db_url.replace("sqlite:///", ""))
        else:
            self.database_path = self.data_dir / "text-to-linux-os.db"

        self.max_iso_size_gb: int = int(os.getenv("MAX_ISO_SIZE_GB", "3"))
        self.build_timeout_minutes: int = int(os.getenv("BUILD_TIMEOUT_MINUTES", "120"))

        self.debian_mirror: str = os.getenv("DEBIAN_MIRROR", "https://deb.debian.org/debian")
        self.debian_suite: str = os.getenv("DEBIAN_SUITE", "bookworm")
        self.debian_areas: list[str] = os.getenv(
            "DEBIAN_AREAS", "main,contrib,non-free,non-free-firmware"
        ).split(",")
        # Refresh the package index when older than this many hours
        self.package_index_max_age_hours: int = int(os.getenv("PACKAGE_INDEX_MAX_AGE_HOURS", "24"))

        self.boot_test_timeout_seconds: int = int(os.getenv("BOOT_TEST_TIMEOUT_SECONDS", "420"))
        self.boot_test_memory_mb: int = int(os.getenv("BOOT_TEST_MEMORY_MB", "2048"))

        self.log_level: str = os.getenv("LOG_LEVEL", "INFO")

    def ensure_directories(self) -> None:
        for d in (self.data_dir, self.builds_dir, self.cache_dir / "packages"):
            d.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
