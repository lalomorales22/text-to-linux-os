"""Package API — validation against the real Debian index, search, dry-run."""
import logging

from fastapi import APIRouter

from backend.database.db import MetaDB, PackageDB
from backend.database.models import PackagesRequest
from backend.services import debian_packages

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/packages", tags=["packages"])


@router.get("/status")
async def index_status() -> dict:
    return {
        "packages": PackageDB.count(),
        "synced_at": MetaDB.get(debian_packages.INDEX_SYNCED_KEY),
        "stale": debian_packages.index_is_stale(),
        "apt_dry_run_available": debian_packages.apt_available(),
    }


@router.post("/sync")
async def sync_index() -> dict:
    return await debian_packages.sync_index(force=True)


@router.post("/validate")
async def validate(req: PackagesRequest) -> dict:
    return debian_packages.validate_packages(req.packages)


@router.get("/search")
async def search(q: str, limit: int = 25) -> dict:
    return {"results": PackageDB.search(q, limit=min(limit, 100))}


@router.post("/dry-run")
async def dry_run(req: PackagesRequest) -> dict:
    return await debian_packages.apt_dry_run(req.packages)
