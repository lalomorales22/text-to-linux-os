"""Build orchestration.

Build state lives in SQLite (surviving restarts) and full logs stream to a file
per build, so the gallery can reattach to a running build and logs are never
lost with the process. Cancellation kills the whole live-build process group.
"""
import asyncio
import hashlib
import logging
import os
import signal
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from backend.config import get_settings
from backend.database.db import BuildDB, ProjectDB, VersionDB
from backend.services import ai, livebuild, qemu_test

logger = logging.getLogger(__name__)


class BuildCancelled(Exception):
    pass


class BuildJob:
    def __init__(self, build_id: str, build_dir: Path, log_path: Path):
        self.build_id = build_id
        self.build_dir = build_dir
        self.log_path = log_path
        self.process: Optional[asyncio.subprocess.Process] = None
        self.cancelled = False
        self.task: Optional[asyncio.Task] = None

    # ---------------------------------------------------------------- logging
    def log(self, line: str) -> None:
        with self.log_path.open("a") as f:
            f.write(line.rstrip("\n") + "\n")

    def set_progress(self, progress: int, step: str, status: str = "running") -> None:
        BuildDB.update(self.build_id, status=status, progress=progress, step=step)
        self.log(f"[{progress:3d}%] {step}")

    # ------------------------------------------------------------ subprocess
    async def run_command(self, command: list[str], timeout: Optional[int] = None,
                          progress_hook=None) -> int:
        """Run a command in the build dir, streaming output to the log file."""
        self.log(f"$ {' '.join(command)}")
        self.process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=self.build_dir,
            start_new_session=True,  # own process group -> clean cancellation
        )

        async def _pump():
            assert self.process and self.process.stdout
            async for raw in self.process.stdout:
                line = raw.decode("utf-8", errors="replace").rstrip()
                if line:
                    self.log(line)
                    if progress_hook:
                        progress_hook(line)
            await self.process.wait()

        try:
            await asyncio.wait_for(_pump(), timeout=timeout)
        except asyncio.TimeoutError:
            self.terminate()
            raise RuntimeError(f"Command timed out after {timeout}s: {command[0]}")
        finally:
            proc, self.process = self.process, None

        if self.cancelled:
            raise BuildCancelled()
        return proc.returncode or 0

    def terminate(self) -> None:
        if self.process and self.process.pid:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass

    def cancel(self) -> None:
        self.cancelled = True
        self.terminate()
        if self.task:
            self.task.cancel()


