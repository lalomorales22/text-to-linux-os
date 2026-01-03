"""
Builder API endpoints for ISO generation
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict, Any, Optional
import asyncio
import logging
import os
import uuid

from backend.database.db import ProjectDB, VersionDB
from backend.database.models import BuildRequest, BuildStatus as BuildStatusModel
from backend.builder.config_generator import generate_live_build_config, create_build_directory, copy_templates_to_config
from backend.builder.live_build import build_iso_async
from backend.builder.theme_generator import apply_theme_to_config
from backend.builder.error_handler import BuildErrorAnalyzer
from backend.utils.validators import validate_iso_config, sanitize_project_name

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/build", tags=["builder"])

# Active builds tracking
active_builds = {}


class BuildTracker:
    """Track build progress and status"""

    def __init__(self, build_id: str, project_id: int, version_id: int):
        self.build_id = build_id
        self.project_id = project_id
        self.version_id = version_id
        self.status = "queued"
        self.progress = 0
        self.current_step = "Initializing"
        self.logs = []
        self.error = None
        self.iso_path = None

    def update(self, progress: int, step: str):
        """Update build progress"""
        self.progress = progress
        self.current_step = step
        self.logs.append(f"[{progress}%] {step}")
        logger.info(f"Build {self.build_id}: {step}")


@router.post("/start")
async def start_build(build_req: BuildRequest, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """
    Start building an ISO
    """
    try:
        # Get project and version
        project = ProjectDB.get(build_req.project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Get version config
        if build_req.version_id:
            version = VersionDB.get(build_req.version_id)
        else:
            versions = VersionDB.get_by_project(build_req.project_id)
            version = versions[0] if versions else None

        if not version:
            raise HTTPException(status_code=404, detail="No version found for project")

        # Validate config
        is_valid, errors = validate_iso_config(version['config'])
        if not is_valid:
            raise HTTPException(status_code=400, detail=f"Invalid configuration: {', '.join(errors)}")

        # Generate build ID
        build_id = str(uuid.uuid4())

        # Create build tracker
        tracker = BuildTracker(build_id, build_req.project_id, version['id'])
        active_builds[build_id] = tracker

        # Update project status
        ProjectDB.update(build_req.project_id, status="building")

        # Start build in background
        background_tasks.add_task(run_build, build_id, project, version)

        return {
            "build_id": build_id,
            "status": "queued",
            "message": "Build started successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting build: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def run_build(build_id: str, project: Dict[str, Any], version: Dict[str, Any]):
    """
    Run the actual build process
    """
    tracker = active_builds[build_id]

    try:
        tracker.status = "running"
        tracker.update(0, "Preparing build environment")

        # Create build directory
        project_name = sanitize_project_name(project['name'])
        build_dir = create_build_directory(project_name, version['version_number'])

        tracker.update(5, "Generating configuration")

        # Generate live-build config
        config_dir = generate_live_build_config(version['config'], build_dir)

        # Apply theme if present
        if version.get('theme_config'):
            tracker.update(8, "Applying theme")
            apply_theme_to_config(version['theme_config'], config_dir)

        # Copy templates
        tracker.update(10, "Copying templates")
        copy_templates_to_config(config_dir)

        tracker.update(15, "Starting ISO build")

        # Build ISO with progress callback
        def progress_callback(progress: int, step: str):
            tracker.update(progress, step)

        result = await build_iso_async(build_dir, progress_callback)

        if result['status'] == 'success':
            tracker.status = "completed"
            tracker.iso_path = result['iso_path']
            tracker.update(100, "Build completed successfully")

            # Update version in database
            VersionDB.update(
                version['id'],
                iso_path=result['iso_path'],
                iso_size=result.get('size_bytes', 0),
                build_logs=result.get('logs', '')
            )

            # Update project status
            ProjectDB.update(project['id'], status="completed")

        else:
            # Build failed - try to analyze error
            tracker.status = "failed"
            tracker.error = result.get('error', 'Unknown error')
            tracker.update(0, "Build failed, analyzing errors")

            # Analyze error with AI
            try:
                analyzer = BuildErrorAnalyzer()
                analysis = analyzer.analyze_build_error(result.get('logs', ''), version['config'])

                tracker.error = f"{analysis['description']}\n\nSuggested fix: {analysis['suggested_fix']}"

            except Exception as e:
                logger.error(f"Error analyzing build failure: {e}")

            # Update version in database
            VersionDB.update(
                version['id'],
                build_logs=result.get('logs', '')
            )

            # Update project status
            ProjectDB.update(project['id'], status="failed")

    except Exception as e:
        logger.error(f"Build {build_id} failed: {e}", exc_info=True)
        tracker.status = "failed"
        tracker.error = str(e)
        ProjectDB.update(project['id'], status="failed")


@router.get("/status/{build_id}")
async def get_build_status(build_id: str) -> BuildStatusModel:
    """
    Get status of a build
    """
    if build_id not in active_builds:
        raise HTTPException(status_code=404, detail="Build not found")

    tracker = active_builds[build_id]

    return BuildStatusModel(
        build_id=build_id,
        status=tracker.status,
        progress=tracker.progress,
        current_step=tracker.current_step,
        logs="\n".join(tracker.logs[-50:]),  # Last 50 log lines
        iso_path=tracker.iso_path,
        error=tracker.error
    )


@router.get("/logs/{build_id}")
async def get_build_logs(build_id: str) -> Dict[str, Any]:
    """
    Get complete build logs
    """
    if build_id not in active_builds:
        raise HTTPException(status_code=404, detail="Build not found")

    tracker = active_builds[build_id]

    return {
        "build_id": build_id,
        "logs": "\n".join(tracker.logs)
    }


@router.post("/cancel/{build_id}")
async def cancel_build(build_id: str) -> Dict[str, Any]:
    """
    Cancel a running build
    """
    if build_id not in active_builds:
        raise HTTPException(status_code=404, detail="Build not found")

    tracker = active_builds[build_id]

    if tracker.status == "running":
        # TODO: Implement actual cancellation of build process
        tracker.status = "cancelled"
        tracker.update(tracker.progress, "Build cancelled by user")

        return {"message": "Build cancelled"}
    else:
        return {"message": f"Cannot cancel build in status: {tracker.status}"}
