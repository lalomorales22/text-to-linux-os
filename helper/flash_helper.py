#!/usr/bin/env python3
"""Text-to-Linux-OS USB Flash Helper.

The web app runs inside Docker, which cannot see USB drives — so this small
companion runs on the host machine and does the flashing. It exposes a
localhost-only HTTP API that the web UI talks to: detect removable drives,
unmount, stream-write the ISO directly from the app, verify the written bytes
against the ISO's SHA-256, and eject.

Run it with admin rights when you want to flash a USB stick:

    sudo python3 helper/flash_helper.py

It prints a 6-digit pairing code; enter that code in the web app's Flash panel.
Standard library only — no dependencies to install.

Safety model:
  * binds to 127.0.0.1 only, all mutating endpoints require the pairing token
  * only drives detected as removable/external can be selected — internal
    system disks are never listed and are refused even if requested directly
  * requests are also checked against a browser Origin allowlist
"""
import hashlib
import json
import os
import plistlib
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VERSION = "1.0.0"
PORT = 8765
ALLOWED_ORIGINS = {
    "http://localhost:8000", "http://127.0.0.1:8000",
}
CHUNK_SIZE = 4 * 1024 * 1024
MAX_DEVICE_SIZE = 2 * 1024 ** 4  # refuse anything over 2 TB — that's not a USB stick

PAIRING_CODE = f"{secrets.randbelow(1_000_000):06d}"
TOKEN = secrets.token_hex(16)


# --------------------------------------------------------------------- drives

def list_drives() -> list[dict]:
    if sys.platform == "darwin":
        return _list_drives_macos()
    if sys.platform.startswith("linux"):
        return _list_drives_linux()
    return []


def _list_drives_macos() -> list[dict]:
    try:
        raw = subprocess.run(
            ["diskutil", "list", "-plist", "external", "physical"],
            capture_output=True, check=True, timeout=30,
        ).stdout
        listing = plistlib.loads(raw)
    except Exception:
        return []
    drives = []
    for disk in listing.get("AllDisksAndPartitions", []):
        identifier = disk.get("DeviceIdentifier", "")
        if not re.fullmatch(r"disk\d+", identifier) or identifier == "disk0":
            continue
        try:
            info = plistlib.loads(subprocess.run(
                ["diskutil", "info", "-plist", f"/dev/{identifier}"],
                capture_output=True, check=True, timeout=30,
            ).stdout)
        except Exception:
            continue
        if info.get("Internal", False):
            continue
        size = int(info.get("TotalSize") or info.get("Size") or 0)
        if not size or size > MAX_DEVICE_SIZE:
            continue
        drives.append({
            "device": f"/dev/{identifier}",
            "raw_device": f"/dev/r{identifier}",
            "name": (info.get("MediaName") or "External drive").strip(),
            "size_bytes": size,
            "removable": bool(info.get("RemovableMediaOrExternalDevice", True)),
        })
    return drives


def _list_drives_linux() -> list[dict]:
    try:
        raw = subprocess.run(
            ["lsblk", "-J", "-b", "-o", "NAME,SIZE,MODEL,RM,TYPE,PATH,MOUNTPOINTS"],
            capture_output=True, check=True, timeout=30,
        ).stdout
        listing = json.loads(raw)
    except Exception:
        return []
    drives = []
    for dev in listing.get("blockdevices", []):
        if dev.get("type") != "disk" or not dev.get("rm"):
            continue
        mounts = _collect_mounts(dev)
        if "/" in mounts or "/boot" in mounts:
            continue
        size = int(dev.get("size") or 0)
        if not size or size > MAX_DEVICE_SIZE:
            continue
        drives.append({
            "device": dev.get("path") or f"/dev/{dev['name']}",
            "raw_device": dev.get("path") or f"/dev/{dev['name']}",
            "name": (dev.get("model") or "USB drive").strip(),
            "size_bytes": size,
            "removable": True,
        })
    return drives


def _collect_mounts(dev: dict) -> list[str]:
    mounts = [m for m in (dev.get("mountpoints") or []) if m]
    for child in dev.get("children", []) or []:
        mounts.extend(_collect_mounts(child))
    return mounts


