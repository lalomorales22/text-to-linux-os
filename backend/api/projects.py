"""
Projects API endpoints
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from typing import Dict, Any, List
import logging
import os

from backend.database.db import ProjectDB, VersionDB, ConversationDB
from backend.database.models import Project
from backend.builder.theme_generator import generate_random_theme

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("/create")
async def create_project(project: Project) -> Dict[str, Any]:
    """
    Create a new project
    """
    try:
        project_id = ProjectDB.create(name=project.name, status="draft")
        return {
            "project_id": project_id,
            "name": project.name,
            "status": "draft"
        }
    except Exception as e:
        logger.error(f"Error creating project: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_projects() -> List[Dict[str, Any]]:
    """
    List all projects
    """
    try:
        projects = ProjectDB.list_all()

        # Enrich with version info
        for project in projects:
            versions = VersionDB.get_by_project(project['id'])
            project['version_count'] = len(versions)

            # Get latest version info
            if versions:
                latest = versions[0]
                project['latest_version'] = {
                    'version_number': latest['version_number'],
                    'iso_path': latest.get('iso_path'),
                    'iso_size': latest.get('iso_size'),
                    'theme_preview': latest.get('theme_config', {}).get('base_colors') if latest.get('theme_config') else None
                }

        return projects

    except Exception as e:
        logger.error(f"Error listing projects: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_id}")
async def get_project(project_id: int) -> Dict[str, Any]:
    """
    Get project details with all versions
    """
    try:
        project = ProjectDB.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Get all versions
        versions = VersionDB.get_by_project(project_id)
        project['versions'] = versions

        # Get conversation history
        conversations = ConversationDB.get_history(project_id)
        project['conversations'] = conversations

        return project

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting project: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{project_id}/update")
async def update_project(project_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update project details
    """
    try:
        project = ProjectDB.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Update allowed fields
        allowed_fields = ['name', 'status']
        update_data = {k: v for k, v in updates.items() if k in allowed_fields}

        ProjectDB.update(project_id, **update_data)

        return {"message": "Project updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating project: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{project_id}")
async def delete_project(project_id: int) -> Dict[str, Any]:
    """
    Delete a project and all related data
    """
    try:
        project = ProjectDB.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Delete project (cascades to versions and conversations)
        ProjectDB.delete(project_id)

        # TODO: Delete ISO files from disk

        return {"message": "Project deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting project: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/theme/randomize")
async def randomize_theme() -> Dict[str, Any]:
    """
    Generate a random theme
    """
    try:
        theme = generate_random_theme()
        return theme
    except Exception as e:
        logger.error(f"Error generating theme: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/theme/apply")
async def apply_theme(project_id: int, theme: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply theme to project's current version
    """
    try:
        project = ProjectDB.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Get current version
        versions = VersionDB.get_by_project(project_id)
        if not versions:
            raise HTTPException(status_code=404, detail="No version found for project")

        current_version = versions[0]

        # Update theme config
        VersionDB.update(current_version['id'], theme_config=theme)

        return {"message": "Theme applied successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error applying theme: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download/{project_id}/v{version_number}")
async def download_iso(project_id: int, version_number: int):
    """
    Download ISO file for a specific version
    """
    try:
        # Get version
        versions = VersionDB.get_by_project(project_id)
        version = next((v for v in versions if v['version_number'] == version_number), None)

        if not version:
            raise HTTPException(status_code=404, detail="Version not found")

        if not version.get('iso_path') or not os.path.exists(version['iso_path']):
            raise HTTPException(status_code=404, detail="ISO file not found")

        return FileResponse(
            version['iso_path'],
            media_type='application/octet-stream',
            filename=os.path.basename(version['iso_path'])
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading ISO: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
