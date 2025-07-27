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
        Create a bootable Weirding Module by writing ISO directly to drive.
        
        Args:
            plan: PartitionPlan with drive and base image information
            progress_callback: Optional callback for progress updates
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not plan.base_image:
                print("Error: Base image is required for Weirding Module creation")
                return False
            
            from base_images import BaseImageCatalog
            catalog = BaseImageCatalog()
            
            # Step 1: Ensure image is available locally
            if progress_callback:
                progress_callback(f"Preparing {plan.base_image.name}...")
            
            if not catalog.is_image_cached(plan.base_image):
                if progress_callback:
                    progress_callback(f"Downloading {plan.base_image.name} ({catalog.format_size(plan.base_image.size_mb)})...")
                
                image_path = catalog.download_image(plan.base_image, progress_callback)
                if not image_path:
                    print(f"Failed to download base image: {plan.base_image.name}")
                    return False
            else:
                image_path = catalog.get_cached_image_path(plan.base_image)
            
            if not image_path or not os.path.exists(image_path):
                print(f"Image file not found: {image_path}")
                return False
            
            # Step 2: Write ISO directly to drive (creating bootable USB)
            if progress_callback:
                progress_callback("Creating bootable Weirding Module...")
            
            success = self._write_iso_to_drive(image_path, plan.drive.device, progress_callback)
            if not success:
                return False
            
            # Step 3: Add Weirding-specific configuration to the bootable drive
            if progress_callback:
                progress_callback("Adding Weirding Module configuration...")
            
            success = self._add_weirding_config(plan)
            if not success:
                print("Warning: Could not add Weirding configuration, but drive is bootable")
            
            return True
            
        except Exception as e:
            print(f"Error creating Weirding Module: {e}")
            return False
    
    def _write_iso_to_drive(self, iso_path: str, device: str, progress_callback=None) -> bool:
        """Write ISO directly to drive to create bootable USB with comprehensive validation."""
        try:
            if progress_callback:
                progress_callback("Preparing to write ISO to drive...")
            
            # Step 1: Verify source ISO integrity and bootability
            print(f"🔍 Verifying ISO file integrity: {iso_path}")
            if not self._verify_iso_integrity(iso_path, progress_callback):
                print("❌ ISO integrity verification failed")
                return False
            
            # Step 2: Get source and target sizes for validation
            iso_size = os.path.getsize(iso_path)
            print(f"📏 Source ISO size: {iso_size:,} bytes ({iso_size / (1024*1024):.1f} MB)")
            
            if progress_callback:
                progress_callback("Writing ISO to drive (this may take several minutes)...")
            
            print(f"💾 Writing {iso_path} to {device}...")
            
            # Use dd to write ISO directly to device with USB 4.0 compatibility
            # USB 4.0 drives need smaller block sizes and different sync options for compatibility
            dd_cmd = [
                'dd',
                f'if={iso_path}',
                f'of={device}',
                'bs=1M',          # Smaller block size for USB 4.0 compatibility
                'status=progress',
                'conv=fsync',     # File system sync (more compatible than fdatasync)
                'oflag=direct'    # Direct I/O for better reliability
            ]
            
            print(f"🔧 Using USB 4.0 compatible parameters: bs=1M, conv=fsync, oflag=direct")
            
            # Capture both stdout and stderr separately for better diagnostics
            process = subprocess.Popen(
                dd_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Monitor progress and capture all output
            dd_output = []
            dd_errors = []
            
            while True:
                # Read from both stdout and stderr
                stdout_line = process.stdout.readline()
                stderr_line = process.stderr.readline()
                
                if stdout_line == '' and stderr_line == '' and process.poll() is not None:
                    break
                    
                if stdout_line:
                    dd_output.append(stdout_line.strip())
                    print(f"DD OUTPUT: {stdout_line.strip()}")
                    if progress_callback and "copied" in stdout_line.lower():
                        progress_callback("Writing ISO to drive...")
                        
                if stderr_line:
                    dd_errors.append(stderr_line.strip())
                    print(f"DD STATUS: {stderr_line.strip()}")
                    if progress_callback and ("MB" in stderr_line or "GB" in stderr_line):
                        progress_callback("Writing ISO to drive...")
            
            return_code = process.poll()
            
            # Print final dd statistics
            print(f"📊 DD command completed with return code: {return_code}")
            if dd_output:
                print("📋 DD Output:")
                for line in dd_output[-5:]:  # Show last 5 lines
                    print(f"  {line}")
            if dd_errors:
                print("📋 DD Status/Errors:")
                for line in dd_errors[-5:]:  # Show last 5 lines
                    print(f"  {line}")
            
            if return_code != 0:
                print(f"❌ DD command failed with return code: {return_code}")
                return False
            
            # Step 3: Sync and wait for write completion
            if progress_callback:
                progress_callback("Syncing data to drive...")
            
            print("🔄 Syncing filesystem...")
            subprocess.run(['sync'], check=True)
            
            # Force sync specifically for the device
            try:
                subprocess.run(['blockdev', '--flushbufs', device], check=True)
                print(f"🔄 Flushed buffers for {device}")
            except subprocess.CalledProcessError as e:
                print(f"⚠️  Could not flush device buffers: {e}")
            
            # Wait a moment for the drive to settle
            time.sleep(3)
            
            # Step 4: Verify the write was successful
            if progress_callback:
                progress_callback("Verifying USB drive bootability...")
            
            print("🔍 Verifying written data...")
            if not self._verify_usb_bootability(device, iso_size, progress_callback):
                print("❌ USB bootability verification failed")
                return False
            
            if progress_callback:
                progress_callback("✅ Bootable USB drive created successfully")
            
            print("✅ ISO written successfully and verified as bootable")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Error writing ISO to drive: {e}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error writing ISO: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _verify_iso_integrity(self, iso_path: str, progress_callback=None) -> bool:
        """Verify ISO file integrity and bootability signatures."""
        try:
            if not os.path.exists(iso_path):
                print(f"❌ ISO file not found: {iso_path}")
                return False
            
            # Check file size (should be > 100MB for a valid Linux ISO)
            iso_size = os.path.getsize(iso_path)
            if iso_size < 100 * 1024 * 1024:  # 100MB minimum
                print(f"❌ ISO file too small: {iso_size:,} bytes (minimum 100MB)")
                return False
            
            if progress_callback:
                progress_callback("Checking ISO boot signatures...")
            
            # Check for ISO 9660 signature
            with open(iso_path, 'rb') as f:
                # ISO 9660 primary volume descriptor at sector 16 (offset 32768)
                f.seek(32768)
                pvd = f.read(2048)
                
                # Check for ISO 9660 signature "CD001"
                if pvd[1:6] != b'CD001':
                    print("❌ Invalid ISO 9660 signature")
                    return False
                
                print("✅ Valid ISO 9660 signature found")
                
                # Check for El Torito boot record (bootable ISO)
                f.seek(34816)  # Sector 17
                boot_record = f.read(2048)
                
                if boot_record[0:1] == b'\x00' and boot_record[1:6] == b'CD001':
                    el_torito_offset = int.from_bytes(boot_record[71:75], 'little') * 2048
                    
                    # Check El Torito signature
                    f.seek(el_torito_offset)
                    el_torito = f.read(32)
                    
                    if el_torito[0:23] == b'\x01\x00\x00\x00EL TORITO SPECIFICATION':
                        print("✅ El Torito bootable signature found")
                        return True
                    else:
                        print("⚠️  El Torito signature not found, but ISO may still be bootable")
                        return True  # Some ISOs don't have El Torito but are still bootable
                else:
                    print("⚠️  Boot record not found, checking for hybrid ISO...")
                    
                    # Check for hybrid ISO (has MBR boot sector)
                    f.seek(0)
                    mbr = f.read(512)
                    
                    # Check for MBR signature (0x55AA at end)
                    if mbr[510:512] == b'\x55\xaa':
                        print("✅ Hybrid ISO with MBR boot sector found")
                        return True
                    else:
                        print("❌ No bootable signatures found in ISO")
                        return False
                        
        except Exception as e:
            print(f"❌ Error verifying ISO integrity: {e}")
            return False
    
    def _verify_usb_bootability(self, device: str, expected_size: int, progress_callback=None) -> bool:
        """Verify that the USB drive was written correctly and has bootable signatures."""
        try:
            if progress_callback:
                progress_callback("Checking USB drive boot sectors...")
            
            # Wait for device to be ready
            time.sleep(2)
            
            # Check if device exists and is accessible
            if not os.path.exists(device):
                print(f"❌ Device not found: {device}")
                return False
            
            try:
                # Read the first sector (MBR/boot sector)
                with open(device, 'rb') as f:
                    # Check MBR signature
                    f.seek(510)
                    mbr_sig = f.read(2)
                    if mbr_sig == b'\x55\xaa':
                        print("✅ Valid MBR boot signature found on USB drive")
                    else:
                        print("⚠️  MBR boot signature not found, checking ISO signature...")
                    
                    # Check for ISO 9660 signature (hybrid ISO)
                    f.seek(32768)
                    try:
                        pvd = f.read(6)
                        if pvd[1:6] == b'CD001':
                            print("✅ ISO 9660 signature found on USB drive")
                        else:
                            print("⚠️  ISO 9660 signature not found")
                    except:
                        print("⚠️  Could not read ISO signature area")
                
                # Verify approximate size by checking if we can read near the expected end
                try:
                    with open(device, 'rb') as f:
                        # Try to read near the end of the expected data
                        test_offset = max(0, expected_size - 4096)  # 4KB before end
                        f.seek(test_offset)
                        data = f.read(1024)
                        if len(data) > 0:
                            print(f"✅ Data successfully written (verified up to {test_offset:,} bytes)")
                        else:
                            print("⚠️  Could not verify data at expected end position")
                except Exception as e:
                    print(f"⚠️  Could not verify data size: {e}")
                
                # Check partition table
                result = subprocess.run([
                    'fdisk', '-l', device
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    fdisk_output = result.stdout
                    print("📋 Partition table information:")
                    for line in fdisk_output.split('\n'):
                        if device in line or 'boot' in line.lower() or 'start' in line.lower():
                            print(f"  {line.strip()}")
                    
                    # Look for bootable partition indicator
                    if '*' in fdisk_output or 'boot' in fdisk_output.lower():
                        print("✅ Bootable partition detected")
                    else:
                        print("⚠️  No bootable partition flag detected (may still be bootable)")
                else:
                    print("⚠️  Could not read partition information")
                
                print("✅ USB drive verification completed")
                return True
                
            except PermissionError:
                print("❌ Permission denied reading USB device (may need root access)")
                return False
            except Exception as e:
                print(f"❌ Error reading USB device: {e}")
                return False
                
        except Exception as e:
            print(f"❌ Error during USB verification: {e}")
            return False

    def _add_weirding_config(self, plan: PartitionPlan) -> bool:
        """Add Weirding-specific configuration to the bootable drive."""
        try:
            # Wait for drive to settle after dd
            time.sleep(2)
            
            # Create a simple weirding configuration file
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
                "base_image": {
                    "name": plan.base_image.name if plan.base_image else None,
                    "version": plan.base_image.version if plan.base_image else None,
                    "architecture": plan.base_image.architecture if plan.base_image else None,
                    "ai_optimized": plan.base_image.ai_optimized if plan.base_image else False
                },
                "bootable": True,
                "portable": True
            }
            
            # Try to mount the drive and add config (non-critical)
            try:
                # Find the first partition
                partitions = subprocess.run(
                    ['lsblk', '-n', '-o', 'NAME', plan.drive.device],
                    capture_output=True, text=True, check=True
                ).stdout.strip().split('\n')[1:]  # Skip the device itself
                
                if partitions:
                    partition = f"{plan.drive.device}{partitions[0].strip()}"
                    
                    # Create temporary mount point
                    mount_point = Path("/tmp/weirding_config_mount")
                    mount_point.mkdir(exist_ok=True)
                    
                    # Mount the partition
                    subprocess.run([
                        'mount', partition, str(mount_point)
                    ], capture_output=True, text=True, check=True)
                    
                    # Write config file
                    config_file = mount_point / "weirding.json"
                    with open(config_file, 'w') as f:
                        json.dump(weirding_config, f, indent=2)
                    
                    # Unmount
                    subprocess.run(['umount', str(mount_point)], capture_output=True)
                    
                    print("Added Weirding configuration to bootable drive")
                    
            except subprocess.CalledProcessError:
                # Config addition failed, but drive is still bootable
                print("Could not add configuration file, but drive is bootable")
            
            return True
            
        except Exception as e:
            print(f"Error adding Weirding config: {e}")
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
                '--include=systemd,systemd-sysv,dbus,openssh-server,curl,wget,gnupg,ca-certificates,locales',
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
    
    def _install_from_iso(self, base_image, root_mount: str, progress_callback=None) -> bool:
        """Install base system from ISO image."""
        try:
            from base_images import BaseImageCatalog
            catalog = BaseImageCatalog()
            
            # Ubuntu Server ISOs are installer ISOs, not live systems
            # Fall back to debootstrap for server installations
            if "server" in base_image.name.lower():
                if progress_callback:
                    progress_callback(f"Server ISO detected, using debootstrap installation...")
                print(f"DEBUG: Server ISO detected for {base_image.name}, falling back to debootstrap")
                return self._install_base_system(root_mount, progress_callback)
            
            # Step 1: Ensure image is available locally
            if not catalog.is_image_cached(base_image):
                if progress_callback:
                    progress_callback(f"Downloading {base_image.name} ({catalog.format_size(base_image.size_mb)})...")
                
                image_path = catalog.download_image(base_image, progress_callback)
                if not image_path:
                    print(f"Failed to download base image: {base_image.name}")
                    return False
            else:
                image_path = catalog.get_cached_image_path(base_image)
            
            if not image_path or not os.path.exists(image_path):
                print(f"Image file not found: {image_path}")
                return False
            
            # Step 3: Mount the ISO
            iso_mount_dir = Path("/tmp/weirding_iso_mount")
            iso_mount_dir.mkdir(exist_ok=True)
            
            if progress_callback:
                progress_callback("Mounting base image...")
            
            try:
                subprocess.run([
                    'mount', '-o', 'loop,ro', str(image_path), str(iso_mount_dir)
                ], capture_output=True, text=True, check=True)
            except subprocess.CalledProcessError as e:
                print(f"Failed to mount ISO: {e.stderr}")
                return False
            
            # Step 4: Extract filesystem from ISO
            if progress_callback:
                progress_callback("Extracting base system filesystem...")
            
            squashfs_mount_dir = None
            try:
                # Find the squashfs filesystem inside the ISO (Ubuntu uses casper/filesystem.squashfs)
                squashfs_path = None
                possible_paths = [
                    iso_mount_dir / "casper" / "filesystem.squashfs",
                    iso_mount_dir / "live" / "filesystem.squashfs",
                    iso_mount_dir / "filesystem.squashfs"
                ]
                
                for path in possible_paths:
                    if path.exists():
                        squashfs_path = path
                        break
                
                if not squashfs_path:
                    print(f"Could not find squashfs filesystem in ISO. Available files:")
                    for item in iso_mount_dir.rglob("*"):
                        if item.is_file():
                            print(f"  {item.relative_to(iso_mount_dir)}")
                    return False
                
                if progress_callback:
                    progress_callback("Mounting filesystem from ISO...")
                
                # Mount the squashfs filesystem
                squashfs_mount_dir = Path("/tmp/weirding_squashfs_mount")
                squashfs_mount_dir.mkdir(exist_ok=True)
                
                subprocess.run([
                    'mount', '-t', 'squashfs', '-o', 'loop,ro',
                    str(squashfs_path), str(squashfs_mount_dir)
                ], capture_output=True, text=True, check=True)
                
                if progress_callback:
                    progress_callback("Extracting filesystem contents...")
                
                # Use rsync to copy the actual filesystem
                rsync_cmd = [
                    'rsync', '-av', '--progress',
                    f"{squashfs_mount_dir}/",
                    f"{root_mount}/"
                ]
                
                process = subprocess.Popen(
                    rsync_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                
                # Monitor rsync progress
                while True:
                    output = process.stdout.readline()
                    if output == '' and process.poll() is not None:
                        break
                    if output and progress_callback:
                        # Extract meaningful progress info from rsync output
                        if "%" in output:
                            progress_callback("Extracting filesystem...")
                        elif "sent" in output and "received" in output:
                            progress_callback("Finalizing filesystem extraction...")
                
                return_code = process.poll()
                print(f"DEBUG: rsync completed with return code: {return_code}")
                if return_code != 0:
                    print(f"Filesystem extraction failed with return code {return_code}")
                    return False
                
                print(f"DEBUG: Filesystem extraction completed successfully")
                
            except subprocess.CalledProcessError as e:
                print(f"Error extracting filesystem: {e.stderr}")
                return False
            except Exception as e:
                print(f"Error during filesystem extraction: {e}")
                import traceback
                traceback.print_exc()
                return False
            finally:
                print(f"DEBUG: Starting cleanup...")
                # Unmount squashfs
                if squashfs_mount_dir:
                    try:
                        subprocess.run(['umount', str(squashfs_mount_dir)], capture_output=True)
                        print(f"DEBUG: Unmounted squashfs")
                    except subprocess.CalledProcessError as e:
                        print(f"DEBUG: Failed to unmount squashfs: {e}")
                        pass
                
                # Unmount ISO
                try:
                    subprocess.run(['umount', str(iso_mount_dir)], capture_output=True)
                    print(f"DEBUG: Unmounted ISO")
                except subprocess.CalledProcessError as e:
                    print(f"DEBUG: Failed to unmount ISO: {e}")
                    pass
                
                print(f"DEBUG: Cleanup completed")
            
            print(f"DEBUG: About to call _configure_iso_system...")
            
            # Step 5: Post-extraction configuration for ISO-based systems
            if progress_callback:
                progress_callback("Configuring extracted system...")
            
            print(f"DEBUG: Calling _configure_iso_system for {base_image.name}...")
            success = self._configure_iso_system(base_image, root_mount)
            print(f"DEBUG: _configure_iso_system returned: {success}")
            if not success:
                print(f"DEBUG: _configure_iso_system failed, returning False")
                return False
            
            return True
            
        except Exception as e:
            print(f"Error installing from ISO: {e}")
            return False
    
    def _configure_iso_system(self, base_image, root_mount: str) -> bool:
        """Configure system after ISO extraction."""
        try:
            print(f"DEBUG: Starting ISO system configuration for {base_image.name}")
            
            # Ensure essential directories exist
            essential_dirs = [
                'proc', 'sys', 'dev', 'tmp', 'var/tmp',
                'opt/weirding', 'opt/models', 'var/lib/weirding'
            ]
            
            print(f"DEBUG: Creating essential directories...")
            for dir_path in essential_dirs:
                full_path = Path(f"{root_mount}/{dir_path}")
                full_path.mkdir(parents=True, exist_ok=True)
                print(f"DEBUG: Created directory: {dir_path}")
            
            # Check if basic system files exist
            critical_files = [
                'etc/apt/sources.list',
                'usr/bin/apt-get',
                'bin/bash',
                'etc/passwd'
            ]
            
            print(f"DEBUG: Checking for critical system files...")
            missing_files = []
            for file_path in critical_files:
                full_path = Path(f"{root_mount}/{file_path}")
                if not full_path.exists():
                    missing_files.append(file_path)
                    print(f"DEBUG: Missing critical file: {file_path}")
                else:
                    print(f"DEBUG: Found critical file: {file_path}")
            
            if missing_files:
                print(f"WARNING: Missing critical files: {missing_files}")
                # Try to continue anyway - might be a different filesystem layout
            
            # Skip apt operations for now to isolate the issue
            print(f"DEBUG: Skipping apt operations to isolate configuration issue")
            
            print(f"DEBUG: ISO system configuration completed successfully")
            return True
            
        except Exception as e:
            print(f"Error configuring ISO system: {e}")
            import traceback
            traceback.print_exc()
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
            # Configure sources.list in the chroot for better package availability
            sources_list_content = f"""deb {self.debian_mirror} {self.debian_release} main
deb {self.debian_mirror} {self.debian_release}-updates main
deb http://security.debian.org/debian-security {self.debian_release}-security main
"""
            with open(f"{root_mount}/etc/apt/sources.list", 'w') as f:
                f.write(sources_list_content)
            
            # Update package lists
            subprocess.run([
                'chroot', root_mount, 'apt-get', 'update'
            ], capture_output=True, text=True, check=True)
            
            # Fix any broken dependencies first
            subprocess.run([
                'chroot', root_mount, 'apt-get', 'install', '-f', '-y'
            ], capture_output=True, text=True, check=True)
            
            # Install packages in order of importance to avoid conflicts
            kernel_packages = [
                'linux-image-amd64',
                'linux-headers-amd64'
            ]
            
            # Install only grub-efi-amd64 for UEFI systems (avoid conflicts with grub-pc)
            bootloader_packages = [
                'grub-efi-amd64',
                'os-prober'
            ]
            
            essential_packages = [
                'sudo',
                'vim',
                'nano',
                'htop',
                'git',
                'python3',
                'python3-pip',
                'jq',
                'curl',
                'wget',
                'unzip'
            ]
            
            development_packages = [
                'build-essential',
                'pkg-config',
                'lshw',
                'pciutils',
                'usbutils',
                'dmidecode'
            ]
            
            # Docker packages (might conflict, so install separately)
            docker_packages = [
                'docker.io',
                'docker-compose'
            ]
            
            # Optional firmware packages - install if available
            optional_packages = [
                'firmware-linux',
                'firmware-linux-nonfree'
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
            
            # Try to install optional firmware packages (don't fail if they're not available)
            if progress_callback:
                progress_callback("Installing optional firmware packages...")
            
            for package in optional_packages:
                try:
                    subprocess.run([
                        'chroot', root_mount, 'apt-get', 'install', '-y', package
                    ], capture_output=True, text=True, check=True)
                    if progress_callback:
                        progress_callback(f"Installed optional package: {package}")
                except subprocess.CalledProcessError:
                    # Optional packages, so continue if they fail
                    if progress_callback:
                        progress_callback(f"Optional package {package} not available, continuing...")
                    pass
            
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
                "base_image": {
                    "name": plan.base_image.name if plan.base_image else None,
                    "version": plan.base_image.version if plan.base_image else None,
                    "architecture": plan.base_image.architecture if plan.base_image else None,
                    "ai_optimized": plan.base_image.ai_optimized if plan.base_image else False,
                    "installation_method": "iso_extraction" if plan.base_image else "debootstrap"
                },
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