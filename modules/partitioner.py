#!/usr/bin/env python3
"""
Partitioning Module for Weirding Host Utility

This module handles disk partitioning operations for converting external drives
into Weirding Modules, including GPT partition table creation, backup/recovery,
and support for both full wipe and dual-use scenarios.
"""

import subprocess
import json
import os
import time
import tempfile
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

from device_setup import DriveInfo


@dataclass
class PartitionPlan:
    """Plan for partitioning a drive."""
    drive: DriveInfo
    mode: str  # 'full_wipe' or 'dual_use'
    partitions: List[Dict]
    backup_file: Optional[str] = None
    base_image: Optional[object] = None  # BaseImage object


class DrivePartitioner:
    """Handles partitioning operations for Weirding Module setup."""
    
    def __init__(self):
        self.backup_dir = Path.home() / ".weirding_backups"
        self.backup_dir.mkdir(exist_ok=True)
    
    def create_partition_plan(self, drive: DriveInfo, mode: str, module_name: str = None) -> PartitionPlan:
        """
        Create a partitioning plan based on drive and setup mode.
        
        Args:
            drive: DriveInfo object for the target drive
            mode: Setup mode ('full_wipe' or 'dual_use')
            module_name: Optional name for the module
            
        Returns:
            PartitionPlan object with the planned partition layout
        """
        partitions = []
        
        if mode == 'full_wipe':
            # Full wipe mode: Create complete new partition table
            partitions = self._create_full_wipe_plan(drive, module_name)
        elif mode == 'dual_use':
            # Dual-use mode: Add Weirding partition to existing layout
            partitions = self._create_dual_use_plan(drive, module_name)
        else:
            raise ValueError(f"Unknown setup mode: {mode}")
        
        return PartitionPlan(
            drive=drive,
            mode=mode,
            partitions=partitions
        )
    
    def _create_full_wipe_plan(self, drive: DriveInfo, module_name: str = None) -> List[Dict]:
        """Create partition plan for full wipe mode with proper GPT overhead accounting."""
        total_size = drive.size
        
        # DIAGNOSTIC: Log initial drive size and partition calculation
        print(f"[DEBUG] Planning partitions for drive {drive.device}")
        print(f"[DEBUG] Drive total size: {total_size:,} bytes ({total_size // (1024**3):.1f} GB)")
        
        # Calculate usable space accounting for GPT overhead upfront
        drive_size_sectors = total_size // 512
        primary_gpt_sectors = 2048  # Primary GPT + alignment (1MB)
        backup_gpt_sectors = 33     # Backup GPT table
        usable_sectors = drive_size_sectors - primary_gpt_sectors - backup_gpt_sectors
        usable_size = usable_sectors * 512
        
        print(f"[DEBUG] GPT overhead calculation:")
        print(f"  Drive sectors: {drive_size_sectors:,}")
        print(f"  Primary GPT + alignment: {primary_gpt_sectors} sectors ({primary_gpt_sectors * 512:,} bytes)")
        print(f"  Backup GPT: {backup_gpt_sectors} sectors ({backup_gpt_sectors * 512:,} bytes)")
        print(f"  Usable sectors: {usable_sectors:,}")
        print(f"  Usable size: {usable_size:,} bytes ({usable_size // (1024**3):.1f} GB)")
        
        # Calculate fixed partition sizes
        bios_boot_size = 2 * 1024 * 1024  # 2MB for GRUB
        efi_size = 512 * 1024 * 1024  # 512MB for EFI boot partition
        
        # Scale root partition based on drive size (but cap at 20GB for large drives)
        if usable_size < 64 * 1024**3:  # Less than 64GB usable
            root_size = 10 * 1024**3  # 10GB for smaller drives
        else:
            root_size = 20 * 1024**3  # 20GB for larger drives
        
        # Calculate swap size (4GB or 1/32 of usable space, whichever is smaller)
        swap_size = min(4 * 1024**3, usable_size // 32)
        
        # Reserve alignment buffer (10MB for partition alignment overhead)
        alignment_buffer = 10 * 1024 * 1024
        
        # Calculate models partition size (remaining usable space)
        fixed_partitions_size = bios_boot_size + efi_size + root_size + swap_size + alignment_buffer
        models_size = usable_size - fixed_partitions_size
        
        # DIAGNOSTIC: Log individual partition sizes
        print(f"[DEBUG] Partition size calculations (accounting for GPT overhead):")
        print(f"  BIOS boot: {bios_boot_size:,} bytes ({bios_boot_size // (1024**2)} MB)")
        print(f"  EFI: {efi_size:,} bytes ({efi_size // (1024**2)} MB)")
        print(f"  Root: {root_size:,} bytes ({root_size // (1024**3)} GB)")
        print(f"  Swap: {swap_size:,} bytes ({swap_size // (1024**3):.1f} GB)")
        print(f"  Alignment buffer: {alignment_buffer:,} bytes ({alignment_buffer // (1024**2)} MB)")
        print(f"  Models (remaining): {models_size:,} bytes ({models_size // (1024**3):.1f} GB)")
        
        # Sanity check: ensure models partition is reasonable
        if models_size < 5 * 1024**3:  # Less than 5GB
            print(f"[ERROR] Models partition too small: {models_size // (1024**3):.1f} GB")
            print(f"[ERROR] Drive may be too small for full Weirding Module setup")
            # Reduce root partition as fallback
            root_size = 8 * 1024**3  # 8GB minimum
            models_size = usable_size - (bios_boot_size + efi_size + root_size + swap_size + alignment_buffer)
            print(f"[FALLBACK] Reduced root to {root_size // (1024**3)} GB, models now {models_size // (1024**3):.1f} GB")
        
        # DIAGNOSTIC: Check total allocation against usable space
        total_allocated = bios_boot_size + efi_size + root_size + swap_size + models_size
        print(f"[DEBUG] Total allocated: {total_allocated:,} bytes ({total_allocated // (1024**3):.1f} GB)")
        print(f"[DEBUG] Usable space: {usable_size:,} bytes ({usable_size // (1024**3):.1f} GB)")
        print(f"[DEBUG] Remaining for alignment: {usable_size - total_allocated:,} bytes")
        
        # Create partition layout with calculated sizes
        partitions = [
            {
                'number': 1,
                'type': 'BIOS boot',
                'filesystem': 'none',
                'size': bios_boot_size,
                'label': 'BIOS_BOOT',
                'flags': ['bios_grub'],
                'mount_point': None
            },
            {
                'number': 2,
                'type': 'EFI System',
                'filesystem': 'fat32',
                'size': efi_size,
                'label': 'WEIRD_EFI',
                'flags': ['boot', 'esp'],
                'mount_point': '/boot/efi'
            },
            {
                'number': 3,
                'type': 'Linux filesystem',
                'filesystem': 'ext4',
                'size': root_size,
                'label': f'{module_name}_ROOT' if module_name else 'WEIRDING_ROOT',
                'flags': [],
                'mount_point': '/'
            },
            {
                'number': 4,
                'type': 'Linux swap',
                'filesystem': 'linux-swap',
                'size': swap_size,
                'label': 'WEIRDING_SWAP',
                'flags': [],
                'mount_point': 'swap'
            },
            {
                'number': 5,
                'type': 'Linux filesystem',
                'filesystem': 'ext4',
                'size': models_size,
                'label': f'{module_name}_MODELS' if module_name else 'WEIRDING_MODELS',
                'flags': [],
                'mount_point': '/opt/models'
            }
        ]
        
        # Final validation
        total_partition_size = sum(p['size'] for p in partitions)
        if total_partition_size > usable_size:
            print(f"[ERROR] Total partition size {total_partition_size:,} exceeds usable space {usable_size:,}")
            raise ValueError("Partition plan exceeds available space")
        
        print(f"[DEBUG] Partition plan created successfully")
        print(f"[DEBUG] {len(partitions)} partitions, total size: {total_partition_size:,} bytes")
        
        return partitions
    
    def _create_dual_use_plan(self, drive: DriveInfo, module_name: str = None) -> List[Dict]:
        """Create partition plan for dual-use mode."""
        # Get current partition information
        current_partitions = self._get_current_partitions(drive)
        
        # Calculate available space for Weirding partition
        used_space = sum(self._get_partition_size(p) for p in current_partitions)
        available_space = drive.size - used_space
        
        # Reserve space for Weirding Module (minimum 25GB, maximum 50GB or available space)
        weirding_size = min(50 * 1024 * 1024 * 1024, max(25 * 1024 * 1024 * 1024, available_space - 1024 * 1024 * 1024))
        
        # Find next available partition number
        next_partition_num = max([p.get('number', 0) for p in current_partitions], default=0) + 1
        
        # Create new Weirding partition
        new_partition = {
            'number': next_partition_num,
            'type': 'Linux filesystem',
            'filesystem': 'ext4',
            'size': weirding_size,
            'label': f'{module_name}_WEIRDING' if module_name else 'WEIRDING_MODULE',
            'flags': [],
            'mount_point': '/opt/weirding',
            'action': 'create'  # Mark as new partition
        }
        
        # Return existing partitions plus new one
        partitions = current_partitions.copy()
        for partition in partitions:
            partition['action'] = 'preserve'  # Mark existing partitions as preserved
        
        partitions.append(new_partition)
        return partitions
    
    def backup_partition_table(self, drive: DriveInfo) -> str:
        """
        Create a backup of the current partition table.
        
        Args:
            drive: DriveInfo object for the drive to backup
            
        Returns:
            Path to the backup file
        """
        timestamp = int(time.time())
        device_name = drive.device.replace('/dev/', '')
        backup_filename = f"{device_name}_partition_backup_{timestamp}.sgdisk"
        backup_path = self.backup_dir / backup_filename
        
        try:
            # Use sgdisk to backup GPT partition table
            result = subprocess.run([
                'sgdisk', '--backup', str(backup_path), drive.device
            ], capture_output=True, text=True, check=True)
            
            # Also create a human-readable backup
            readable_backup = backup_path.with_suffix('.txt')
            result = subprocess.run([
                'sgdisk', '--print', drive.device
            ], capture_output=True, text=True, check=True)
            
            with open(readable_backup, 'w') as f:
                f.write(f"Partition table backup for {drive.device}\n")
                f.write(f"Created: {time.ctime()}\n")
                f.write(f"Drive: {drive.model} ({drive.vendor})\n")
                f.write(f"Size: {drive.size} bytes\n\n")
                f.write(result.stdout)
            
            return str(backup_path)
            
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to backup partition table: {e.stderr}")
    
    def restore_partition_table(self, drive: DriveInfo, backup_file: str) -> bool:
        """
        Restore partition table from backup.
        
        Args:
            drive: DriveInfo object for the target drive
            backup_file: Path to the backup file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Verify backup file exists
            if not os.path.exists(backup_file):
                raise FileNotFoundError(f"Backup file not found: {backup_file}")
            
            # Restore using sgdisk
            result = subprocess.run([
                'sgdisk', '--load-backup', backup_file, drive.device
            ], capture_output=True, text=True, check=True)
            
            # Inform kernel of partition table changes
            subprocess.run(['partprobe', drive.device], capture_output=True)
            
            return True
            
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"Failed to restore partition table: {e}")
            return False
    
    def apply_partition_plan(self, plan: PartitionPlan, progress_callback=None) -> bool:
        """
        Apply the partitioning plan to the drive.
        
        Args:
            plan: PartitionPlan object with the partitioning plan
            progress_callback: Optional callback for progress updates
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Step 1: Create backup
            if progress_callback:
                progress_callback("Creating partition table backup...")
            
            plan.backup_file = self.backup_partition_table(plan.drive)
            
            # Step 2: Unmount all partitions
            if progress_callback:
                progress_callback("Unmounting drive partitions...")
            
            self._unmount_all_partitions(plan.drive)
            
            # Step 3: Apply partitioning based on mode
            if plan.mode == 'full_wipe':
                success = self._apply_full_wipe_partitioning(plan, progress_callback)
            elif plan.mode == 'dual_use':
                success = self._apply_dual_use_partitioning(plan, progress_callback)
            else:
                raise ValueError(f"Unknown partitioning mode: {plan.mode}")
            
            if not success:
                return False
            
            # Step 4: Inform kernel of changes
            if progress_callback:
                progress_callback("Updating kernel partition table...")
            
            subprocess.run(['partprobe', plan.drive.device], capture_output=True)
            time.sleep(2)  # Give kernel time to recognize changes
            
            # Step 5: Format new partitions
            if progress_callback:
                progress_callback("Formatting new partitions...")
            
            self._format_partitions(plan, progress_callback)
            
            return True
            
        except Exception as e:
            print(f"Error applying partition plan: {e}")
            
            # Attempt to restore from backup if available
            if plan.backup_file and os.path.exists(plan.backup_file):
                print("Attempting to restore from backup...")
                self.restore_partition_table(plan.drive, plan.backup_file)
            
            return False
    
    def _apply_full_wipe_partitioning(self, plan: PartitionPlan, progress_callback=None) -> bool:
        """Apply full wipe partitioning using sgdisk with proper GPT space handling."""
        try:
            device = plan.drive.device
            
            # DIAGNOSTIC: Log drive size and partition calculations
            print(f"[DEBUG] Drive {device}: Total size = {plan.drive.size:,} bytes ({plan.drive.size // (1024**3):.1f} GB)")
            
            # Clear existing partition table and create new GPT
            if progress_callback:
                progress_callback("Creating new GPT partition table...")
            
            subprocess.run(['sgdisk', '--zap-all', device], capture_output=True, text=True, check=True)
            subprocess.run(['sgdisk', '--clear', device], capture_output=True, text=True, check=True)
            
            # Calculate usable space accounting for GPT overhead
            drive_size_sectors = plan.drive.size // 512
            backup_gpt_sectors = 33  # GPT backup table requires 33 sectors
            usable_sectors = drive_size_sectors - backup_gpt_sectors
            usable_bytes = usable_sectors * 512
            
            print(f"[DEBUG] Drive total sectors: {drive_size_sectors:,}")
            print(f"[DEBUG] Backup GPT sectors reserved: {backup_gpt_sectors}")
            print(f"[DEBUG] Usable sectors: {usable_sectors:,}")
            print(f"[DEBUG] Usable bytes: {usable_bytes:,} ({usable_bytes // (1024**3):.1f} GB)")
            
            # Recalculate last partition size to fit within usable space
            total_fixed_partitions_size = sum(p['size'] for p in plan.partitions[:-1])
            available_for_last = usable_bytes - 2048 * 512 - total_fixed_partitions_size  # Account for starting sector
            
            if available_for_last < plan.partitions[-1]['size']:
                original_size = plan.partitions[-1]['size']
                plan.partitions[-1]['size'] = available_for_last
                print(f"[WARNING] Adjusted last partition from {original_size:,} bytes to {available_for_last:,} bytes")
                print(f"[WARNING] Space saved: {original_size - available_for_last:,} bytes ({(original_size - available_for_last)/(1024**3):.1f} GB)")
            
            # Create partitions with proper alignment (1MB boundaries)
            current_sector = 2048  # Start after GPT header (already 1MB aligned)
            
            for i, partition in enumerate(plan.partitions):
                if progress_callback:
                    progress_callback(f"Creating partition {partition['number']}: {partition['label']}")
                
                # Calculate partition size in sectors with proper rounding
                size_bytes = partition['size']
                size_sectors = (size_bytes + 511) // 512  # Round up to next sector
                
                # Align to 1MB boundaries (2048 sectors = 1MB) for optimal performance
                if partition['type'] != 'BIOS boot':  # BIOS boot partition doesn't need alignment
                    alignment_sectors = 2048
                    size_sectors = ((size_sectors + alignment_sectors - 1) // alignment_sectors) * alignment_sectors
                
                end_sector = current_sector + size_sectors - 1
                actual_size_bytes = size_sectors * 512
                
                print(f"[DEBUG] Partition {partition['number']} ({partition['label']}):")
                print(f"  Requested size: {size_bytes:,} bytes ({size_bytes // (1024**2):.1f} MB)")
                print(f"  Aligned sectors: {size_sectors:,}")
                print(f"  Sector range: {current_sector} - {end_sector}")
                print(f"  Actual size: {actual_size_bytes:,} bytes ({actual_size_bytes // (1024**2):.1f} MB)")
                
                # Final safety check for last partition
                if i == len(plan.partitions) - 1:
                    if end_sector > usable_sectors:
                        print(f"[ERROR] Last partition still extends beyond usable space!")
                        print(f"[ERROR] End sector {end_sector} > usable sectors {usable_sectors}")
                        # Force fit within usable space
                        end_sector = usable_sectors
                        size_sectors = end_sector - current_sector + 1
                        actual_size_bytes = size_sectors * 512
                        print(f"[FIXED] Adjusted to end at sector {end_sector}, size: {actual_size_bytes:,} bytes")
                
                # Create partition using sgdisk
                cmd = [
                    'sgdisk',
                    f"--new={partition['number']}:{current_sector}:{end_sector}",
                    f"--typecode={partition['number']}:{self._get_partition_type_code(partition['type'])}",
                    f"--change-name={partition['number']}:{partition['label']}",
                    device
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                
                # Set partition flags if needed
                for flag in partition.get('flags', []):
                    if flag == 'boot':
                        subprocess.run(['sgdisk', f"--attributes={partition['number']}:set:2", device],
                                     capture_output=True, text=True, check=True)
                    elif flag == 'bios_grub':
                        subprocess.run(['sgdisk', f"--attributes={partition['number']}:set:0", device],
                                     capture_output=True, text=True, check=True)
                
                current_sector = end_sector + 1
            
            # Verify final partition table
            result = subprocess.run(['sgdisk', '--verify', device], capture_output=True, text=True)
            if result.returncode != 0:
                print(f"[WARNING] GPT verification failed: {result.stderr}")
            else:
                print(f"[DEBUG] GPT partition table verified successfully")
            
            # DIAGNOSTIC: Print final partition table
            result = subprocess.run(['sgdisk', '--print', device], capture_output=True, text=True)
            print(f"[DEBUG] Final partition table:")
            print(result.stdout)
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"Error in full wipe partitioning: {e.stderr}")
            return False
    
    def _apply_dual_use_partitioning(self, plan: PartitionPlan, progress_callback=None) -> bool:
        """Apply dual-use partitioning by adding new partition."""
        try:
            device = plan.drive.device
            
            # Find the new partition to create
            new_partitions = [p for p in plan.partitions if p.get('action') == 'create']
            
            for partition in new_partitions:
                if progress_callback:
                    progress_callback(f"Creating new partition: {partition['label']}")
                
                # Use sgdisk to create new partition in available space
                cmd = [
                    'sgdisk',
                    f"--new={partition['number']}:0:+{partition['size'] // (1024*1024)}M",
                    f"--typecode={partition['number']}:{self._get_partition_type_code(partition['type'])}",
                    f"--change-name={partition['number']}:{partition['label']}",
                    device
                ]
                
                subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"Error in dual-use partitioning: {e.stderr}")
            return False
    
    def _format_partitions(self, plan: PartitionPlan, progress_callback=None):
        """Format the partitions according to the plan."""
        for partition in plan.partitions:
            # Skip existing partitions in dual-use mode
            if partition.get('action') == 'preserve':
                continue
            
            partition_device = f"{plan.drive.device}{partition['number']}"
            filesystem = partition['filesystem']
            label = partition['label']
            
            if progress_callback:
                progress_callback(f"Formatting {partition_device} as {filesystem}")
            
            try:
                if filesystem == 'ext4':
                    subprocess.run([
                        'mkfs.ext4', '-F', '-L', label, partition_device
                    ], capture_output=True, text=True, check=True)
                    
                elif filesystem == 'fat32':
                    subprocess.run([
                        'mkfs.fat', '-F', '32', '-n', label, partition_device
                    ], capture_output=True, text=True, check=True)
                    
                elif filesystem == 'linux-swap':
                    subprocess.run([
                        'mkswap', '-L', label, partition_device
                    ], capture_output=True, text=True, check=True)
                    
                elif filesystem == 'none':
                    # Skip formatting for BIOS boot partition and similar
                    continue
                    
                else:
                    print(f"Warning: Unknown filesystem type {filesystem} for {partition_device}")
                    
            except subprocess.CalledProcessError as e:
                print(f"Error formatting {partition_device}: {e.stderr}")
                raise
    
    def _get_partition_type_code(self, partition_type: str) -> str:
        """Get SGDisk type code for partition type."""
        type_codes = {
            'BIOS boot': 'EF02',
            'EFI System': 'EF00',
            'Linux filesystem': '8300',
            'Linux swap': '8200',
            'Microsoft basic data': '0700'
        }
        return type_codes.get(partition_type, '8300')
    
    def _get_current_partitions(self, drive: DriveInfo) -> List[Dict]:
        """Get current partition information from the drive."""
        partitions = []
        
        for i, partition_info in enumerate(drive.partitions, 1):
            partitions.append({
                'number': i,
                'name': partition_info['name'],
                'size': self._parse_size_to_bytes(partition_info['size']),
                'filesystem': partition_info['fstype'],
                'mountpoint': partition_info['mountpoint']
            })
        
        return partitions
    
    def _get_partition_size(self, partition: Dict) -> int:
        """Get partition size in bytes."""
        return partition.get('size', 0)
    
    def _parse_size_to_bytes(self, size_str: str) -> int:
        """Convert size string to bytes (reuse from DriveDetector)."""
        if not size_str:
            return 0
        
        import re
        size_str = size_str.strip()
        match = re.match(r'([0-9.]+)([KMGTPE]?)', size_str.upper())
        if not match:
            return 0
        
        number = float(match.group(1))
        unit = match.group(2)
        
        multipliers = {
            '': 1, 'K': 1024, 'M': 1024**2, 'G': 1024**3,
            'T': 1024**4, 'P': 1024**5, 'E': 1024**6
        }
        
        return int(number * multipliers.get(unit, 1))
    
    def _unmount_all_partitions(self, drive: DriveInfo):
        """Unmount all partitions on the drive."""
        try:
            # Get all mounted partitions for this device
            result = subprocess.run(['mount'], capture_output=True, text=True)
            mount_lines = result.stdout.split('\n')
            
            partitions_to_unmount = []
            for line in mount_lines:
                if drive.device in line:
                    parts = line.split()
                    if len(parts) > 0:
                        partition = parts[0]
                        partitions_to_unmount.append(partition)
            
            # Unmount each partition
            for partition in partitions_to_unmount:
                try:
                    subprocess.run(['umount', partition], capture_output=True, text=True, check=True)
                except subprocess.CalledProcessError:
                    # Try lazy unmount if regular unmount fails
                    try:
                        subprocess.run(['umount', '-l', partition], capture_output=True, text=True, check=True)
                    except subprocess.CalledProcessError:
                        pass  # Continue with other partitions
            
        except Exception:
            pass  # Ignore errors in unmounting


def main():
    """Test the partitioner functionality."""
    from device_setup import DriveDetector
    
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
    
    print(f"Testing partitioner with drive: {test_drive.device}")
    print(f"Drive model: {test_drive.model}")
    print(f"Drive size: {detector.format_size(test_drive.size)}")
    
    # Create partition plans
    print("\n=== Full Wipe Plan ===")
    full_wipe_plan = partitioner.create_partition_plan(test_drive, 'full_wipe', 'TestModule')
    for i, partition in enumerate(full_wipe_plan.partitions):
        print(f"Partition {partition['number']}: {partition['label']} "
              f"({detector.format_size(partition['size'])}) - {partition['filesystem']}")
    
    print("\n=== Dual Use Plan ===")
    dual_use_plan = partitioner.create_partition_plan(test_drive, 'dual_use', 'TestModule')
    for partition in dual_use_plan.partitions:
        action = partition.get('action', 'unknown')
        size_info = detector.format_size(partition.get('size', 0)) if partition.get('size') else 'existing'
        print(f"Partition {partition.get('number', '?')}: {partition.get('label', 'N/A')} "
              f"({size_info}) - {action}")


if __name__ == "__main__":
    main()