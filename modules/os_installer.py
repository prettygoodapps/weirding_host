#!/usr/bin/env python3
"""
OS Installation Module for Weirding Host Utility

This module handles the installation of a minimal Debian Linux system
onto Weirding Modules using debootstrap and custom configurations.
"""

import subprocess
import os
import tempfile
import shutil
import urllib.request
import json
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import time

from device_setup import DriveInfo
from partitioner import PartitionPlan


class OSInstaller:
    """Handles OS installation for Weirding Modules."""
    
    def __init__(self):
        self.mount_base = Path("/tmp/weirding_install")
        self.mount_base.mkdir(exist_ok=True)
        self.debian_mirror = "http://deb.debian.org/debian"
        self.debian_release = "bookworm"  # Debian 12 - stable and well-supported
        
    def install_os(self, plan: PartitionPlan, progress_callback=None) -> bool:
        """
        Install minimal Debian OS on the Weirding Module.
        
        Args:
            plan: PartitionPlan with partition information
            progress_callback: Optional callback for progress updates
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Step 1: Mount partitions
            if progress_callback:
                progress_callback("Mounting partitions for OS installation...")
            
            mount_points = self._mount_partitions(plan)
            if not mount_points:
                return False
            
            # Step 2: Install base system with debootstrap
            if progress_callback:
                progress_callback("Installing base Debian system (this may take 10-20 minutes)...")
            
            success = self._install_base_system(mount_points['root'], progress_callback)
            if not success:
                self._unmount_partitions(mount_points)
                return False
            
            # Step 3: Configure the system
            if progress_callback:
                progress_callback("Configuring system settings...")
            
            success = self._configure_system(plan, mount_points, progress_callback)
            if not success:
                self._unmount_partitions(mount_points)
                return False
            
            # Step 4: Install kernel and essential packages
            if progress_callback:
                progress_callback("Installing kernel and essential packages...")
            
            success = self._install_kernel_and_essentials(mount_points['root'], progress_callback)
            if not success:
                self._unmount_partitions(mount_points)
                return False
            
            # Step 5: Configure hardware detection
            if progress_callback:
                progress_callback("Setting up hardware detection...")
            
            success = self._setup_hardware_detection(mount_points['root'])
            if not success:
                self._unmount_partitions(mount_points)
                return False
            
            # Step 6: Create Weirding-specific configurations
            if progress_callback:
                progress_callback("Creating Weirding Module configurations...")
            
            success = self._create_weirding_configs(plan, mount_points['root'])
            if not success:
                self._unmount_partitions(mount_points)
                return False
            
            # Step 7: Cleanup and unmount
            if progress_callback:
                progress_callback("Finalizing installation...")
            
            self._cleanup_installation(mount_points['root'])
            self._unmount_partitions(mount_points)
            
            return True
            
        except Exception as e:
            print(f"Error during OS installation: {e}")
            return False
    
    def _mount_partitions(self, plan: PartitionPlan) -> Dict[str, str]:
        """Mount all necessary partitions for OS installation."""
        mount_points = {}
        
        try:
            # Create mount directories
            root_mount = self.mount_base / "root"
            root_mount.mkdir(exist_ok=True)
            
            # Find and mount root partition
            root_partition = None
            efi_partition = None
            swap_partition = None
            
            for partition in plan.partitions:
                if partition.get('mount_point') == '/':
                    root_partition = f"{plan.drive.device}{partition['number']}"
                elif partition.get('mount_point') == '/boot/efi':
                    efi_partition = f"{plan.drive.device}{partition['number']}"
                elif partition.get('mount_point') == 'swap':
                    swap_partition = f"{plan.drive.device}{partition['number']}"
            
            if not root_partition:
                raise RuntimeError("No root partition found in plan")
            
            # Mount root partition
            subprocess.run([
                'mount', root_partition, str(root_mount)
            ], capture_output=True, text=True, check=True)
            mount_points['root'] = str(root_mount)
            
            # Create and mount other directories
            if efi_partition:
                efi_dir = root_mount / "boot" / "efi"
                efi_dir.mkdir(parents=True, exist_ok=True)
                
                subprocess.run([
                    'mount', efi_partition, str(efi_dir)
                ], capture_output=True, text=True, check=True)
                mount_points['efi'] = str(efi_dir)
            
            # Enable swap if available
            if swap_partition:
                try:
                    subprocess.run(['swapon', swap_partition], capture_output=True, text=True, check=True)
                    mount_points['swap'] = swap_partition
                except subprocess.CalledProcessError:
                    pass  # Swap is optional
            
            # Mount essential filesystems for chroot
            for fs_type, mount_point in [('proc', 'proc'), ('sys', 'sys'), ('dev', 'dev')]:
                target_dir = root_mount / mount_point
                target_dir.mkdir(exist_ok=True)
                subprocess.run([
                    'mount', '-t', fs_type, fs_type, str(target_dir)
                ], capture_output=True, text=True, check=True)
                mount_points[fs_type] = str(target_dir)
            
            # Mount dev/pts
            devpts_dir = root_mount / "dev" / "pts"
            devpts_dir.mkdir(exist_ok=True)
            subprocess.run([
                'mount', '-t', 'devpts', 'devpts', str(devpts_dir)
            ], capture_output=True, text=True, check=True)
            mount_points['devpts'] = str(devpts_dir)
            
            return mount_points
            
        except subprocess.CalledProcessError as e:
            print(f"Error mounting partitions: {e.stderr}")
            self._unmount_partitions(mount_points)
            return {}
    
    def _install_base_system(self, root_mount: str, progress_callback=None) -> bool:
        """Install base Debian system using debootstrap."""
        try:
            # Check if debootstrap is available
            try:
                subprocess.run(['which', 'debootstrap'], capture_output=True, text=True, check=True)
            except subprocess.CalledProcessError:
                print("debootstrap not found. Installing...")
                subprocess.run(['apt-get', 'update'], capture_output=True)
                subprocess.run(['apt-get', 'install', '-y', 'debootstrap'], 
                             capture_output=True, text=True, check=True)
            
            # Run debootstrap to install base system
            debootstrap_cmd = [
                'debootstrap',
                '--arch=amd64',
                '--include=systemd,systemd-sysv,dbus,openssh-server,curl,wget,gnupg,ca-certificates',
                self.debian_release,
                root_mount,
                self.debian_mirror
            ]
            
            if progress_callback:
                progress_callback("Running debootstrap (downloading and installing base packages)...")
            
            # Run debootstrap with real-time output
            process = subprocess.Popen(
                debootstrap_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Monitor progress
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output and progress_callback:
                    # Extract meaningful progress info from debootstrap output
                    if "Retrieving" in output:
                        progress_callback("Downloading packages...")
                    elif "Extracting" in output:
                        progress_callback("Extracting packages...")
                    elif "Installing" in output:
                        progress_callback("Installing base system...")
            
            return_code = process.poll()
            if return_code != 0:
                print(f"debootstrap failed with return code {return_code}")
                return False
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"Error installing base system: {e.stderr}")
            return False
        except Exception as e:
            print(f"Unexpected error during base system installation: {e}")
            return False
    
    def _configure_system(self, plan: PartitionPlan, mount_points: Dict[str, str], progress_callback=None) -> bool:
        """Configure the installed system."""
        try:
            root_mount = mount_points['root']
            
            # Configure hostname
            module_name = "weirding"
            for partition in plan.partitions:
                if 'ROOT' in partition.get('label', ''):
                    module_name = partition['label'].replace('_ROOT', '').lower()
                    break
            
            with open(f"{root_mount}/etc/hostname", 'w') as f:
                f.write(f"{module_name}\n")
            
            # Configure hosts file
            with open(f"{root_mount}/etc/hosts", 'w') as f:
                f.write(f"""127.0.0.1	localhost
