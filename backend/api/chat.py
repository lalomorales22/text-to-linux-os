"""Chat API — Server-Sent Events streaming from the AI wizard."""
import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.database.db import ConversationDB, ProjectDB
from backend.database.models import ChatRequest
from backend.services import ai

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


@router.post("/message")
async def send_message(req: ChatRequest) -> StreamingResponse:
    if req.project_id:
        project = ProjectDB.get(req.project_id)
        if not project:
            raise HTTPException(404, "Project not found")
        project_id = req.project_id
    else:
        project_id = ProjectDB.create(name="New Project", status="configuring")
        project = ProjectDB.get(project_id)

    ConversationDB.add_message(project_id, "user", req.message)
    history = ConversationDB.get_history(project_id)

    async def event_stream():
        yield _sse({"type": "project", "project_id": project_id})
        assistant_text = ""
        try:
            async for event in ai.stream_chat(project_id, history, project.get("draft_config")):
                if event["type"] == "done":
                    assistant_text = event.pop("full_text", "")
                yield _sse(event)
        except Exception as exc:
            logger.error("Chat stream failed: %s", exc, exc_info=True)
            yield _sse({"type": "error", "message": f"Chat failed: {exc}"})
        finally:
            if assistant_text.strip():
                ConversationDB.add_message(project_id, "assistant", assistant_text)

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


@router.get("/history/{project_id}")
async def get_history(project_id: int) -> dict:
    project = ProjectDB.get(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return {
        "project_id": project_id,
        "messages": ConversationDB.get_history(project_id),
        "draft_config": project.get("draft_config"),
        "theme_config": project.get("theme_config"),
    }
