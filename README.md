# Weirding Host Utility

A command-line tool to configure external drives as portable AI servers (Weirding Modules) and to prepare host systems to use them.

## Features

- **Module Setup**: Interactively partition and format an external storage device.
- **OS Installation**: Install a minimal, headless Linux OS (Debian) onto the module.
- **AI Stack Deployment**: Automatically install and configure Ollama, HuggingFace Transformers, and other ML tools.
- **Host Configuration**: Prepare a host system to mount and utilize a Weirding Module for AI tasks.

## Installation

```bash
# Clone the repository
git clone https://github.com/your-username/weirding-host.git
cd weirding-host

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Setting up a Weirding Module

This command will guide you through selecting a drive and installing the necessary software.

```bash
python main.py setup-module
```

### Configuring a Host System

This command will prepare your current system to work with a pre-existing Weirding Module.

```bash
python main.py setup-host
```

## Development

To contribute to development, please see the `.gemini` file for project configuration and guidelines.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