127.0.1.1	{module_name}

# The following lines are desirable for IPv6 capable hosts
::1     localhost ip6-localhost ip6-loopback
ff02::1 ip6-allnodes
ff02::2 ip6-allrouters
""")
            
            # Configure fstab
            self._create_fstab(plan, f"{root_mount}/etc/fstab")
            
            # Configure network (use systemd-networkd)
            network_dir = Path(f"{root_mount}/etc/systemd/network")
            network_dir.mkdir(exist_ok=True)
            
            with open(network_dir / "20-wired.network", 'w') as f:
                f.write("""[Match]
Name=en*

[Network]
DHCP=yes
IPForward=yes

[DHCP]
UseDNS=yes
UseRoutes=yes
""")
            
            # Configure DNS
            with open(f"{root_mount}/etc/resolv.conf", 'w') as f:
                f.write("""nameserver 8.8.8.8
nameserver 8.8.4.4
nameserver 1.1.1.1
""")
            
            # Configure timezone
            subprocess.run([
                'chroot', root_mount, 'ln', '-sf', '/usr/share/zoneinfo/UTC', '/etc/localtime'
            ], capture_output=True, text=True, check=True)
            
            # Configure locale
            with open(f"{root_mount}/etc/locale.gen", 'w') as f:
                f.write("en_US.UTF-8 UTF-8\n")
            
            subprocess.run([
                'chroot', root_mount, 'locale-gen'
            ], capture_output=True, text=True, check=True)
            
            with open(f"{root_mount}/etc/default/locale", 'w') as f:
                f.write("LANG=en_US.UTF-8\n")
            
            # Enable essential services
            services_to_enable = [
                'systemd-networkd',
                'systemd-resolved',
                'ssh'
            ]
            
            for service in services_to_enable:
                try:
                    subprocess.run([
                        'chroot', root_mount, 'systemctl', 'enable', service
                    ], capture_output=True, text=True, check=True)
                except subprocess.CalledProcessError:
                    pass  # Some services might not be available yet
            
            return True
            
        except Exception as e:
            print(f"Error configuring system: {e}")
            return False
    
    def _create_fstab(self, plan: PartitionPlan, fstab_path: str):
        """Create /etc/fstab file."""
        fstab_entries = []
        
        for partition in plan.partitions:
            partition_device = f"{plan.drive.device}{partition['number']}"
            
            # Get UUID for the partition
            try:
                result = subprocess.run([
                    'blkid', '-s', 'UUID', '-o', 'value', partition_device
                ], capture_output=True, text=True, check=True)
                uuid = result.stdout.strip()
            except subprocess.CalledProcessError:
                uuid = None
            
            # Create fstab entry
            if partition.get('mount_point') == '/':
                device_spec = f"UUID={uuid}" if uuid else partition_device
                fstab_entries.append(f"{device_spec} / ext4 defaults 0 1")
                
            elif partition.get('mount_point') == '/boot/efi':
                device_spec = f"UUID={uuid}" if uuid else partition_device
                fstab_entries.append(f"{device_spec} /boot/efi vfat defaults 0 2")
                
            elif partition.get('mount_point') == 'swap':
                device_spec = f"UUID={uuid}" if uuid else partition_device
                fstab_entries.append(f"{device_spec} none swap sw 0 0")
                
            elif partition.get('mount_point') == '/opt/models':
                device_spec = f"UUID={uuid}" if uuid else partition_device
                fstab_entries.append(f"{device_spec} /opt/models ext4 defaults 0 2")
        
        # Add tmpfs entries for performance
        fstab_entries.extend([
            "tmpfs /tmp tmpfs defaults,noatime,mode=1777 0 0",
            "tmpfs /var/tmp tmpfs defaults,noatime,mode=1777 0 0"
        ])
        
        with open(fstab_path, 'w') as f:
            f.write("# /etc/fstab: static file system information.\n")
            f.write("# <file system> <mount point> <type> <options> <dump> <pass>\n\n")
            for entry in fstab_entries:
                f.write(f"{entry}\n")
    
    def _install_kernel_and_essentials(self, root_mount: str, progress_callback=None) -> bool:
        """Install Linux kernel and essential packages."""
        try:
            # Update package lists
            subprocess.run([
                'chroot', root_mount, 'apt-get', 'update'
            ], capture_output=True, text=True, check=True)
            
            # Install kernel and essential packages
            essential_packages = [
                'linux-image-amd64',
                'linux-headers-amd64',
                'firmware-linux',
                'firmware-linux-nonfree',
                'grub-pc',
                'grub-efi-amd64',
                'os-prober',
                'sudo',
                'vim',
                'nano',
                'htop',
                'git',
                'python3',
                'python3-pip',
                'docker.io',
                'docker-compose',
                'jq',
                'curl',
                'wget',
                'unzip',
                'build-essential',
                'pkg-config',
                'lshw',
                'pciutils',
                'usbutils',
                'dmidecode'
            ]
            
            if progress_callback:
                progress_callback("Installing kernel and essential packages...")
            
            # Install packages in chunks to avoid timeout
            chunk_size = 10
            for i in range(0, len(essential_packages), chunk_size):
                chunk = essential_packages[i:i + chunk_size]
                
                if progress_callback:
                    progress_callback(f"Installing packages: {', '.join(chunk[:3])}...")
                
                subprocess.run([
                    'chroot', root_mount, 'apt-get', 'install', '-y'
                ] + chunk, capture_output=True, text=True, check=True)
            
            # Clean up package cache
            subprocess.run([
                'chroot', root_mount, 'apt-get', 'clean'
            ], capture_output=True, text=True, check=True)
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"Error installing kernel and essentials: {e.stderr}")
            return False
    
    def _setup_hardware_detection(self, root_mount: str) -> bool:
        """Set up hardware detection capabilities."""
        try:
            # Create hardware detection service
            service_content = """[Unit]
