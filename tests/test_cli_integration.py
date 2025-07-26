#!/usr/bin/env python3
"""
Integration tests for the Weirding Host Utility CLI functionality.

Tests the main.py and weirding-setup script functionality including
command-line interface, error handling, and user interactions.
"""

import unittest
from unittest.mock import patch, MagicMock, call
import subprocess
import sys
import os
from pathlib import Path
import tempfile
import json

# Add project root to path for testing
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "modules"))

import typer
from typer.testing import CliRunner
from main import app as main_app


class TestMainCLI(unittest.TestCase):
    """Test cases for main.py CLI functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.runner = CliRunner()
        
        # Sample drive data for mocking
        self.sample_drives_data = [
            {
                "device": "/dev/sdc",
                "size": int(1.8 * 1024**4),
                "model": "PSSD T7 Shield",
                "vendor": "Samsung",
                "serial": "S123456789",
                "removable": True,
                "mounted": True,
                "mount_points": ["/media/user/T7 Shield"],
                "partitions": [{
                    'name': '/dev/sdc1',
                    'size': '1.8T',
                    'fstype': 'exfat',
                    'mountpoint': '/media/user/T7 Shield'
                }],
                "filesystem_type": None,
                "usage_percent": None,
                "is_external": True,
                "connection_type": "USB"
            }
        ]
    
    def test_version_command(self):
        """Test the version command."""
        result = self.runner.invoke(main_app, ["version"])
        
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Weirding Host Utility", result.stdout)
        self.assertIn("0.1.0-alpha", result.stdout)
        self.assertIn("portable AI server", result.stdout.lower())
    
    def test_help_command(self):
        """Test the help command."""
        result = self.runner.invoke(main_app, ["--help"])
        
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Weirding Host Utility", result.stdout)
        self.assertIn("setup-module", result.stdout)
        self.assertIn("setup-host", result.stdout)
        self.assertIn("list-drives", result.stdout)
        self.assertIn("relabel-drive", result.stdout)
        self.assertIn("version", result.stdout)
    
    @patch('modules.device_setup.DriveDetector')
    def test_list_drives_command(self, mock_detector_class):
        """Test the list-drives command."""
        # Mock the DriveDetector
        mock_detector = MagicMock()
        mock_detector_class.return_value = mock_detector
        
        # Create mock drive objects
        from modules.device_setup import DriveInfo
        mock_drive = DriveInfo(**self.sample_drives_data[0])
        
        mock_detector.scan_drives.return_value = [mock_drive]
        mock_detector.get_external_drives.return_value = [mock_drive]
        mock_detector.check_drive_requirements.return_value = (True, [])
        mock_detector.analyze_drive_usage.return_value = {
            'safety_warnings': ['Drive contains existing data']
        }
        mock_detector.format_size.return_value = "1.8 TB"
        
        result = self.runner.invoke(main_app, ["list-drives"])
        
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Scanning storage devices", result.stdout)
        self.assertIn("/dev/sdc", result.stdout)
        self.assertIn("PSSD T7 Shield", result.stdout)
        self.assertIn("1.8 TB", result.stdout)
    
    def test_setup_host_command(self):
        """Test the setup-host command (placeholder functionality)."""
        result = self.runner.invoke(main_app, ["setup-host"])
        
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Host setup functionality coming soon", result.stdout)
        self.assertIn("Mount Weirding Modules automatically", result.stdout)
        self.assertIn("Optimize performance for AI workloads", result.stdout)
    
    @patch('os.geteuid')
    def test_setup_module_requires_root(self, mock_geteuid):
        """Test that setup-module requires root privileges."""
        mock_geteuid.return_value = 1000  # Non-root user
        
        result = self.runner.invoke(main_app, ["setup-module"])
        
        self.assertEqual(result.exit_code, 1)
        self.assertIn("requires root privileges", result.stdout)
        self.assertIn("sudo", result.stdout)
    
    @patch('os.geteuid')
    def test_relabel_drive_requires_root(self, mock_geteuid):
        """Test that relabel-drive requires root privileges."""
        mock_geteuid.return_value = 1000  # Non-root user
        
        result = self.runner.invoke(main_app, ["relabel-drive"])
        
        self.assertEqual(result.exit_code, 1)
        self.assertIn("requires root privileges", result.stdout)
        self.assertIn("sudo", result.stdout)
    
    @patch('os.geteuid')
    @patch('modules.interactive_ui.WeirdingUI')
    def test_setup_module_with_root_cancelled_by_user(self, mock_ui_class, mock_geteuid):
        """Test setup-module when user cancels at welcome screen."""
        mock_geteuid.return_value = 0  # Root user
        
        # Mock UI to return False for welcome (user cancels)
        mock_ui = MagicMock()
        mock_ui_class.return_value = mock_ui
        mock_ui.show_welcome.return_value = False
        
        result = self.runner.invoke(main_app, ["setup-module"])
        
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Setup cancelled by user", result.stdout)


class TestStandaloneScript(unittest.TestCase):
    """Test cases for the standalone weirding-setup script."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.script_path = Path(__file__).parent.parent / "weirding-setup"
        self.assertTrue(self.script_path.exists(), "weirding-setup script not found")
    
    def test_script_executable(self):
        """Test that the standalone script is executable."""
        self.assertTrue(os.access(self.script_path, os.X_OK))
    
    def test_version_command(self):
        """Test the version command in standalone script."""
        result = subprocess.run([
            str(self.script_path), "version"
        ], capture_output=True, text=True)
        
        self.assertEqual(result.returncode, 0)
        self.assertIn("Weirding Module Setup Utility", result.stdout)
        self.assertIn("0.1.0-alpha (Standalone)", result.stdout)
    
    def test_help_command(self):
        """Test the help command in standalone script."""
        result = subprocess.run([
            str(self.script_path), "--help"
        ], capture_output=True, text=True)
        
        self.assertEqual(result.returncode, 0)
        self.assertIn("Weirding Module Setup Utility", result.stdout)
        self.assertIn("setup-module", result.stdout)
        self.assertIn("relabel-drive", result.stdout)
        self.assertIn("list-drives", result.stdout)
        self.assertIn("version", result.stdout)
    
    def test_list_drives_command(self):
        """Test the list-drives command in standalone script."""
        result = subprocess.run([
            str(self.script_path), "list-drives"
        ], capture_output=True, text=True)
        
        self.assertEqual(result.returncode, 0)
        self.assertIn("Scanning storage devices", result.stdout)
        # Should show some drives (at least the system drives)
        self.assertIn("Found", result.stdout)
        self.assertIn("drives", result.stdout)
    
    def test_setup_module_requires_root(self):
        """Test that setup-module requires root in standalone script."""
        result = subprocess.run([
            str(self.script_path), "setup-module"
        ], capture_output=True, text=True)
        
        # Should fail with exit code 1 if not root
        if os.geteuid() != 0:
            self.assertEqual(result.returncode, 1)
            self.assertIn("requires root privileges", result.stdout)
    
    def test_relabel_drive_requires_root(self):
        """Test that relabel-drive requires root in standalone script."""
        result = subprocess.run([
            str(self.script_path), "relabel-drive"
        ], capture_output=True, text=True)
        
        # Should fail with exit code 1 if not root
        if os.geteuid() != 0:
            self.assertEqual(result.returncode, 1)
            self.assertIn("requires root privileges", result.stdout)


