FROM debian:bookworm

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Live-build and dependencies
    live-build \
    debootstrap \
    # Python
    python3.11 \
    python3-pip \
    python3-venv \
    # Database
    sqlite3 \
    # Utilities
    curl \
    wget \
    git \
    # Build tools
    isolinux \
    syslinux \
    grub-pc-bin \
    grub-efi-amd64-bin \
    xorriso \
    squashfs-tools \
    # Clean up
    && rm -rf /var/lib/apt/lists/*

# Create application directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY . /app

# Create required directories with proper permissions
RUN mkdir -p \
    /app/cache/packages \
    /app/builds \
    /app/data \
    /app/templates \
    && chmod -R 755 /app

# Expose port
EXPOSE 8000

# Set entrypoint
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

# Default command
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
