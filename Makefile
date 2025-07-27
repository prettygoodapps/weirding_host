# Weirding Host Utility - Makefile
# Portable AI Server Setup Tool

.PHONY: help setup install deps clean dev-setup standalone list-drives relabel-drive setup-module version test

# Default target
.DEFAULT_GOAL := help

# Python and virtual environment settings
PYTHON := python3
VENV := .venv
VENV_BIN := $(VENV)/bin
PIP := $(VENV_BIN)/pip
PYTHON_VENV := $(VENV_BIN)/python

# Project files
STANDALONE_SCRIPT := weirding-setup
INSTALL_SCRIPT := install-deps.sh
MAIN_SCRIPT := main.py

help: ## Show this help message
	@echo "Weirding Host Utility - Makefile Commands"
	@echo "========================================"
	@echo ""
	@echo "Setup Commands:"
	@echo "  make setup          - Complete project setup (recommended for new clones)"
	@echo "  make install        - Install dependencies using install-deps.sh"
	@echo "  make dev-setup      - Set up development environment with virtual env"
	@echo "  make deps           - Install Python dependencies in virtual environment"
	@echo ""
	@echo "Usage Commands (Standalone):"
	@echo "  make list-drives    - List all available drives"
	@echo "  make relabel-drive  - Relabel an external drive (requires sudo)"
	@echo "  make setup-module   - Set up a Weirding Module (requires sudo)"
	@echo "  make version        - Show version information"
	@echo ""
	@echo "Development Commands:"
	@echo "  make dev-list       - List drives using development environment"
	@echo "  make dev-relabel    - Relabel drive using development environment"
	@echo "  make dev-setup-mod  - Setup module using development environment"
	@echo "  make dev-version    - Show version using development environment"
	@echo ""
	@echo "Utility Commands:"
	@echo "  make clean          - Clean up generated files and caches"
	@echo "  make test           - Run basic functionality tests"
	@echo "  make permissions    - Fix script permissions"
	@echo ""
	@echo "For first-time setup after cloning, run: make setup"

setup: permissions install ## Complete setup for new project clone
	@echo "✅ Weirding Host Utility setup complete!"
	@echo ""
	@echo "Available commands:"
	@echo "  make list-drives    - List available drives"
	@echo "  make relabel-drive  - Relabel external drive (sudo required)"
	@echo "  make setup-module   - Setup Weirding Module (sudo required)"
	@echo ""
	@echo "For development with virtual environment:"
	@echo "  make dev-setup      - Setup development environment"
	@echo "  source venv/bin/activate  - Activate virtual environment"

permissions: ## Make scripts executable
	@echo "Setting script permissions..."
	@chmod +x $(STANDALONE_SCRIPT)
	@chmod +x $(INSTALL_SCRIPT)
	@echo "✅ Script permissions set"

install: permissions ## Install dependencies using install-deps.sh
	@echo "Installing dependencies..."
	@./$(INSTALL_SCRIPT)

dev-setup: $(VENV) deps ## Set up development environment with virtual environment
	@echo "✅ Development environment ready!"
	@echo "Activate with: source $(VENV_BIN)/activate"

$(VENV): ## Create virtual environment
	@echo "Creating virtual environment..."
	@$(PYTHON) -m venv $(VENV)
	@echo "✅ Virtual environment created"

deps: $(VENV) ## Install Python dependencies in virtual environment
	@echo "Installing Python dependencies in virtual environment..."
	@$(PIP) install --upgrade pip
	@$(PIP) install typer rich questionary
	@echo "✅ Dependencies installed in virtual environment"

# Standalone utility commands
list-drives: permissions ## List all available drives using standalone utility
	@./$(STANDALONE_SCRIPT) list-drives

relabel-drive: permissions ## Relabel an external drive using standalone utility (requires sudo)
	@echo "⚠️  This command requires sudo privileges for drive operations"
	@sudo ./$(STANDALONE_SCRIPT) relabel-drive

setup-module: permissions ## Set up a Weirding Module using standalone utility (requires sudo)
	@echo "⚠️  This command requires sudo privileges for drive operations"
	@sudo ./$(STANDALONE_SCRIPT) setup-module

version: permissions ## Show version information using standalone utility
	@./$(STANDALONE_SCRIPT) version

