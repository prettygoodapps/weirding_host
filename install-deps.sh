#!/bin/bash
"""
Dependency Installation Script for Weirding Module Setup Utility

This script attempts to install the required Python packages using various methods.
"""

echo "🔧 Installing dependencies for Weirding Module Setup Utility..."
echo

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if a Python package is installed
python_package_exists() {
    python3 -c "import $1" >/dev/null 2>&1
}

# Check what's already installed
echo "📋 Checking current installation status..."
packages=("typer" "rich" "questionary")
missing_packages=()

for package in "${packages[@]}"; do
    if python_package_exists "$package"; then
        echo "✅ $package is already installed"
    else
        echo "❌ $package is missing"
        missing_packages+=("$package")
    fi
done

if [ ${#missing_packages[@]} -eq 0 ]; then
    echo
    echo "🎉 All dependencies are already installed!"
    echo "You can now run: ./weirding-setup --help"
    exit 0
fi

echo
echo "📦 Installing missing packages: ${missing_packages[*]}"
echo

# Try different installation methods
if command_exists pip3; then
    echo "🔄 Attempting installation with pip3..."
    if pip3 install --user "${missing_packages[@]}"; then
        echo "✅ Successfully installed dependencies with pip3!"
        echo "You can now run: ./weirding-setup --help"
        exit 0
    else
        echo "❌ pip3 installation failed"
    fi
elif command_exists pip; then
    echo "🔄 Attempting installation with pip..."
    if pip install --user "${missing_packages[@]}"; then
        echo "✅ Successfully installed dependencies with pip!"
        echo "You can now run: ./weirding-setup --help"
        exit 0
    else
        echo "❌ pip installation failed"
    fi
fi

# Try apt installation (Ubuntu/Debian)
if command_exists apt; then
    echo "🔄 Attempting installation with apt..."
    apt_packages=()
    for package in "${missing_packages[@]}"; do
        apt_packages+=("python3-$package")
    done
    
    if sudo apt update && sudo apt install -y "${apt_packages[@]}"; then
        echo "✅ Successfully installed dependencies with apt!"
        echo "You can now run: ./weirding-setup --help"
        exit 0
    else
        echo "❌ apt installation failed or packages not available"
    fi
fi

# Try using the virtual environment
if [ -d "venv" ] && [ -f "requirements.txt" ]; then
    echo "🔄 Attempting installation using virtual environment..."
    if source venv/bin/activate && pip install -r requirements.txt; then
        echo "✅ Successfully installed dependencies in virtual environment!"
        echo "To use the utility, either:"
        echo "1. Activate the virtual environment: source venv/bin/activate"
        echo "2. Or use: ./venv/bin/python main.py --help"
        exit 0
    else
        echo "❌ Virtual environment installation failed"
    fi
fi

# If all methods failed
echo
echo "❌ Automatic installation failed. Please install manually:"
echo
echo "Method 1 - Using pip:"
echo "  pip3 install --user ${missing_packages[*]}"
echo
echo "Method 2 - Using system package manager (Ubuntu/Debian):"
for package in "${missing_packages[@]}"; do
    echo "  sudo apt install python3-$package"
done
echo
echo "Method 3 - Using virtual environment:"
echo "  python3 -m venv venv"
echo "  source venv/bin/activate"
echo "  pip install ${missing_packages[*]}"
echo
echo "After installation, run: ./weirding-setup --help"
exit 1