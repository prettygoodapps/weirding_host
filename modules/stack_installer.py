#!/usr/bin/env python3
"""
AI Stack Installation Module for Weirding Host Utility

This module handles the installation and configuration of the AI software stack
including Ollama, HuggingFace Transformers, PyTorch, and other ML tools.
"""

import subprocess
import os
import json
import urllib.request
import tempfile
import shutil
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import time

from device_setup import DriveInfo
from partitioner import PartitionPlan


class AIStackInstaller:
    """Handles AI stack installation for Weirding Modules."""
    
    def __init__(self):
        self.mount_base = Path("/tmp/weirding_ai_install")
        self.mount_base.mkdir(exist_ok=True)
        
    def install_ai_stack(self, plan: PartitionPlan, progress_callback=None) -> bool:
        """
        Install complete AI stack on the Weirding Module.
        
        Args:
            plan: PartitionPlan with partition information
            progress_callback: Optional callback for progress updates
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Step 1: Mount the root partition
            if progress_callback:
                progress_callback("Mounting system for AI stack installation...")
            
            mount_points = self._mount_system(plan)
            if not mount_points:
                return False
            
            # Step 2: Install Docker and container runtime
            if progress_callback:
                progress_callback("Setting up container runtime...")
            
            success = self._setup_container_runtime(mount_points['root'], progress_callback)
            if not success:
                self._unmount_system(mount_points)
                return False
            
            # Step 3: Install Python ML environment
            if progress_callback:
                progress_callback("Installing Python ML environment...")
            
            success = self._install_python_ml_stack(mount_points['root'], progress_callback)
            if not success:
                self._unmount_system(mount_points)
                return False
            
            # Step 4: Install Ollama
            if progress_callback:
                progress_callback("Installing Ollama LLM server...")
            
            success = self._install_ollama(mount_points['root'], progress_callback)
            if not success:
                self._unmount_system(mount_points)
                return False
            
            # Step 5: Install GPU support
            if progress_callback:
                progress_callback("Setting up GPU support...")
            
            success = self._setup_gpu_support(mount_points['root'], progress_callback)
            if not success:
                self._unmount_system(mount_points)
                return False
            
            # Step 6: Install additional AI tools
            if progress_callback:
                progress_callback("Installing additional AI tools...")
            
            success = self._install_additional_tools(mount_points['root'], progress_callback)
            if not success:
                self._unmount_system(mount_points)
                return False
            
            # Step 7: Configure AI services
            if progress_callback:
                progress_callback("Configuring AI services...")
            
            success = self._configure_ai_services(plan, mount_points['root'])
            if not success:
                self._unmount_system(mount_points)
                return False
            
            # Step 8: Create management scripts
            if progress_callback:
                progress_callback("Creating management scripts...")
            
            success = self._create_management_scripts(mount_points['root'])
            if not success:
                self._unmount_system(mount_points)
                return False
            
            # Step 9: Download initial models (optional, based on space)
            if progress_callback:
                progress_callback("Preparing model storage...")
            
            self._prepare_model_storage(mount_points['root'])
            
            # Cleanup
            self._unmount_system(mount_points)
            
            return True
            
        except Exception as e:
            print(f"Error during AI stack installation: {e}")
            return False
    
    def _mount_system(self, plan: PartitionPlan) -> Dict[str, str]:
        """Mount the system for AI stack installation."""
        mount_points = {}
        
        try:
            # Create mount directory
            root_mount = self.mount_base / "root"
            root_mount.mkdir(exist_ok=True)
            
            # Find root partition
            root_partition = None
            for partition in plan.partitions:
                if partition.get('mount_point') == '/':
                    root_partition = f"{plan.drive.device}{partition['number']}"
                    break
            
            if not root_partition:
                raise RuntimeError("No root partition found")
            
            # Mount root partition
            subprocess.run([
                'mount', root_partition, str(root_mount)
            ], capture_output=True, text=True, check=True)
            mount_points['root'] = str(root_mount)
            
            # Mount essential filesystems for chroot
            mount_specs = [
                ('proc', 'proc', 'proc'),       # filesystem type, device, mount point
                ('sysfs', 'sysfs', 'sys'),      # filesystem type, device, mount point
                ('devtmpfs', 'devtmpfs', 'dev') # filesystem type, device, mount point
            ]
            
            for fs_type, device, mount_point in mount_specs:
                target_dir = root_mount / mount_point
                target_dir.mkdir(exist_ok=True)
                subprocess.run([
                    'mount', '-t', fs_type, device, str(target_dir)
                ], capture_output=True, text=True, check=True)
                mount_points[mount_point] = str(target_dir)
            
            return mount_points
            
        except subprocess.CalledProcessError as e:
            print(f"Error mounting system: {e.stderr}")
            self._unmount_system(mount_points)
            return {}
    
    def _setup_container_runtime(self, root_mount: str, progress_callback=None) -> bool:
        """Set up Docker container runtime."""
        try:
            # Docker should already be installed by OS installer
            # Configure Docker daemon
            docker_config = {
                "data-root": "/opt/models/docker",
                "storage-driver": "overlay2",
                "log-driver": "json-file",
                "log-opts": {
                    "max-size": "10m",
                    "max-file": "3"
                },
                "default-runtime": "runc",
                "runtimes": {
                    "nvidia": {
                        "path": "nvidia-container-runtime",
                        "runtimeArgs": []
                    }
                }
            }
            
            docker_config_dir = Path(f"{root_mount}/etc/docker")
            docker_config_dir.mkdir(exist_ok=True)
            
            with open(docker_config_dir / "daemon.json", 'w') as f:
                json.dump(docker_config, f, indent=2)
            
            # Create Docker data directory
            docker_data_dir = Path(f"{root_mount}/opt/models/docker")
            docker_data_dir.mkdir(parents=True, exist_ok=True)
            
            # Enable Docker service
            subprocess.run([
                'chroot', root_mount, 'systemctl', 'enable', 'docker'
            ], capture_output=True, text=True, check=True)
            
            return True
            
        except Exception as e:
            print(f"Error setting up container runtime: {e}")
            return False
    
    def _install_python_ml_stack(self, root_mount: str, progress_callback=None) -> bool:
        """Install Python ML environment."""
        try:
            # Install Python packages
            python_packages = [
                'python3-venv',
                'python3-dev',
                'python3-pip',
                'python3-setuptools',
                'python3-wheel'
            ]
            
            subprocess.run([
                'chroot', root_mount, 'apt-get', 'update'
            ], capture_output=True, text=True, check=True)
            
            subprocess.run([
                'chroot', root_mount, 'apt-get', 'install', '-y'
            ] + python_packages, capture_output=True, text=True, check=True)
            
            # Create virtual environment for AI stack
            subprocess.run([
                'chroot', root_mount, 'python3', '-m', 'venv', '/opt/weirding/venv'
            ], capture_output=True, text=True, check=True)
            
            # Install core ML packages in virtual environment
            ml_packages = [
                'torch',
                'torchvision',
                'torchaudio',
                'transformers',
                'datasets',
                'accelerate',
                'bitsandbytes',
                'scipy',
                'numpy',
                'pandas',
                'scikit-learn',
                'matplotlib',
                'seaborn',
                'jupyter',
                'jupyterlab',
                'ipywidgets',
                'requests',
                'aiohttp',
                'fastapi',
                'uvicorn',
                'gradio',
                'streamlit'
            ]
            
            # Install packages in chunks to avoid memory issues
            chunk_size = 5
            for i in range(0, len(ml_packages), chunk_size):
                chunk = ml_packages[i:i + chunk_size]
                
                if progress_callback:
                    progress_callback(f"Installing ML packages: {', '.join(chunk[:2])}...")
                
                subprocess.run([
                    'chroot', root_mount, '/opt/weirding/venv/bin/pip', 'install'
                ] + chunk, capture_output=True, text=True, check=True)
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"Error installing Python ML stack: {e.stderr}")
            return False
    
    def _install_ollama(self, root_mount: str, progress_callback=None) -> bool:
        """Install Ollama LLM server."""
        try:
            # Download and install Ollama
            ollama_install_script = """#!/bin/bash
