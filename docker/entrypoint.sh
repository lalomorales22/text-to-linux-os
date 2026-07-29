#!/bin/bash
set -e

echo "Text-to-Linux-OS Builder starting..."

if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "WARNING: ANTHROPIC_API_KEY is not set — the AI wizard will not work."
    echo "Add it to your .env file and restart."
fi

mkdir -p /app/cache/packages /app/builds /app/data

# Refresh apt lists in the background so the pre-build dependency dry-run
# (apt-get --simulate) has current data. Non-fatal if offline.
(apt-get update -qq >/dev/null 2>&1 && echo "apt lists refreshed (dry-run ready)") &

exec "$@"