# Development environment commands
dev-list: $(VENV) ## List drives using development environment
	@$(PYTHON_VENV) $(MAIN_SCRIPT) list-drives

dev-relabel: $(VENV) ## Relabel drive using development environment (requires sudo)
	@echo "⚠️  This command requires sudo privileges for drive operations"
	@sudo $(PYTHON_VENV) $(MAIN_SCRIPT) relabel-drive

dev-setup-mod: $(VENV) ## Setup module using development environment (requires sudo)
	@echo "⚠️  This command requires sudo privileges for drive operations"
	@sudo $(PYTHON_VENV) $(MAIN_SCRIPT) setup-module

dev-version: $(VENV) ## Show version using development environment
	@$(PYTHON_VENV) $(MAIN_SCRIPT) version

test: permissions ## Run basic functionality tests
	@echo "Running basic functionality tests..."
	@echo "Testing standalone script..."
	@./$(STANDALONE_SCRIPT) version > /dev/null && echo "✅ Standalone script works" || echo "❌ Standalone script failed"
	@echo "Testing dependency detection..."
	@./$(STANDALONE_SCRIPT) list-drives --help > /dev/null && echo "✅ Dependencies available" || echo "⚠️  Dependencies may need installation"
	@echo "Testing script permissions..."
	@test -x $(STANDALONE_SCRIPT) && echo "✅ Standalone script is executable" || echo "❌ Standalone script not executable"
	@test -x $(INSTALL_SCRIPT) && echo "✅ Install script is executable" || echo "❌ Install script not executable"

test-unit: $(VENV) ## Run unit tests
	@echo "Running unit tests..."
	@$(PYTHON_VENV) -m pytest tests/test_device_setup.py -v || $(PYTHON_VENV) tests/test_device_setup.py

test-integration: $(VENV) ## Run integration tests
	@echo "Running integration tests..."
	@$(PYTHON_VENV) -m pytest tests/test_cli_integration.py -v || $(PYTHON_VENV) tests/test_cli_integration.py

test-all: $(VENV) ## Run comprehensive test suite
	@echo "Running comprehensive test suite..."
	@$(PYTHON_VENV) tests/run_tests.py

clean: ## Clean up generated files and caches
	@echo "Cleaning up..."
	@rm -rf __pycache__/
	@rm -rf modules/__pycache__/
	@rm -rf *.pyc
	@rm -rf .pytest_cache/
	@rm -rf build/
	@rm -rf dist/
	@rm -rf *.egg-info/
	@echo "✅ Cleanup complete"

clean-all: clean ## Clean everything including virtual environment
	@echo "Removing virtual environment..."
	@rm -rf $(VENV)
	@echo "✅ Complete cleanup finished"

# Development shortcuts
run: list-drives ## Alias for list-drives
dev: dev-setup ## Alias for dev-setup
check: test ## Alias for test

# Show project status
status: ## Show project status and available commands
	@echo "Weirding Host Utility - Project Status"
	@echo "====================================="
	@echo ""
	@echo "Scripts:"
	@test -x $(STANDALONE_SCRIPT) && echo "✅ $(STANDALONE_SCRIPT) (executable)" || echo "❌ $(STANDALONE_SCRIPT) (not executable)"
	@test -x $(INSTALL_SCRIPT) && echo "✅ $(INSTALL_SCRIPT) (executable)" || echo "❌ $(INSTALL_SCRIPT) (not executable)"
	@test -f $(MAIN_SCRIPT) && echo "✅ $(MAIN_SCRIPT) (present)" || echo "❌ $(MAIN_SCRIPT) (missing)"
	@echo ""
	@echo "Virtual Environment:"
	@test -d $(VENV) && echo "✅ Virtual environment exists" || echo "❌ Virtual environment not created"
	@test -f $(VENV_BIN)/python && echo "✅ Python available in venv" || echo "❌ Python not available in venv"
	@echo ""
	@echo "Dependencies (system):"
	@python3 -c "import typer" 2>/dev/null && echo "✅ typer available" || echo "❌ typer not available"
	@python3 -c "import rich" 2>/dev/null && echo "✅ rich available" || echo "❌ rich not available"
	@python3 -c "import questionary" 2>/dev/null && echo "✅ questionary available" || echo "❌ questionary not available"
	@echo ""
	@echo "Run 'make help' for available commands"