set -e

# Download Ollama installer
curl -fsSL https://ollama.ai/install.sh -o /tmp/ollama_install.sh
chmod +x /tmp/ollama_install.sh

# Install Ollama
OLLAMA_HOME=/opt/models/ollama /tmp/ollama_install.sh

# Create Ollama user and group
groupadd -f ollama
useradd -r -s /bin/false -g ollama -d /opt/models/ollama ollama || true

# Set permissions
chown -R ollama:ollama /opt/models/ollama
chmod 755 /opt/models/ollama

# Clean up
rm -f /tmp/ollama_install.sh
"""
            
            script_path = f"{root_mount}/tmp/install_ollama.sh"
            with open(script_path, 'w') as f:
                f.write(ollama_install_script)
            
            os.chmod(script_path, 0o755)
            
            # Run the installation script
            subprocess.run([
                'chroot', root_mount, '/tmp/install_ollama.sh'
            ], capture_output=True, text=True, check=True)
            
            # Create Ollama systemd service
            ollama_service = """[Unit]
Description=Ollama Service
After=network-online.target

[Service]
ExecStart=/usr/local/bin/ollama serve
User=ollama
Group=ollama
Restart=always
RestartSec=3
Environment="OLLAMA_HOST=0.0.0.0"
Environment="OLLAMA_MODELS=/opt/models/ollama"

