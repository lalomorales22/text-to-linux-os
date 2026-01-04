# Text-to-Linux-OS Builder

Build custom Debian-based Linux ISOs through an AI-powered chatbot wizard. Create bootable, minimal distributions tailored to your exact needs - from hardware optimization to package selection.

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![License](https://img.shields.io/badge/license-GPL--3.0-green)
![Python](https://img.shields.io/badge/python-3.11+-blue)

## Features

### 🤖 AI-Powered Configuration
- Conversational wizard powered by Claude Opus 4.5
- Intelligent package suggestions based on use case
- Automatic conflict detection
- Real-time ISO size estimation
- Hardware-optimized configurations

### 🎨 Random Theme Generator
- One-click theme randomization
- Custom OpenBox window manager themes
- Terminal color schemes
- Panel/taskbar theming
- GRUB bootloader customization
- ASCII boot screen animations

### 💿 Automated ISO Building
- Debian live-build integration
- Real-time build progress streaming
- AI-powered error analysis and fixes
- Package caching for faster rebuilds
- Bootable ISO validation

### 📦 Project Management
- Multiple project support
- Version control per project
- Project gallery with previews
- Download management
- Conversation history

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Anthropic API key ([Get one here](https://console.anthropic.com/))
- 20GB+ free disk space (for builds)
- 4GB+ RAM recommended

### Installation

```bash
# Clone the repository
git clone https://github.com/lalomorales22/text-to-linux-os
cd text-to-linux-os

# Create environment file
cp .env.example .env

# Add your Anthropic API key to .env
echo "ANTHROPIC_API_KEY=your-key-here" >> .env

# Start the application
docker-compose -f docker/docker-compose.yml up --build
```

The application will be available at **http://localhost:8000**

## Usage

### Creating Your First ISO

1. **Open the application** at http://localhost:8000
2. **Click "Start Building Your OS"**
3. **Chat with the AI wizard**:
   - Describe your hardware (RAM, CPU, storage)
   - Specify your use case (development, browsing, media, etc.)
   - Request specific packages and tools
   - Review the configuration

4. **Customize the theme** (optional):
   - Click "Randomize Theme" until you find colors you like
   - Preview shows OpenBox, terminal, and panel colors

5. **Build the ISO**:
   - Click "Build ISO" when ready
   - Monitor real-time build progress
   - Download when complete (typically 30-60 minutes)

6. **Use your ISO**:
   - Write to USB drive with tools like `dd`, Rufus, or Etcher
   - Boot on target hardware
   - Enjoy your custom Linux distribution!

### Example Conversation

```
AI: How much RAM do you have?
You: 8GB

AI: What's your primary use case?
You: Development with Python and Node.js

AI: Great! I'll include:
- Python 3.11 and pip
- Node.js and npm
- Git for version control
- VSCode (code-oss)
- Firefox ESR for browsing

Current size estimate: ~1.8GB

Would you like to add anything else?
You: Add Docker

AI: Added Docker! Final size: ~2.1GB
Ready to build!
```

## Architecture

### Technology Stack

- **Backend**: Python 3.11 + FastAPI
- **Frontend**: Vanilla JavaScript + Tailwind CSS
- **Database**: SQLite
- **Build System**: Debian live-build
- **AI**: Anthropic Claude Opus 4.5
- **Containerization**: Docker + Docker Compose
- **Window Manager**: OpenBox (for generated ISOs)

### Project Structure

```
text-to-linux-os/
├── backend/
│   ├── main.py              # FastAPI application
│   ├── api/                 # API endpoints
│   │   ├── chatbot.py       # AI chatbot logic
│   │   ├── builder.py       # ISO build orchestration
│   │   └── projects.py      # Project management
│   ├── database/
│   │   ├── models.py        # Pydantic models
│   │   └── db.py            # SQLite operations
│   ├── builder/
│   │   ├── config_generator.py    # live-build configs
│   │   ├── live_build.py          # Build orchestration
│   │   ├── theme_generator.py     # Theme generation
│   │   └── error_handler.py       # AI error analysis
│   └── utils/
│       └── validators.py    # Input validation
├── frontend/
│   ├── index.html           # Main UI
│   ├── css/styles.css       # Custom styles
│   └── js/
│       ├── app.js           # Main controller
│       ├── chatbot.js       # Chat interface
│       ├── theme-randomizer.js    # Theme UI
│       └── project-gallery.js     # Project gallery
├── templates/
│   ├── openbox/             # OpenBox configs
│   ├── plymouth-ascii/      # Boot screen themes
│   └── grub/                # GRUB themes
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── entrypoint.sh
└── builds/                  # Generated ISOs
```

## API Documentation

Once running, visit http://localhost:8000/docs for interactive API documentation.

### Key Endpoints

#### Chatbot
- `POST /api/chat/message` - Send message to AI
- `GET /api/chat/history/{project_id}` - Get conversation history

#### Builder
- `POST /api/build/start` - Start ISO build
- `POST /api/build/retry/{project_id}` - Retry failed build
- `GET /api/build/status/{build_id}` - Get build status
- `GET /api/build/logs/{build_id}` - Get build logs
- `POST /api/build/cancel/{build_id}` - Cancel running build

#### Projects
- `POST /api/projects/create` - Create new project
- `GET /api/projects/list` - List all projects
- `GET /api/projects/{id}` - Get project details
- `GET /api/projects/download/{id}/v{version}` - Download ISO

#### Themes
- `POST /api/projects/theme/randomize` - Generate random theme
- `POST /api/projects/{id}/theme/apply` - Apply theme to project

## Configuration

### Environment Variables

```bash
ANTHROPIC_API_KEY=your-api-key-here
DATABASE_URL=sqlite:///./data/text-to-linux-os.db
MAX_ISO_SIZE_GB=3
BUILD_TIMEOUT_MINUTES=120
LOG_LEVEL=INFO
```

### Default Packages

Every ISO includes these essential packages:
- `linux-image-amd64` - Linux kernel
- `live-boot` - Live system support
- `systemd` - Init system
- `network-manager` - Network management
- `xorg` - X Window System
- `openbox` - Window manager
- `tint2` - Panel/taskbar
- `pcmanfm` - File manager
- `lxterminal` - Terminal emulator
- `firefox-esr` - Web browser

## Advanced Usage

### Custom Package Lists

The AI can add any package from Debian repositories:

```
- Development: build-essential, gcc, make
- Languages: python3, nodejs, ruby, go
- Editors: vim, nano, code-oss
- Tools: git, docker, curl, wget
- Media: vlc, gimp, inkscape
```

### Theme Customization

Themes control:
- Window borders and title bars
- Terminal color schemes (16 colors)
- Panel background and active task highlighting
- GRUB boot menu appearance
- Plymouth boot animation

### Build Process

1. **Configuration Generation**: Creates live-build config files
2. **Package Download**: Downloads and caches .deb packages
3. **Root Filesystem Build**: Installs packages into chroot
4. **Theme Application**: Applies custom themes
5. **ISO Creation**: Generates bootable hybrid ISO
6. **Validation**: Checks ISO integrity and size

### Error Handling

If a build fails:
1. Logs are automatically analyzed by Claude AI
2. Suggestions are provided (e.g., "Package X not found, try Y")
3. Configuration can be updated and rebuild attempted
4. All attempts are logged for debugging

## Development

### Running Locally

```bash
# Install Python dependencies
pip install -r requirements.txt

# Initialize database
python -c "from backend.database.db import init_db; init_db()"

# Run development server
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### Running Tests

```bash
# Coming soon
pytest tests/
```

## Troubleshooting

### Build Fails with "live-build (lb) command not found"

This error occurs when live-build is not installed on your system. This application **requires** a Debian/Ubuntu Linux environment to build ISOs.

**Solutions:**

1. **Use Docker (Recommended)**: The Docker setup includes all required dependencies
   ```bash
   docker-compose -f docker/docker-compose.yml up --build
   ```

2. **Running on Linux**: Install live-build directly
   ```bash
   sudo apt-get update
   sudo apt-get install -y live-build debootstrap
   ```

3. **Running on macOS/Windows**: Use Docker or a Linux VM
   - macOS: live-build is not supported natively
   - Windows: Use WSL2 with Ubuntu or Docker

**Note**: The backend will automatically detect if live-build is missing and provide helpful error messages with installation instructions.

### Build Fails with "Package not found"

The AI will suggest alternatives. Common fixes:
- `chrome` → `chromium` or `firefox-esr`
- `vscode` → `code-oss`
- `python` → `python3`

### ISO Too Large

- Remove unnecessary packages
- Use minimal alternatives (e.g., `nano` instead of `vim`)
- Skip large applications like LibreOffice

### Docker Permission Issues

```bash
# Add your user to docker group
sudo usermod -aG docker $USER

# Or run with sudo
sudo docker-compose up
```

### API Key Not Working

1. Check `.env` file exists and contains valid key
2. Restart docker containers: `docker-compose restart`
3. Check logs: `docker-compose logs -f`

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

GPL-3.0 License - See LICENSE file for details

## Credits

- **Built with**: [Anthropic Claude](https://www.anthropic.com/)
- **Based on**: [Debian live-build](https://wiki.debian.org/DebianLive)
- **UI Framework**: [Tailwind CSS](https://tailwindcss.com/)
- **Icon Font**: System fonts

## Roadmap

- [ ] QEMU integration for ISO testing
- [ ] Multi-architecture support (ARM64)
- [ ] Persistent storage options
- [ ] Custom kernel configurations
- [ ] Cloud deployment templates
- [ ] Pre-built ISO templates
- [ ] Community package repository

## Support

- **Issues**: [GitHub Issues](https://github.com/lalomorales22/text-to-linux-os/issues)
- **Discussions**: [GitHub Discussions](https://github.com/lalomorales22/text-to-linux-os/discussions)

## Acknowledgments

Special thanks to:
- The Debian live-build team
- Anthropic for Claude API
- The open-source community

---

**Made with ❤️ by the Text-to-Linux-OS team**
