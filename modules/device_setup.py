#!/usr/bin/env python3
"""
Device Setup Module for Weirding Host Utility

This module handles detection, analysis, and setup of external storage devices
for conversion into Weirding Modules (portable AI servers).
"""

import subprocess
import json
import re
import os
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DriveInfo:
    """Information about a storage device."""
    device: str
    size: int
    model: str
    vendor: str
    serial: str
    removable: bool
    mounted: bool
    mount_points: List[str]
    partitions: List[Dict]
    filesystem_type: Optional[str]
    usage_percent: Optional[float]
    is_external: bool
    connection_type: str  # USB, SATA, NVMe, etc.


class DriveDetector:
    """Detects and analyzes storage devices for Weirding Module setup."""
    
    def __init__(self):
        self.detected_drives: List[DriveInfo] = []
    
    def scan_drives(self) -> List[DriveInfo]:
        """
        Scan system for all storage devices and identify external drives.
        
        Returns:
            List of DriveInfo objects for detected drives
        """
        self.detected_drives = []
        
        try:
            # Use lsblk to get detailed block device information
            result = subprocess.run([
                'lsblk', '-J', '-o', 
                'NAME,SIZE,MODEL,VENDOR,SERIAL,RM,MOUNTPOINT,FSTYPE,TYPE,TRAN'
            ], capture_output=True, text=True, check=True)
            
            lsblk_data = json.loads(result.stdout)
            
            for device in lsblk_data.get('blockdevices', []):
                if device.get('type') == 'disk':
                    drive_info = self._parse_drive_info(device)
                    if drive_info:
                        self.detected_drives.append(drive_info)
            
        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            print(f"Error scanning drives: {e}")
            return []
        
        return self.detected_drives
    
    def _parse_drive_info(self, device_data: Dict) -> Optional[DriveInfo]:
        """
        Parse lsblk device data into DriveInfo object.
        
        Args:
            device_data: Raw device data from lsblk
            
        Returns:
            DriveInfo object or None if parsing fails
        """
        try:
            device_name = f"/dev/{device_data['name']}"
            size_str = device_data.get('size', '0')
            size_bytes = self._parse_size_to_bytes(size_str)
            
            # Determine if device is external/removable
            is_removable = device_data.get('rm') == '1'
            connection_type = device_data.get('tran', 'unknown').upper()
            is_external = is_removable or connection_type == 'USB'
            
            # Get partition information
            partitions = []
            mount_points = []
            mounted = False
            
            if 'children' in device_data:
                for child in device_data['children']:
                    partition_info = {
                        'name': f"/dev/{child['name']}",
                        'size': child.get('size', ''),
                        'fstype': child.get('fstype', ''),
                        'mountpoint': child.get('mountpoint', '')
                    }
                    partitions.append(partition_info)
                    
                    if child.get('mountpoint'):
                        mount_points.append(child['mountpoint'])
                        mounted = True
            
            # Get filesystem info for the main device
            main_mountpoint = device_data.get('mountpoint')
            if main_mountpoint:
                mount_points.append(main_mountpoint)
                mounted = True
            
            return DriveInfo(
                device=device_name,
                size=size_bytes,
                model=(device_data.get('model') or 'Unknown').strip(),
                vendor=(device_data.get('vendor') or 'Unknown').strip(),
                serial=(device_data.get('serial') or 'Unknown').strip(),
                removable=is_removable,
                mounted=mounted,
                mount_points=mount_points,
                partitions=partitions,
                filesystem_type=device_data.get('fstype'),
                usage_percent=None,  # Will be calculated separately
                is_external=is_external,
                connection_type=connection_type
            )
            
        except Exception as e:
            print(f"Error parsing device data: {e}")
            return None
    
    def _parse_size_to_bytes(self, size_str: str) -> int:
        """
        Convert size string (e.g., '1.8T', '500G') to bytes.
        
        Args:
            size_str: Size string from lsblk
            
        Returns:
            Size in bytes
        """
        if not size_str:
            return 0
        
        # Remove any whitespace
        size_str = size_str.strip()
        
        # Extract number and unit
        match = re.match(r'([0-9.]+)([KMGTPE]?)', size_str.upper())
        if not match:
            return 0
        
        number = float(match.group(1))
        unit = match.group(2)
        
        multipliers = {
            '': 1,
            'K': 1024,
            'M': 1024**2,
            'G': 1024**3,
            'T': 1024**4,
            'P': 1024**5,
            'E': 1024**6
        }
        
        return int(number * multipliers.get(unit, 1))
    
    def get_external_drives(self) -> List[DriveInfo]:
        """
        Get only external/removable drives suitable for Weirding Module setup.
        
        Returns:
            List of external DriveInfo objects
        """
        return [drive for drive in self.detected_drives if drive.is_external]
    
    def analyze_drive_usage(self, drive: DriveInfo) -> Dict:
        """
        Analyze current usage and partition layout of a drive.
        
        Args:
            drive: DriveInfo object to analyze
            
        Returns:
            Dictionary with usage analysis
        """
        analysis = {
            'total_size': drive.size,
            'used_space': 0,
            'free_space': 0,
            'partition_count': len(drive.partitions),
            'has_data': False,
            'filesystem_types': [],
            'mount_status': drive.mounted,
            'safety_warnings': []
        }
        
        # Calculate used space from mounted partitions
        for partition in drive.partitions:
            if partition['mountpoint']:
                try:
                    statvfs = os.statvfs(partition['mountpoint'])
                    total_bytes = statvfs.f_frsize * statvfs.f_blocks
                    free_bytes = statvfs.f_frsize * statvfs.f_bavail
                    used_bytes = total_bytes - free_bytes
                    
                    analysis['used_space'] += used_bytes
                    analysis['has_data'] = True
                    
                except OSError:
                    pass
            
            if partition['fstype']:
                analysis['filesystem_types'].append(partition['fstype'])
        
        analysis['free_space'] = drive.size - analysis['used_space']
        analysis['filesystem_types'] = list(set(analysis['filesystem_types']))
        
        # Add safety warnings
        if analysis['has_data']:
            analysis['safety_warnings'].append("Drive contains existing data")
        
        if drive.mounted:
            analysis['safety_warnings'].append("Drive is currently mounted")
        
        if analysis['partition_count'] > 0:
            analysis['safety_warnings'].append(f"Drive has {analysis['partition_count']} existing partitions")
        
        return analysis
    
    def format_size(self, bytes_size: int) -> str:
        """
        Format byte size into human-readable string.
        
        Args:
            bytes_size: Size in bytes
            
        Returns:
            Formatted size string (e.g., '1.5 GB')
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.1f} EB"
    
    def check_drive_requirements(self, drive: DriveInfo) -> Tuple[bool, List[str]]:
        """
        Check if drive meets minimum requirements for Weirding Module.
        
        Args:
            drive: DriveInfo object to check
            
        Returns:
            Tuple of (meets_requirements, list_of_issues)
        """
        issues = []
        
        # Minimum size requirement (32GB)
        min_size = 32 * 1024**3  # 32GB in bytes
        if drive.size < min_size:
            issues.append(f"Drive too small: {self.format_size(drive.size)} < {self.format_size(min_size)}")
        
        # Check if it's actually external
        if not drive.is_external:
            issues.append("Drive does not appear to be external/removable")
        
        # Check connection type
        if drive.connection_type not in ['USB', 'UNKNOWN']:
            issues.append(f"Unusual connection type: {drive.connection_type}")
        
        return len(issues) == 0, issues


def main():
    """Test the drive detection functionality."""
    detector = DriveDetector()
    drives = detector.scan_drives()
    
    print("Detected Storage Devices:")
    print("=" * 50)
    
    for drive in drives:
        print(f"\nDevice: {drive.device}")
        print(f"Model: {drive.model} ({drive.vendor})")
        print(f"Size: {detector.format_size(drive.size)}")
        print(f"Connection: {drive.connection_type}")
        print(f"External: {drive.is_external}")
        print(f"Mounted: {drive.mounted}")
        
        if drive.mount_points:
            print(f"Mount points: {', '.join(drive.mount_points)}")
        
        print(f"Partitions: {len(drive.partitions)}")
        
        # Check requirements
        meets_req, issues = detector.check_drive_requirements(drive)
        print(f"Suitable for Weirding Module: {meets_req}")
        if issues:
            print(f"Issues: {', '.join(issues)}")
    
    # Show external drives specifically
    external_drives = detector.get_external_drives()
    if external_drives:
        print(f"\n\nExternal Drives Suitable for Weirding Module:")
        print("=" * 50)
        for drive in external_drives:
            analysis = detector.analyze_drive_usage(drive)
            print(f"\n{drive.device} - {drive.model}")
            print(f"  Size: {detector.format_size(drive.size)}")
            print(f"  Used: {detector.format_size(analysis['used_space'])}")
            print(f"  Free: {detector.format_size(analysis['free_space'])}")
            if analysis['safety_warnings']:
                print(f"  Warnings: {', '.join(analysis['safety_warnings'])}")


if __name__ == "__main__":
    main()