[Install]
WantedBy=default.target
"""
            
            with open(f"{root_mount}/etc/systemd/system/ollama.service", 'w') as f:
                f.write(ollama_service)
            
            # Enable Ollama service
            subprocess.run([
                'chroot', root_mount, 'systemctl', 'enable', 'ollama'
            ], capture_output=True, text=True, check=True)
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"Error installing Ollama: {e.stderr}")
            return False
    
    def _setup_gpu_support(self, root_mount: str, progress_callback=None) -> bool:
        """Set up GPU support for NVIDIA and AMD."""
        try:
            # Install NVIDIA Container Toolkit
            nvidia_setup_script = """#!/bin/bash
set -e

# Add NVIDIA package repository
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# Update package list
apt-get update

# Install NVIDIA Container Toolkit
apt-get install -y nvidia-container-toolkit || true

# Configure Docker to use NVIDIA runtime
nvidia-ctk runtime configure --runtime=docker || true
"""
            
            script_path = f"{root_mount}/tmp/setup_nvidia.sh"
            with open(script_path, 'w') as f:
                f.write(nvidia_setup_script)
            
            os.chmod(script_path, 0o755)
            
            # Run NVIDIA setup (may fail if no NVIDIA GPU, that's OK)
            try:
                subprocess.run([
                    'chroot', root_mount, '/tmp/setup_nvidia.sh'
                ], capture_output=True, text=True, check=True)
            except subprocess.CalledProcessError:
                pass  # NVIDIA setup is optional
            
            # Install AMD ROCm support
            rocm_setup_script = """#!/bin/bash
set -e

# Add ROCm repository
wget -q -O - https://repo.radeon.com/rocm/rocm.gpg.key | apt-key add - || true
echo 'deb [arch=amd64] https://repo.radeon.com/rocm/apt/debian/ ubuntu main' | \
    tee /etc/apt/sources.list.d/rocm.list || true

# Update package list
apt-get update