Description=Weirding Hardware Detection
After=multi-user.target
Wants=multi-user.target

[Service]
Type=oneshot
ExecStart=/opt/weirding/scripts/detect_hardware.sh
ExecStartPost=/opt/weirding/scripts/optimize_boot.sh
RemainAfterExit=yes
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
            
            service_dir = Path(f"{root_mount}/etc/systemd/system")
            service_dir.mkdir(exist_ok=True)
            
            with open(service_dir / "weirding-hardware-detect.service", 'w') as f:
                f.write(service_content)
            
            # Enable the service
            subprocess.run([
                'chroot', root_mount, 'systemctl', 'enable', 'weirding-hardware-detect.service'
            ], capture_output=True, text=True, check=True)
            
            return True
            
        except Exception as e:
            print(f"Error setting up hardware detection: {e}")
            return False
    
    def _create_weirding_configs(self, plan: PartitionPlan, root_mount: str) -> bool:
        """Create Weirding-specific configuration files."""
        try:
            # Create Weirding directories
            weirding_dirs = [
                "/opt/weirding",
                "/opt/weirding/config",
                "/opt/weirding/scripts",
                "/opt/weirding/logs",
                "/opt/models",
                "/var/lib/weirding"
            ]
            
            for dir_path in weirding_dirs:
                full_path = Path(f"{root_mount}{dir_path}")
                full_path.mkdir(parents=True, exist_ok=True)
            
            # Create Weirding configuration file
            weirding_config = {
                "version": "1.0",
                "module_name": "weirding",
                "created": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
                "drive_info": {
                    "device": plan.drive.device,
                    "model": plan.drive.model,
                    "vendor": plan.drive.vendor,
                    "size": plan.drive.size
                },
                "setup_mode": plan.mode,
                "services": {
                    "ollama": {
                        "enabled": True,
                        "port": 11434,
                        "models_path": "/opt/models/ollama"
                    },
                    "jupyter": {
                        "enabled": True,
                        "port": 8888,
                        "password": "weirding"
                    },
                    "ssh": {
                        "enabled": True,
                        "port": 22
                    }
                },
                "hardware_detection": {
                    "enabled": True,
                    "auto_optimize": True,
                    "gpu_support": ["nvidia", "amd", "intel"]
                }
            }
            
            with open(f"{root_mount}/opt/weirding/config/weirding.json", 'w') as f:
                json.dump(weirding_config, f, indent=2)
            
            # Create default user (weirding)
            subprocess.run([
                'chroot', root_mount, 'useradd', '-m', '-s', '/bin/bash', 'weirding'
            ], capture_output=True, text=True, check=True)
            
            # Add user to sudo group
            subprocess.run([
                'chroot', root_mount, 'usermod', '-aG', 'sudo,docker', 'weirding'
            ], capture_output=True, text=True, check=True)
            
            # Set default password (should be changed on first boot)
            subprocess.run([
                'chroot', root_mount, 'bash', '-c', 'echo "weirding:weirding" | chpasswd'
            ], capture_output=True, text=True, check=True)
            
            # Create first-boot script
            first_boot_script = """#!/bin/bash
# First boot setup script for Weirding Module

echo "=== Weirding Module First Boot Setup ==="

# Force password change on first login
chage -d 0 weirding

# Generate SSH host keys
ssh-keygen -A

# Start and enable Docker
systemctl start docker
systemctl enable docker

# Create models directory structure
mkdir -p /opt/models/{ollama,huggingface,custom}
chown -R weirding:weirding /opt/models

# Set up log rotation
cat > /etc/logrotate.d/weirding << EOF
/opt/weirding/logs/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 644 weirding weirding
}
EOF

# Mark first boot as complete
touch /opt/weirding/.first_boot_complete

echo "First boot setup complete!"
"""
            
            with open(f"{root_mount}/opt/weirding/scripts/first_boot.sh", 'w') as f:
                f.write(first_boot_script)
            
            os.chmod(f"{root_mount}/opt/weirding/scripts/first_boot.sh", 0o755)
            
            # Create first boot service
            first_boot_service = """[Unit]
Description=Weirding First Boot Setup
After=multi-user.target
ConditionPathExists=!/opt/weirding/.first_boot_complete

[Service]
Type=oneshot
ExecStart=/opt/weirding/scripts/first_boot.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
"""
            
            with open(f"{root_mount}/etc/systemd/system/weirding-first-boot.service", 'w') as f:
                f.write(first_boot_service)
            
            subprocess.run([
                'chroot', root_mount, 'systemctl', 'enable', 'weirding-first-boot.service'
            ], capture_output=True, text=True, check=True)
            
            return True
            
        except Exception as e:
            print(f"Error creating Weirding configs: {e}")
            return False
    
    def _cleanup_installation(self, root_mount: str):
        """Clean up after installation."""
        try:
            # Clean package cache
            subprocess.run([
                'chroot', root_mount, 'apt-get', 'clean'
            ], capture_output=True, text=True)
            
            # Remove temporary files
            temp_dirs = [
                f"{root_mount}/tmp/*",
                f"{root_mount}/var/tmp/*"
            ]
            
            for temp_dir in temp_dirs:
                try:
                    subprocess.run(['rm', '-rf'] + [temp_dir], capture_output=True)
                except:
                    pass
            
        except Exception:
            pass  # Cleanup errors are not critical
    
    def _unmount_partitions(self, mount_points: Dict[str, str]):
        """Unmount all mounted partitions."""
        # Unmount in reverse order
        mount_order = ['devpts', 'dev', 'sys', 'proc', 'efi', 'root']
        
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
        
        # Disable swap if it was enabled
        if 'swap' in mount_points:
            try:
                subprocess.run(['swapoff', mount_points['swap']], capture_output=True)
            except subprocess.CalledProcessError:
                pass


def main():
    """Test the OS installer functionality."""
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
    installer = OSInstaller()
    
    print(f"Testing OS installer with drive: {test_drive.device}")
    print(f"Drive model: {test_drive.model}")
    
    # Create a test partition plan
    plan = partitioner.create_partition_plan(test_drive, 'full_wipe', 'TestModule')
    
    print("\n=== OS Installation Test ===")
    print("This would install:")
    print("- Minimal Debian 12 (Bookworm) base system")
    print("- Linux kernel with hardware support")
    print("- Essential packages (Docker, Python, etc.)")
    print("- Hardware detection and optimization")
    print("- Weirding-specific configurations")
    print("- SSH server and default user account")
    
    print(f"\nEstimated installation time: 20-40 minutes")
    print(f"Network connection required for package downloads")


if __name__ == "__main__":
    main()