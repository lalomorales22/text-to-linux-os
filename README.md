# Text-to-Linux — OS Foundry

Describe a machine in plain English. Get a verified, bootable Linux ISO — and flash it to a USB stick without ever leaving the app.

![Version](https://img.shields.io/badge/version-2.0.0-blue)
![License](https://img.shields.io/badge/license-GPL--3.0-green)
![Python](https://img.shields.io/badge/python-3.11+-blue)
![Platform](https://img.shields.io/badge/platform-Docker-blue)

## What it does

1. **Configure** — A streaming AI wizard (Claude) turns "old 2010 laptop, 2GB RAM, just for browsing" into a real Debian package selection. Every package is checked against the **actual Debian package index** (~64,000 packages, synced locally), so typos and nonexistent packages are caught in seconds — not 40 minutes into a build.
2. **Build** — Debian live-build produces a hybrid BIOS+UEFI ISO with your hostname, user, packages, and a generated desktop theme (Openbox + tint2 + themed terminal).
3. **Verify** — The finished ISO is **boot-tested in QEMU** automatically (BIOS and/or UEFI). You get a screenshot of your OS actually booting as proof, right in the UI.
4. **Flash** — A small companion helper runs on your machine and gives you a built-in Etcher: detect USB drives, erase, write, **verify every byte against the ISO's SHA-256**, and eject. Plug the stick into an old laptop or desktop and boot your own OS.

## What's new in 2.0

Version 2.0 is a ground-up overhaul of the 1.x codebase:

- **Real package validation** — 1.x guessed package sizes from a hardcoded table of ~40 entries and couldn't tell whether a package existed. 2.0 syncs the actual Debian package index and validates everything against it before a build can start.
- **QEMU boot verification** — new. Every build is boot-tested automatically, with screenshot proof in the UI.
- **Built-in USB flashing** — new. The `helper/flash_helper.py` companion turns the app into a full Etcher replacement: detect, erase, write, verify, eject.
- **Streaming AI wizard** — responses stream token-by-token, and the configuration is captured through a strict tool-use schema instead of scraping JSON out of chat text. Runs on `claude-opus-5` with server-side refusal fallbacks.
- **Builds that survive restarts** — build state moved from an in-memory dict into SQLite, logs stream to files, the gallery reattaches to running builds, and Cancel actually kills the build process group (in 1.x it was a TODO).
- **Real versioning** — each build snapshots the config as an incrementing version per project (1.x always wrote version 1).
- **Pre-build dependency dry-run** — `apt --simulate` inside the container surfaces conflicts in seconds.
- **Completely new UI** — the dot-grid/ASCII terminal look is gone, replaced by a color-coded pipeline design (Configure → Build → Verify → Flash) with a live build sheet. No frameworks, no build step, no CDN Tailwind.
- **Harmonious theme generation** — HSL-derived palettes with proper Openbox/tint2/LXTerminal theming, replacing pure-random RGB.
- **A test suite** — pytest coverage for the database layer, package validation, config generation, and theming ("coming soon" since 1.0).

## Quick start

Requirements: Docker + Docker Compose, an [Anthropic API key](https://console.anthropic.com/), ~20GB free disk, 4GB+ RAM.

**One command (macOS or Linux):**

```bash
git clone https://github.com/lalomorales22/text-to-linux-os
cd text-to-linux-os
./install.sh
```

The installer checks Docker (and offers to install it on Linux), sets up your `.env`, asks for your API key, builds the container, and waits until the app is live. Use `./install.sh --no-start` to set up without launching.

**Or manually:**

```bash
cp .env.example .env
# put your key in .env:  ANTHROPIC_API_KEY=sk-ant-...

docker-compose -f docker/docker-compose.yml up --build
```

Open **http://localhost:8000**, describe your machine, and press **Build ISO** when the wizard confirms your configuration.

> **Apple Silicon (M1–M4) Macs:** the container runs in amd64 emulation so it can build x86_64 ISOs. Builds are slower but fully functional.

## Flashing a USB drive

The web app runs inside Docker, which can't see USB hardware — so flashing is done by a tiny companion that runs on your actual machine (standard library Python, nothing to install):

```bash
sudo python3 helper/flash_helper.py
```

It prints a 6-digit pairing code. Click **Flash to USB** in the app, enter the code, pick your drive, confirm — the app streams the ISO straight to the stick, verifies the written bytes, and ejects it.

Safety rails: the helper listens on localhost only, requires the pairing code, only ever lists removable/external drives (system disks are never shown or accepted), and refuses drives smaller than the ISO.

## Booting your OS

1. Plug the flashed USB stick into the target machine.
2. Open its boot menu (usually F12, F10, Esc, or Del at power-on).
3. Choose the USB drive. Your system boots straight into its desktop with your theme, packages, and auto-login user.

## Architecture

- **Backend** — Python 3.11 + FastAPI. Chat streams over SSE; ISO configuration is extracted through a strict tool-use schema (no JSON scraping); build state persists in SQLite so builds survive page reloads and server restarts; cancellation kills the real build process group.
- **Package intelligence** — the Debian `Packages.gz` index for bookworm (main/contrib/non-free/non-free-firmware) is downloaded and cached, giving real existence checks, real installed sizes, fuzzy "did you mean" suggestions, and an `apt --simulate` dependency dry-run inside the container.
- **Builder** — Debian live-build with generated config trees: package lists, auto-login hooks, hostname/user setup, Openbox/tint2/LXTerminal theming.
- **Verification** — QEMU (with OVMF for UEFI) boots the ISO headlessly, watches the screen progress past the bootloader, and captures screenshots via the QEMU monitor.
- **Frontend** — dependency-free ES modules + a hand-rolled design system. No frameworks, no build step.
- **Flash helper** — single-file stdlib Python HTTP service; macOS (`diskutil`) and Linux (`lsblk`) drive detection, raw device writes, SHA-256 read-back verification.

```
backend/
├── main.py                  # FastAPI app (lifespan, static, health)
├── config.py                # settings from env/.env
├── api/                     # chat (SSE), builds (SSE logs), projects, packages
├── services/
│   ├── ai.py                # streaming wizard + tool-use config, failure analysis
│   ├── debian_packages.py   # real package index sync/validation/dry-run
│   ├── livebuild.py         # live-build config tree generation
│   ├── orchestrator.py      # persistent builds, cancellation, ISO finalize+sha256
│   ├── qemu_test.py         # boot verification + screenshots
│   └── themes.py            # palette generation + desktop config writers
└── database/                # SQLite layer (projects, versions, builds, package index)
helper/flash_helper.py       # host-side USB flasher (run with sudo)
frontend/                    # index.html, css/, js/ (ES modules)
docker/                      # Dockerfile, compose, entrypoint
tests/                       # pytest suite
install.sh                   # universal macOS/Linux setup script
```

## Key API endpoints

Interactive docs at http://localhost:8000/docs.

| Endpoint | What it does |
|---|---|
| `POST /api/chat/message` | Stream a wizard conversation turn (SSE) |
| `POST /api/packages/validate` | Check packages against the real Debian index |
| `POST /api/packages/dry-run` | Simulate the apt install to catch dependency conflicts |
| `POST /api/builds` | Start a build (creates a new version snapshot) |
| `GET /api/builds/{id}/logs/stream` | Live build log + progress (SSE) |
| `POST /api/builds/{id}/cancel` | Actually kill the build process group |
| `GET /api/builds/{id}/screenshot/{mode}` | QEMU boot-proof screenshot (bios/uefi) |
| `GET /api/projects/{id}/download` | Download the ISO (SHA-256 in headers) |
| `GET /api/projects/{id}/iso-info` | Metadata the flash helper uses |

## Development

Run the backend natively (macOS/Linux — everything works except `lb build` and QEMU, which need the container):

```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```

Run the tests:

```bash
pip install pytest
python -m pytest tests/
```

## Troubleshooting

- **"live-build (lb) is not installed"** — ISO building needs the Docker container (or a Debian/Ubuntu host with `live-build` + `debootstrap`). The UI and package validation work anywhere.
- **Build fails on unknown packages** — the pre-build validator normally blocks these; if the AI suggested something odd, the failure analysis will name the package and a replacement.
- **`mknod: Operation not permitted`** — make sure you're using the shipped `docker-compose.yml`: builds live in a Docker *volume* with `privileged: true` and the `SYS_ADMIN`/`MKNOD` capabilities.
- **Boot test never passes** — under emulation (Apple Silicon) QEMU is slow; a "did not finish booting" verdict doesn't delete your ISO. Try the stick on real hardware, or raise `BOOT_TEST_TIMEOUT_SECONDS`.
- **Flash helper not found** — it must run on the host (not in Docker), with `sudo`, while the web app is open on `localhost:8000`.

## License

GPL-3.0 — see LICENSE.

## Credits

Built with [Anthropic Claude](https://www.anthropic.com/), [Debian live-build](https://wiki.debian.org/DebianLive), and [QEMU](https://www.qemu.org/).