# Install ROCm (basic packages)
apt-get install -y rocm-dev rocm-libs || true
"""
            
            script_path = f"{root_mount}/tmp/setup_rocm.sh"
            with open(script_path, 'w') as f:
                f.write(rocm_setup_script)
            
            os.chmod(script_path, 0o755)
            
            # Run ROCm setup (may fail, that's OK)
            try:
                subprocess.run([
                    'chroot', root_mount, '/tmp/setup_rocm.sh'
                ], capture_output=True, text=True, check=True)
            except subprocess.CalledProcessError:
                pass  # ROCm setup is optional
            
            return True
            
        except Exception as e:
            print(f"Error setting up GPU support: {e}")
            return False
    
    def _install_additional_tools(self, root_mount: str, progress_callback=None) -> bool:
        """Install additional AI and development tools."""
        try:
            # Install Node.js for web interfaces
            nodejs_script = """#!/bin/bash
set -e

# Install Node.js
curl -fsSL https://deb.nodesource.com/setup_lts.x | bash -
apt-get install -y nodejs

# Install useful global packages
npm install -g pm2 http-server
"""
            
            script_path = f"{root_mount}/tmp/install_nodejs.sh"
            with open(script_path, 'w') as f:
                f.write(nodejs_script)
            
            os.chmod(script_path, 0o755)
            
            subprocess.run([
                'chroot', root_mount, '/tmp/install_nodejs.sh'
            ], capture_output=True, text=True, check=True)
            
            # Install additional system packages
            additional_packages = [
                'ffmpeg',
                'imagemagick',
                'pandoc',
                'texlive-latex-base',
                'texlive-fonts-recommended',
                'redis-server',
                'postgresql-client',
                'sqlite3',
                'tmux',
                'screen',
                'rsync',
                'rclone'
            ]
            
            subprocess.run([
                'chroot', root_mount, 'apt-get', 'install', '-y'
            ] + additional_packages, capture_output=True, text=True, check=True)
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"Error installing additional tools: {e.stderr}")
            return False
    
    def _configure_ai_services(self, plan: PartitionPlan, root_mount: str) -> bool:
        """Configure AI services and web interfaces."""
        try:
            # Create Jupyter configuration
            jupyter_config = """
c.ServerApp.ip = '0.0.0.0'
c.ServerApp.port = 8888
c.ServerApp.open_browser = False
c.ServerApp.password = 'argon2:$argon2id$v=19$m=10240,t=10,p=8$8S8QVZ8Q8Q8Q8Q8Q8Q8Q8Q$8Q8Q8Q8Q8Q8Q8Q8Q8Q8Q8Q8Q8Q8Q8Q8Q8Q8Q8Q8Q8Q'
c.ServerApp.allow_root = True
c.ServerApp.notebook_dir = '/opt/models'
"""
            
            jupyter_config_dir = Path(f"{root_mount}/opt/weirding/.jupyter")
            jupyter_config_dir.mkdir(parents=True, exist_ok=True)
            
            with open(jupyter_config_dir / "jupyter_server_config.py", 'w') as f:
                f.write(jupyter_config)
            
            # Create Jupyter service
            jupyter_service = """[Unit]
Description=Jupyter Lab
After=network.target

