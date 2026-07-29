"""AI layer: streaming configuration wizard + build failure analysis.

The wizard streams text to the frontend over SSE and maintains the ISO
configuration through a strict `update_config` tool call instead of scraping
JSON out of chat text. Every config update is validated against the real
Debian package index before it is accepted; invalid packages bounce back to
the model as a tool error so it corrects itself in the same turn.

Uses claude-opus-5 with server-side refusal fallbacks enabled.
"""
import json
import logging
from typing import Any, AsyncIterator, Optional

import anthropic

from backend.config import get_settings
from backend.database.db import ProjectDB
from backend.services import debian_packages

logger = logging.getLogger(__name__)

_client: Optional[anthropic.AsyncAnthropic] = None


def get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=get_settings().anthropic_api_key or None)
    return _client


SYSTEM_PROMPT = """You are the configuration wizard for Text-to-Linux-OS, a tool that builds \
custom bootable Debian-based live ISOs. You help the user design a minimal Linux system for \
their hardware and use case, then hand off a validated configuration for building.

How to work:
- Be conversational, warm, and efficient. Aim to reach a buildable configuration in a handful \
of exchanges. Ask only what you can't infer; propose sensible defaults and move forward.
- Learn their hardware (RAM, CPU age, storage, BIOS vs UEFI) and primary use case, then \
propose a package set. Only packages from the official Debian stable repositories exist — \
use validate_packages to check anything you're unsure about (e.g. use chromium not chrome, \
docker.io not docker, codium not vscode).
- Every ISO automatically includes the base system (kernel, live-boot, systemd, \
NetworkManager, sudo) and a lightweight desktop (Xorg, Openbox, tint2 panel, PCManFM, \
LXTerminal, LightDM). Don't add those yourself — only add packages on top.
- Call update_config every time the configuration meaningfully changes so the user sees the \
live summary panel update. The tool validates packages and returns the real size estimate; \
if it reports invalid packages, fix them immediately and call it again.
- Target ISO size is under {max_size_gb}GB. If the estimate gets close, suggest lighter \
alternatives.
- Set ready=true only when the user has confirmed they're happy with the configuration. \
When you set ready=true, tell them to press "Build ISO".
- Old hardware guidance: for machines with <2GB RAM avoid heavy browsers (suggest \
falkon or dillo); prefer bios boot mode for pre-2010 machines.
"""

UPDATE_CONFIG_TOOL = {
    "name": "update_config",
    "description": (
        "Save the current ISO configuration. Call this whenever the configuration changes "
        "so the user's summary panel stays current. Packages are validated against the real "
        "Debian index — if validation fails, correct the package names and call again. "
        "Set ready=true only after the user confirms they want to build."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "hostname": {"type": "string", "description": "System hostname (lowercase, no spaces)"},
            "username": {"type": "string", "description": "Default login user"},
            "use_case": {"type": "string", "description": "Short label, e.g. 'python development'"},
            "hardware": {
                "type": "object",
                "properties": {
                    "ram_gb": {"type": "integer"},
                    "cpu": {"type": "string", "enum": ["modern", "older", "very-old"]},
                    "storage": {"type": "string", "enum": ["ssd", "hdd"]},
                    "boot": {"type": "string", "enum": ["uefi", "bios", "both"]},
                },
                "required": ["ram_gb", "cpu", "storage", "boot"],
                "additionalProperties": False,
            },
            "packages": {
                "type": "array", "items": {"type": "string"},
                "description": "Extra Debian packages beyond the automatic base system",
            },
            "ready": {"type": "boolean", "description": "True once the user confirms the build"},
        },
        "required": ["hostname", "username", "use_case", "hardware", "packages", "ready"],
        "additionalProperties": False,
    },
}

VALIDATE_PACKAGES_TOOL = {
    "name": "validate_packages",
    "description": (
        "Check whether package names exist in the Debian stable repositories. Returns real "
        "installed sizes and suggested alternatives for anything that doesn't exist. Use this "
        "before recommending packages you are not certain about."
    ),
    "input_schema": {
        "type": "object",
        "properties": {"packages": {"type": "array", "items": {"type": "string"}}},
        "required": ["packages"],
        "additionalProperties": False,
    },
}

FALLBACK_OPTS = {
    "extra_headers": {"anthropic-beta": "server-side-fallback-2026-07-01"},
    "extra_body": {"fallbacks": "default"},
}


def _build_api_messages(history: list[dict], draft_config: Optional[dict]) -> list[dict]:
    """Rebuild the API conversation from stored display history. Tool exchanges
    are not persisted; instead the current config state is injected as context
    ahead of the latest user message."""
    messages: list[dict] = []
    for msg in history:
        role = "assistant" if msg["role"] == "assistant" else "user"
        if messages and messages[-1]["role"] == role:
            messages[-1]["content"] += "\n\n" + msg["content"]
        else:
            messages.append({"role": role, "content": msg["content"]})
    if messages and draft_config:
        state = json.dumps(draft_config, indent=None)
        messages[-1]["content"] = (
            f"<current_config_state>{state}</current_config_state>\n\n"
            + messages[-1]["content"]
        )
    return messages


