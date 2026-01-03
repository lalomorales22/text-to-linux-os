"""
Chatbot API endpoints for AI-powered Linux ISO configuration
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
import anthropic
import os
import json
import logging

from backend.database.db import ProjectDB, ConversationDB, VersionDB
from backend.database.models import ChatMessage
from backend.utils.validators import estimate_iso_size, validate_package_name

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chatbot"])

# Initialize Anthropic client
anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


SYSTEM_PROMPT = """You are an expert Linux system architect helping users create custom Debian-based Linux ISOs.

Your role is to guide users through creating their ideal minimal Linux distribution by:
1. Understanding their hardware specifications (RAM, CPU, storage)
2. Determining their primary use case (coding, browsing, media, etc.)
3. Helping them select appropriate packages
4. Warning about conflicts and dependencies
5. Keeping track of estimated ISO size (target: under 3GB)

Guidelines:
- Be conversational and helpful
- Suggest packages based on use case, but always ask before adding
- Warn about package conflicts (e.g., vim vs nano)
- Keep running total of ISO size
- Suggest minimal alternatives if size is getting too large
- Only recommend packages from official Debian repositories
- Use open-source alternatives (Firefox ESR not Chrome, code-oss not VSCode)

Essential packages (always included):
- linux-image-amd64, live-boot, systemd, network-manager

Desktop packages (recommend for GUI):
- xorg, openbox, tint2, pcmanfm, lxterminal

When you have all the information needed, output a JSON configuration in this format:
```json
{
  "ready_to_build": true,
  "config": {
    "hardware": {
      "ram_gb": 4,
      "cpu_age": "modern",
      "storage_type": "ssd",
      "architecture": "amd64"
    },
    "use_case": "development",
    "packages": ["list", "of", "packages"],
    "custom_tools": ["claude-code", "gemini-cli"],
    "size_estimate_mb": 2048
  }
}
```

Keep conversations focused and efficient. Aim to complete configuration in 5-10 messages.
"""


@router.post("/message")
async def send_message(chat_msg: ChatMessage) -> Dict[str, Any]:
    """
    Send a message to the chatbot and get response
    """
    try:
        # Get or create project
        if not chat_msg.project_id:
            # Create new project
            project_id = ProjectDB.create(name="New Project", status="configuring")
        else:
            project_id = chat_msg.project_id

        # Save user message
        ConversationDB.add_message(project_id, "user", chat_msg.message)

        # Get conversation history
        history = ConversationDB.get_history(project_id)

        # Build messages for Claude
        messages = []
        for msg in history:
            messages.append({
                "role": "assistant" if msg['role'] == "assistant" else "user",
                "content": msg['message']
            })

        # Get response from Claude
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=messages
        )

        assistant_message = response.content[0].text

        # Save assistant response
        ConversationDB.add_message(project_id, "assistant", assistant_message)

        # Check if configuration is ready
        config = None
        ready_to_build = False

        if "ready_to_build" in assistant_message:
            try:
                # Extract JSON from response
                json_match = assistant_message[assistant_message.find("{"):assistant_message.rfind("}")+1]
                parsed = json.loads(json_match)
                if parsed.get("ready_to_build"):
                    config = parsed.get("config")
                    ready_to_build = True

                    # Create version with config
                    version_id = VersionDB.create(
                        project_id=project_id,
                        version_number=1,
                        config=config
                    )

                    # Update project status
                    ProjectDB.update(project_id, status="configured")

            except json.JSONDecodeError:
                logger.warning("Failed to parse config JSON from assistant response")

        return {
            "project_id": project_id,
            "message": assistant_message,
            "ready_to_build": ready_to_build,
            "config": config
        }

    except Exception as e:
        logger.error(f"Error in chat: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{project_id}")
async def get_chat_history(project_id: int) -> Dict[str, Any]:
    """
    Get conversation history for a project
    """
    try:
        history = ConversationDB.get_history(project_id)
        return {
            "project_id": project_id,
            "messages": history
        }
    except Exception as e:
        logger.error(f"Error getting history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/estimate-size")
async def estimate_size(packages: List[str]) -> Dict[str, Any]:
    """
    Estimate ISO size for given packages
    """
    size_mb = estimate_iso_size(packages)
    return {
        "size_mb": size_mb,
        "size_gb": round(size_mb / 1024, 2),
        "warning": size_mb > 2500,
        "too_large": size_mb > 3072
    }