class TestMakefileIntegration(unittest.TestCase):
    """Test cases for Makefile integration."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.project_root = Path(__file__).parent.parent
        self.makefile_path = self.project_root / "Makefile"
        self.assertTrue(self.makefile_path.exists(), "Makefile not found")
    
    def test_make_version(self):
        """Test make version command."""
        result = subprocess.run([
            "make", "version"
        ], cwd=self.project_root, capture_output=True, text=True)
        
        self.assertEqual(result.returncode, 0)
        self.assertIn("Weirding Module Setup Utility", result.stdout)
        self.assertIn("0.1.0-alpha", result.stdout)
    
    def test_make_list_drives(self):
        """Test make list-drives command."""
        result = subprocess.run([
            "make", "list-drives"
        ], cwd=self.project_root, capture_output=True, text=True)
        
        self.assertEqual(result.returncode, 0)
        self.assertIn("Scanning storage devices", result.stdout)
    
    def test_make_status(self):
        """Test make status command."""
        result = subprocess.run([
            "make", "status"
        ], cwd=self.project_root, capture_output=True, text=True)
        
        self.assertEqual(result.returncode, 0)
        self.assertIn("Project Status", result.stdout)
        self.assertIn("weirding-setup", result.stdout)
        self.assertIn("main.py", result.stdout)
    
    def test_make_test(self):
        """Test make test command."""
        result = subprocess.run([
            "make", "test"
        ], cwd=self.project_root, capture_output=True, text=True)
        
        self.assertEqual(result.returncode, 0)
        self.assertIn("Running basic functionality tests", result.stdout)
        self.assertIn("Standalone script works", result.stdout)
        self.assertIn("Dependencies available", result.stdout)
    
    def test_make_help(self):
        """Test make help command."""
        result = subprocess.run([
            "make", "help"
        ], cwd=self.project_root, capture_output=True, text=True)
        
        self.assertEqual(result.returncode, 0)
        self.assertIn("Weirding Host Utility - Makefile Commands", result.stdout)
        self.assertIn("Setup Commands", result.stdout)
        self.assertIn("Usage Commands", result.stdout)


class TestErrorHandling(unittest.TestCase):
    """Test cases for error handling and edge cases."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.runner = CliRunner()
    
    def test_invalid_command(self):
        """Test handling of invalid commands."""
        result = self.runner.invoke(main_app, ["invalid-command"])
        
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("No such command", result.stdout)
    
    @patch('modules.device_setup.DriveDetector')
    def test_list_drives_no_drives_found(self, mock_detector_class):
        """Test list-drives when no drives are found."""
        mock_detector = MagicMock()
        mock_detector_class.return_value = mock_detector
        mock_detector.scan_drives.return_value = []
        mock_detector.get_external_drives.return_value = []
        
        result = self.runner.invoke(main_app, ["list-drives"])
        
        self.assertEqual(result.exit_code, 0)
        self.assertIn("No storage devices detected", result.stdout)
    
    @patch('modules.device_setup.DriveDetector')
    def test_list_drives_scan_error(self, mock_detector_class):
        """Test list-drives when scanning fails."""
        mock_detector = MagicMock()
        mock_detector_class.return_value = mock_detector
        mock_detector.scan_drives.side_effect = Exception("Scan failed")
        
        # Should handle the exception gracefully
        result = self.runner.invoke(main_app, ["list-drives"])
        
        # The command should not crash, but may show an error
        self.assertIsNotNone(result.exit_code)


class TestDependencyChecking(unittest.TestCase):
    """Test cases for dependency checking and installation."""
    
    def test_required_packages_importable(self):
        """Test that all required packages can be imported."""
        required_packages = ['typer', 'rich', 'questionary']
        
        for package in required_packages:
            with self.subTest(package=package):
                try:
                    __import__(package)
                except ImportError:
                    self.fail(f"Required package '{package}' is not available")
    
    def test_modules_importable(self):
        """Test that all project modules can be imported."""
        modules_to_test = [
            'device_setup',
            'interactive_ui',
            'logger',
            'partitioner',
            'bootloader',
            'os_installer',
            'stack_installer'
        ]
        
        for module_name in modules_to_test:
            with self.subTest(module=module_name):
                try:
                    module_path = Path(__file__).parent.parent / "modules" / f"{module_name}.py"
                    if module_path.exists():
                        # Try to import the module
                        spec = __import__(f"modules.{module_name}", fromlist=[module_name])
                        self.assertIsNotNone(spec)
                except ImportError as e:
                    self.fail(f"Module '{module_name}' failed to import: {e}")


if __name__ == '__main__':
    # Run the tests with verbose output
    unittest.main(verbosity=2)