class BuildManager:
    """Singleton owning in-flight build jobs for this process."""

    def __init__(self) -> None:
        self.jobs: dict[str, BuildJob] = {}

    def start_build(self, project: dict, version: dict, run_boot_test: bool = True) -> str:
        build_id = str(uuid.uuid4())
        build_dir = livebuild.create_build_directory(project["name"], version["version_number"])
        log_path = build_dir / "build.log"
        log_path.write_text("")  # fresh log per attempt

        BuildDB.create(build_id, project["id"], version["id"], str(log_path))
        ProjectDB.update(project["id"], status="building")

        job = BuildJob(build_id, build_dir, log_path)
        self.jobs[build_id] = job
        job.task = asyncio.create_task(self._run(job, project, version, run_boot_test))
        return build_id

    def cancel_build(self, build_id: str) -> bool:
        job = self.jobs.get(build_id)
        if not job:
            return False
        job.cancel()
        return True

    def get_job(self, build_id: str) -> Optional[BuildJob]:
        return self.jobs.get(build_id)

    # ------------------------------------------------------------- pipeline
    async def _run(self, job: BuildJob, project: dict, version: dict,
                   run_boot_test: bool) -> None:
        settings = get_settings()
        config = version["config"]
        try:
            job.set_progress(1, "Preparing build environment")
            if not livebuild.live_build_available():
                raise RuntimeError(
                    "live-build (lb) is not installed. ISO building requires the Docker "
                    "container or a Debian/Ubuntu system with live-build installed."
                )

            job.set_progress(3, "Generating live-build configuration")
            livebuild.generate_config_tree(config, version.get("theme_config"), job.build_dir)

            job.set_progress(5, "Cleaning previous build artifacts")
            try:
                await job.run_command(["lb", "clean", "--purge"], timeout=300)
            except BuildCancelled:
                raise
            except Exception as exc:
                job.log(f"(clean skipped: {exc})")
            for stale in (".build", ".stage"):
                path = job.build_dir / stale
                if path.is_dir():
                    import shutil
                    shutil.rmtree(path, ignore_errors=True)

            job.set_progress(8, "Configuring live-build")
            rc = await job.run_command(["lb", "config"], timeout=300)
            if rc != 0:
                raise RuntimeError(f"lb config failed with exit code {rc}")

            job.set_progress(12, "Building ISO — bootstrapping Debian base system")

            def progress_hook(line: str) -> None:
                markers = [
                    ("P: Begin bootstrapping system", 15, "Bootstrapping Debian base system"),
                    ("P: Begin installing packages", 35, "Installing packages"),
                    ("P: Begin executing hooks", 60, "Running configuration hooks"),
                    ("P: Begin building binary", 72, "Compressing filesystem and creating ISO"),
                    ("P: Begin building iso", 82, "Writing hybrid ISO image"),
                ]
                for marker, pct, step in markers:
                    if marker in line:
                        BuildDB.update(job.build_id, progress=pct, step=step)

            rc = await job.run_command(
                ["lb", "build"],
                timeout=settings.build_timeout_minutes * 60,
                progress_hook=progress_hook,
            )
            if rc != 0:
                raise RuntimeError(f"lb build failed with exit code {rc}")

            job.set_progress(88, "Validating and finalizing ISO")
            iso_path = self._finalize_iso(job, project)
            sha256 = await asyncio.to_thread(self._sha256, iso_path)
            VersionDB.update(version["id"], iso_path=str(iso_path),
                             iso_size=iso_path.stat().st_size, iso_sha256=sha256)

            boot_result: Optional[dict[str, Any]] = None
            if run_boot_test:
                job.set_progress(90, "Boot-testing ISO in QEMU (this can take a few minutes)",
                                 status="testing")
                boot_result = await qemu_test.boot_test(
                    iso_path, job.build_dir,
                    boot_mode=config.get("hardware", {}).get("boot", "both"),
                    log=job.log,
                )
                BuildDB.update(job.build_id, boot_test=boot_result)

            job.set_progress(100, "Build complete", status="completed")
            ProjectDB.update(project["id"], status="completed")
            job.log(f"ISO: {iso_path.name} ({iso_path.stat().st_size / 1024 / 1024:.0f} MB)")
            job.log(f"SHA256: {sha256}")

        except (BuildCancelled, asyncio.CancelledError):
            job.log("Build cancelled by user")
            BuildDB.update(job.build_id, status="cancelled", step="Cancelled")
            ProjectDB.update(project["id"], status="cancelled")
        except Exception as exc:
            logger.error("Build %s failed: %s", job.build_id, exc, exc_info=True)
            job.log(f"ERROR: {exc}")
            analysis = await self._analyze_failure(job, config)
            BuildDB.update(job.build_id, status="failed", step="Failed",
                           error=str(exc), boot_test=None)
            if analysis:
                BuildDB.update(job.build_id, error=(
                    f"{exc}\n\n{analysis['description']}\n\nSuggested fix: "
                    f"{analysis['suggested_fix']}"
                ))
            ProjectDB.update(project["id"], status="failed")
        finally:
            self.jobs.pop(job.build_id, None)

    async def _analyze_failure(self, job: BuildJob, config: dict) -> Optional[dict]:
        try:
            log_tail = job.log_path.read_text()[-15000:]
            return await ai.analyze_build_failure(log_tail, config)
        except Exception:
            return None

    def _finalize_iso(self, job: BuildJob, project: dict) -> Path:
        isos = sorted(job.build_dir.glob("*.iso"), key=lambda p: p.stat().st_mtime)
        if not isos:
            raise RuntimeError("Build finished but no ISO file was produced")
        iso = isos[-1]
        if iso.stat().st_size < 100 * 1024 * 1024:
            raise RuntimeError(
                f"ISO is suspiciously small ({iso.stat().st_size // (1024*1024)} MB) — "
                "the build likely failed silently"
            )
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
        final = job.build_dir / f"{livebuild.sanitize_name(project['name'])}-{stamp}.iso"
        if iso != final:
            iso.rename(final)
        return final

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()


build_manager = BuildManager()
