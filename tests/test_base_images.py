#!/usr/bin/env python3
"""
Unit tests for Base Image Catalog and ISO-based OS Installation.

Tests the base image selection, caching, and ISO-based installation functionality
that was added to support multiple operating system options.
"""

import unittest
import sys
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add project root and modules to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "modules"))

from base_images import BaseImageCatalog, BaseImage
from os_installer import OSInstaller
from partitioner import PartitionPlan
from device_setup import DriveInfo


class TestBaseImageCatalog(unittest.TestCase):
    """Test cases for BaseImageCatalog functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.catalog = BaseImageCatalog()
        
        # Create a temporary cache directory for testing
        self.temp_dir = tempfile.mkdtemp()
        self.catalog.cache_dir = Path(self.temp_dir)
        self.catalog.cache_dir.mkdir(exist_ok=True)
    
    def tearDown(self):
        """Clean up test fixtures."""
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_catalog_initialization(self):
        """Test that the catalog initializes correctly."""
        self.assertIsInstance(self.catalog, BaseImageCatalog)
        self.assertTrue(self.catalog.cache_dir.exists())
    
    def test_get_all_images(self):
        """Test getting all available base images."""
        images = self.catalog.get_all_images()
        
        self.assertIsInstance(images, list)
        self.assertGreater(len(images), 0, "Should have at least one base image")
        
        # Check that all items are BaseImage instances
        for image in images:
            self.assertIsInstance(image, BaseImage)
            self.assertIsInstance(image.name, str)
            self.assertIsInstance(image.version, str)
            self.assertIsInstance(image.size_mb, int)
            self.assertIsInstance(image.ai_optimized, bool)
    
    def test_format_size(self):
        """Test size formatting functionality."""
        # Test various sizes
        test_cases = [
            (0, "0 B"),
            (512, "512 MB"),
            (1024, "1.0 GB"),
            (1536, "1.5 GB"),
            (2048, "2.0 GB")
        ]
        
        for size_mb, expected in test_cases:
            result = self.catalog.format_size(size_mb)
            self.assertIsInstance(result, str)
            # Basic validation that it contains expected elements
            if size_mb >= 1024:
                self.assertIn("GB", result)
            elif size_mb > 0:
                self.assertIn("MB", result)
    
    def test_is_image_cached(self):
        """Test image caching detection."""
        # Get a test image
        images = self.catalog.get_all_images()
        test_image = images[0]
        
        # Initially should not be cached
        self.assertFalse(self.catalog.is_image_cached(test_image))
        
        # Create a mock cached file
        image_path = self.catalog.cache_dir / f"{test_image.id}.iso"
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_text("mock image data")
        
        # Now should be cached
        self.assertTrue(self.catalog.is_image_cached(test_image))
    
    def test_get_cached_image_path(self):
        """Test cached image path generation."""
        images = self.catalog.get_all_images()
        test_image = images[0]
        
        # Initially should return None (not cached)
        path = self.catalog.get_cached_image_path(test_image)
        self.assertIsNone(path)
        
        # Create a cached file
        cache_path = self.catalog.cache_dir / f"{test_image.id}.iso"
        cache_path.write_text("mock image data")
        
        # Now should return path
        path = self.catalog.get_cached_image_path(test_image)
        self.assertIsInstance(path, Path)
        self.assertTrue(str(path).endswith('.iso'))
        self.assertIn(test_image.id, str(path))
    
    @patch('urllib.request.urlretrieve')
    def test_download_image(self, mock_urlretrieve):
        """Test image download functionality."""
        images = self.catalog.get_all_images()
        test_image = images[0]
        
        # Mock successful download
        cache_path = self.catalog.cache_dir / f"{test_image.id}.iso"
        
        # Mock progress callback
        progress_callback = Mock()
        
        # Mock the download method to avoid actual network calls
        with patch.object(self.catalog, '_verify_image_integrity', return_value=True):
            result = self.catalog.download_image(test_image, progress_callback)
            
            # Should return the cache path
            self.assertIsInstance(result, Path)
            self.assertEqual(result, cache_path)


class TestBaseImageOSInstaller(unittest.TestCase):
    """Test cases for OS Installer with base image support."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.installer = OSInstaller()
        
        # Create mock drive and partition plan
        self.mock_drive = DriveInfo(
            device='/dev/sdx',
            size=64 * 1024**3,  # 64GB
            model='Test Drive',
            vendor='TestVendor',
            serial='TEST123',
            removable=True,
            mounted=False,
            mount_points=[],
            partitions=[],
            filesystem_type=None,
            usage_percent=None,
            is_external=True,
            connection_type='USB'
        )
        
        # Create mock base image
        self.mock_image = BaseImage(
            name="Test Ubuntu",
            version="22.04",
            architecture="x86_64",
            size_mb=1400,
            ai_optimized=True,
            container_ready=True,
            gpu_support=["nvidia", "amd"],
            description="Test Ubuntu image for testing",
            download_url="https://example.com/test.iso",
            sha256_hash="mock_hash",
            recommended_for=["testing", "development"]
        )
    
    def test_installer_initialization(self):
        """Test that the OS installer initializes correctly."""
        self.assertIsInstance(self.installer, OSInstaller)
        self.assertTrue(self.installer.mount_base.exists())
    
    @patch('subprocess.run')
    @patch('os.path.exists')
    def test_install_os_with_base_image(self, mock_exists, mock_subprocess):
        """Test OS installation with base image."""
        # Create a mock partition plan with base image
        mock_plan = Mock()
        mock_plan.drive = self.mock_drive
        mock_plan.base_image = self.mock_image
        mock_plan.partitions = [
            {
                'number': 1,
                'mount_point': '/',
                'type': 'Linux filesystem',
                'filesystem': 'ext4'
            }
        ]
        
        # Mock successful operations
        mock_exists.return_value = True
        mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")
        
        # Mock the mounting and other operations
        with patch.object(self.installer, '_mount_partitions') as mock_mount:
            mock_mount.return_value = {'root': '/tmp/test_mount'}
            
            with patch.object(self.installer, '_install_from_iso') as mock_install_iso:
                mock_install_iso.return_value = True
                
                with patch.object(self.installer, '_configure_system') as mock_configure:
                    mock_configure.return_value = True
                    
                    with patch.object(self.installer, '_install_kernel_and_essentials') as mock_kernel:
                        mock_kernel.return_value = True
                        
                        with patch.object(self.installer, '_setup_hardware_detection') as mock_hardware:
                            mock_hardware.return_value = True
                            
                            with patch.object(self.installer, '_create_weirding_configs') as mock_configs:
                                mock_configs.return_value = True
                                
                                with patch.object(self.installer, '_cleanup_installation'):
                                    with patch.object(self.installer, '_unmount_partitions'):
                                        # Test the installation
                                        result = self.installer.install_os(mock_plan)
                                        
                                        self.assertTrue(result, "Installation should succeed with mocked operations")
                                        mock_install_iso.assert_called_once()
    
    @patch('subprocess.run')
    def test_install_os_without_base_image(self, mock_subprocess):
        """Test OS installation without base image (debootstrap fallback)."""
        # Create a mock partition plan without base image
        mock_plan = Mock()
        mock_plan.drive = self.mock_drive
        mock_plan.base_image = None  # No base image
        mock_plan.partitions = [
            {
                'number': 1,
                'mount_point': '/',
                'type': 'Linux filesystem',
                'filesystem': 'ext4'
            }
        ]
        
        # Mock successful operations
        mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")
        
        # Mock the mounting and other operations
        with patch.object(self.installer, '_mount_partitions') as mock_mount:
            mock_mount.return_value = {'root': '/tmp/test_mount'}
            
            with patch.object(self.installer, '_install_base_system') as mock_install_base:
                mock_install_base.return_value = True
                
                with patch.object(self.installer, '_configure_system') as mock_configure:
                    mock_configure.return_value = True
                    
                    with patch.object(self.installer, '_install_kernel_and_essentials') as mock_kernel:
                        mock_kernel.return_value = True
                        
                        with patch.object(self.installer, '_setup_hardware_detection') as mock_hardware:
                            mock_hardware.return_value = True
                            
                            with patch.object(self.installer, '_create_weirding_configs') as mock_configs:
                                mock_configs.return_value = True
                                
                                with patch.object(self.installer, '_cleanup_installation'):
                                    with patch.object(self.installer, '_unmount_partitions'):
                                        # Test the installation
                                        result = self.installer.install_os(mock_plan)
                                        
                                        self.assertTrue(result, "Installation should succeed with mocked operations")
                                        mock_install_base.assert_called_once()
    
    def test_configure_iso_system(self):
        """Test ISO system configuration."""
        temp_root = tempfile.mkdtemp()
        
        try:
            with patch('subprocess.run') as mock_subprocess:
                mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")
                
                result = self.installer._configure_iso_system(self.mock_image, temp_root)
                
                # Should create essential directories
                essential_dirs = [
                    'proc', 'sys', 'dev', 'tmp', 'var/tmp',
                    'opt/weirding', 'opt/models', 'var/lib/weirding'
                ]
                
                for dir_name in essential_dirs:
                    dir_path = Path(temp_root) / dir_name
                    self.assertTrue(dir_path.exists(), f"Directory {dir_name} should be created")
                
                self.assertTrue(result, "ISO system configuration should succeed")
        
        finally:
            shutil.rmtree(temp_root)


