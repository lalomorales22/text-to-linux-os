#!/usr/bin/env bash
# =============================================================================
# Text-to-Linux — OS Foundry installer
#
# Universal setup for macOS and Linux:
#   * checks Docker + Docker Compose (offers to install on Linux)
#   * creates your .env and asks for the Anthropic API key
#   * builds and starts the app container
#   * waits for the app to come up and prints next steps
#
# Usage:
#   ./install.sh              # full interactive setup + start
#   ./install.sh --no-start   # set everything up but don't start containers
# =============================================================================
set -euo pipefail

cd "$(dirname "$0")"

# ------------------------------------------------------------------ cosmetics
BOLD=$(tput bold 2>/dev/null || true)
DIM=$(tput dim 2>/dev/null || true)
GREEN=$(tput setaf 2 2>/dev/null || true)
YELLOW=$(tput setaf 3 2>/dev/null || true)
RED=$(tput setaf 1 2>/dev/null || true)
RESET=$(tput sgr0 2>/dev/null || true)

say()  { printf '%s\n' "$1"; }
ok()   { printf '%s✓%s %s\n' "$GREEN" "$RESET" "$1"; }
warn() { printf '%s!%s %s\n' "$YELLOW" "$RESET" "$1"; }
fail() { printf '%s✗ %s%s\n' "$RED" "$1" "$RESET"; exit 1; }

ask_yes() {  # ask_yes "question" -> 0 if yes; defaults to NO when non-interactive
  if [ ! -t 0 ]; then return 1; fi
  printf '%s [Y/n] ' "$1"
  read -r reply || reply=""
  case "$reply" in n|N|no|NO) return 1 ;; *) return 0 ;; esac
}

START_APP=1
[ "${1:-}" = "--no-start" ] && START_APP=0

say ""
say "${BOLD}  Text-to-Linux — OS Foundry installer${RESET}"
say "${DIM}  ------------------------------------------------${RESET}"
say ""

# --------------------------------------------------------------- detect OS
OS="$(uname -s)"
case "$OS" in
  Darwin) PLATFORM="macOS" ;;
  Linux)  PLATFORM="Linux" ;;
  *)      fail "Unsupported platform: $OS (this installer supports macOS and Linux)" ;;
esac
ok "Platform: $PLATFORM"

# ----------------------------------------------------------------- Docker
if ! command -v docker >/dev/null 2>&1; then
  if [ "$PLATFORM" = "macOS" ]; then
    warn "Docker is not installed."
    say  "  Install Docker Desktop from https://www.docker.com/products/docker-desktop/"
    if command -v brew >/dev/null 2>&1 && ask_yes "  Install it now with Homebrew (brew install --cask docker)?"; then
      brew install --cask docker
      say "  Open Docker.app once so the Docker engine starts, then re-run ./install.sh"
      exit 0
    fi
    fail "Install Docker Desktop, start it, then re-run ./install.sh"
  else
    warn "Docker is not installed."
    if ask_yes "  Install Docker now using the official convenience script (get.docker.com)?"; then
      curl -fsSL https://get.docker.com | sh
      if [ "$(id -u)" != "0" ]; then
        sudo usermod -aG docker "$USER" || true
        warn "Added $USER to the docker group — log out and back in (or run 'newgrp docker') for it to take effect."
      fi
    else
      fail "Install Docker (https://docs.docker.com/engine/install/) and re-run ./install.sh"
    fi
  fi
fi

if ! docker info >/dev/null 2>&1; then
  if [ "$PLATFORM" = "macOS" ]; then
    fail "Docker is installed but not running. Start Docker Desktop, then re-run ./install.sh"
  else
    warn "Docker daemon isn't reachable. Trying with sudo…"
    sudo docker info >/dev/null 2>&1 || fail "Docker daemon is not running. Start it (sudo systemctl start docker) and re-run."
    warn "You'll need sudo for docker commands until your docker group membership takes effect."
  fi
fi
ok "Docker is installed and running"

# ---------------------------------------------------------------- Compose
if docker compose version >/dev/null 2>&1; then
  COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE="docker-compose"
else
  fail "Docker Compose not found. It ships with Docker Desktop / docker-compose-plugin — install it and re-run."
fi
ok "Docker Compose available ($COMPOSE)"

# ---------------------------------------------------------------- Python 3
if command -v python3 >/dev/null 2>&1; then
  ok "Python 3 found ($(python3 -V 2>&1)) — needed later for the USB flash helper"
else
  warn "Python 3 not found. The app itself runs in Docker, but the USB flash helper"
  warn "(sudo python3 helper/flash_helper.py) needs Python 3 on this machine."
fi

# -------------------------------------------------------------------- .env
if [ ! -f .env ]; then
  cp .env.example .env
  ok "Created .env from .env.example"
fi

if grep -q "your-anthropic-api-key-here" .env 2>/dev/null || ! grep -q "^ANTHROPIC_API_KEY=sk" .env 2>/dev/null; then
  if [ -t 0 ]; then
    say ""
    say "The AI wizard needs an Anthropic API key (https://console.anthropic.com/)."
    printf 'Paste your API key (or press Enter to skip for now): '
    read -r api_key || api_key=""
    if [ -n "$api_key" ]; then
      # replace existing key line, or append one
      if grep -q "^ANTHROPIC_API_KEY=" .env; then
        tmp=$(mktemp)
        sed "s|^ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=$api_key|" .env > "$tmp" && mv "$tmp" .env
      else
        printf 'ANTHROPIC_API_KEY=%s\n' "$api_key" >> .env
      fi
      ok "API key saved to .env"
    else
      warn "Skipped. Edit .env later and set ANTHROPIC_API_KEY, then restart the app."
    fi
  else
    warn "No API key configured — edit .env and set ANTHROPIC_API_KEY before using the wizard."
  fi
else
  ok "Anthropic API key already configured in .env"
fi

# -------------------------------------------------------------- build/start
if [ "$START_APP" = "0" ]; then
  say ""
  ok "Setup complete (started with --no-start)."
  say "  Start the app any time with:"
  say "    $COMPOSE -f docker/docker-compose.yml up --build -d"
  exit 0
fi

say ""
say "Building and starting the app (first build downloads the Debian base image — a few minutes)…"
$COMPOSE -f docker/docker-compose.yml up --build -d

printf 'Waiting for the app to come up'
for _ in $(seq 1 60); do
  if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
    printf '\n'
    ok "App is running"
    break
  fi
  printf '.'
  sleep 2
done

if ! curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
  printf '\n'
  warn "The app didn't respond yet. Check logs with:"
  say  "  $COMPOSE -f docker/docker-compose.yml logs -f"
  exit 1
fi

say ""
say "${BOLD}${GREEN}  All set.${RESET}"
say ""
say "  Open the app:        ${BOLD}http://localhost:8000${RESET}"
say "  Flash USB drives:    ${BOLD}sudo python3 helper/flash_helper.py${RESET}  (run when you're ready to flash)"
say "  Stop the app:        $COMPOSE -f docker/docker-compose.yml down"
say "  Follow the logs:     $COMPOSE -f docker/docker-compose.yml logs -f"
say ""
