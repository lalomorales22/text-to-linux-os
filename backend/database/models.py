"""
Database models for Text-to-Linux-OS Builder
"""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class Project(BaseModel):
    """Project model"""
    id: Optional[int] = None
    name: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    current_version: int = 1
    status: str = "draft"  # draft, building, completed, failed


class Version(BaseModel):
    """Version model for project versions"""
    id: Optional[int] = None
    project_id: int
    version_number: int
    config: Dict[str, Any]
    theme_config: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.now)
    iso_path: Optional[str] = None
    iso_size: Optional[int] = None
    build_logs: Optional[str] = None


class Conversation(BaseModel):
    """Conversation model for chatbot messages"""
    id: Optional[int] = None
    project_id: int
    version_id: Optional[int] = None
    role: str  # user, assistant, system
    message: str
    timestamp: datetime = Field(default_factory=datetime.now)


class PackageCache(BaseModel):
    """Package cache model"""
    id: Optional[int] = None
    package_name: str
    version: Optional[str] = None
    download_url: Optional[str] = None
    file_hash: Optional[str] = None
    cached_path: Optional[str] = None
    last_used: datetime = Field(default_factory=datetime.now)


class ChatMessage(BaseModel):
    """Chat message request/response model"""
    project_id: Optional[int] = None
    message: str
    role: str = "user"


class BuildRequest(BaseModel):
    """Build request model"""
    project_id: int
    version_id: Optional[int] = None


class BuildStatus(BaseModel):
    """Build status response model"""
    build_id: str
    status: str  # queued, running, completed, failed
    progress: int  # 0-100
    current_step: str
    logs: Optional[str] = None
    iso_path: Optional[str] = None
    error: Optional[str] = None


class ThemeConfig(BaseModel):
    """Theme configuration model"""
    openbox: Dict[str, Any]
    terminal: Dict[str, Any]
    panel: Dict[str, Any]
    grub: Dict[str, Any]
    wallpaper: Optional[Dict[str, Any]] = None


class ISOConfig(BaseModel):
    """Complete ISO configuration"""
    hardware: Dict[str, Any]
    use_case: str
    packages: list[str]
    custom_tools: Optional[list[str]] = None
    size_estimate_mb: int
    theme: Optional[ThemeConfig] = None