def unmount_drive(device: str) -> None:
    if sys.platform == "darwin":
        subprocess.run(["diskutil", "unmountDisk", device],
                       capture_output=True, timeout=60)
    else:
        try:
            raw = subprocess.run(["lsblk", "-J", "-o", "PATH,TYPE", device],
                                 capture_output=True, check=True, timeout=30).stdout
            for dev in json.loads(raw).get("blockdevices", []):
                for child in dev.get("children", []) or []:
                    subprocess.run(["umount", child["path"]], capture_output=True, timeout=30)
        except Exception:
            pass


def eject_drive(device: str) -> None:
    if sys.platform == "darwin":
        subprocess.run(["diskutil", "eject", device], capture_output=True, timeout=60)
    elif shutil.which("eject"):
        subprocess.run(["eject", device], capture_output=True, timeout=60)


# ------------------------------------------------------------------ flash job

class FlashJob:
    def __init__(self, drive: dict, download_url: str, sha256: str, size_bytes: int):
        self.drive = drive
        self.download_url = download_url
        self.expected_sha256 = (sha256 or "").lower()
        self.total_bytes = size_bytes
        self.state = "starting"
        self.message = ""
        self.bytes_done = 0
        self.cancelled = False
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self.thread.start()

    def cancel(self) -> None:
        self.cancelled = True

    @property
    def active(self) -> bool:
        return self.state in ("starting", "unmounting", "writing", "verifying", "ejecting")

    def progress(self) -> dict:
        return {
            "state": self.state,
            "message": self.message,
            "bytes_done": self.bytes_done,
            "total_bytes": self.total_bytes,
            "percent": round(self.bytes_done / self.total_bytes * 100, 1)
            if self.total_bytes else 0,
            "device": self.drive["device"],
        }

    def _run(self) -> None:
        target = self.drive.get("raw_device") or self.drive["device"]
        try:
            self.state, self.message = "unmounting", "Unmounting drive"
            unmount_drive(self.drive["device"])
            time.sleep(1)

            self.state, self.message = "writing", "Writing ISO to drive"
            written_hash = self._write_image(target)
            if self.cancelled:
                raise InterruptedError("Flash cancelled")
            if self.expected_sha256 and written_hash != self.expected_sha256:
                raise RuntimeError("Downloaded ISO checksum mismatch — download was corrupted")

            self.state, self.message = "verifying", "Verifying written data"
            self.bytes_done = 0
            device_hash = self._hash_device(target)
            if self.cancelled:
                raise InterruptedError("Flash cancelled")
            reference = self.expected_sha256 or written_hash
            if device_hash != reference:
                raise RuntimeError("Verification failed — data on the drive does not match the ISO")

            self.state, self.message = "ejecting", "Ejecting drive"
            eject_drive(self.drive["device"])
            self.state = "done"
            self.message = ("Success! The USB drive is verified, ejected, and ready to boot. "
                            "You can unplug it now.")
        except InterruptedError:
            self.state, self.message = "cancelled", "Flash cancelled. The drive is in an incomplete state — reflash before using it."
        except Exception as exc:
            self.state, self.message = "error", str(exc)

    def _write_image(self, target: str) -> str:
        digest = hashlib.sha256()
        request = urllib.request.Request(self.download_url)
        with urllib.request.urlopen(request, timeout=60) as response:
            fd = os.open(target, os.O_WRONLY)
            try:
                while True:
                    if self.cancelled:
                        raise InterruptedError()
                    chunk = response.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    digest.update(chunk)
                    os.write(fd, chunk)
                    self.bytes_done += len(chunk)
                os.fsync(fd)
            finally:
                os.close(fd)
        self.total_bytes = self.bytes_done or self.total_bytes
        return digest.hexdigest()

    def _hash_device(self, target: str) -> str:
        digest = hashlib.sha256()
        remaining = self.total_bytes
        fd = os.open(target, os.O_RDONLY)
        try:
            while remaining > 0:
                if self.cancelled:
                    raise InterruptedError()
                chunk = os.read(fd, min(CHUNK_SIZE, remaining))
                if not chunk:
                    break
                digest.update(chunk)
                remaining -= len(chunk)
                self.bytes_done += len(chunk)
        finally:
            os.close(fd)
        return digest.hexdigest()


