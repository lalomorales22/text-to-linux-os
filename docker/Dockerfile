FROM debian:bookworm

ENV DEBIAN_FRONTEND=noninteractive

# live-build toolchain, Python runtime, and QEMU for boot verification
RUN apt-get update && apt-get install -y --no-install-recommends \
    live-build \
    debootstrap \
    xorriso \
    squashfs-tools \
    python3 \
    python3-pip \
    python3-venv \
    sqlite3 \
    curl \
    ca-certificates \
    qemu-system-x86 \
    qemu-utils \
    ovmf \
    && rm -rf /var/lib/apt/lists/*

# Architecture-specific bootloader payloads for the generated ISOs
RUN apt-get update && \
    ARCH=$(dpkg --print-architecture) && \
    if [ "$ARCH" = "amd64" ]; then \
        apt-get install -y --no-install-recommends \
            isolinux syslinux grub-pc-bin grub-efi-amd64-bin; \
    else \
        apt-get install -y --no-install-recommends \
            grub-efi-$ARCH-bin || true; \
    fi && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
# --break-system-packages is fine inside the container
RUN pip3 install --break-system-packages --no-cache-dir -r requirements.txt

COPY . /app

RUN mkdir -p /app/cache/packages /app/builds /app/data

EXPOSE 8000

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
