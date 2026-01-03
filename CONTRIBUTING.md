# Contributing to Text-to-Linux-OS Builder

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/text-to-linux-os`
3. Create a branch: `git checkout -b feature/your-feature-name`
4. Make your changes
5. Test your changes
6. Commit with clear messages
7. Push to your fork
8. Open a Pull Request

## Development Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Add your ANTHROPIC_API_KEY

# Run locally
uvicorn backend.main:app --reload
```

## Code Style

- **Python**: Follow PEP 8
- **JavaScript**: Use ES6+ features
- **Formatting**: Use consistent indentation (4 spaces for Python, 2 for JS)
- **Comments**: Write clear, helpful comments

## Commit Messages

Use clear, descriptive commit messages:

```
Good: "Add theme preview to project gallery"
Bad: "Update files"

Good: "Fix ISO size calculation for large packages"
Bad: "Fix bug"
```

## Pull Request Process

1. Update documentation if needed
2. Add tests for new features
3. Ensure all tests pass
4. Update CHANGELOG.md
5. Request review from maintainers

## Areas for Contribution

### High Priority
- [ ] Add comprehensive test suite
- [ ] Improve error handling
- [ ] Add QEMU integration for ISO testing
- [ ] Multi-architecture support (ARM64)

### Features
- [ ] Additional theme presets
- [ ] Custom kernel configuration
- [ ] Package search/autocomplete
- [ ] ISO templates library

### Documentation
- [ ] Video tutorials
- [ ] More usage examples
- [ ] Troubleshooting guide expansion
- [ ] Architecture diagrams

### Bug Fixes
Check the [Issues](https://github.com/lalomorales22/text-to-linux-os/issues) page for open bugs.

## Code Review Process

All submissions require review. We use GitHub pull requests for this purpose.

Reviewers will check for:
- Code quality and style
- Test coverage
- Documentation updates
- Breaking changes

## Community Guidelines

- Be respectful and inclusive
- Help others in discussions
- Share knowledge and experiences
- Follow the Code of Conduct

## Questions?

- Open an issue for bugs
- Use discussions for questions
- Tag maintainers for urgent issues

## License

By contributing, you agree that your contributions will be licensed under the GPL-3.0 License.