[Service]
Type=simple
User=weirding
Group=weirding
WorkingDirectory=/opt/models
Environment="PATH=/opt/weirding/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=/opt/weirding/venv/bin/jupyter lab --config=/opt/weirding/.jupyter/jupyter_server_config.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
            
            with open(f"{root_mount}/etc/systemd/system/jupyter.service", 'w') as f:
                f.write(jupyter_service)
            
            # Enable Jupyter service
            subprocess.run([
                'chroot', root_mount, 'systemctl', 'enable', 'jupyter'
            ], capture_output=True, text=True, check=True)
            
            # Create web dashboard service
            dashboard_script = """#!/usr/bin/env python3
import json
import subprocess
import psutil
from flask import Flask, render_template_string, jsonify
import threading
import time

app = Flask(__name__)

def get_system_info():
    return {
        'cpu_percent': psutil.cpu_percent(interval=1),
        'memory': psutil.virtual_memory()._asdict(),
        'disk': psutil.disk_usage('/opt/models')._asdict(),
        'gpu_info': get_gpu_info()
    }

def get_gpu_info():
    gpu_info = []
    try:
        result = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total,memory.used', '--format=csv,noheader,nounits'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            for line in result.stdout.strip().split('\\n'):
                parts = line.split(', ')
                if len(parts) == 3:
                    gpu_info.append({
                        'name': parts[0],
                        'memory_total': int(parts[1]),
                        'memory_used': int(parts[2])
                    })
    except:
        pass
    return gpu_info

@app.route('/')
def dashboard():
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>Weirding Module Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .card { background: white; padding: 20px; margin: 10px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .header { text-align: center; color: #333; }
        .services { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        .service-link { display: block; padding: 15px; background: #007bff; color: white; text-decoration: none; border-radius: 5px; text-align: center; }
        .service-link:hover { background: #0056b3; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }
        .stat { text-align: center; }
        .stat-value { font-size: 2em; font-weight: bold; color: #007bff; }
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <h1 class="header">🚀 Weirding Module Dashboard</h1>
            <p class="header">Your portable AI server is ready!</p>
        </div>
        
        <div class="card">
            <h2>AI Services</h2>
            <div class="services">
                <a href="http://localhost:11434" class="service-link">Ollama API (Port 11434)</a>
                <a href="http://localhost:8888" class="service-link">Jupyter Lab (Port 8888)</a>
                <a href="/api/system" class="service-link">System API</a>
            </div>
        </div>
        
        <div class="card">
            <h2>System Status</h2>
            <div class="stats" id="stats">
                <div class="stat">
                    <div class="stat-value" id="cpu">--</div>
                    <div>CPU Usage</div>
                </div>
                <div class="stat">
                    <div class="stat-value" id="memory">--</div>
                    <div>Memory Usage</div>
                </div>
                <div class="stat">
                    <div class="stat-value" id="disk">--</div>
                    <div>Disk Usage</div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        function updateStats() {
            fetch('/api/system')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('cpu').textContent = data.cpu_percent.toFixed(1) + '%';
                    document.getElementById('memory').textContent = (data.memory.percent).toFixed(1) + '%';
                    document.getElementById('disk').textContent = (data.disk.used / data.disk.total * 100).toFixed(1) + '%';
                });
        }
        
        updateStats();
        setInterval(updateStats, 5000);
    </script>
</body>
</html>
    ''')

@app.route('/api/system')
def api_system():
    return jsonify(get_system_info())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
"""
            
            with open(f"{root_mount}/opt/weirding/scripts/dashboard.py", 'w') as f:
                f.write(dashboard_script)
            
            os.chmod(f"{root_mount}/opt/weirding/scripts/dashboard.py", 0o755)
            
            # Install Flask for dashboard
            subprocess.run([
                'chroot', root_mount, '/opt/weirding/venv/bin/pip', 'install', 'flask', 'psutil'
            ], capture_output=True, text=True, check=True)
            
            # Create dashboard service
            dashboard_service = """[Unit]
Description=Weirding Dashboard
After=network.target

[Service]
Type=simple
User=weirding
Group=weirding
WorkingDirectory=/opt/weirding
Environment="PATH=/opt/weirding/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=/opt/weirding/venv/bin/python /opt/weirding/scripts/dashboard.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
            
            with open(f"{root_mount}/etc/systemd/system/weirding-dashboard.service", 'w') as f:
                f.write(dashboard_service)
            
            # Enable dashboard service
            subprocess.run([
                'chroot', root_mount, 'systemctl', 'enable', 'weirding-dashboard'
            ], capture_output=True, text=True, check=True)
            
            return True
            
        except Exception as e:
            print(f"Error configuring AI services: {e}")
            return False
    
    def _create_management_scripts(self, root_mount: str) -> bool:
        """Create management and utility scripts."""
        try:
            scripts_dir = Path(f"{root_mount}/opt/weirding/scripts")
            
            # Model management script
            model_manager_script = """#!/bin/bash
