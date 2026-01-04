"""
Live-build ISO builder orchestration
"""
import os
import subprocess
import asyncio
import logging
import shutil
from typing import Optional, Dict, Any, Callable
from datetime import datetime

logger = logging.getLogger(__name__)


class BuildStatus:
    """Build status tracker"""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class LiveBuildOrchestrator:
    """Orchestrates the live-build process"""

    def __init__(self, build_dir: str, progress_callback: Optional[Callable] = None):
        # Ensure build_dir is an absolute path
        self.build_dir = os.path.abspath(build_dir)
        self.progress_callback = progress_callback
        self.current_step = ""
        self.progress = 0
        self.logs = []
        self.status = BuildStatus.QUEUED

    def _check_live_build_installed(self) -> tuple[bool, str]:
        """Check if live-build is installed on the system"""
        lb_path = shutil.which('lb')

        if not lb_path:
            error_msg = (
                "live-build (lb) command not found. "
                "This tool is required to build Debian-based ISOs.\n\n"
                "Installation instructions:\n"
                "- On Debian/Ubuntu: sudo apt-get install live-build\n"
                "- On macOS: live-build is not supported. Please use Docker or a Linux VM.\n"
                "- Using Docker: docker run -v $(pwd):/work debian:bookworm bash -c 'apt-get update && apt-get install -y live-build'\n\n"
                "Note: This application must run on a Debian/Ubuntu Linux system for ISO building."
            )
            return False, error_msg

        return True, f"live-build found at: {lb_path}"

    async def build_iso(self) -> Dict[str, Any]:
        """
        Build the ISO using live-build
        Returns build result with status, logs, and ISO path
        """
        try:
            self.status = BuildStatus.RUNNING
            self.update_progress(0, "Initializing build environment")

            # Check if live-build is installed
            is_installed, message = self._check_live_build_installed()
            if not is_installed:
                raise Exception(message)

            self.logs.append(message)

            # Step 1: Clean previous builds
            await self._run_step(10, "Cleaning previous builds", self._clean_build)

            # Step 2: Run lb config
            await self._run_step(20, "Configuring live-build", self._run_lb_config)

            # Step 3: Run lb build
            await self._run_step(30, "Building ISO (this may take 30-60 minutes)", self._run_lb_build)

            # Step 4: Validate ISO
            await self._run_step(90, "Validating ISO", self._validate_iso)

            # Step 5: Move ISO to final location
            iso_path = await self._run_step(95, "Finalizing ISO", self._finalize_iso)

            self.update_progress(100, "Build completed successfully")
            self.status = BuildStatus.COMPLETED

            return {
                "status": "success",
                "iso_path": iso_path,
                "logs": "\n".join(self.logs),
                "size_bytes": os.path.getsize(iso_path) if iso_path else 0
            }

        except Exception as e:
            self.status = BuildStatus.FAILED
            error_msg = f"Build failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.logs.append(error_msg)

            return {
                "status": "failed",
                "error": error_msg,
                "logs": "\n".join(self.logs)
            }

    async def _run_step(self, progress: int, description: str, func):
        """Run a build step with progress tracking"""
        self.update_progress(progress, description)
        try:
            result = await func()
            return result
        except Exception as e:
            self.logs.append(f"ERROR in {description}: {str(e)}")
            raise

    def update_progress(self, progress: int, step: str):
        """Update build progress"""
        self.progress = progress
        self.current_step = step
        log_msg = f"[{progress}%] {step}"
        self.logs.append(log_msg)
        logger.info(log_msg)

        if self.progress_callback:
            self.progress_callback(progress, step)

    async def _clean_build(self):
        """Clean previous build artifacts"""
        try:
            # Remove previous live-build artifacts
            # Also remove any stale stage files that might cause issues
            await self._run_command("lb clean --purge", "Clean")
            # Remove stale stage files if they exist
            stage_files = [".build", ".stage"]
            for sf in stage_files:
                stage_path = os.path.join(self.build_dir, sf)
                if os.path.exists(stage_path):
                    if os.path.isdir(stage_path):
                        shutil.rmtree(stage_path)
                    else:
                        os.remove(stage_path)
        except Exception as e:
            # It's okay if clean fails (might be first build)
            logger.warning(f"Clean failed (expected for first build): {e}")

    async def _run_lb_config(self):
        """Run lb config"""
        # The auto/config script should already be created by config_generator
        await self._run_command("lb config", "Config")

    async def _run_lb_build(self):
        """Run lb build - this is the main build process"""
        # Run with streaming output directly in the build directory
        process = await asyncio.create_subprocess_shell(
            "lb build 2>&1",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=self.build_dir
        )

        # Stream output
        while True:
            line = await process.stdout.readline()
            if not line:
                break

            line_str = line.decode('utf-8', errors='ignore').strip()
            if line_str:
                self.logs.append(line_str)
                logger.info(f"[BUILD] {line_str}")

                # Update progress based on output
                if "P: Begin downloading packages" in line_str:
                    self.update_progress(40, "Downloading packages")
                elif "P: Begin installing packages" in line_str:
                    self.update_progress(60, "Installing packages")
                elif "P: Begin building root filesystem" in line_str:
                    self.update_progress(75, "Building root filesystem")
                elif "P: Begin building binary" in line_str:
                    self.update_progress(85, "Creating ISO image")

        await process.wait()

        if process.returncode != 0:
            raise Exception(f"Build failed with exit code {process.returncode}")

    async def _validate_iso(self):
        """Validate that the ISO was created and is valid"""
        iso_files = []
        for file in os.listdir(self.build_dir):
            if file.endswith('.iso'):
                iso_files.append(file)

        if not iso_files:
            raise Exception("No ISO file was generated")

        iso_path = os.path.join(self.build_dir, iso_files[0])
        iso_size = os.path.getsize(iso_path)

        # Check if ISO is reasonable size (at least 100MB)
        if iso_size < 100 * 1024 * 1024:
            raise Exception(f"ISO file seems too small ({iso_size} bytes)")

        self.logs.append(f"ISO validated: {iso_files[0]} ({iso_size / (1024*1024):.1f} MB)")
        return iso_path

    async def _finalize_iso(self):
        """Move ISO to final location with proper naming"""
        # Find the generated ISO
        iso_files = [f for f in os.listdir(self.build_dir) if f.endswith('.iso')]

        if not iso_files:
            raise Exception("No ISO file found to finalize")

        source_iso = os.path.join(self.build_dir, iso_files[0])

        # Create final filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        build_name = os.path.basename(self.build_dir)
        final_name = f"{build_name}_{timestamp}.iso"
        final_path = os.path.join(self.build_dir, final_name)

        # Rename ISO
        if source_iso != final_path:
            os.rename(source_iso, final_path)

        self.logs.append(f"ISO finalized: {final_name}")
        return final_path

    async def _run_command(self, command: str, step_name: str):
        """Run a shell command and capture output"""
        logger.info(f"Running: {command} (in {self.build_dir})")

        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=self.build_dir
        )

        stdout, _ = await process.communicate()
        output = stdout.decode('utf-8', errors='ignore')

        if output:
            for line in output.split('\n'):
                if line.strip():
                    self.logs.append(f"[{step_name}] {line}")

        if process.returncode != 0:
            raise Exception(f"{step_name} failed with exit code {process.returncode}")

        return output


async def build_iso_async(build_dir: str, progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
    """
    Async wrapper for building ISO
    """
    orchestrator = LiveBuildOrchestrator(build_dir, progress_callback)
    result = await orchestrator.build_iso()
    return result


def build_iso_sync(build_dir: str) -> Dict[str, Any]:
    """
    Synchronous wrapper for building ISO
    """
    return asyncio.run(build_iso_async(build_dir))
