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
        """Create partition plan for full wipe mode."""
        total_size = drive.size
        
        # Calculate partition sizes
        efi_size = 512 * 1024 * 1024  # 512MB for EFI boot partition
        root_size = 20 * 1024 * 1024 * 1024  # 20GB for OS root partition
        swap_size = min(4 * 1024 * 1024 * 1024, total_size // 32)  # 4GB or 1/32 of drive, whichever is smaller
        models_size = total_size - efi_size - root_size - swap_size - (100 * 1024 * 1024)  # Remaining space minus 100MB buffer
        
        partitions = [
            {
                'number': 1,
                'type': 'EFI System',
                'filesystem': 'fat32',
                'size': efi_size,
                'label': 'WEIRDING_EFI',
                'flags': ['boot', 'esp'],
                'mount_point': '/boot/efi'
            },
            {
                'number': 2,
                'type': 'Linux filesystem',
                'filesystem': 'ext4',
                'size': root_size,
                'label': f'{module_name}_ROOT' if module_name else 'WEIRDING_ROOT',
                'flags': [],
                'mount_point': '/'
            },
            {
                'number': 3,
                'type': 'Linux swap',
                'filesystem': 'linux-swap',
                'size': swap_size,
                'label': 'WEIRDING_SWAP',
                'flags': [],
                'mount_point': 'swap'
            },
            {
                'number': 4,
                'type': 'Linux filesystem',
                'filesystem': 'ext4',
                'size': models_size,
                'label': f'{module_name}_MODELS' if module_name else 'WEIRDING_MODELS',
                'flags': [],
                'mount_point': '/opt/models'
            }
        ]
        
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
        """Apply full wipe partitioning using sgdisk."""
        try:
            device = plan.drive.device
            
            # Clear existing partition table and create new GPT
            if progress_callback:
                progress_callback("Creating new GPT partition table...")
            
            subprocess.run(['sgdisk', '--zap-all', device], capture_output=True, text=True, check=True)
            subprocess.run(['sgdisk', '--clear', device], capture_output=True, text=True, check=True)
            
            # Create partitions
            current_sector = 2048  # Start after GPT header
            
            for partition in plan.partitions:
                if progress_callback:
                    progress_callback(f"Creating partition {partition['number']}: {partition['label']}")
                
                # Calculate partition size in sectors (512 bytes per sector)
                size_sectors = partition['size'] // 512
                end_sector = current_sector + size_sectors - 1
                
                # Create partition
                cmd = [
                    'sgdisk',
                    f"--new={partition['number']}:{current_sector}:{end_sector}",
                    f"--typecode={partition['number']}:{self._get_partition_type_code(partition['type'])}",
                    f"--change-name={partition['number']}:{partition['label']}",
                    device
                ]
                
                subprocess.run(cmd, capture_output=True, text=True, check=True)
                
                # Set flags if needed
                for flag in partition.get('flags', []):
                    if flag == 'boot':
                        subprocess.run(['sgdisk', f"--attributes={partition['number']}:set:2", device], 
                                     capture_output=True, text=True, check=True)
                    elif flag == 'esp':
                        # EFI System Partition type is already set by typecode
                        pass
                
                current_sector = end_sector + 1
            
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
                    
                else:
                    print(f"Warning: Unknown filesystem type {filesystem} for {partition_device}")
                    
            except subprocess.CalledProcessError as e:
                print(f"Error formatting {partition_device}: {e.stderr}")
                raise
    
    def _get_partition_type_code(self, partition_type: str) -> str:
        """Get SGDisk type code for partition type."""
        type_codes = {
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