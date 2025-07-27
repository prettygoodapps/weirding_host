# Weirding Module AI Server Testing Guide

## How to Test Your Bootable AI Server USB Drive

This guide helps you verify that your Weirding Module USB drive is functioning correctly as a portable AI server.

## 🚀 Step 1: Boot Test

### Initial Boot Verification
1. **Insert USB drive** into target computer
2. **Access boot menu** (F12, F8, F10, or F11 during startup)
3. **Select your USB drive** (may appear as "Hard Drive", "Storage Device", or by model name)
4. **Watch for successful boot messages**

### Expected Boot Sequence
```
[    0.000000] Linux version 6.x.x-x-generic
[    0.500000] USB device detected...
[    2.345000] systemd[1]: Starting services...
[   10.123000] systemd[1]: Reached target Multi-User System
[   12.456000] Ubuntu 24.04.x LTS hostname login:
```

### Login Credentials (Default)
```
Username: weirding
Password: weirding
```
**Note**: You'll be prompted to change password on first login.

## 🔍 Step 2: System Verification

### Basic System Check
```bash
# Check system information
uname -a
lsb_release -a
whoami
pwd

# Verify Weirding configuration
cat /opt/weirding/config/weirding.json

# Check available disk space
df -h
lsblk
```

### Expected Output
```bash
weirding@weirding:~$ cat /opt/weirding/config/weirding.json
{
  "version": "1.0",
  "module_name": "weirding",
  "created": "2024-XX-XX XX:XX:XX UTC",
  "bootable": true,
  "portable": true,
  "services": {
    "ollama": {"enabled": true, "port": 11434},
    "jupyter": {"enabled": true, "port": 8888},
    "ssh": {"enabled": true, "port": 22}
  }
}
```

## 🌐 Step 3: Network Connectivity Test

### Check Network Interface
```bash
# Verify network interface is up
ip addr show
ping -c 4 8.8.8.8
ping -c 4 google.com

# Check DNS resolution
nslookup google.com
```

### Expected Network Output
```
weirding@weirding:~$ ip addr show
2: enp0s3: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500
    inet 192.168.1.100/24 brd 192.168.1.255 scope global dynamic enp0s3
```

## 🤖 Step 4: AI Services Verification

### Check Running Services
```bash
# Check system services status
sudo systemctl status ollama
sudo systemctl status jupyter
sudo systemctl status ssh

# Check listening ports
sudo netstat -tlnp | grep -E "(11434|8888|22)"
# Alternative: ss -tlnp | grep -E "(11434|8888|22)"
```

### Test Ollama AI Service
```bash
# Check if Ollama is responding
curl http://localhost:11434/api/version

# List available models
curl http://localhost:11434/api/tags

# Test basic AI query (if models are installed)
curl http://localhost:11434/api/generate -d '{
  "model": "llama2",
  "prompt": "Hello, how are you?",
  "stream": false
}'
```

### Expected Ollama Response
```json
{"version":"0.1.x"}
```

### Test Jupyter Notebook Service
```bash
# Check Jupyter status
sudo systemctl status jupyter

# Access Jupyter (from another computer on network)
# Open browser to: http://[WEIRDING_IP]:8888
# Password: weirding (default)
```

### Test SSH Access
```bash
# From another computer, test SSH connection
ssh weirding@[WEIRDING_IP]
# Password: weirding (or your changed password)
```

## 🖥️ Step 5: Hardware Detection Test

### CPU and Memory Check
```bash
# Check CPU information
lscpu
cat /proc/cpuinfo | grep "model name" | head -1

# Check memory
free -h
cat /proc/meminfo | grep MemTotal
```

### GPU Detection (if available)
```bash
# Check for NVIDIA GPU
nvidia-smi
lspci | grep -i nvidia

# Check for AMD GPU
lspci | grep -i amd
lspci | grep -i radeon

# Check for Intel GPU
lspci | grep -i intel | grep -i vga
```

### Storage and USB Information
```bash
# Check storage devices
lsblk
fdisk -l

# Check USB devices
lsusb
dmesg | grep -i usb | tail -10
```

## 📊 Step 6: Performance Testing

### Basic Performance Test
```bash
# CPU stress test (install if needed: sudo apt install stress)
stress --cpu 4 --timeout 30s

# Memory test
free -h
# Check memory usage during operation

# Disk I/O test
dd if=/dev/zero of=/tmp/testfile bs=1M count=100 oflag=direct
rm /tmp/testfile
```

### Network Performance
```bash
# Download speed test (install if needed: sudo apt install speedtest-cli)
speedtest-cli

# Internal network speed
iperf3 -c speedtest.example.com  # If available
```

## 🔧 Step 7: AI Functionality Testing

