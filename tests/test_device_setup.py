#!/usr/bin/env python3
"""
Unit tests for the device_setup module.

Tests the DriveDetector class functionality including drive scanning,
analysis, and requirements checking.
"""

import unittest
from unittest.mock import patch, MagicMock, mock_open
import subprocess
import json
import sys
import os
from pathlib import Path

# Add modules directory to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent / "modules"))

from device_setup import DriveDetector, DriveInfo


class TestDriveDetector(unittest.TestCase):
    """Test cases for DriveDetector class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.detector = DriveDetector()
        
        # Sample lsblk output for testing
        self.sample_lsblk_output = {
            "blockdevices": [
                {
                    "name": "sda",
                    "size": "0B",
                    "model": "MassStorageClass",
                    "vendor": "Generic",
                    "serial": "123456789",
                    "rm": "1",
                    "mountpoint": None,
                    "fstype": None,
                    "type": "disk",
                    "tran": "usb",
                    "children": []
                },
                {
                    "name": "sdc",
                    "size": "1.8T",
                    "model": "PSSD T7 Shield",
                    "vendor": "Samsung",
                    "serial": "S123456789",
                    "rm": "1",
                    "mountpoint": None,
                    "fstype": None,
                    "type": "disk",
                    "tran": "usb",
                    "children": [
                        {
                            "name": "sdc1",
                            "size": "1.8T",
                            "fstype": "exfat",
                            "mountpoint": "/media/user/T7 Shield",
                            "type": "part"
                        }
                    ]
                },
                {
                    "name": "nvme0n1",
                    "size": "476.9G",
                    "model": "Micron_3400_MTFDKBA512TFH",
                    "vendor": "Micron",
                    "serial": "N123456789",
                    "rm": "0",
                    "mountpoint": None,
                    "fstype": None,
                    "type": "disk",
                    "tran": "nvme",
                    "children": [
                        {
                            "name": "nvme0n1p1",
                            "size": "512M",
                            "fstype": "vfat",
                            "mountpoint": "/boot/efi",
                            "type": "part"
                        },
                        {
                            "name": "nvme0n1p2",
                            "size": "476.4G",
                            "fstype": "ext4",
                            "mountpoint": "/",
                            "type": "part"
                        }
                    ]
                }
            ]
        }
    
    def test_parse_size_to_bytes(self):
        """Test size string parsing to bytes."""
        test_cases = [
            ("1.8T", 1.8 * 1024**4),
            ("500G", 500 * 1024**3),
            ("32G", 32 * 1024**3),
            ("1024M", 1024 * 1024**2),
            ("512K", 512 * 1024),
            ("1024", 1024),
            ("", 0),
            ("invalid", 0)
        ]
        
        for size_str, expected_bytes in test_cases:
            with self.subTest(size_str=size_str):
                result = self.detector._parse_size_to_bytes(size_str)
                self.assertEqual(result, int(expected_bytes))
    
    def test_format_size(self):
        """Test byte size formatting to human-readable strings."""
        test_cases = [
            (1024, "1.0 KB"),
            (1024**2, "1.0 MB"),
            (1024**3, "1.0 GB"),
            (1.8 * 1024**4, "1.8 TB"),
            (500, "500.0 B"),
            (0, "0.0 B")
        ]
        
        for bytes_size, expected_str in test_cases:
            with self.subTest(bytes_size=bytes_size):
                result = self.detector.format_size(int(bytes_size))
                self.assertEqual(result, expected_str)
    
    @patch('subprocess.run')
    def test_scan_drives_success(self, mock_run):
        """Test successful drive scanning."""
        # Mock successful lsblk command
        mock_run.return_value = MagicMock(
            stdout=json.dumps(self.sample_lsblk_output),
            returncode=0
        )
        
        drives = self.detector.scan_drives()
        
        # Should find 3 drives
        self.assertEqual(len(drives), 3)
        
        # Check first drive (small USB)
        usb_drive = next(d for d in drives if d.device == "/dev/sda")
        self.assertEqual(usb_drive.model, "MassStorageClass")
        self.assertTrue(usb_drive.is_external)
        self.assertEqual(usb_drive.connection_type, "USB")
        self.assertFalse(usb_drive.mounted)
        
        # Check large external drive
        external_drive = next(d for d in drives if d.device == "/dev/sdc")
        self.assertEqual(external_drive.model, "PSSD T7 Shield")
        self.assertTrue(external_drive.is_external)
        self.assertTrue(external_drive.mounted)
        self.assertEqual(len(external_drive.partitions), 1)
        
        # Check internal NVMe drive
        internal_drive = next(d for d in drives if d.device == "/dev/nvme0n1")
        self.assertEqual(internal_drive.model, "Micron_3400_MTFDKBA512TFH")
        self.assertFalse(internal_drive.is_external)
        self.assertEqual(internal_drive.connection_type, "NVME")
    
    @patch('subprocess.run')
    def test_scan_drives_command_failure(self, mock_run):
        """Test drive scanning when lsblk command fails."""
        mock_run.side_effect = subprocess.CalledProcessError(1, 'lsblk')
        
        drives = self.detector.scan_drives()
        self.assertEqual(len(drives), 0)
    
    @patch('subprocess.run')
    def test_scan_drives_json_parse_error(self, mock_run):
        """Test drive scanning when JSON parsing fails."""
        mock_run.return_value = MagicMock(
            stdout="invalid json",
            returncode=0
        )
        
        drives = self.detector.scan_drives()
        self.assertEqual(len(drives), 0)
    
    def test_get_external_drives(self):
        """Test filtering for external drives only."""
        # Create test drives
        internal_drive = DriveInfo(
            device="/dev/nvme0n1", size=500*1024**3, model="Internal SSD",
            vendor="Samsung", serial="123", removable=False, mounted=True,
            mount_points=["/"], partitions=[], filesystem_type="ext4",
            usage_percent=50.0, is_external=False, connection_type="NVME"
        )
        
        external_drive = DriveInfo(
            device="/dev/sdc", size=1.8*1024**4, model="External SSD",
            vendor="Samsung", serial="456", removable=True, mounted=False,
            mount_points=[], partitions=[], filesystem_type=None,
            usage_percent=None, is_external=True, connection_type="USB"
        )
        
        self.detector.detected_drives = [internal_drive, external_drive]
        
        external_drives = self.detector.get_external_drives()
        self.assertEqual(len(external_drives), 1)
        self.assertEqual(external_drives[0].device, "/dev/sdc")
    
    def test_check_drive_requirements(self):
        """Test drive requirements checking."""
        # Test drive that meets requirements
        good_drive = DriveInfo(
            device="/dev/sdc", size=64*1024**3, model="Good Drive",
            vendor="Samsung", serial="123", removable=True, mounted=False,
            mount_points=[], partitions=[], filesystem_type=None,
            usage_percent=None, is_external=True, connection_type="USB"
        )
        
        meets_req, issues = self.detector.check_drive_requirements(good_drive)
        self.assertTrue(meets_req)
        self.assertEqual(len(issues), 0)
        
        # Test drive that's too small
        small_drive = DriveInfo(
            device="/dev/sda", size=16*1024**3, model="Small Drive",
            vendor="Generic", serial="456", removable=True, mounted=False,
            mount_points=[], partitions=[], filesystem_type=None,
            usage_percent=None, is_external=True, connection_type="USB"
        )
        
        meets_req, issues = self.detector.check_drive_requirements(small_drive)
        self.assertFalse(meets_req)
        self.assertIn("Drive too small", issues[0])
        
        # Test internal drive
        internal_drive = DriveInfo(
            device="/dev/nvme0n1", size=500*1024**3, model="Internal Drive",
            vendor="Samsung", serial="789", removable=False, mounted=True,
            mount_points=["/"], partitions=[], filesystem_type="ext4",
            usage_percent=50.0, is_external=False, connection_type="NVME"
        )
        
        meets_req, issues = self.detector.check_drive_requirements(internal_drive)
        self.assertFalse(meets_req)
        self.assertIn("not appear to be external", issues[0])
        self.assertIn("Unusual connection type", issues[1])
    
    @patch('os.statvfs')
    def test_analyze_drive_usage(self, mock_statvfs):
        """Test drive usage analysis."""
        # Mock filesystem stats
        mock_statvfs.return_value = MagicMock(
            f_frsize=4096,
            f_blocks=1000000,  # Total blocks
            f_bavail=500000    # Available blocks
        )
        
        # Create test drive with mounted partition
        test_drive = DriveInfo(
            device="/dev/sdc", size=4*1024**3, model="Test Drive",
            vendor="Test", serial="123", removable=True, mounted=True,
            mount_points=["/media/test"], 
            partitions=[{
                'name': '/dev/sdc1',
                'size': '4G',
                'fstype': 'ext4',
                'mountpoint': '/media/test'
            }],
            filesystem_type="ext4", usage_percent=None, 
            is_external=True, connection_type="USB"
        )
        
        analysis = self.detector.analyze_drive_usage(test_drive)
        
        self.assertEqual(analysis['total_size'], 4*1024**3)
        self.assertEqual(analysis['partition_count'], 1)
        self.assertTrue(analysis['has_data'])
        self.assertTrue(analysis['mount_status'])
        self.assertIn('ext4', analysis['filesystem_types'])
        self.assertIn("Drive contains existing data", analysis['safety_warnings'])
        self.assertIn("Drive is currently mounted", analysis['safety_warnings'])
        self.assertIn("Drive has 1 existing partitions", analysis['safety_warnings'])
    
    @patch('subprocess.run')
    def test_get_current_label_success(self, mock_run):
        """Test getting current drive label successfully."""
        mock_run.return_value = MagicMock(
            stdout="TEST_LABEL\n",
            returncode=0
        )
        
        test_drive = DriveInfo(
            device="/dev/sdc", size=64*1024**3, model="Test Drive",
            vendor="Test", serial="123", removable=True, mounted=False,
            mount_points=[], 
            partitions=[{
                'name': '/dev/sdc1',
                'size': '64G',
                'fstype': 'ext4',
                'mountpoint': ''
            }],
            filesystem_type=None, usage_percent=None,
            is_external=True, connection_type="USB"
        )
        
        label = self.detector.get_current_label(test_drive)
        self.assertEqual(label, "TEST_LABEL")
    
    @patch('subprocess.run')
    def test_get_current_label_no_label(self, mock_run):
        """Test getting current drive label when no label exists."""
        mock_run.side_effect = subprocess.CalledProcessError(1, 'blkid')
        
        test_drive = DriveInfo(
            device="/dev/sdc", size=64*1024**3, model="Test Drive",
            vendor="Test", serial="123", removable=True, mounted=False,
            mount_points=[], 
            partitions=[{
                'name': '/dev/sdc1',
                'size': '64G',
                'fstype': 'ext4',
                'mountpoint': ''
            }],
            filesystem_type=None, usage_percent=None,
            is_external=True, connection_type="USB"
        )
        
        label = self.detector.get_current_label(test_drive)
        self.assertIsNone(label)
    
    def test_parse_drive_info_edge_cases(self):
        """Test parsing drive info with edge cases."""
        # Test with minimal data
        minimal_device = {
            "name": "sdd",
            "type": "disk"
        }
        
        drive_info = self.detector._parse_drive_info(minimal_device)
        self.assertIsNotNone(drive_info)
        self.assertEqual(drive_info.device, "/dev/sdd")
        self.assertEqual(drive_info.model, "Unknown")
        self.assertEqual(drive_info.vendor, "Unknown")
        self.assertEqual(drive_info.size, 0)
        
        # Test with invalid data that should return None
        invalid_device = {}
        drive_info = self.detector._parse_drive_info(invalid_device)
        self.assertIsNone(drive_info)


class TestDriveInfo(unittest.TestCase):
    """Test cases for DriveInfo dataclass."""
    
    def test_drive_info_creation(self):
        """Test creating DriveInfo objects."""
        drive = DriveInfo(
            device="/dev/sdc",
            size=1024**3,
            model="Test Drive",
            vendor="Test Vendor",
            serial="123456",
            removable=True,
            mounted=False,
            mount_points=[],
            partitions=[],
            filesystem_type="ext4",
            usage_percent=25.5,
            is_external=True,
            connection_type="USB"
        )
        
        self.assertEqual(drive.device, "/dev/sdc")
        self.assertEqual(drive.size, 1024**3)
        self.assertEqual(drive.model, "Test Drive")
        self.assertTrue(drive.is_external)
        self.assertEqual(drive.usage_percent, 25.5)


if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)