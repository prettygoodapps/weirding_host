#!/usr/bin/env python3
"""
Interactive User Interface Module for Weirding Host Utility

This module provides rich, interactive interfaces for guiding users through
the Weirding Module setup process with safety checks and clear feedback.
"""

import questionary
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.prompt import Confirm
from rich.text import Text
from rich.layout import Layout
from rich.align import Align
from typing import List, Dict, Optional, Tuple
import time
import subprocess

from device_setup import DriveInfo, DriveDetector
from base_images import BaseImageCatalog, BaseImage


class WeirdingUI:
    """Interactive user interface for Weirding Module setup."""
    
    def __init__(self):
        self.console = Console()
        self.detector = DriveDetector()
        self.image_catalog = BaseImageCatalog()
        
    def show_welcome(self):
        """Display welcome message and project overview."""
        welcome_text = """
[bold blue]Weirding Module Setup Utility[/bold blue]

Transform your external drive into a portable AI server that adapts to any host system.

[yellow]What is a Weirding Module?[/yellow]
• A self-contained, bootable AI environment on external storage
• Automatically detects and optimizes for host hardware (GPU/CPU/Memory)
• Includes Ollama, HuggingFace Transformers, and optimized ML stack
• Portable across different computers with hardware-adaptive performance

[red]⚠️  IMPORTANT SAFETY NOTICE ⚠️[/red]
This process can modify or erase data on your external drive.
Always backup important data before proceeding.
        """
        
        panel = Panel(
            welcome_text,
            title="🚀 Weirding Host Utility",
            border_style="blue",
            padding=(1, 2)
        )
        
        self.console.print(panel)
        self.console.print()
        
        if not Confirm.ask("Do you want to continue with the setup?", default=True):
            self.console.print("[yellow]Setup cancelled by user.[/yellow]")
            return False
        
        return True
    
    def scan_and_display_drives(self) -> List[DriveInfo]:
        """Scan for drives and display them in a formatted table."""
        self.console.print("\n[blue]Scanning for external drives...[/blue]")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
            transient=True
        ) as progress:
            task = progress.add_task("Detecting storage devices...", total=None)
            drives = self.detector.scan_drives()
            progress.update(task, completed=100)
        
        external_drives = self.detector.get_external_drives()
        
        if not external_drives:
            self.console.print("[red]No suitable external drives found.[/red]")
            self.console.print("Please connect an external drive (32GB or larger) and try again.")
            return []
        
        # Create drives table
        table = Table(title="Available External Drives", show_header=True, header_style="bold magenta")
        table.add_column("Device", style="cyan", no_wrap=True)
        table.add_column("Model", style="green")
        table.add_column("Size", style="yellow")
        table.add_column("Connection", style="blue")
        table.add_column("Status", style="red")
        table.add_column("Suitable", style="bold")
        
        for drive in external_drives:
            # Check requirements
            meets_req, issues = self.detector.check_drive_requirements(drive)
            
            # Format status
            status_parts = []
            if drive.mounted:
                status_parts.append("Mounted")
            if len(drive.partitions) > 0:
                status_parts.append(f"{len(drive.partitions)} partitions")
            
            status = ", ".join(status_parts) if status_parts else "Available"
            suitable = "[green]✓ Yes[/green]" if meets_req else "[red]✗ No[/red]"
            
            table.add_row(
                drive.device,
                f"{drive.model} ({drive.vendor})",
                self.detector.format_size(drive.size),
                drive.connection_type,
                status,
                suitable
            )
        
        self.console.print(table)
        return external_drives
    
    def select_drive(self, drives: List[DriveInfo]) -> Optional[DriveInfo]:
        """Allow user to select a drive for setup."""
        if not drives:
            return None
        
        # Filter to only suitable drives
        suitable_drives = [d for d in drives if self.detector.check_drive_requirements(d)[0]]
        
        if not suitable_drives:
            self.console.print("\n[red]No drives meet the minimum requirements for Weirding Module setup.[/red]")
            self.console.print("Requirements:")
            self.console.print("• Minimum 32GB capacity")
            self.console.print("• External/removable drive")
            return None
        
        # Create selection choices
        choices = []
        for drive in suitable_drives:
            analysis = self.detector.analyze_drive_usage(drive)
            warnings = f" ⚠️  {len(analysis['safety_warnings'])} warnings" if analysis['safety_warnings'] else ""
            
            choice_text = f"{drive.device} - {drive.model} ({self.detector.format_size(drive.size)}){warnings}"
            choices.append({
                'name': choice_text,
                'value': drive
            })
        
        self.console.print()
        selected_drive = questionary.select(
            "Select the drive to convert into a Weirding Module:",
            choices=choices,
            style=questionary.Style([
                ('question', 'bold'),
                ('answer', 'fg:#ff9d00 bold'),
                ('pointer', 'fg:#ff9d00 bold'),
                ('highlighted', 'fg:#ff9d00 bold'),
                ('selected', 'fg:#cc5454'),
                ('separator', 'fg:#cc5454'),
                ('instruction', ''),
                ('text', ''),
            ])
        ).ask()
        
        return selected_drive
    
    def show_drive_analysis(self, drive: DriveInfo) -> Dict:
        """Display detailed analysis of the selected drive."""
        analysis = self.detector.analyze_drive_usage(drive)
        
        # Create analysis panel
        analysis_text = f"""
[bold]Drive Analysis: {drive.device}[/bold]

[blue]Hardware Information:[/blue]
• Model: {drive.model} ({drive.vendor})
• Size: {self.detector.format_size(drive.size)}
• Connection: {drive.connection_type}
• Serial: {drive.serial}

[blue]Current Usage:[/blue]
• Total Space: {self.detector.format_size(analysis['total_size'])}
• Used Space: {self.detector.format_size(analysis['used_space'])}
• Free Space: {self.detector.format_size(analysis['free_space'])}
• Partitions: {analysis['partition_count']}
• Filesystem Types: {', '.join(analysis['filesystem_types']) if analysis['filesystem_types'] else 'None'}

[blue]Mount Status:[/blue]
• Currently Mounted: {'Yes' if analysis['mount_status'] else 'No'}
• Mount Points: {', '.join(drive.mount_points) if drive.mount_points else 'None'}
        """
        
        if analysis['safety_warnings']:
            analysis_text += f"\n[red]⚠️  Safety Warnings:[/red]\n"
            for warning in analysis['safety_warnings']:
                analysis_text += f"• {warning}\n"
        
        panel = Panel(
            analysis_text.strip(),
            title=f"📊 Drive Analysis",
            border_style="yellow",
            padding=(1, 2)
        )
        
        self.console.print(panel)
        return analysis
    
    def select_setup_mode(self, drive: DriveInfo, analysis: Dict) -> Optional[str]:
        """Allow user to select setup mode (full wipe vs dual-use)."""
        self.console.print("\n[bold blue]Setup Mode Selection[/bold blue]")
        
        # Calculate space requirements
        min_weirding_space = 25 * 1024**3  # 25GB minimum for Weirding Module
        recommended_space = 50 * 1024**3   # 50GB recommended
        
        modes = []
        
        # Full wipe mode - always available
        modes.append({
            'name': '🔥 Full Wipe Mode - Complete drive conversion',
            'value': 'full_wipe',
            'description': 'Erase entire drive and dedicate it completely to Weirding Module'
        })
        
        # Dual-use mode - only if there's enough space
        if analysis['free_space'] >= min_weirding_space:
            modes.append({
                'name': '🔄 Dual-Use Mode - Preserve existing data',
                'value': 'dual_use', 
                'description': 'Keep existing data and add Weirding Module partition'
            })
        
        # Show mode details
        mode_details = f"""
[yellow]Mode Options:[/yellow]

[bold]🔥 Full Wipe Mode[/bold]
• Erases ALL existing data on the drive
• Uses entire drive capacity for Weirding Module
• Maximum performance and storage for AI models
• Recommended for dedicated AI server drives

[bold]🔄 Dual-Use Mode[/bold]
• Preserves existing files and partitions
• Creates new partition for Weirding Module
• Requires at least {self.detector.format_size(min_weirding_space)} free space
• Good for drives you want to use for other purposes too
"""
        
        if analysis['free_space'] < min_weirding_space:
            mode_details += f"\n[red]⚠️  Dual-Use Mode unavailable: Only {self.detector.format_size(analysis['free_space'])} free space available[/red]"
            mode_details += f"\n[red]   Minimum required: {self.detector.format_size(min_weirding_space)}[/red]"
        
        panel = Panel(
            mode_details.strip(),
            title="Setup Mode Selection",
            border_style="cyan",
            padding=(1, 2)
        )
        
        self.console.print(panel)
        
        # Get user selection
        selected_mode = questionary.select(
            "Choose setup mode:",
            choices=[{'name': mode['name'], 'value': mode['value']} for mode in modes],
            style=questionary.Style([
                ('question', 'bold'),
                ('answer', 'fg:#ff9d00 bold'),
                ('pointer', 'fg:#ff9d00 bold'),
                ('highlighted', 'fg:#ff9d00 bold'),
            ])
        ).ask()
        
        return selected_mode
    
    def select_base_image(self, drive: DriveInfo, mode: str) -> Optional[BaseImage]:
        """Allow user to select a base operating system image."""
        self.console.print("\n[bold blue]Base Image Selection[/bold blue]")
        
        # Show base image catalog
        images = self.image_catalog.get_all_images()
        
        # Create image selection table
        table = Table(title="Available Base Operating System Images", show_header=True, header_style="bold magenta")
        table.add_column("Image", style="cyan", no_wrap=True)
        table.add_column("Version", style="green")
        table.add_column("Size", style="yellow")
        table.add_column("Status", style="blue")
        table.add_column("AI/ML", style="red")
        table.add_column("Use Cases", style="white")
        
        for image in images:
            # Check if image is cached
            cached_status = "✅ Cached" if self.image_catalog.is_image_cached(image) else "📥 Download"
            ai_status = "🤖 Optimized" if image.ai_optimized else "○ Standard"
            use_cases = ", ".join(image.recommended_for[:2])  # Show first 2 use cases
            
            table.add_row(
                image.name,
                f"v{image.version}",
                self.image_catalog.format_size(image.size_mb),
                cached_status,
                ai_status,
                use_cases
            )
        
        self.console.print(table)
        
        # Show detailed information panel
        info_text = """
[yellow]Image Selection Guide:[/yellow]

[green]🚀 Recommended for AI/ML:[/green]
• Ubuntu 24.04 AI-Optimized - Pre-configured with AI frameworks
• Ubuntu 22.04 Server - Modern hardware support, great for GPU workloads
• Fedora 39 - Latest AI/ML tools and frameworks

[blue]💾 Lightweight Options:[/blue]
• Alpine Linux 3.19 - Ultra-minimal (180MB) for resource-constrained setups
• Debian 12 Minimal - Lightweight and stable (380MB)

[red]⚡ Performance Notes:[/red]
• Cached images install instantly
• Download time varies by connection speed
• Larger images include more pre-installed software
        """
        
        panel = Panel(
            info_text.strip(),
            title="📋 Base Image Information",
            border_style="cyan",
            padding=(1, 2)
        )
        
        self.console.print(panel)
        
        # Create selection choices
        choices = []
        for image in images:
            cached_indicator = "✅" if self.image_catalog.is_image_cached(image) else "📥"
            ai_indicator = "🤖" if image.ai_optimized else ""
            
            choice_text = f"{cached_indicator} {image.name} v{image.version} - {self.image_catalog.format_size(image.size_mb)} {ai_indicator}"
            choices.append({
                'name': choice_text,
                'value': image
            })
        
        # Add option to show detailed information
        choices.append({
            'name': "ℹ️  Show detailed image information",
            'value': 'show_details'
        })
        
        while True:
            selected = questionary.select(
                "Choose a base operating system image:",
                choices=choices,
                style=questionary.Style([
                    ('question', 'bold'),
                    ('answer', 'fg:#ff9d00 bold'),
                    ('pointer', 'fg:#ff9d00 bold'),
                    ('highlighted', 'fg:#ff9d00 bold'),
                ])
            ).ask()
            
            if not selected:
                return None
            
            if selected == 'show_details':
                self._show_detailed_image_info(images)
                continue
            
            # Confirm selection
            self.console.print(f"\n[blue]Selected:[/blue] {selected.name} v{selected.version}")
            self.console.print(f"[blue]Description:[/blue] {selected.description}")
            self.console.print(f"[blue]Size:[/blue] {self.image_catalog.format_size(selected.size_mb)}")
            
            if not self.image_catalog.is_image_cached(selected):
                self.console.print(f"[yellow]Note:[/yellow] This image will be downloaded ({self.image_catalog.format_size(selected.size_mb)})")
            
            from rich.prompt import Confirm
            if Confirm.ask(f"Use {selected.name} as the base image?", default=True):
                return selected
    
    def _show_detailed_image_info(self, images: List[BaseImage]):
        """Show detailed information about all available images."""
        for image in images:
            cached = "✅ Available locally" if self.image_catalog.is_image_cached(image) else "📥 Requires download"
            
            detail_text = f"""
[bold]{image.name} v{image.version}[/bold]

[blue]Description:[/blue] {image.description}
[blue]Size:[/blue] {self.image_catalog.format_size(image.size_mb)}
[blue]Architecture:[/blue] {image.architecture}
[blue]Status:[/blue] {cached}

[green]Features:[/green]
• AI/ML Optimized: {'Yes' if image.ai_optimized else 'No'}
• Container Ready: {'Yes' if image.container_ready else 'No'}
• GPU Support: {', '.join(image.gpu_support)}

[yellow]Recommended for:[/yellow] {', '.join(image.recommended_for)}
            """
            
            panel = Panel(
                detail_text.strip(),
                title=f"🖥️  {image.name}",
                border_style="blue",
                padding=(1, 2)
            )
            
            self.console.print(panel)
            self.console.print()
    
    def configure_module_name(self, drive: DriveInfo) -> Optional[str]:
        """
        Allow user to configure the Weirding Module name/label.
        
        Args:
            drive: DriveInfo object for the selected drive
            
        Returns:
            New label name or None if cancelled
        """
        current_label = self.detector.get_current_label(drive)
        
        # Show current label information
        label_info = f"""
[bold blue]Weirding Module Name Configuration[/bold blue]

[yellow]Current Drive Label:[/yellow] {current_label if current_label else 'No label set'}

[blue]About Module Names:[/blue]
• The module name will be used as the drive label and hostname
• Choose a descriptive name for easy identification
• Names are limited to 11 characters (alphanumeric, underscore, hyphen)
• Examples: 'AI_Server', 'WeirdingAI', 'MyAIBox', 'PortableML'

[green]Suggested Names:[/green]
• Based on your drive: 'T7_AI_Server' or 'Samsung_AI'
• Generic options: 'WeirdingAI', 'PortableAI', 'AIModule'
        """
        
        panel = Panel(
            label_info.strip(),
            title="🏷️ Module Name Configuration",
            border_style="blue",
            padding=(1, 2)
        )
        
        self.console.print(panel)
        
        # Provide naming options
        naming_choices = [
            {
                'name': '🎯 Use suggested name: "WeirdingAI"',
                'value': 'WeirdingAI'
            },
            {
                'name': '🔧 Use drive-based name: "T7_AI"',
                'value': 'T7_AI'
            },
            {
                'name': '✏️ Enter custom name',
                'value': 'custom'
            },
            {
                'name': '📋 Keep current label' + (f' ("{current_label}")' if current_label else ' (no change)'),
                'value': 'keep'
            }
        ]
        
        choice = questionary.select(
            "Choose how to name your Weirding Module:",
            choices=naming_choices,
            style=questionary.Style([
                ('question', 'bold'),
                ('answer', 'fg:#ff9d00 bold'),
                ('pointer', 'fg:#ff9d00 bold'),
                ('highlighted', 'fg:#ff9d00 bold'),
            ])
        ).ask()
        
        if not choice:
            return None
        
        if choice == 'keep':
            return current_label
        elif choice == 'custom':
            # Get custom name from user
            while True:
                custom_name = questionary.text(
                    "Enter custom name for your Weirding Module:",
                    validate=lambda text: len(text.strip()) > 0 and len(text.strip()) <= 11,
                    instruction="(1-11 characters, alphanumeric/underscore/hyphen only)"
                ).ask()
                
                if not custom_name:
                    return None
                
                # Validate and sanitize
                import re
                sanitized = re.sub(r'[^a-zA-Z0-9_-]', '_', custom_name.strip())
                
                if sanitized != custom_name.strip():
                    self.console.print(f"[yellow]Name sanitized to: '{sanitized}'[/yellow]")
                    if not questionary.confirm(f"Use '{sanitized}' as the module name?").ask():
                        continue
                
                return sanitized
        else:
            return choice
    
    def apply_drive_label(self, drive: DriveInfo, new_label: str) -> bool:
        """
        Apply the new label to the drive with user feedback.
        
        Args:
            drive: DriveInfo object for the drive
            new_label: New label to apply
            
        Returns:
            True if successful, False otherwise
        """
        if not new_label:
            return True  # No change requested
        
        current_label = self.detector.get_current_label(drive)
        if current_label == new_label:
            self.console.print(f"[green]Drive already has the label '{new_label}'[/green]")
            return True
        
        self.console.print(f"\n[blue]Applying label '{new_label}' to {drive.device}...[/blue]")
        
        # Check if drive needs to be unmounted
        if drive.mounted:
            self.console.print("[yellow]Drive is currently mounted. Attempting to unmount...[/yellow]")
            
            try:
                # Attempt to unmount all mount points
                for mount_point in drive.mount_points:
                    result = subprocess.run(['umount', mount_point],
                                          capture_output=True, text=True, check=True)
                self.console.print("[green]Drive unmounted successfully.[/green]")
                
                # Update drive status
                drive.mounted = False
                drive.mount_points = []
                
            except subprocess.CalledProcessError as e:
                self.show_error("Unmount Failed",
                              f"Could not unmount drive: {e.stderr.strip() if e.stderr else str(e)}")
                return False
        
        # Apply the label
        with self.show_progress_screen("Applying Label") as progress:
            task = progress.add_task("Relabeling drive...", total=100)
            
            success, message = self.detector.relabel_drive(drive, new_label)
            progress.update(task, completed=100)
        
        if success:
            self.console.print(f"[green]✅ {message}[/green]")
            return True
        else:
            # Check if it's a permission error and provide helpful guidance
            if "Root privileges required" in message:
                self.show_error("Permission Required",
                              "Drive relabeling requires root privileges.\n\n" +
                              "Please run with sudo using the virtual environment:\n" +
                              "sudo ./venv/bin/python main.py setup-module\n" +
                              "or\n" +
                              "sudo ./venv/bin/python main.py relabel-drive\n\n" +
                              "Alternatively, activate the virtual environment first:\n" +
                              "source venv/bin/activate && sudo python main.py setup-module")
            else:
                self.show_error("Labeling Failed", message)
            return False
    
    def show_setup_summary(self, drive: DriveInfo, mode: str, analysis: Dict, module_name: str = None, base_image = None) -> bool:
        """Show final setup summary and get confirmation."""
        
        if mode == 'full_wipe':
            impact_text = f"""
[red]⚠️  DESTRUCTIVE OPERATION WARNING ⚠️[/red]

[bold]This will PERMANENTLY ERASE ALL DATA on {drive.device}[/bold]

[red]What will be lost:[/red]
• All {analysis['partition_count']} existing partitions
• All files and data ({self.detector.format_size(analysis['used_space'])} of data)
• Current filesystem configuration

[green]What will be created:[/green]
• EFI boot partition (512MB)
• Weirding Module root partition (~20GB)
• AI model storage partition (remaining space)
• Hardware-adaptive configuration system
            """
        else:  # dual_use
            weirding_size = min(analysis['free_space'], 50 * 1024**3)  # Use up to 50GB
            impact_text = f"""
[yellow]⚠️  PARTITION MODIFICATION WARNING ⚠️[/yellow]

[bold]This will modify the partition table on {drive.device}[/bold]

[green]What will be preserved:[/green]
• All existing partitions and data
• Current mount points and filesystem types
• {self.detector.format_size(analysis['used_space'])} of existing data

[blue]What will be created:[/blue]
• New Weirding Module partition (~{self.detector.format_size(weirding_size)})
• Bootloader configuration for dual-boot capability
• Hardware-adaptive AI stack installation
            """
        
        # Base image information
        base_image_info = ""
        if base_image:
            cached_status = "locally cached" if self.image_catalog.is_image_cached(base_image) else f"will download {self.image_catalog.format_size(base_image.size_mb)}"
            ai_info = "🤖 AI-optimized" if base_image.ai_optimized else "Standard"
            
            base_image_info = f"""
[bold]Base Image:[/bold] {base_image.name} v{base_image.version} ({ai_info})
[bold]Image Size:[/bold] {self.image_catalog.format_size(base_image.size_mb)} ({cached_status})
[bold]Description:[/bold] {base_image.description}"""
        
        summary_text = f"""
[bold blue]Setup Summary[/bold blue]

[bold]Target Drive:[/bold] {drive.device}
[bold]Model:[/bold] {drive.model} ({drive.vendor})
[bold]Size:[/bold] {self.detector.format_size(drive.size)}
[bold]Mode:[/bold] {mode.replace('_', ' ').title()}
[bold]Module Name:[/bold] {module_name if module_name else 'No custom name set'}{base_image_info}

{impact_text}

[bold yellow]Next Steps After Confirmation:[/bold yellow]
1. Unmount drive (if mounted)
2. Backup partition table
3. Create/modify partitions
4. Install bootloader
5. {"Download and install base OS image" if base_image else "Install minimal Debian OS"}
6. Install AI stack (Ollama, HuggingFace, PyTorch)
7. Configure hardware detection
8. Download initial AI models
9. Verify installation

[bold]Estimated Time:[/bold] {"15-30 minutes" if base_image and self.image_catalog.is_image_cached(base_image) else "30-60 minutes"} depending on internet speed
        """
        
        panel = Panel(
            summary_text.strip(),
            title="🚨 Final Confirmation Required",
            border_style="red" if mode == 'full_wipe' else "yellow",
            padding=(1, 2)
        )
        
        self.console.print(panel)
        self.console.print()
        
        # Multiple confirmations for destructive operations
        if mode == 'full_wipe':
            self.console.print("[red]This operation will PERMANENTLY ERASE ALL DATA on the drive.[/red]")
            
            if not Confirm.ask(f"Are you absolutely sure you want to erase {drive.device}?", default=False):
                return False
            
            if not Confirm.ask("Type the drive path to confirm", default=False):
                typed_path = questionary.text(f"Please type '{drive.device}' to confirm:").ask()
                if typed_path != drive.device:
                    self.console.print("[red]Drive path mismatch. Operation cancelled.[/red]")
                    return False
        
        final_confirm = Confirm.ask(
            f"Proceed with {mode.replace('_', ' ')} setup on {drive.device}?",
            default=False
        )
        
        return final_confirm
    
    def show_progress_screen(self, title: str):
        """Create a progress tracking interface."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console
        )
    
    def show_error(self, title: str, message: str, details: str = None):
        """Display error message with optional details."""
        error_text = f"[red]{message}[/red]"
        if details:
            error_text += f"\n\n[dim]{details}[/dim]"
        
        panel = Panel(
            error_text,
            title=f"❌ {title}",
            border_style="red",
            padding=(1, 2)
        )
        
        self.console.print(panel)
    
    def show_success(self, title: str, message: str):
        """Display success message."""
        panel = Panel(
            f"[green]{message}[/green]",
            title=f"✅ {title}",
            border_style="green",
            padding=(1, 2)
        )
        
        self.console.print(panel)
    
    def show_completion_summary(self, drive: DriveInfo, mode: str):
        """Show final completion summary with next steps."""
        completion_text = f"""
