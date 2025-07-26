#!/usr/bin/env python3
"""
Bootloader Installation Module for Weirding Host Utility

This module handles GRUB bootloader installation for Weirding Modules,
providing UEFI/BIOS compatibility and hardware detection capabilities.
"""

import subprocess
import os
import tempfile
import shutil
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import time

from device_setup import DriveInfo
from partitioner import PartitionPlan


class BootloaderInstaller:
    """Handles GRUB bootloader installation for Weirding Modules."""
    
    def __init__(self):
        self.mount_base = Path("/tmp/weirding_mounts")
        self.mount_base.mkdir(exist_ok=True)
        
    def install_bootloader(self, plan: PartitionPlan, progress_callback=None) -> bool:
        """
        Install GRUB bootloader on the Weirding Module.
        
        Args:
            plan: PartitionPlan with partition information
            progress_callback: Optional callback for progress updates
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Step 1: Mount the necessary partitions
            if progress_callback:
                progress_callback("Mounting partitions for bootloader installation...")
            
            mount_points = self._mount_partitions(plan)
            if not mount_points:
                return False
            
            # Step 2: Install GRUB for both UEFI and BIOS
            if progress_callback:
                progress_callback("Installing GRUB bootloader...")
            
            success = self._install_grub(plan, mount_points, progress_callback)
            
            if success:
                # Step 3: Generate GRUB configuration
                if progress_callback:
                    progress_callback("Generating GRUB configuration...")
                
                success = self._generate_grub_config(plan, mount_points)
            
            # Step 4: Cleanup - unmount partitions
            self._unmount_partitions(mount_points)
            
            return success
            
        except Exception as e:
            print(f"Error installing bootloader: {e}")
            return False
    
    def _mount_partitions(self, plan: PartitionPlan) -> Dict[str, str]:
        """
        Mount the necessary partitions for bootloader installation.
        
        Args:
            plan: PartitionPlan with partition information
            
        Returns:
            Dictionary mapping partition types to mount points
        """
        mount_points = {}
        
        try:
            # Create mount directories
            root_mount = self.mount_base / "root"
            efi_mount = self.mount_base / "efi"
            
            root_mount.mkdir(exist_ok=True)
            efi_mount.mkdir(exist_ok=True)
            
            # Find and mount root partition
            root_partition = None
            efi_partition = None
            
            for partition in plan.partitions:
                if partition.get('mount_point') == '/':
                    root_partition = f"{plan.drive.device}{partition['number']}"
                elif partition.get('mount_point') == '/boot/efi':
                    efi_partition = f"{plan.drive.device}{partition['number']}"
            
            if not root_partition:
                raise RuntimeError("No root partition found in plan")
            
            # Mount root partition
            subprocess.run([
                'mount', root_partition, str(root_mount)
            ], capture_output=True, text=True, check=True)
            mount_points['root'] = str(root_mount)
            
            # Create boot directory structure
            boot_dir = root_mount / "boot"
            boot_dir.mkdir(exist_ok=True)
            
            # Mount EFI partition if it exists
            if efi_partition:
                efi_dir = root_mount / "boot" / "efi"
                efi_dir.mkdir(exist_ok=True)
                
                subprocess.run([
                    'mount', efi_partition, str(efi_dir)
                ], capture_output=True, text=True, check=True)
                mount_points['efi'] = str(efi_dir)
            
            return mount_points
            
        except subprocess.CalledProcessError as e:
            print(f"Error mounting partitions: {e.stderr}")
            self._unmount_partitions(mount_points)
            return {}
        except Exception as e:
            print(f"Error in partition mounting: {e}")
            self._unmount_partitions(mount_points)
            return {}
    
    def _install_grub(self, plan: PartitionPlan, mount_points: Dict[str, str], progress_callback=None) -> bool:
        """
        Install GRUB bootloader for both UEFI and BIOS.
        
        Args:
            plan: PartitionPlan with partition information
            mount_points: Dictionary of mounted partition paths
            progress_callback: Optional progress callback
            
        Returns:
            True if successful, False otherwise
        """
        try:
            root_mount = mount_points['root']
            device = plan.drive.device
            
            # Install GRUB for BIOS (MBR) compatibility
            if progress_callback:
                progress_callback("Installing GRUB for BIOS compatibility...")
            
            subprocess.run([
                'grub-install',
                '--target=i386-pc',
                '--boot-directory', f"{root_mount}/boot",
                '--recheck',
                device
            ], capture_output=True, text=True, check=True)
            
            # Install GRUB for UEFI if EFI partition exists
            if 'efi' in mount_points:
                if progress_callback:
                    progress_callback("Installing GRUB for UEFI compatibility...")
                
                subprocess.run([
                    'grub-install',
                    '--target=x86_64-efi',
                    '--efi-directory', mount_points['efi'],
                    '--boot-directory', f"{root_mount}/boot",
                    '--bootloader-id=WEIRDING',
                    '--recheck'
                ], capture_output=True, text=True, check=True)
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"Error installing GRUB: {e.stderr}")
            return False
    
    def _generate_grub_config(self, plan: PartitionPlan, mount_points: Dict[str, str]) -> bool:
        """
        Generate GRUB configuration file with hardware detection.
        
        Args:
            plan: PartitionPlan with partition information
            mount_points: Dictionary of mounted partition paths
            
        Returns:
            True if successful, False otherwise
        """
        try:
            root_mount = mount_points['root']
            grub_dir = Path(root_mount) / "boot" / "grub"
            grub_dir.mkdir(exist_ok=True)
            
            # Find root partition UUID
            root_partition = None
            for partition in plan.partitions:
                if partition.get('mount_point') == '/':
                    root_partition = f"{plan.drive.device}{partition['number']}"
                    break
            
            if not root_partition:
                raise RuntimeError("No root partition found")
            
            # Get partition UUID
            result = subprocess.run([
                'blkid', '-s', 'UUID', '-o', 'value', root_partition
            ], capture_output=True, text=True, check=True)
            root_uuid = result.stdout.strip()
            
            # Generate GRUB configuration
            grub_config = self._create_grub_config_content(root_uuid, plan)
            
            # Write GRUB configuration
            grub_cfg_path = grub_dir / "grub.cfg"
            with open(grub_cfg_path, 'w') as f:
                f.write(grub_config)
            
            # Set proper permissions
            os.chmod(grub_cfg_path, 0o644)
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"Error generating GRUB config: {e.stderr}")
            return False
        except Exception as e:
            print(f"Error in GRUB config generation: {e}")
            return False
    
    def _create_grub_config_content(self, root_uuid: str, plan: PartitionPlan) -> str:
        """
        Create GRUB configuration content with hardware detection.
        
        Args:
            root_uuid: UUID of the root partition
            plan: PartitionPlan with partition information
            
        Returns:
            GRUB configuration content as string
        """
        module_name = "Weirding"
        for partition in plan.partitions:
            if 'ROOT' in partition.get('label', ''):
                module_name = partition['label'].replace('_ROOT', '')
                break
        
        config = f'''# GRUB Configuration for {module_name} Weirding Module
# Generated automatically - do not edit manually

set timeout=5
set default=0

# Hardware detection and optimization
insmod part_gpt
insmod part_msdos
insmod ext2
insmod fat
insmod ntfs
insmod chain
insmod normal
insmod configfile
insmod search
insmod search_fs_uuid
insmod search_fs_file
insmod gfxterm
insmod gfxmenu
insmod loadenv
insmod probe
insmod videotest
insmod videoinfo

# Enable graphical terminal
if loadfont /boot/grub/fonts/unicode.pf2 ; then
    set gfxmode=auto
    insmod gfxterm
    set gfxpayload=keep
    terminal_output gfxterm
fi

# Hardware detection function
function detect_hardware {{
    echo "Detecting hardware configuration..."
    
    # Detect CPU information
    if cpuid -1 | grep -q "Intel"; then
        set cpu_vendor="Intel"
    elif cpuid -1 | grep -q "AMD"; then
        set cpu_vendor="AMD"
    else
        set cpu_vendor="Unknown"
    fi
    
    # Detect memory
    set memory_mb=`cat /proc/meminfo | grep MemTotal | awk '{{print $2/1024}}'`
    
    # Set optimization flags based on hardware
    if [ "$cpu_vendor" = "Intel" ]; then
        set kernel_params="intel_pstate=enable"
    elif [ "$cpu_vendor" = "AMD" ]; then
        set kernel_params="amd_pstate=enable"
    else
        set kernel_params=""
    fi
}}

# Main menu entry for Weirding Module
menuentry "{module_name} AI Server (Hardware Adaptive)" {{
    call detect_hardware
    
    search --no-floppy --fs-uuid --set=root {root_uuid}
    
    echo "Loading {module_name} Weirding Module..."
    echo "Hardware: $cpu_vendor CPU, ${{memory_mb}}MB RAM"
    echo "Optimizations: $kernel_params"
    
    linux /boot/vmlinuz root=UUID={root_uuid} ro quiet splash $kernel_params weirding.mode=adaptive
    initrd /boot/initrd.img
}}

# Recovery mode entry
menuentry "{module_name} AI Server (Recovery Mode)" {{
    search --no-floppy --fs-uuid --set=root {root_uuid}
    
    echo "Loading {module_name} in recovery mode..."
    
    linux /boot/vmlinuz root=UUID={root_uuid} ro recovery nomodeset
    initrd /boot/initrd.img
}}

# Hardware test entry
menuentry "Hardware Detection Test" {{
    call detect_hardware
    
    echo "=== Hardware Detection Results ==="
    echo "CPU Vendor: $cpu_vendor"
    echo "Memory: ${{memory_mb}}MB"
    echo "Kernel Parameters: $kernel_params"
    echo ""
    echo "Press any key to continue..."
    read
}}

# Chainload to host system (if dual-use mode)
'''

        # Add chainload entry for dual-use mode
        if plan.mode == 'dual_use':
            config += '''
menuentry "Boot Host System" {
    echo "Searching for host system bootloader..."
    
    # Try to chainload Windows bootloader
    search --no-floppy --set=root --file /EFI/Microsoft/Boot/bootmgfw.efi
    if [ -f /EFI/Microsoft/Boot/bootmgfw.efi ]; then
        echo "Found Windows bootloader"
        chainloader /EFI/Microsoft/Boot/bootmgfw.efi
        boot
    fi
    
    # Try to chainload other EFI bootloaders
    search --no-floppy --set=root --file /EFI/BOOT/BOOTX64.EFI
    if [ -f /EFI/BOOT/BOOTX64.EFI ]; then
        echo "Found generic EFI bootloader"
        chainloader /EFI/BOOT/BOOTX64.EFI
        boot
    fi
    
    echo "No host system bootloader found"
    echo "Press any key to return to main menu..."
    read
}
'''

        config += '''
# Advanced options submenu
submenu "Advanced Options" {
    menuentry "Memory Test (memtest86+)" {
        echo "Loading memory test..."
        linux16 /boot/memtest86+.bin
    }
    
    menuentry "Hardware Information" {
        call detect_hardware
        
        echo "=== Detailed Hardware Information ==="
        echo "CPU: $cpu_vendor"
        echo "Memory: ${memory_mb}MB"
        echo "Boot Device: $root"
        echo ""
        
        # Display PCI devices if available
        if [ -f /proc/bus/pci/devices ]; then
            echo "PCI Devices:"
            cat /proc/bus/pci/devices
        fi
        
        echo ""
        echo "Press any key to continue..."
        read
    }
    
    menuentry "Return to Main Menu" {
        configfile /boot/grub/grub.cfg
    }
}

# Automatic hardware optimization on boot
if [ "${grub_platform}" = "efi" ]; then
    echo "UEFI boot detected - enabling EFI optimizations"
    set efi_optimizations="efi=runtime"
else
    echo "BIOS boot detected - enabling legacy optimizations"
    set efi_optimizations=""
fi
'''
        
        return config
    
    def _unmount_partitions(self, mount_points: Dict[str, str]):
        """
        Unmount all mounted partitions.
        
        Args:
            mount_points: Dictionary of mounted partition paths
        """
        for mount_type, mount_path in mount_points.items():
            try:
                subprocess.run(['umount', mount_path], capture_output=True, text=True, check=True)
            except subprocess.CalledProcessError:
                # Try lazy unmount if regular unmount fails
                try:
                    subprocess.run(['umount', '-l', mount_path], capture_output=True, text=True, check=True)
                except subprocess.CalledProcessError:
                    pass  # Continue with other partitions
    
    def verify_bootloader_installation(self, plan: PartitionPlan) -> bool:
        """
        Verify that the bootloader was installed correctly.
        
        Args:
            plan: PartitionPlan with partition information
            
        Returns:
            True if bootloader is properly installed, False otherwise
        """
        try:
            device = plan.drive.device
            
            # Check for GRUB installation in MBR
            result = subprocess.run([
                'dd', f'if={device}', 'bs=512', 'count=1'
            ], capture_output=True, check=True)
            
            # Look for GRUB signature in MBR
            if b'GRUB' in result.stdout:
                print("GRUB found in MBR - BIOS boot should work")
                bios_ok = True
            else:
                print("Warning: GRUB not found in MBR - BIOS boot may not work")
                bios_ok = False
            
            # Check for EFI bootloader if EFI partition exists
            efi_ok = True
            efi_partition = None
            for partition in plan.partitions:
                if partition.get('mount_point') == '/boot/efi':
                    efi_partition = f"{device}{partition['number']}"
                    break
            
            if efi_partition:
                # Mount EFI partition temporarily to check
                with tempfile.TemporaryDirectory() as temp_mount:
                    try:
                        subprocess.run(['mount', efi_partition, temp_mount],
                                     capture_output=True, text=True, check=True)
                        
                        efi_file = Path(temp_mount) / "EFI" / "WEIRDING" / "grubx64.efi"
                        if efi_file.exists():
                            print("GRUB EFI bootloader found - UEFI boot should work")
                            efi_ok = True
                        else:
                            print("Warning: GRUB EFI bootloader not found - UEFI boot may not work")
                            efi_ok = False
                        
                        subprocess.run(['umount', temp_mount], capture_output=True)
                        
                    except subprocess.CalledProcessError:
                        print("Warning: Could not verify EFI bootloader installation")
                        efi_ok = False
            
            return bios_ok or efi_ok  # At least one boot method should work
            
        except Exception as e:
            print(f"Error verifying bootloader installation: {e}")
            return False
    
    def create_boot_scripts(self, plan: PartitionPlan, mount_points: Dict[str, str]) -> bool:
        """
        Create additional boot scripts for hardware detection and optimization.
        
        Args:
            plan: PartitionPlan with partition information
            mount_points: Dictionary of mounted partition paths
            
        Returns:
            True if successful, False otherwise
        """
        try:
            root_mount = mount_points['root']
            scripts_dir = Path(root_mount) / "opt" / "weirding" / "scripts"
            scripts_dir.mkdir(parents=True, exist_ok=True)
            
            # Create hardware detection script
            hw_detect_script = scripts_dir / "detect_hardware.sh"
            with open(hw_detect_script, 'w') as f:
                f.write(self._get_hardware_detection_script())
            
            os.chmod(hw_detect_script, 0o755)
            
            # Create boot optimization script
            boot_opt_script = scripts_dir / "optimize_boot.sh"
            with open(boot_opt_script, 'w') as f:
                f.write(self._get_boot_optimization_script())
            
            os.chmod(boot_opt_script, 0o755)
            
            return True
            
        except Exception as e:
            print(f"Error creating boot scripts: {e}")
            return False
    
    def _get_hardware_detection_script(self) -> str:
        """Get the hardware detection script content."""
        return '''#!/bin/bash
# Hardware Detection Script for Weirding Module
# This script detects and optimizes for the current host hardware

set -e

WEIRDING_CONFIG="/opt/weirding/config"
HARDWARE_INFO="/opt/weirding/hardware.json"

echo "=== Weirding Module Hardware Detection ==="

# Detect CPU
CPU_VENDOR=$(lscpu | grep "Vendor ID" | awk '{print $3}' || echo "Unknown")
CPU_MODEL=$(lscpu | grep "Model name" | cut -d: -f2 | xargs || echo "Unknown")
CPU_CORES=$(nproc || echo "1")

echo "CPU: $CPU_VENDOR $CPU_MODEL ($CPU_CORES cores)"

# Detect Memory
MEMORY_GB=$(free -g | awk '/^Mem:/{print $2}' || echo "0")
echo "Memory: ${MEMORY_GB}GB"

# Detect GPU
GPU_INFO=""
if command -v nvidia-smi >/dev/null 2>&1; then
    GPU_INFO=$(nvidia-smi --query-gpu=name --format=csv,noheader,nounits | head -1 || echo "NVIDIA GPU (unknown)")
    echo "GPU: $GPU_INFO (NVIDIA)"
elif command -v rocm-smi >/dev/null 2>&1; then
    GPU_INFO="AMD GPU (ROCm compatible)"
    echo "GPU: $GPU_INFO"
elif lspci | grep -i "vga\\|3d\\|display" | grep -i "intel" >/dev/null; then
    GPU_INFO="Intel Integrated Graphics"
    echo "GPU: $GPU_INFO"
else
    GPU_INFO="No dedicated GPU detected"
    echo "GPU: $GPU_INFO"
fi

# Detect Storage
STORAGE_INFO=$(lsblk -d -o NAME,SIZE,MODEL | grep -v "NAME" | head -5)
echo "Storage devices:"
echo "$STORAGE_INFO"

# Create hardware configuration
mkdir -p "$WEIRDING_CONFIG"
cat > "$HARDWARE_INFO" << EOF
{
    "detection_time": "$(date -Iseconds)",
    "cpu": {
        "vendor": "$CPU_VENDOR",
        "model": "$CPU_MODEL",
        "cores": $CPU_CORES
    },
    "memory": {
        "total_gb": $MEMORY_GB
    },
    "gpu": {
        "description": "$GPU_INFO",
        "nvidia": $(command -v nvidia-smi >/dev/null 2>&1 && echo "true" || echo "false"),
        "amd": $(command -v rocm-smi >/dev/null 2>&1 && echo "true" || echo "false")
    },
    "optimization_profile": "$([ $MEMORY_GB -gt 16 ] && echo "high_performance" || echo "balanced")"
}
EOF

echo "Hardware detection complete. Configuration saved to $HARDWARE_INFO"
'''
    
    def _get_boot_optimization_script(self) -> str:
        """Get the boot optimization script content."""
        return '''#!/bin/bash
# Boot Optimization Script for Weirding Module
# This script applies hardware-specific optimizations at boot time

set -e

HARDWARE_INFO="/opt/weirding/hardware.json"
OPTIMIZATION_LOG="/var/log/weirding_optimization.log"

echo "=== Weirding Module Boot Optimization ===" | tee -a "$OPTIMIZATION_LOG"
echo "$(date): Starting boot optimization" | tee -a "$OPTIMIZATION_LOG"

if [ ! -f "$HARDWARE_INFO" ]; then
    echo "Hardware info not found, running detection..." | tee -a "$OPTIMIZATION_LOG"
    /opt/weirding/scripts/detect_hardware.sh
fi

# Read hardware configuration
if command -v jq >/dev/null 2>&1 && [ -f "$HARDWARE_INFO" ]; then
    CPU_CORES=$(jq -r '.cpu.cores' "$HARDWARE_INFO" 2>/dev/null || echo "1")
    MEMORY_GB=$(jq -r '.memory.total_gb' "$HARDWARE_INFO" 2>/dev/null || echo "1")
    HAS_NVIDIA=$(jq -r '.gpu.nvidia' "$HARDWARE_INFO" 2>/dev/null || echo "false")
    HAS_AMD=$(jq -r '.gpu.amd' "$HARDWARE_INFO" 2>/dev/null || echo "false")
    PROFILE=$(jq -r '.optimization_profile' "$HARDWARE_INFO" 2>/dev/null || echo "balanced")
else
    # Fallback detection
    CPU_CORES=$(nproc || echo "1")
    MEMORY_GB=$(free -g | awk '/^Mem:/{print $2}' || echo "1")
    HAS_NVIDIA="false"
    HAS_AMD="false"
    PROFILE="balanced"
fi

echo "Optimizing for: $CPU_CORES cores, ${MEMORY_GB}GB RAM, profile: $PROFILE" | tee -a "$OPTIMIZATION_LOG"

# CPU optimizations
if [ "$CPU_CORES" -gt 4 ]; then
    echo "High-core CPU detected, enabling parallel processing optimizations" | tee -a "$OPTIMIZATION_LOG"
    # Set CPU governor for performance
    echo performance | tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor 2>/dev/null || true
fi

# Memory optimizations
if [ "$MEMORY_GB" -gt 8 ]; then
    echo "High memory system, enabling memory-intensive optimizations" | tee -a "$OPTIMIZATION_LOG"
    # Adjust swappiness for high-memory systems
    echo 10 > /proc/sys/vm/swappiness 2>/dev/null || true
fi

# GPU optimizations
if [ "$HAS_NVIDIA" = "true" ]; then
    echo "NVIDIA GPU detected, enabling CUDA optimizations" | tee -a "$OPTIMIZATION_LOG"
    # Enable persistence mode if nvidia-smi is available
    nvidia-smi -pm 1 2>/dev/null || true
fi

if [ "$HAS_AMD" = "true" ]; then
    echo "AMD GPU detected, enabling ROCm optimizations" | tee -a "$OPTIMIZATION_LOG"
    # Set AMD GPU power profile
    echo high > /sys/class/drm/card*/device/power_dpm_force_performance_level 2>/dev/null || true
fi

echo "$(date): Boot optimization complete" | tee -a "$OPTIMIZATION_LOG"
'''


def main():
    """Test the bootloader installer functionality."""
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
    bootloader = BootloaderInstaller()
    
    print(f"Testing bootloader installer with drive: {test_drive.device}")
    print(f"Drive model: {test_drive.model}")
    
    # Create a test partition plan
    plan = partitioner.create_partition_plan(test_drive, 'full_wipe', 'TestModule')
    
    print("\n=== Bootloader Installation Test ===")
    print("This would install GRUB bootloader with:")
    print("- BIOS (MBR) compatibility")
    print("- UEFI compatibility")
    print("- Hardware detection capabilities")
    print("- Adaptive boot configuration")
    
    print(f"\nPartitions that would be used:")
    for partition in plan.partitions:
        if partition.get('mount_point') in ['/', '/boot/efi']:
            print(f"- {partition['label']}: {partition['mount_point']} "
                  f"({detector.format_size(partition['size'])})")


if __name__ == "__main__":
    main()