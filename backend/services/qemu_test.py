"""QEMU boot verification.

After a build, the ISO is booted headlessly in QEMU (BIOS and/or UEFI to match
the configured boot mode). Screendumps are captured through the QEMU monitor
socket; the boot is considered successful when the VM stays alive and the
screen visibly progresses past the initial bootloader frame. The final
screenshot is saved as proof and shown in the UI.

Inside Docker on Apple Silicon this runs under TCG emulation, so it is slow —
the timeout is generous and the test is best-effort: a failed *test* does not
delete the ISO, it just reports what it saw.
"""
import asyncio
import logging
import shutil
import socket
from pathlib import Path
from typing import Callable, Optional

from backend.config import get_settings

logger = logging.getLogger(__name__)

OVMF_PATHS = [
    "/usr/share/ovmf/OVMF.fd",
    "/usr/share/OVMF/OVMF.fd",
    "/usr/share/OVMF/OVMF_CODE.fd",
]


def qemu_available() -> bool:
    return shutil.which("qemu-system-x86_64") is not None


def _find_ovmf() -> Optional[str]:
    for path in OVMF_PATHS:
        if Path(path).exists():
            return path
    return None


async def boot_test(iso_path: Path, work_dir: Path, boot_mode: str = "both",
                    log: Optional[Callable[[str], None]] = None) -> dict:
    """Run boot tests for the firmware modes the ISO targets."""
    log = log or (lambda line: None)
    if not qemu_available():
        return {"available": False,
                "message": "qemu-system-x86_64 not installed; boot test skipped"}

    modes = {"bios": ["bios"], "uefi": ["uefi"], "both": ["bios", "uefi"]}.get(boot_mode, ["bios"])
    results: dict = {"available": True, "modes": {}}

    for mode in modes:
        if mode == "uefi" and not _find_ovmf():
            results["modes"][mode] = {"passed": False, "skipped": True,
                                      "message": "OVMF UEFI firmware not installed"}
            log("[boot-test] UEFI skipped: OVMF not installed")
            continue
        log(f"[boot-test] Booting ISO in QEMU ({mode.upper()})...")
        results["modes"][mode] = await _boot_once(iso_path, work_dir, mode, log)

    ran = [r for r in results["modes"].values() if not r.get("skipped")]
    results["passed"] = bool(ran) and all(r["passed"] for r in ran)
    return results


async def _boot_once(iso_path: Path, work_dir: Path, mode: str,
                     log: Callable[[str], None]) -> dict:
    settings = get_settings()
    monitor_path = work_dir / f"qemu-monitor-{mode}.sock"
    monitor_path.unlink(missing_ok=True)
    screenshot_ppm = work_dir / f"boot-{mode}.ppm"
    screenshot_png = work_dir / f"boot-{mode}.png"

    cmd = [
        "qemu-system-x86_64",
        "-m", str(settings.boot_test_memory_mb),
        "-smp", "2",
        "-cdrom", str(iso_path),
        "-boot", "d",
        "-display", "none",
        "-monitor", f"unix:{monitor_path},server,nowait",
        "-no-reboot",
    ]
    if mode == "uefi":
        cmd += ["-bios", _find_ovmf()]

    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )

    first_frame: Optional[bytes] = None
    progressed = False
    deadline = asyncio.get_event_loop().time() + settings.boot_test_timeout_seconds
    poll_interval = 15

    try:
        await asyncio.sleep(10)  # let the bootloader draw
        while asyncio.get_event_loop().time() < deadline:
            if proc.returncode is not None:
                stderr = (await proc.stderr.read()).decode(errors="replace")[-500:]
                return {"passed": False,
                        "message": f"VM exited early (code {proc.returncode}): {stderr}"}
            frame = await _screendump(monitor_path, screenshot_ppm)
            if frame:
                if first_frame is None:
                    first_frame = frame
                elif _frames_differ(first_frame, frame):
                    progressed = True
                    log(f"[boot-test] {mode.upper()}: screen progressed past bootloader")
                    # Keep booting a bit longer so the screenshot shows the
                    # desktop rather than kernel messages, then stop.
                    await asyncio.sleep(min(90, max(0, deadline - asyncio.get_event_loop().time())))
                    await _screendump(monitor_path, screenshot_ppm)
                    break
            await asyncio.sleep(poll_interval)
    finally:
        if proc.returncode is None:
            proc.kill()
        try:
            await asyncio.wait_for(proc.wait(), timeout=10)
        except asyncio.TimeoutError:
            pass
        monitor_path.unlink(missing_ok=True)

    screenshot = _convert_screenshot(screenshot_ppm, screenshot_png)
    if progressed:
        return {"passed": True, "message": "Boot progressed past the bootloader",
                "screenshot": screenshot}
    return {"passed": False, "screenshot": screenshot,
            "message": "Screen never progressed past the initial frame within the timeout "
                       "(may be too slow under emulation — try booting on real hardware)"}


async def _screendump(monitor_path: Path, out_path: Path) -> Optional[bytes]:
    """Ask the QEMU monitor for a screendump; return the raw PPM bytes."""
    def _request() -> Optional[bytes]:
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(10)
                sock.connect(str(monitor_path))
                sock.recv(4096)  # banner
                sock.sendall(f"screendump {out_path}\n".encode())
                sock.recv(4096)
        except OSError:
            return None
        try:
            return out_path.read_bytes() if out_path.exists() else None
        except OSError:
            return None

    result = await asyncio.to_thread(_request)
    if result is not None:
        await asyncio.sleep(1)  # give qemu a moment to finish writing
        result = await asyncio.to_thread(lambda: out_path.read_bytes() if out_path.exists() else None)
    return result


def _frames_differ(a: bytes, b: bytes, threshold: float = 0.02) -> bool:
    """True when >2% of sampled bytes differ between two PPM frames."""
    if len(a) != len(b):
        return True
    step = max(1, len(a) // 20000)
    total = diff = 0
    for i in range(0, len(a), step):
        total += 1
        if a[i] != b[i]:
            diff += 1
    return total > 0 and (diff / total) > threshold


def _convert_screenshot(ppm: Path, png: Path) -> Optional[str]:
    if not ppm.exists():
        return None
    try:
        from PIL import Image
        Image.open(ppm).save(png)
        ppm.unlink(missing_ok=True)
        return png.name
    except Exception:
        return ppm.name