[bold green]🎉 Weirding Module Setup Complete![/bold green]

[bold]Your new Weirding Module is ready:[/bold]
• Device: {drive.device}
• Model: {drive.model}
• Mode: {mode.replace('_', ' ').title()}

[bold blue]What's been installed:[/bold blue]
• Minimal Debian Linux OS with hardware detection
• Ollama container runtime for LLM serving
• HuggingFace Transformers and PyTorch
• Hardware-adaptive performance optimization
• Initial AI model cache structure

[bold yellow]Next Steps:[/bold yellow]
1. Safely eject the drive: [code]sudo umount {drive.device}*[/code]
2. Test on different computers to see hardware adaptation
3. Download AI models: [code]ollama pull llama2[/code]
4. Access via web interface: [code]http://localhost:11434[/code]

[bold cyan]Usage Tips:[/bold cyan]
• The module will auto-detect GPU/CPU capabilities on each host
• Models are cached locally for offline use
• Performance scales automatically with available hardware
• Use [code]python main.py setup-host[/code] to optimize host systems

[green]Your portable AI server is ready to go! 🚀[/green]
        """
        
        panel = Panel(
            completion_text.strip(),
            title="Setup Complete",
            border_style="green",
            padding=(1, 2)
        )
        
        self.console.print(panel)


def main():
    """Test the interactive UI."""
    ui = WeirdingUI()
    
    if not ui.show_welcome():
        return
    
    drives = ui.scan_and_display_drives()
    if not drives:
        return
    
    selected_drive = ui.select_drive(drives)
    if not selected_drive:
        return
    
    analysis = ui.show_drive_analysis(selected_drive)
    mode = ui.select_setup_mode(selected_drive, analysis)
    
    if mode:
        module_name = ui.configure_module_name(selected_drive)
        if module_name is not None:
            if ui.apply_drive_label(selected_drive, module_name):
                if ui.show_setup_summary(selected_drive, mode, analysis, module_name):
                    ui.console.print("\n[green]Setup would proceed here...[/green]")
                    ui.show_completion_summary(selected_drive, mode)


if __name__ == "__main__":
    main()