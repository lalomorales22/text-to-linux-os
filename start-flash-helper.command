#!/bin/bash
# Text-to-Linux — USB flash helper launcher.
#
# macOS: double-click this file in Finder and it opens in Terminal.
# Linux: run it from a terminal (./start-flash-helper.command) or
#        double-click and choose "Run in Terminal" if your file manager asks.
#
# The helper needs sudo for raw disk access; you'll be asked for your password.

cd "$(dirname "$0")"

echo "══════════════════════════════════════════════════"
echo "  Text-to-Linux · USB flash helper"
echo "══════════════════════════════════════════════════"
echo
echo "Keep this window open while flashing."
echo "sudo is required for raw USB disk access."
echo

PYTHON="$(command -v python3 || true)"
if [ -z "$PYTHON" ]; then
  echo "python3 was not found on this machine — install it and run me again."
  read -r -p "Press Enter to close… "
  exit 1
fi

sudo "$PYTHON" helper/flash_helper.py
status=$?

echo
if [ $status -ne 0 ]; then
  echo "The helper exited with an error (code $status)."
  read -r -p "Press Enter to close… "
fi