### Install Test Model (if not pre-installed)
```bash
# Pull a small model for testing
curl http://localhost:11434/api/pull -d '{"name": "llama2:7b"}'

# Check installation progress
curl http://localhost:11434/api/ps
```

### Test AI Inference
```bash
# Simple text generation test
curl http://localhost:11434/api/generate -d '{
  "model": "llama2:7b",
  "prompt": "Explain artificial intelligence in one paragraph.",
  "stream": false
}' | jq '.response'

# Chat test
curl http://localhost:11434/api/chat -d '{
  "model": "llama2:7b",
  "messages": [
    {"role": "user", "content": "What is machine learning?"}
  ],
  "stream": false
}' | jq '.message.content'
```

### Jupyter Notebook AI Test
1. **Open browser** to `http://[WEIRDING_IP]:8888`
2. **Login** with password: `weirding`
3. **Create new notebook** (Python 3)
4. **Test code**:
```python
import requests
import json

# Test Ollama connection
response = requests.get('http://localhost:11434/api/version')
print("Ollama version:", response.json())

# Test AI inference
prompt_data = {
    "model": "llama2:7b",
    "prompt": "Write a haiku about computers",
    "stream": False
}

response = requests.post('http://localhost:11434/api/generate', 
                        json=prompt_data)
result = response.json()
print("AI Response:", result.get('response', 'No response'))
```

## 🌍 Step 8: External Access Testing

### From Another Computer on Network
```bash
# Find Weirding Module IP
# On the Weirding Module, run:
hostname -I

# From another computer, test services:
# SSH access
ssh weirding@[WEIRDING_IP]

# Ollama API access
curl http://[WEIRDING_IP]:11434/api/version

# Jupyter access (in browser)
http://[WEIRDING_IP]:8888
```

### Mobile Device Testing
1. **Connect mobile device** to same network
2. **Open browser** to `http://[WEIRDING_IP]:8888`
3. **Verify Jupyter interface** loads
4. **Test creating and running** a simple notebook

## ✅ Success Criteria Checklist

### ✅ Boot and System
- [ ] USB drive boots successfully
- [ ] Login with default credentials works
- [ ] System information displays correctly
- [ ] Weirding configuration file exists and is valid
- [ ] Network connectivity established

### ✅ AI Services
- [ ] Ollama service is running on port 11434
- [ ] Ollama API responds to version requests
- [ ] Jupyter notebook is accessible on port 8888
- [ ] SSH service is running on port 22

### ✅ Hardware Detection
- [ ] CPU information correctly detected
- [ ] Memory information accurate
- [ ] Storage devices properly recognized
- [ ] GPU detected (if present)

### ✅ AI Functionality
- [ ] Can install/pull AI models via Ollama
- [ ] AI text generation works
- [ ] Jupyter notebook can interact with Ollama
- [ ] External network access to services works

## 🚨 Troubleshooting Common Issues

### "Services Not Running"
```bash
# Start services manually
sudo systemctl start ollama
sudo systemctl start jupyter
sudo systemctl enable ollama
sudo systemctl enable jupyter

# Check service logs
sudo journalctl -u ollama -f
sudo journalctl -u jupyter -f
```

### "Cannot Access from External Network"
```bash
# Check firewall settings
sudo ufw status
sudo ufw allow 11434
sudo ufw allow 8888
sudo ufw allow 22

# Check if services are binding to all interfaces
sudo netstat -tlnp | grep -E "(11434|8888|22)"
```

### "AI Models Not Working"
```bash
# Check available models
curl http://localhost:11434/api/tags

# Pull a basic model
curl http://localhost:11434/api/pull -d '{"name": "llama2:7b"}'

# Check model installation
ls -la /opt/models/ollama/
```

### "Performance Issues"
```bash
# Check system resources
htop
iotop
free -h

# Check for thermal throttling
cat /proc/cpuinfo | grep MHz
sensors  # If available
```

## 📈 Performance Benchmarks

### Expected Response Times
- **Ollama API version check**: < 100ms
- **Simple text generation (small model)**: 2-10 seconds  
- **Jupyter notebook startup**: < 5 seconds
- **SSH connection**: < 2 seconds

### Minimum System Requirements Met
- **RAM usage**: < 4GB for basic operation
- **CPU usage**: < 50% during idle
- **Storage usage**: < 80% of available space
- **Network latency**: < 100ms for local network access

## 🎯 Production Readiness Test

### Full Stack Test
1. **Boot from USB** on target hardware
2. **Connect to network** (WiFi or Ethernet)
3. **Access from external device** (laptop/phone)
4. **Run AI inference** through Jupyter
5. **Verify persistent storage** (models remain after reboot)
6. **Test under load** (multiple concurrent requests)

If all tests pass, your Weirding Module is functioning correctly as a portable AI server! 🎉