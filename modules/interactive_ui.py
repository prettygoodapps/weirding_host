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

from device_setup import DriveInfo, DriveDetector


class WeirdingUI:
    """Interactive user interface for Weirding Module setup."""
    
    def __init__(self):
        self.console = Console()
        self.detector = DriveDetector()
        
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
    
    def show_setup_summary(self, drive: DriveInfo, mode: str, analysis: Dict) -> bool:
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
        
        summary_text = f"""
[bold blue]Setup Summary[/bold blue]

[bold]Target Drive:[/bold] {drive.device}
[bold]Model:[/bold] {drive.model} ({drive.vendor})
[bold]Size:[/bold] {self.detector.format_size(drive.size)}
[bold]Mode:[/bold] {mode.replace('_', ' ').title()}

{impact_text}

[bold yellow]Next Steps After Confirmation:[/bold yellow]
1. Unmount drive (if mounted)
2. Backup partition table
3. Create/modify partitions
4. Install bootloader
5. Install minimal Debian OS
6. Install AI stack (Ollama, HuggingFace, PyTorch)
7. Configure hardware detection
8. Download initial AI models
9. Verify installation

[bold]Estimated Time:[/bold] 30-60 minutes depending on internet speed
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
    
    if mode and ui.show_setup_summary(selected_drive, mode, analysis):
        ui.console.print("\n[green]Setup would proceed here...[/green]")
        ui.show_completion_summary(selected_drive, mode)


if __name__ == "__main__":
    main()