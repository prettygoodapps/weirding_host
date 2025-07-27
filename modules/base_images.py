#!/usr/bin/env python3
"""
Base Image Management for Weirding Host Utility

This module handles the catalog and management of base operating system images
that can be used as the foundation for Weirding Modules.
"""

import hashlib
import urllib.request
import socket
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass
import json
import os


@dataclass
class BaseImage:
    """Information about a base operating system image."""
    id: str
    name: str
    description: str
    version: str
    architecture: str
    size_mb: int
    download_url: str
    sha256_hash: str
    recommended_for: List[str]
    ai_optimized: bool
    container_ready: bool
    gpu_support: List[str]


class BaseImageCatalog:
    """Manages the catalog of available base images for Weirding Modules."""
    
    def __init__(self):
        self.cache_dir = Path.home() / ".weirding_cache" / "images"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.catalog = self._initialize_catalog()
    
    def _initialize_catalog(self) -> List[BaseImage]:
        """Initialize the catalog with available base images."""
        # Start with cached images
        catalog = self._build_cached_catalog()
        
        # If no cached images, build from live APIs
        if not catalog:
            catalog = self._build_live_catalog()
        
        return catalog
    
    def _build_cached_catalog(self) -> List[BaseImage]:
        """Build catalog from cached ISO files."""
        catalog = []
        
        if not self.cache_dir.exists():
            return catalog
        
        for iso_file in self.cache_dir.glob("*.iso"):
            # Try to extract image info from filename
            image = self._parse_cached_iso(iso_file)
            if image:
                catalog.append(image)
        
        return catalog
    
    def _parse_cached_iso(self, iso_path: Path) -> Optional[BaseImage]:
        """Parse cached ISO file to create BaseImage."""
        filename = iso_path.name
        
        # Ubuntu patterns
        if "ubuntu" in filename.lower():
            if "24.04" in filename:
                return BaseImage(
                    id="ubuntu-24-desktop",
                    name="Ubuntu 24.04 Desktop",
                    description="Ubuntu 24.04 LTS Desktop (Cached)",
                    version="24.04.2",
                    architecture="amd64",
                    size_mb=int(iso_path.stat().st_size // (1024 * 1024)),
                    download_url="",  # Already cached
                    sha256_hash="",   # Will verify when used
                    recommended_for=["desktop", "development", "ai_workloads"],
                    ai_optimized=True,
                    container_ready=True,
                    gpu_support=["intel", "amd", "nvidia"]
                )
            elif "22.04" in filename:
                return BaseImage(
                    id="ubuntu-22-server",
                    name="Ubuntu 22.04 Server",
                    description="Ubuntu 22.04 LTS Server (Cached)",
                    version="22.04",
                    architecture="amd64",
                    size_mb=int(iso_path.stat().st_size // (1024 * 1024)),
                    download_url="",
                    sha256_hash="",
                    recommended_for=["server", "ai_workloads", "gpu_computing"],
                    ai_optimized=True,
                    container_ready=True,
                    gpu_support=["intel", "amd", "nvidia"]
                )
        
        # Debian patterns
        elif "debian" in filename.lower():
            return BaseImage(
                id="debian-12-minimal",
                name="Debian 12 Minimal",
                description="Debian 12 (Bookworm) - Cached",
                version="12",
                architecture="amd64",
                size_mb=int(iso_path.stat().st_size // (1024 * 1024)),
                download_url="",
                sha256_hash="",
                recommended_for=["general", "lightweight", "servers"],
                ai_optimized=False,
                container_ready=True,
                gpu_support=["intel", "amd", "nvidia"]
            )
        
        return None
    
    def _build_live_catalog(self) -> List[BaseImage]:
        """Build catalog by querying live Ubuntu/Debian APIs."""
        catalog = []
        
        # Add Ubuntu releases
        catalog.extend(self._query_ubuntu_releases())
        
        # Add fallback minimal set if API fails
        if not catalog:
            catalog = self._get_fallback_catalog()
        
        return catalog
    
    def _query_ubuntu_releases(self) -> List[BaseImage]:
        """Query Ubuntu release API for current ISOs."""
        catalog = []
        
        try:
            # Query Ubuntu 24.04 LTS
            ubuntu_24_images = self._get_ubuntu_release_info("24.04")
            catalog.extend(ubuntu_24_images)
            
            # Query Ubuntu 22.04 LTS
            ubuntu_22_images = self._get_ubuntu_release_info("22.04")
            catalog.extend(ubuntu_22_images)
            
        except Exception as e:
            print(f"Warning: Could not query Ubuntu APIs: {e}")
        
        return catalog
    
    def _get_ubuntu_release_info(self, version: str) -> List[BaseImage]:
        """Get Ubuntu release information for a specific version."""
        images = []
        
        try:
            # Fetch Ubuntu release page
            url = f"https://releases.ubuntu.com/{version}/"
            with urllib.request.urlopen(url) as response:
                content = response.read().decode('utf-8')
            
            # Parse for desktop and server ISOs
            import re
            iso_pattern = r'href="(ubuntu-[\d\.]+-(?:desktop|live-server)-amd64\.iso)"'
            matches = re.findall(iso_pattern, content)
            
            # Get SHA256 hashes
            sha_url = f"https://releases.ubuntu.com/{version}/SHA256SUMS"
            sha_hashes = {}
            try:
                with urllib.request.urlopen(sha_url) as response:
                    sha_content = response.read().decode('utf-8')
                for line in sha_content.split('\n'):
                    if '.iso' in line:
                        parts = line.split()
                        if len(parts) >= 2:
                            sha_hashes[parts[1].replace('*', '')] = parts[0]
            except:
                pass
            
            for iso_filename in matches:
                if "desktop" in iso_filename:
                    images.append(BaseImage(
                        id=f"ubuntu-{version.replace('.', '')}-desktop",
                        name=f"Ubuntu {version} Desktop",
                        description=f"Ubuntu {version} LTS Desktop with full GUI",
                        version=version,
                        architecture="amd64",
                        size_mb=5900,  # Approximate size
                        download_url=f"https://releases.ubuntu.com/{version}/{iso_filename}",
                        sha256_hash=sha_hashes.get(iso_filename, ""),
                        recommended_for=["desktop", "development", "ai_workloads"],
                        ai_optimized=True,
                        container_ready=True,
                        gpu_support=["intel", "amd", "nvidia"]
                    ))
                elif "server" in iso_filename:
                    images.append(BaseImage(
                        id=f"ubuntu-{version.replace('.', '')}-server",
                        name=f"Ubuntu {version} Server",
                        description=f"Ubuntu {version} LTS Server for headless deployment",
                        version=version,
                        architecture="amd64",
                        size_mb=3000,  # Approximate size
                        download_url=f"https://releases.ubuntu.com/{version}/{iso_filename}",
                        sha256_hash=sha_hashes.get(iso_filename, ""),
                        recommended_for=["server", "ai_workloads", "gpu_computing"],
                        ai_optimized=True,
                        container_ready=True,
                        gpu_support=["intel", "amd", "nvidia"]
                    ))
                        
        except Exception as e:
            print(f"Warning: Could not fetch Ubuntu {version} release info: {e}")
        
        return images
    
    def _get_fallback_catalog(self) -> List[BaseImage]:
        """Fallback catalog when APIs are unavailable."""
        return [
            BaseImage(
                id="ubuntu-2404-desktop",
                name="Ubuntu 24.04 Desktop",
                description="Ubuntu 24.04 LTS Desktop (Latest)",
                version="24.04.2",
                architecture="amd64",
                size_mb=5900,
                download_url="https://releases.ubuntu.com/24.04/ubuntu-24.04.2-desktop-amd64.iso",
                sha256_hash="d7fe3d6a0419667d2f8eff12796996328daa2d4f90cd9f87aa9371b362f987bf",
                recommended_for=["desktop", "development", "ai_workloads"],
                ai_optimized=True,
                container_ready=True,
                gpu_support=["intel", "amd", "nvidia"]
            ),
            BaseImage(
                id="ubuntu-2404-server",
                name="Ubuntu 24.04 Server",
                description="Ubuntu 24.04 LTS Server (Latest)",
                version="24.04.2",
                architecture="amd64",
                size_mb=3000,
                download_url="https://releases.ubuntu.com/24.04/ubuntu-24.04.2-live-server-amd64.iso",
                sha256_hash="d6dab0c3a657988501b4bd76f1297c053df710e06e0c3aece60dead24f270b4d",
                recommended_for=["server", "ai_workloads", "gpu_computing"],
                ai_optimized=True,
                container_ready=True,
                gpu_support=["intel", "amd", "nvidia"]
            )
        ]
    
    def get_all_images(self) -> List[BaseImage]:
        """Get all available base images."""
        return self.catalog
    
    def get_image_by_id(self, image_id: str) -> Optional[BaseImage]:
        """Get a specific image by ID."""
        for image in self.catalog:
            if image.id == image_id:
                return image
        return None
    
    def get_recommended_images(self, use_case: str = None) -> List[BaseImage]:
        """Get images recommended for a specific use case."""
        if not use_case:
            return self.catalog
        
        return [img for img in self.catalog if use_case in img.recommended_for]
    
    def get_ai_optimized_images(self) -> List[BaseImage]:
        """Get images that are pre-optimized for AI workloads."""
        return [img for img in self.catalog if img.ai_optimized]
    
    def is_image_cached(self, image: BaseImage) -> bool:
        """Check if an image is already downloaded and cached."""
        cache_path = self.cache_dir / f"{image.id}.iso"
        if not cache_path.exists():
            return False
        
        # Verify file integrity
        return self._verify_image_integrity(cache_path, image.sha256_hash)
    
    def get_cached_image_path(self, image: BaseImage) -> Optional[Path]:
        """Get the path to a cached image if available."""
        if self.is_image_cached(image):
            return self.cache_dir / f"{image.id}.iso"
        return None
    
    def download_image(self, image: BaseImage, progress_callback=None) -> Path:
        """
        Download an image to cache if not already available.
        
        Args:
            image: BaseImage to download
            progress_callback: Optional callback for download progress
            
        Returns:
            Path to the downloaded image file
        """
        cache_path = self.cache_dir / f"{image.id}.iso"
        
        # Return cached version if available and valid
        if self.is_image_cached(image):
            if progress_callback:
                progress_callback(f"Using cached image: {image.name}")
            return cache_path
        
        if progress_callback:
            progress_callback(f"Downloading {image.name} ({image.size_mb}MB)...")
        
        # Download the image
        try:
            with urllib.request.urlopen(image.download_url) as response:
                total_size = int(response.headers.get('Content-Length', 0))
                downloaded = 0
                
                with open(cache_path, 'wb') as f:
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if progress_callback and total_size > 0:
                            percent = (downloaded / total_size) * 100
                            progress_callback(f"Downloading {image.name}: {percent:.1f}%")
            
            # Verify integrity
            if not self._verify_image_integrity(cache_path, image.sha256_hash):
                cache_path.unlink()
                raise RuntimeError(f"Downloaded image failed integrity check: {image.name}")
            
            if progress_callback:
                progress_callback(f"Successfully downloaded and verified: {image.name}")
            
            return cache_path
            
        except Exception as e:
            if cache_path.exists():
                cache_path.unlink()
            raise RuntimeError(f"Failed to download {image.name}: {str(e)}")
    
    def _verify_image_integrity(self, file_path: Path, expected_hash: str) -> bool:
        """Verify the SHA256 hash of a downloaded image."""
        try:
            sha256_hash = hashlib.sha256()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)
            
            return sha256_hash.hexdigest().lower() == expected_hash.lower()
        except Exception:
            return False
    
    def format_size(self, size_mb: int) -> str:
        """Format size in MB to human-readable string."""
        if size_mb < 1024:
            return f"{size_mb} MB"
        else:
            return f"{size_mb / 1024:.1f} GB"
    
    def clear_cache(self):
        """Clear all cached images."""
        import shutil
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)


def main():
    """Test the base image catalog functionality."""
    catalog = BaseImageCatalog()
    
    print("=== Available Base Images ===")
    for image in catalog.get_all_images():
        cached = "✓ Cached" if catalog.is_image_cached(image) else "○ Not cached"
        ai_opt = "🤖 AI-Optimized" if image.ai_optimized else ""
        gpu_support = f"GPU: {', '.join(image.gpu_support)}"
        
        print(f"\n{image.name} (v{image.version})")
        print(f"  ID: {image.id}")
        print(f"  Size: {catalog.format_size(image.size_mb)}")
        print(f"  Status: {cached} {ai_opt}")
        print(f"  {gpu_support}")
        print(f"  Use cases: {', '.join(image.recommended_for)}")
        print(f"  Description: {image.description}")
    
    print(f"\n=== AI-Optimized Images ===")
    ai_images = catalog.get_ai_optimized_images()
    for image in ai_images:
        print(f"- {image.name}: {image.description}")
    
    print(f"\n=== Lightweight Images ===")
    lightweight = catalog.get_recommended_images("lightweight")
    for image in lightweight:
        print(f"- {image.name}: {catalog.format_size(image.size_mb)}")


if __name__ == "__main__":
    main()