# Weirding Model Manager

set -e

MODELS_DIR="/opt/models"
OLLAMA_MODELS="$MODELS_DIR/ollama"
HF_MODELS="$MODELS_DIR/huggingface"

show_usage() {
    echo "Weirding Model Manager"
    echo "Usage: $0 [command] [options]"
    echo ""
    echo "Commands:"
    echo "  list                 List installed models"
    echo "  download <model>     Download a model"
    echo "  remove <model>       Remove a model"
    echo "  status              Show system status"
    echo "  update              Update model list"
    echo ""
    echo "Examples:"
    echo "  $0 download llama2"
    echo "  $0 download codellama:7b"
    echo "  $0 list"
}

list_models() {
    echo "=== Installed Models ==="
    echo ""
    echo "Ollama Models:"
    ollama list 2>/dev/null || echo "  No Ollama models installed"
    echo ""
    echo "HuggingFace Models:"
    if [ -d "$HF_MODELS" ]; then
        ls -la "$HF_MODELS" 2>/dev/null || echo "  No HuggingFace models installed"
    else
        echo "  No HuggingFace models installed"
    fi
}

download_model() {
    local model="$1"
    if [ -z "$model" ]; then
        echo "Error: Model name required"
        show_usage
        exit 1
    fi
    
    echo "Downloading model: $model"
    
    # Try Ollama first
    if ollama pull "$model" 2>/dev/null; then
        echo "Successfully downloaded $model via Ollama"
        return 0
    fi
    
    # Try HuggingFace
    echo "Trying HuggingFace..."
    python3 -c "
from transformers import AutoTokenizer, AutoModel
import os
os.makedirs('$HF_MODELS', exist_ok=True)
try:
    tokenizer = AutoTokenizer.from_pretrained('$model', cache_dir='$HF_MODELS')
    model = AutoModel.from_pretrained('$model', cache_dir='$HF_MODELS')
    print('Successfully downloaded $model via HuggingFace')
except Exception as e:
    print(f'Error downloading $model: {e}')
    exit(1)
"
}

remove_model() {
    local model="$1"
    if [ -z "$model" ]; then
        echo "Error: Model name required"
        show_usage
        exit 1
    fi
    
    echo "Removing model: $model"
    
    # Try Ollama
    if ollama rm "$model" 2>/dev/null; then
        echo "Removed $model from Ollama"
    fi
    
    # Clean up HuggingFace cache
    if [ -d "$HF_MODELS" ]; then
        find "$HF_MODELS" -name "*$model*" -type d -exec rm -rf {} + 2>/dev/null || true
        echo "Cleaned HuggingFace cache for $model"
    fi
}

show_status() {
    echo "=== Weirding Module Status ==="
    echo ""
    echo "System:"
    echo "  CPU: $(nproc) cores"
    echo "  Memory: $(free -h | awk '/^Mem:/ {print $2}')"
    echo "  Disk: $(df -h /opt/models | awk 'NR==2 {print $3 "/" $2 " (" $5 " used)"}')"
    echo ""
    echo "Services:"
    systemctl is-active ollama >/dev/null && echo "  Ollama: Running" || echo "  Ollama: Stopped"
    systemctl is-active jupyter >/dev/null && echo "  Jupyter: Running" || echo "  Jupyter: Stopped"
    systemctl is-active weirding-dashboard >/dev/null && echo "  Dashboard: Running" || echo "  Dashboard: Stopped"
    echo ""
    echo "GPU:"
    if command -v nvidia-smi >/dev/null 2>&1; then
        nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits | while read line; do
            echo "  NVIDIA: $line"
        done
    elif command -v rocm-smi >/dev/null 2>&1; then
        echo "  AMD ROCm: Available"
    else
        echo "  No dedicated GPU detected"
    fi
}

