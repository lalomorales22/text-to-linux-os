"""Settings API — runtime configuration, starting with the Anthropic API key.

A key saved here is verified against Anthropic's API first, then stored in the
app database (so it survives restarts) and takes effect immediately. A key in
.env / the environment still works as a fallback.
"""
import os
import shlex

import anthropic
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.config import get_settings
from backend.database.db import MetaDB
from backend.services import ai

router = APIRouter(prefix="/api/settings", tags=["settings"])

API_KEY_META = "anthropic_api_key"


class ApiKeyRequest(BaseModel):
    api_key: str


@router.get("")
async def get_app_settings() -> dict:
    stored = MetaDB.get(API_KEY_META)
    env_key = get_settings().anthropic_api_key
    key = stored or env_key
    repo = os.getenv("HOST_REPO_DIR", "").strip()
    if repo:
        quoted = shlex.quote(repo)
        helper_command = f"cd {quoted} && sudo python3 helper/flash_helper.py"
        launcher_path = f"{repo}/start-flash-helper.command"
    else:
        helper_command = "sudo python3 helper/flash_helper.py"
        launcher_path = None
    return {
        "api_key_set": bool(key),
        "api_key_source": "app" if stored else ("env" if env_key else "none"),
        "api_key_hint": f"…{key[-4:]}" if key else None,
        "chat_model": get_settings().chat_model,
        "flash_helper_command": helper_command,
        "flash_launcher_path": launcher_path,
    }


@router.post("/api-key")
async def set_api_key(req: ApiKeyRequest) -> dict:
    key = req.api_key.strip()
    if not key.startswith("sk-ant-"):
        raise HTTPException(400, "That doesn't look like an Anthropic API key "
                                 "(they start with sk-ant-).")
    # Prove the key works before saving it — models.list is free.
    try:
        await anthropic.AsyncAnthropic(api_key=key).models.list(limit=1)
    except anthropic.AuthenticationError:
        raise HTTPException(400, "Anthropic rejected this key — double-check it "
                                 "and try again.")
    except anthropic.APIError as exc:
        raise HTTPException(502, "Couldn't verify the key with Anthropic right now "
                                 f"({exc.__class__.__name__}) — try again in a moment.")
    MetaDB.set(API_KEY_META, key)
    ai.reset_client()
    return {"ok": True, "api_key_hint": f"…{key[-4:]}"}