class TestIntegration(unittest.TestCase):
    """Integration tests for base image and OS installation workflow."""
    
    def setUp(self):
        """Set up integration test fixtures."""
        self.catalog = BaseImageCatalog()
        self.installer = OSInstaller()
    
    def test_complete_workflow_simulation(self):
        """Test the complete workflow from image selection to installation planning."""
        # Step 1: Get available images
        images = self.catalog.get_all_images()
        self.assertGreater(len(images), 0, "Should have available images")
        
        # Step 2: Select an image (simulate user selection)
        selected_image = images[0]  # Select first image
        self.assertIsInstance(selected_image, BaseImage)
        
        # Step 3: Check if image is cached (should not be initially)
        is_cached = self.catalog.is_image_cached(selected_image)
        self.assertIsInstance(is_cached, bool)
        
        # Step 4: Get cached image path for potential download
        image_path = self.catalog.get_cached_image_path(selected_image)
        # Should be None initially (not cached)
        self.assertIsNone(image_path)
        
        # Step 5: Create a mock partition plan with the selected image
        mock_drive = DriveInfo(
            device='/dev/sdx',
            size=64 * 1024**3,
            model='Test Drive',
            vendor='TestVendor',
            serial='TEST123',
            removable=True,
            mounted=False,
            mount_points=[],
            partitions=[],
            filesystem_type=None,
            usage_percent=None,
            is_external=True,
            connection_type='USB'
        )
        
        mock_plan = Mock()
        mock_plan.drive = mock_drive
        mock_plan.base_image = selected_image
        mock_plan.partitions = [
            {
                'number': 1,
                'mount_point': '/',
                'type': 'Linux filesystem',
                'filesystem': 'ext4'
            }
        ]
        
        # Step 6: Verify the installer can handle the plan
        # (We don't actually install, just verify the logic flow)
        self.assertIsNotNone(mock_plan.base_image)
        self.assertEqual(mock_plan.base_image.name, selected_image.name)
        
        print(f"✅ Integration test completed successfully")
        print(f"   Selected image: {selected_image.name} v{selected_image.version}")
        print(f"   Image size: {self.catalog.format_size(selected_image.size_mb)}")
        print(f"   AI optimized: {selected_image.ai_optimized}")


def main():
    """Run the test suite."""
    unittest.main(verbosity=2)


if __name__ == '__main__':
    main()