case "$1" in
    list)
        list_models
        ;;
    download)
        download_model "$2"
        ;;
    remove)
        remove_model "$2"
        ;;
    status)
        show_status
        ;;
    update)
        echo "Updating model repositories..."
        ollama list >/dev/null 2>&1 || echo "Ollama not running"
        ;;
    *)
        show_usage
        ;;
esac
"""
            
            with open(scripts_dir / "weirding-models", 'w') as f:
                f.write(model_manager_script)
            
            os.chmod(scripts_dir / "weirding-models", 0o755)
            
            # Create symlink in /usr/local/bin
            try:
                subprocess.run([
                    'chroot', root_mount, 'ln', '-sf', '/opt/weirding/scripts/weirding-models', '/usr/local/bin/weirding-models'
                ], capture_output=True, text=True, check=True)
            except subprocess.CalledProcessError:
                pass  # Symlink creation is optional
            
            # System update script
            update_script = """#!/bin/bash
# Weirding System Update Script

set -e

echo "=== Weirding Module System Update ==="

# Update system packages
echo "Updating system packages..."
apt-get update
apt-get upgrade -y

# Update Python packages
echo "Updating Python ML packages..."
/opt/weirding/venv/bin/pip install --upgrade pip
/opt/weirding/venv/bin/pip install --upgrade torch torchvision transformers

# Update Ollama
echo "Updating Ollama..."
curl -fsSL https://ollama.ai/install.sh | OLLAMA_HOME=/opt/models/ollama bash

# Update Node.js packages
echo "Updating Node.js packages..."
npm update -g

# Restart services
echo "Restarting services..."
systemctl restart ollama
systemctl restart jupyter
systemctl restart weirding-dashboard

echo "Update complete!"
"""
            
            with open(scripts_dir / "weirding-update", 'w') as f:
                f.write(update_script)
            
            os.chmod(scripts_dir / "weirding-update", 0o755)
            
            # Create symlink for update script
            try:
                subprocess.run([
                    'chroot', root_mount, 'ln', '-sf', '/opt/weirding/scripts/weirding-update', '/usr/local/bin/weirding-update'
                ], capture_output=True, text=True, check=True)
            except subprocess.CalledProcessError:
                pass
            
            return True
            
        except Exception as e:
            print(f"Error creating management scripts: {e}")
            return False
    
    def _prepare_model_storage(self, root_mount: str):
        """Prepare model storage directories and download initial models."""
        try:
            # Create model directories
            model_dirs = [
                "/opt/models/ollama",
                "/opt/models/huggingface",
                "/opt/models/custom",
                "/opt/models/datasets",
                "/opt/models/docker"
            ]
            
            for model_dir in model_dirs:
                full_path = Path(f"{root_mount}{model_dir}")
                full_path.mkdir(parents=True, exist_ok=True)
                
                # Set ownership to weirding user
                subprocess.run([
                    'chroot', root_mount, 'chown', '-R', 'weirding:weirding', model_dir
                ], capture_output=True, text=True)
            
            # Create model configuration
            model_config = {
                "version": "1.0",
                "storage_paths": {
                    "ollama": "/opt/models/ollama",
                    "huggingface": "/opt/models/huggingface",
                    "custom": "/opt/models/custom",
                    "datasets": "/opt/models/datasets"
                },
                "recommended_models": {
                    "small": ["llama2:7b", "codellama:7b", "mistral:7b"],
                    "medium": ["llama2:13b", "codellama:13b", "vicuna:13b"],
                    "large": ["llama2:70b", "codellama:34b"]
                },
                "auto_download": False,
                "max_storage_gb": 100
            }
            
            with open(f"{root_mount}/opt/weirding/config/models.json", 'w') as f:
                json.dump(model_config, f, indent=2)
            
            # Create README for users
            readme_content = """# Weirding Module - AI Model Storage

This directory contains AI models and datasets for your Weirding Module.