async def _handle_tool_call(project_id: int, name: str, tool_input: dict) -> tuple[str, Optional[dict]]:
    """Execute a tool. Returns (result_json_for_model, config_event_or_None)."""
    if name == "validate_packages":
        result = debian_packages.validate_packages(tool_input.get("packages", []))
        return json.dumps(result), None

    if name == "update_config":
        config = {k: v for k, v in tool_input.items() if k != "ready"}
        ready = bool(tool_input.get("ready"))
        validation = debian_packages.validate_packages(config.get("packages", []))
        invalid = [r for r in validation["results"] if not r["exists"]]
        if invalid:
            return json.dumps({
                "accepted": False,
                "invalid_packages": invalid,
                "message": "Fix these package names and call update_config again.",
            }), None

        config["size_estimate_mb"] = validation["size_estimate_mb"]
        config["ready"] = ready
        ProjectDB.update(project_id, draft_config=config,
                         status="configured" if ready else "configuring")
        event = {"type": "config", "config": config, "ready": ready}
        max_mb = get_settings().max_iso_size_gb * 1024
        return json.dumps({
            "accepted": True,
            "size_estimate_mb": validation["size_estimate_mb"],
            "size_warning": validation["size_estimate_mb"] > max_mb * 0.85,
        }), event

    return json.dumps({"error": f"unknown tool {name}"}), None


async def stream_chat(project_id: int, history: list[dict],
                      draft_config: Optional[dict]) -> AsyncIterator[dict]:
    """Yield SSE-ready event dicts: text deltas, config updates, completion."""
    settings = get_settings()
    client = get_client()
    system = SYSTEM_PROMPT.format(max_size_gb=settings.max_iso_size_gb)
    tools = [UPDATE_CONFIG_TOOL, VALIDATE_PACKAGES_TOOL]
    messages = _build_api_messages(history, draft_config)

    full_text_parts: list[str] = []
    ready = bool(draft_config and draft_config.get("ready"))

    for _round in range(8):  # tool-use loop bound
        async with client.messages.stream(
            model=settings.chat_model,
            max_tokens=16000,  # hard cap on thinking + text together
            system=system,
            tools=tools,
            messages=messages,
            **FALLBACK_OPTS,
        ) as stream:
            async for event in stream:
                if (event.type == "content_block_delta"
                        and event.delta.type == "text_delta"):
                    full_text_parts.append(event.delta.text)
                    yield {"type": "text", "delta": event.delta.text}
            final = await stream.get_final_message()

        if final.stop_reason == "refusal":
            yield {"type": "error",
                   "message": "The assistant declined this request. Try rephrasing."}
            break

        tool_uses = [b for b in final.content if b.type == "tool_use"]
        if not tool_uses:
            break

        messages.append({"role": "assistant", "content": final.content})
        tool_results = []
        for tu in tool_uses:
            yield {"type": "tool", "name": tu.name}
            result_json, config_event = await _handle_tool_call(project_id, tu.name, tu.input)
            if config_event:
                ready = config_event["ready"]
                yield config_event
            tool_results.append({
                "type": "tool_result", "tool_use_id": tu.id, "content": result_json,
            })
        messages.append({"role": "user", "content": tool_results})

    yield {"type": "done", "ready": ready, "full_text": "".join(full_text_parts)}


ANALYSIS_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "error_type": {"type": "string"},
            "description": {"type": "string"},
            "suggested_fix": {"type": "string"},
            "package_replacements": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"remove": {"type": "string"}, "add": {"type": "string"}},
                    "required": ["remove", "add"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["error_type", "description", "suggested_fix", "package_replacements"],
        "additionalProperties": False,
    },
}


async def analyze_build_failure(log_tail: str, config: dict) -> dict:
    """Structured AI analysis of a failed build. Never raises."""
    try:
        prompt = (
            "A Debian live-build ISO build failed. Analyze the log and explain what went "
            "wrong in plain language, with a concrete fix.\n\n"
            f"Requested packages: {', '.join(config.get('packages', []))}\n\n"
            f"Last part of the build log:\n```\n{log_tail[-12000:]}\n```"
        )
        response = await get_client().messages.create(
            model=get_settings().chat_model,
            max_tokens=8000,  # thinking shares this budget on claude-opus-5
            output_config={"format": ANALYSIS_SCHEMA},
            messages=[{"role": "user", "content": prompt}],
            **FALLBACK_OPTS,
        )
        if response.stop_reason == "refusal":
            raise RuntimeError("analysis refused")
        text = next(b.text for b in response.content if b.type == "text")
        return json.loads(text)
    except Exception as exc:  # analysis is best-effort; the raw log is still shown
        logger.warning("Build failure analysis unavailable: %s", exc)
        return {
            "error_type": "unknown",
            "description": "Automatic analysis was unavailable for this failure.",
            "suggested_fix": "Check the build log above for lines starting with 'E:'.",
            "package_replacements": [],
        }
