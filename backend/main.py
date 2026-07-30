"""Text-to-Linux-OS Builder — FastAPI application."""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.config import get_settings
from backend.database.db import BuildDB, MetaDB, init_db
from backend.services import debian_packages, livebuild, qemu_test

logging.basicConfig(
    level=get_settings().log_level,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


async def _background_index_sync() -> None:
    try:
        await debian_packages.sync_index()
    except Exception as exc:
        logger.warning("Package index sync failed (will retry on demand): %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.ensure_directories()
    init_db()

    stale = BuildDB.mark_stale_builds_failed()
    if stale:
        logger.info("Marked %d interrupted build(s) as failed after restart", stale)

    if not (settings.anthropic_api_key or MetaDB.get("anthropic_api_key")):
        logger.warning("No Anthropic API key configured — paste one in the app's "
                       "Settings (gear icon) or set ANTHROPIC_API_KEY")
    if not livebuild.live_build_available():
        logger.warning("live-build not found — ISO building requires the Docker container")
    if not qemu_test.qemu_available():
        logger.warning("qemu-system-x86_64 not found — boot testing disabled")

    sync_task = asyncio.create_task(_background_index_sync())
    yield
    sync_task.cancel()


app = FastAPI(
    title="Text-to-Linux-OS Builder",
    description="AI-powered custom Linux ISO generator with built-in verification and USB flashing",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from backend.api import builds, chat, packages, projects, settings as settings_api  # noqa: E402

app.include_router(chat.router)
app.include_router(builds.router)
app.include_router(projects.router)
app.include_router(packages.router)
app.include_router(settings_api.router)

app.mount("/static", StaticFiles(directory=get_settings().frontend_dir), name="static")


@app.get("/")
async def root() -> FileResponse:
    return FileResponse(get_settings().frontend_dir / "index.html")


@app.get("/health")
async def health() -> dict:
    return {
        "status": "healthy",
        "version": "2.0.0",
        "live_build": livebuild.live_build_available(),
        "qemu": qemu_test.qemu_available(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
