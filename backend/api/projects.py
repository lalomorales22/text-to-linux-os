"""Project API — gallery, rename, delete, download, themes."""
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.database.db import BuildDB, ProjectDB, VersionDB
from backend.database.models import RenameRequest, ThemeApplyRequest
from backend.services import themes

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("")
async def list_projects() -> dict:
    projects = ProjectDB.list_all()
    for project in projects:
        latest = VersionDB.latest_for_project(project["id"])
        project["latest_version"] = latest
        project["has_iso"] = bool(latest and latest.get("iso_path")
                                  and Path(latest["iso_path"]).exists())
        active = BuildDB.active_for_project(project["id"])
        project["active_build_id"] = active["id"] if active else None
    return {"projects": projects}


@router.get("/{project_id}")
async def get_project(project_id: int) -> dict:
    project = ProjectDB.get(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    versions = VersionDB.list_for_project(project_id)
    for v in versions:
        v["has_iso"] = bool(v.get("iso_path") and Path(v["iso_path"]).exists())
    build = BuildDB.active_for_project(project_id) or BuildDB.latest_for_project(project_id)
    return {**project, "versions": versions, "build": build}


@router.patch("/{project_id}")
async def rename_project(project_id: int, req: RenameRequest) -> dict:
    if not ProjectDB.get(project_id):
        raise HTTPException(404, "Project not found")
    ProjectDB.update(project_id, name=req.name.strip())
    return {"ok": True}


@router.delete("/{project_id}")
async def delete_project(project_id: int) -> dict:
    if not ProjectDB.get(project_id):
        raise HTTPException(404, "Project not found")
    ProjectDB.delete(project_id)
    return {"ok": True}


@router.get("/{project_id}/download")
async def download_iso(project_id: int, version_id: int | None = None) -> FileResponse:
    version = VersionDB.get(version_id) if version_id else VersionDB.latest_for_project(project_id)
    if not version or version["project_id"] != project_id:
        raise HTTPException(404, "Version not found")
    if not version.get("iso_path") or not Path(version["iso_path"]).exists():
        raise HTTPException(404, "No ISO built for this version")
    path = Path(version["iso_path"])
    headers = {"X-ISO-SHA256": version.get("iso_sha256") or ""}
    return FileResponse(path, media_type="application/x-iso9660-image",
                        filename=path.name, headers=headers)


@router.get("/{project_id}/iso-info")
async def iso_info(project_id: int) -> dict:
    """Metadata the flash helper needs: download URL path, size, checksum."""
    version = VersionDB.latest_for_project(project_id)
    if not version or not version.get("iso_path") or not Path(version["iso_path"]).exists():
        raise HTTPException(404, "No ISO built for this project")
    path = Path(version["iso_path"])
    return {
        "filename": path.name,
        "size_bytes": path.stat().st_size,
        "sha256": version.get("iso_sha256"),
        "download_path": f"/api/projects/{project_id}/download?version_id={version['id']}",
    }


@router.post("/theme/randomize")
async def randomize_theme() -> dict:
    return {"theme": themes.generate_random_theme()}


@router.put("/{project_id}/theme")
async def apply_theme(project_id: int, req: ThemeApplyRequest) -> dict:
    if not ProjectDB.get(project_id):
        raise HTTPException(404, "Project not found")
    theme = themes.normalize_theme(req.theme.model_dump())
    ProjectDB.update(project_id, theme_config=theme)
    return {"ok": True, "theme": theme}
