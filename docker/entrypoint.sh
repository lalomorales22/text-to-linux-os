#!/bin/bash
set -e

echo "========================================"
echo "Text-to-Linux-OS Builder Starting..."
echo "========================================"

# Initialize database if not exists
if [ ! -f /app/data/text-to-linux-os.db ]; then
    echo "Initializing database..."
    python3 -c "from backend.database.db import init_db; init_db()"
fi

# Check for API key
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "WARNING: ANTHROPIC_API_KEY is not set!"
    echo "The chatbot will not work without it."
    echo "Please set it in your .env file"
fi

# Create necessary directories
mkdir -p /app/cache/packages
mkdir -p /app/builds
mkdir -p /app/data

echo "Starting application..."
echo "========================================"

# Execute the main command
exec "$@"
