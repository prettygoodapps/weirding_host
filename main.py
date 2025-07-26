import typer
import sys
import os
from pathlib import Path

# Add modules directory to path
sys.path.append(str(Path(__file__).parent / "modules"))

from modules.interactive_ui import WeirdingUI
from modules.device_setup import DriveDetector

app = typer.Typer(
    name="weirding-host",
    help="Weirding Host Utility - Create portable AI servers on external drives",
    add_completion=False
)

@app.command()
def setup_module():
    """
    Set up a new Weirding Module on an external drive.
    
    This interactive process will guide you through converting an external
    storage device into a portable AI server with hardware-adaptive capabilities.
    """
    # Check if running as root (required for disk operations)
    if os.geteuid() != 0:
        typer.echo("❌ This command requires root privileges for disk operations.", err=True)
        typer.echo("Please run with sudo using the virtual environment:", err=True)
        typer.echo("sudo ./venv/bin/python main.py setup-module", err=True)
        typer.echo("or activate the virtual environment first:", err=True)
        typer.echo("source venv/bin/activate && sudo python main.py setup-module", err=True)
        raise typer.Exit(1)
    
    ui = WeirdingUI()
    
    try:
        # Welcome and initial checks
        if not ui.show_welcome():
            typer.echo("Setup cancelled by user.")
            raise typer.Exit(0)
        
        # Scan and display available drives
        drives = ui.scan_and_display_drives()
        if not drives:
            typer.echo("No suitable external drives found. Please connect an external drive and try again.")
            raise typer.Exit(1)
        
        # Drive selection
        selected_drive = ui.select_drive(drives)
        if not selected_drive:
            typer.echo("No drive selected. Setup cancelled.")
            raise typer.Exit(0)
        
        # Drive analysis
        analysis = ui.show_drive_analysis(selected_drive)
        
        # Setup mode selection
        mode = ui.select_setup_mode(selected_drive, analysis)
        if not mode:
            typer.echo("No setup mode selected. Setup cancelled.")
            raise typer.Exit(0)
        
        # Module name configuration
        module_name = ui.configure_module_name(selected_drive)
        if module_name is None:
            typer.echo("Module name configuration cancelled. Setup cancelled.")
            raise typer.Exit(0)
        
        # Apply drive label if requested
        if module_name and not ui.apply_drive_label(selected_drive, module_name):
            typer.echo("Failed to apply drive label. Setup cancelled.")
            raise typer.Exit(1)
        
        # Final confirmation
        if not ui.show_setup_summary(selected_drive, mode, analysis, module_name):
            typer.echo("Setup cancelled by user.")
            raise typer.Exit(0)
        
        # TODO: Implement actual setup process
        ui.console.print("\n[yellow]⚠️  Setup process implementation in progress...[/yellow]")
        ui.console.print("The following steps would be executed:")
        ui.console.print("1. Unmount drive and backup partition table")
        ui.console.print("2. Create new partition layout")
        ui.console.print("3. Install bootloader (GRUB)")
        ui.console.print("4. Install minimal Debian OS")
        ui.console.print("5. Install AI stack (Ollama, HuggingFace, PyTorch)")
        ui.console.print("6. Configure hardware detection")
        ui.console.print("7. Setup model storage and initial downloads")
        ui.console.print("8. Verify installation")
        
        ui.show_completion_summary(selected_drive, mode)
        
    except KeyboardInterrupt:
        ui.console.print("\n[yellow]Setup interrupted by user.[/yellow]")
        raise typer.Exit(1)
    except Exception as e:
        ui.show_error("Setup Failed", f"An unexpected error occurred: {str(e)}")
        raise typer.Exit(1)

@app.command()
def setup_host():
    """
    Prepare the current system to work with a Weirding Module.
    
    This command optimizes the host system for mounting and using
    Weirding Modules, including driver installation and performance tuning.
    """
    ui = WeirdingUI()
    ui.console.print("[blue]Host setup functionality coming soon...[/blue]")
    ui.console.print("This will prepare your system to:")
    ui.console.print("• Mount Weirding Modules automatically")
    ui.console.print("• Optimize performance for AI workloads")
    ui.console.print("• Install necessary drivers and dependencies")
    ui.console.print("• Configure network access to AI services")

@app.command()
def list_drives():
    """List all detected storage devices and their suitability for Weirding Module setup."""
    detector = DriveDetector()
    ui = WeirdingUI()
    
    ui.console.print("[blue]Scanning storage devices...[/blue]")
    drives = detector.scan_drives()
    
    if not drives:
        ui.console.print("[red]No storage devices detected.[/red]")
        return
    
    external_drives = detector.get_external_drives()
    ui.console.print(f"\nFound {len(drives)} total drives, {len(external_drives)} external drives")
    
    # Show detailed information
    for drive in drives:
        meets_req, issues = detector.check_drive_requirements(drive)
        analysis = detector.analyze_drive_usage(drive)
        
        status = "✅ Suitable" if meets_req else "❌ Not suitable"
        ui.console.print(f"\n{drive.device} - {drive.model} ({detector.format_size(drive.size)}) - {status}")
        
        if issues:
            ui.console.print(f"  Issues: {', '.join(issues)}")
        
        if analysis['safety_warnings']:
            ui.console.print(f"  Warnings: {', '.join(analysis['safety_warnings'])}")

@app.command()
def relabel_drive():
    """Relabel an external drive for easy identification."""
    # Check if running as root (required for drive relabeling)
    if os.geteuid() != 0:
        typer.echo("❌ This command requires root privileges for drive relabeling.", err=True)
        typer.echo("Please run with sudo using the virtual environment:", err=True)
        typer.echo("sudo ./venv/bin/python main.py relabel-drive", err=True)
        typer.echo("or activate the virtual environment first:", err=True)
        typer.echo("source venv/bin/activate && sudo python main.py relabel-drive", err=True)
        raise typer.Exit(1)
    
    detector = DriveDetector()
    ui = WeirdingUI()
    
    ui.console.print("[blue]Scanning for external drives...[/blue]")
    drives = detector.scan_drives()
    external_drives = detector.get_external_drives()
    
    if not external_drives:
        ui.console.print("[red]No external drives found.[/red]")
        return
    
    # Show available drives
    suitable_drives = [d for d in external_drives if detector.check_drive_requirements(d)[0]]
    
    if not suitable_drives:
        ui.console.print("[red]No suitable external drives found for relabeling.[/red]")
        return
    
    # Let user select drive
    selected_drive = ui.select_drive(external_drives)
    if not selected_drive:
        ui.console.print("No drive selected.")
        return
    
    # Show current label
    current_label = detector.get_current_label(selected_drive)
    ui.console.print(f"\n[blue]Current label:[/blue] {current_label if current_label else 'No label set'}")
    
    # Get new label
    module_name = ui.configure_module_name(selected_drive)
    if module_name is None:
        ui.console.print("Relabeling cancelled.")
        return
    
    # Apply the label
    if ui.apply_drive_label(selected_drive, module_name):
        ui.show_success("Drive Relabeled", f"Successfully relabeled drive to '{module_name}'")
    else:
        ui.console.print("[red]Failed to relabel drive.[/red]")

@app.command()
def version():
    """Show version information."""
    ui = WeirdingUI()
    ui.console.print("[bold blue]Weirding Host Utility[/bold blue]")
    ui.console.print("Version: 0.1.0-alpha")
    ui.console.print("A tool for creating portable, hardware-adaptive AI servers")

if __name__ == "__main__":
    app()