current_job: FlashJob | None = None
job_lock = threading.Lock()


# ---------------------------------------------------------------- http server

class Handler(BaseHTTPRequestHandler):
    server_version = f"TTL-FlashHelper/{VERSION}"

    def log_message(self, fmt, *args):  # keep the terminal clean for the pairing code
        pass

    # -- helpers
    def _cors_headers(self) -> None:
        origin = self.headers.get("Origin", "")
        if origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Flash-Token")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def _json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self._cors_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        return secrets.compare_digest(self.headers.get("X-Flash-Token", ""), TOKEN)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            return {}

    # -- routes
    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        origin = self.headers.get("Origin")
        if origin and origin not in ALLOWED_ORIGINS:
            return self._json({"error": "origin not allowed"}, 403)
        if self.path == "/health":
            return self._json({"ok": True, "version": VERSION, "platform": sys.platform,
                               "root": os.geteuid() == 0 if hasattr(os, "geteuid") else None})
        if not self._authorized():
            return self._json({"error": "pairing required"}, 401)
        if self.path == "/drives":
            return self._json({"drives": list_drives()})
        if self.path == "/progress":
            with job_lock:
                if current_job is None:
                    return self._json({"state": "idle"})
                return self._json(current_job.progress())
        self._json({"error": "not found"}, 404)

    def do_POST(self) -> None:
        global current_job
        origin = self.headers.get("Origin")
        if origin and origin not in ALLOWED_ORIGINS:
            return self._json({"error": "origin not allowed"}, 403)
        body = self._read_body()

        if self.path == "/pair":
            if secrets.compare_digest(str(body.get("code", "")), PAIRING_CODE):
                return self._json({"token": TOKEN})
            return self._json({"error": "wrong pairing code"}, 403)

        if not self._authorized():
            return self._json({"error": "pairing required"}, 401)

        if self.path == "/flash":
            device = body.get("device", "")
            download_url = body.get("download_url", "")
            drives = {d["device"]: d for d in list_drives()}
            if device not in drives:
                return self._json({"error": "Device is not a detected removable drive"}, 400)
            if not download_url.startswith(("http://localhost:", "http://127.0.0.1:")):
                return self._json({"error": "download_url must point at the local app"}, 400)
            size_bytes = int(body.get("size_bytes", 0) or 0)
            if size_bytes and size_bytes > drives[device]["size_bytes"]:
                return self._json({"error": "ISO is larger than the selected drive"}, 400)
            with job_lock:
                if current_job and current_job.active:
                    return self._json({"error": "A flash is already in progress"}, 409)
                current_job = FlashJob(drives[device], download_url,
                                       body.get("sha256", ""), size_bytes)
                current_job.start()
            return self._json({"started": True})

        if self.path == "/cancel":
            with job_lock:
                if current_job and current_job.active:
                    current_job.cancel()
            return self._json({"ok": True})

        if self.path == "/eject":
            device = body.get("device", "")
            drives = {d["device"] for d in list_drives()}
            if device in drives:
                eject_drive(device)
                return self._json({"ok": True})
            return self._json({"error": "unknown device"}, 400)

        self._json({"error": "not found"}, 404)


def main() -> None:
    is_root = os.geteuid() == 0 if hasattr(os, "geteuid") else True
    print()
    print("  Text-to-Linux-OS — USB Flash Helper")
    print("  " + "-" * 44)
    if not is_root:
        print("  WARNING: not running as root — writing to USB devices")
        print("  will likely fail. Restart with: sudo python3 helper/flash_helper.py")
    print(f"  Listening on http://127.0.0.1:{PORT} (localhost only)")
    print()
    print(f"  Pairing code:   {PAIRING_CODE}")
    print()
    print("  Enter this code in the web app's Flash USB panel.")
    print("  Press Ctrl+C to quit.")
    print()
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Flash helper stopped.")


if __name__ == "__main__":
    main()
