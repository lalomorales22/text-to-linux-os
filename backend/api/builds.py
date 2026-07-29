"""Build API — start, monitor (SSE log tail), cancel, boot-test artifacts."""
import asyncio
import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from backend.database.db import BuildDB, ProjectDB, VersionDB
from backend.database.models import BuildRequest
from backend.services import debian_packages
from backend.services.orchestrator import build_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/builds", tags=["builds"])


@router.post("")
async def start_build(req: BuildRequest) -> dict:
    project = ProjectDB.get(req.project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    if BuildDB.active_for_project(req.project_id):
        raise HTTPException(409, "A build is already running for this project")

    if req.version_id:
        version = VersionDB.get(req.version_id)
        if not version or version["project_id"] != req.project_id:
            raise HTTPException(404, "Version not found")
    elif project.get("draft_config"):
        # Snapshot the current draft as a new version
        config = dict(project["draft_config"])
        config.pop("ready", None)
        version_id = VersionDB.create(req.project_id, config, project.get("theme_config"))
        version = VersionDB.get(version_id)
    else:
        version = VersionDB.latest_for_project(req.project_id)
        if not version:
            raise HTTPException(400, "Project has no configuration to build yet")

    validation = debian_packages.validate_packages(version["config"].get("packages", []))
    if not validation["all_valid"]:
        invalid = [r["name"] for r in validation["results"] if not r["exists"]]
        raise HTTPException(400, f"Configuration contains unknown packages: {', '.join(invalid)}")

    build_id = build_manager.start_build(project, version, run_boot_test=req.run_boot_test)
    return {"build_id": build_id, "version_id": version["id"], "status": "queued"}


@router.get("/{build_id}")
async def get_build(build_id: str) -> dict:
    build = BuildDB.get(build_id)
    if not build:
        raise HTTPException(404, "Build not found")
    return build


@router.get("/project/{project_id}/current")
async def current_build(project_id: int) -> dict:
    build = BuildDB.active_for_project(project_id) or BuildDB.latest_for_project(project_id)
    if not build:
        raise HTTPException(404, "No builds for this project")
    return build


@router.get("/{build_id}/logs")
async def get_logs(build_id: str) -> dict:
    build = BuildDB.get(build_id)
    if not build:
        raise HTTPException(404, "Build not found")
    log_path = Path(build["log_path"]) if build.get("log_path") else None
    logs = log_path.read_text(errors="replace") if log_path and log_path.exists() else ""
    return {"build_id": build_id, "logs": logs}


@router.get("/{build_id}/logs/stream")
async def stream_logs(build_id: str) -> StreamingResponse:
    build = BuildDB.get(build_id)
    if not build:
        raise HTTPException(404, "Build not found")

    async def tail():
        log_path = Path(build["log_path"])
        position = 0
        idle_after_done = 0
        while True:
            current = BuildDB.get(build_id)
            if log_path.exists():
                with log_path.open("r", errors="replace") as f:
                    f.seek(position)
                    chunk = f.read()
                    position = f.tell()
                if chunk:
                    for line in chunk.splitlines():
                        yield f"data: {json.dumps({'type': 'log', 'line': line})}\n\n"
            status_event = {
                "type": "status",
                "status": current["status"],
                "progress": current["progress"],
                "step": current["step"],
            }
            yield f"data: {json.dumps(status_event)}\n\n"
            if current["status"] not in ("queued", "running", "testing"):
                idle_after_done += 1
                if idle_after_done >= 2:  # one extra pass to flush trailing log lines
                    yield f"data: {json.dumps({'type': 'done', 'status': current['status'], 'error': current.get('error'), 'boot_test': current.get('boot_test')})}\n\n"
                    return
            await asyncio.sleep(1.5)

    return StreamingResponse(tail(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


@router.post("/{build_id}/cancel")
async def cancel_build(build_id: str) -> dict:
    build = BuildDB.get(build_id)
    if not build:
        raise HTTPException(404, "Build not found")
    if build["status"] not in ("queued", "running", "testing"):
        return {"cancelled": False, "message": f"Build is already {build['status']}"}
    if not build_manager.cancel_build(build_id):
        # Job not in this process (e.g. pre-restart record) — mark it directly
        BuildDB.update(build_id, status="cancelled", step="Cancelled")
    return {"cancelled": True}


@router.get("/{build_id}/screenshot/{mode}")
async def boot_screenshot(build_id: str, mode: str) -> FileResponse:
    build = BuildDB.get(build_id)
    if not build or mode not in ("bios", "uefi"):
        raise HTTPException(404, "Not found")
    boot_test = build.get("boot_test") or {}
    shot = (boot_test.get("modes", {}).get(mode) or {}).get("screenshot")
    if not shot:
        raise HTTPException(404, "No screenshot for this mode")
    path = Path(build["log_path"]).parent / shot
    if not path.exists():
        raise HTTPException(404, "Screenshot file missing")
    media = "image/png" if path.suffix == ".png" else "image/x-portable-pixmap"
    return FileResponse(path, media_type=media)