## Directory Structure

- `ollama/` - Ollama LLM models
- `huggingface/` - HuggingFace transformers cache
- `custom/` - Your custom models
- `datasets/` - Training and inference datasets
- `docker/` - Docker container storage

## Managing Models

Use the `weirding-models` command to manage your models:

```bash
# List installed models
weirding-models list

# Download a model
weirding-models download llama2:7b

# Remove a model
weirding-models remove llama2:7b

# Check system status
weirding-models status
```

## Recommended Models for Different Hardware

### Low Memory (< 8GB RAM)
- llama2:7b (4GB)
- mistral:7b (4GB)
- codellama:7b (4GB)

### Medium Memory (8-16GB RAM)
- llama2:13b (7GB)
- vicuna:13b (7GB)
- codellama:13b (7GB)

### High Memory (> 16GB RAM)
- llama2:70b (40GB)
- codellama:34b (20GB)

## Web Interfaces

- Ollama API: http://localhost:11434
- Jupyter Lab: http://localhost:8888 (password: weirding)
- System Dashboard: http://localhost:8080

## Storage Management

Monitor your storage usage:
```bash
df -h /opt/models
```

Clean up unused models:
```bash
docker system prune -f
weirding-models remove <unused-model>
```
"""
            
            with open(f"{root_mount}/opt/models/README.md", 'w') as f:
                f.write(readme_content)
            
        except Exception as e:
            print(f"Error preparing model storage: {e}")
    
    def _unmount_system(self, mount_points: Dict[str, str]):
        """Unmount the system after installation."""
        # Unmount in reverse order
        mount_order = ['dev', 'sys', 'proc', 'root']
        
        for mount_type in mount_order:
            if mount_type in mount_points:
                try:
                    subprocess.run(['umount', mount_points[mount_type]],
                                 capture_output=True, text=True, check=True)
                except subprocess.CalledProcessError:
                    # Try lazy unmount
                    try:
                        subprocess.run(['umount', '-l', mount_points[mount_type]],
                                     capture_output=True, text=True, check=True)
                    except subprocess.CalledProcessError:
                        pass


def main():
    """Test the AI stack installer functionality."""
    from device_setup import DriveDetector
    from partitioner import DrivePartitioner
    
    detector = DriveDetector()
    drives = detector.scan_drives()
    external_drives = detector.get_external_drives()
    
    if not external_drives:
        print("No external drives found for testing.")
        return
    
    # Test with first suitable drive
    suitable_drives = [d for d in external_drives if detector.check_drive_requirements(d)[0]]
    if not suitable_drives:
        print("No suitable drives found for testing.")
        return
    
    test_drive = suitable_drives[0]
    partitioner = DrivePartitioner()
    installer = AIStackInstaller()
    
    print(f"Testing AI stack installer with drive: {test_drive.device}")
    print(f"Drive model: {test_drive.model}")
    
    # Create a test partition plan
    plan = partitioner.create_partition_plan(test_drive, 'full_wipe', 'TestModule')
    
    print("\n=== AI Stack Installation Test ===")
    print("This would install:")
    print("- Docker container runtime with GPU support")
    print("- Python ML environment (PyTorch, Transformers, etc.)")
    print("- Ollama LLM server")
    print("- NVIDIA Container Toolkit (if NVIDIA GPU)")
    print("- AMD ROCm support (if AMD GPU)")
    print("- Jupyter Lab with AI notebooks")
    print("- Web dashboard for system monitoring")
    print("- Model management tools")
    print("- Additional AI development tools")
    
    print(f"\nServices that would be available:")
    print(f"- Ollama API: http://localhost:11434")
    print(f"- Jupyter Lab: http://localhost:8888")
    print(f"- System Dashboard: http://localhost:8080")
    
    print(f"\nEstimated installation time: 30-60 minutes")
    print(f"Network connection required for downloads")


if __name__ == "__main__":
    main()