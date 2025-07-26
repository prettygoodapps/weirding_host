# Weirding Host Utility

A command-line tool to configure external drives as portable AI servers (Weirding Modules) and to prepare host systems to use them.

## Features

- **Module Setup**: Interactively partition and format an external storage device.
- **OS Installation**: Install a minimal, headless Linux OS (Debian) onto the module.
- **AI Stack Deployment**: Automatically install and configure Ollama, HuggingFace Transformers, and other ML tools.
- **Host Configuration**: Prepare a host system to mount and utilize a Weirding Module for AI tasks.

## Installation

### Quick Setup with Makefile (Recommended)

```bash
# Clone the repository
git clone https://github.com/your-username/weirding-host.git
cd weirding-host

# Complete setup (sets permissions, installs dependencies)
make setup

# Show all available commands
make help
```

### Manual Installation

```bash
# Clone the repository
git clone https://github.com/your-username/weirding-host.git
cd weirding-host

# Make scripts executable
chmod +x weirding-setup install-deps.sh

# Install dependencies
./install-deps.sh
```

## Usage

### Using Makefile (Recommended)

The easiest way to use the Weirding Host Utility after running `make setup`:

```bash
# List available drives
make list-drives

# Relabel an external drive (requires sudo)
make relabel-drive

# Set up a Weirding Module (requires sudo)
make setup-module

# Show version information
make version

# Show all available commands
make help

# Check project status
make status

# Run basic functionality tests
make test
```

### Standalone Script Usage

You can also use the standalone script directly:

```bash
# List available drives
./weirding-setup list-drives

# Relabel an external drive
sudo ./weirding-setup relabel-drive

# Set up a Weirding Module
sudo ./weirding-setup setup-module

# Show version information
./weirding-setup version
```

### Development Mode (Virtual Environment)

For development or if you prefer using the virtual environment:

```bash
# Set up development environment with Makefile
make dev-setup
source venv/bin/activate

# OR manually:
# python3 -m venv venv
# source venv/bin/activate
# pip install typer rich questionary

# Using Makefile development commands:
make dev-list          # List drives
make dev-relabel       # Relabel drives (requires sudo)
make dev-setup-mod     # Setup module (requires sudo)
make dev-version       # Show version

# OR using main.py directly:
python main.py list-drives
sudo python main.py relabel-drive
sudo python main.py setup-module
```

## Development

### Available Makefile Commands

```bash
# Setup and Installation
make setup             # Complete project setup
make dev-setup         # Set up development environment
make install           # Install dependencies
make permissions       # Fix script permissions

# Usage Commands
make list-drives       # List available drives
make relabel-drive     # Relabel external drive (sudo)
make setup-module      # Setup Weirding Module (sudo)
make version           # Show version information

# Development Commands
make dev-list          # List drives (dev environment)
make dev-relabel       # Relabel drive (dev environment)
make dev-setup-mod     # Setup module (dev environment)
make dev-version       # Show version (dev environment)

# Utility Commands
make test              # Run basic functionality tests
make status            # Show project status
make clean             # Clean up generated files
make clean-all         # Clean everything including venv
make help              # Show all available commands
```

To contribute to development, please see the `.gemini` file for project configuration and guidelines.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
