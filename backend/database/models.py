"""Pydantic request/response models shared by the API layer."""
from typing import Any, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    project_id: Optional[int] = None


class Hardware(BaseModel):
    ram_gb: int = 4
    cpu: str = "modern"          # modern | older | very-old
    storage: str = "ssd"         # ssd | hdd
    boot: str = "both"           # uefi | bios | both
    architecture: str = "amd64"


class IsoConfig(BaseModel):
    hostname: str = "custom-linux"
    username: str = "user"
    use_case: str = "general"
    hardware: Hardware = Hardware()
    packages: list[str] = []
    notes: Optional[str] = None


class ThemeConfig(BaseModel):
    primary: str = "#6ee7b7"
    secondary: str = "#3b82f6"
    accent: str = "#f59e0b"
    background: str = "#0d1117"
    foreground: str = "#e6edf3"
    terminal: dict[str, Any] = {}


class BuildRequest(BaseModel):
    project_id: int
    version_id: Optional[int] = None
    run_boot_test: bool = True


class PackagesRequest(BaseModel):
    packages: list[str] = Field(max_length=500)


class RenameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ThemeApplyRequest(BaseModel):
    theme: ThemeConfig
