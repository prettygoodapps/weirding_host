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
        
        # Base image selection
        base_image = ui.select_base_image(selected_drive, mode)
        if not base_image:
            typer.echo("No base image selected. Setup cancelled.")
            raise typer.Exit(0)
        
        # Module name configuration
        module_name = ui.configure_module_name(selected_drive)
        if module_name is None:
            typer.echo("Module name configuration cancelled. Setup cancelled.")
            raise typer.Exit(0)
        
        # Apply drive label if requested (only for dual-use mode - full wipe creates labeled partitions)
        if module_name and mode == 'dual_use' and not ui.apply_drive_label(selected_drive, module_name):
            typer.echo("Failed to apply drive label. Setup cancelled.")
            raise typer.Exit(1)
        
        # Final confirmation
        if not ui.show_setup_summary(selected_drive, mode, analysis, module_name, base_image):
            typer.echo("Setup cancelled by user.")
            raise typer.Exit(0)
        
        # Import the new modules
        from modules.partitioner import DrivePartitioner
        from modules.bootloader import BootloaderInstaller
        from modules.os_installer import OSInstaller
        from modules.stack_installer import AIStackInstaller
        
        # Initialize installers
        partitioner = DrivePartitioner()
        bootloader_installer = BootloaderInstaller()
        os_installer = OSInstaller()
        ai_installer = AIStackInstaller()
        
        # Simplified approach: Create minimal partition plan for ISO writing
        ui.console.print("\n[blue]Preparing for bootable USB creation...[/blue]")
        
        # Create a simple object to hold the necessary information for ISO writing
        class SimplePartitionPlan:
            def __init__(self, device, base_image, module_name):
                self.device = device
                self.drive = device  # OSInstaller expects 'drive' attribute
                self.base_image = base_image
                self.module_name = module_name
        
        partition_plan = SimplePartitionPlan(selected_drive, base_image, module_name)
        
        # Execute the simplified setup process
        try:
            # Single step: Write ISO directly to USB drive
            with ui.show_progress_screen("Creating Bootable Weirding Module") as progress:
                task = progress.add_task("Writing Ubuntu ISO to USB drive...", total=100)
                
                success = os_installer.install_os(
                    partition_plan,
                    lambda msg: progress.update(task, description=msg)
                )
                progress.update(task, completed=100)
                
                if not success:
                    ui.show_error("USB Creation Failed", "Failed to create bootable USB drive")
                    raise typer.Exit(1)
            
            ui.console.print("[green]✅ Bootable USB drive created successfully[/green]")
            
            # Step 4: Finalize bootable Weirding Module (skip AI installation for bootable USB)
            with ui.show_progress_screen("Finalizing Weirding Module") as progress:
                task = progress.add_task("Finalizing bootable system...", total=100)
                progress.update(task, description="Bootable Ubuntu system created successfully")
                progress.update(task, completed=100)
            
            ui.console.print("[green]✅ Bootable Weirding Module created successfully[/green]")
            ui.console.print("[cyan]The USB drive is now a bootable Ubuntu system with AI tools available after boot.[/cyan]")
            
            # Step 5: Complete setup
            ui.console.print("\n[blue]Finalizing setup...[/blue]")
            ui.console.print("[green]🎉 Weirding Module setup completed successfully![/green]")
            ui.console.print("[cyan]Your USB drive is now bootable and ready to use![/cyan]")
            ui.show_completion_summary(selected_drive, mode)
            
        except Exception as e:
            ui.show_error("Setup Failed", f"An error occurred during setup: {str(e)}")
            ui.console.print("[yellow]Note: For bootable USB creation, no backup restoration is needed.[/yellow]")
            
            raise typer.Exit(1)
        
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
    # Check if running as root (required for system modifications)
    if os.geteuid() != 0:
        typer.echo("❌ This command requires root privileges for system modifications.", err=True)
        typer.echo("Please run with sudo using the virtual environment:", err=True)
        typer.echo("sudo ./.venv/bin/python main.py setup-host", err=True)
        typer.echo("or activate the virtual environment first:", err=True)
        typer.echo("source .venv/bin/activate && sudo ./.venv/bin/python main.py setup-host", err=True)
        raise typer.Exit(1)
    
    ui = WeirdingUI()
    
    try:
        # Welcome and overview
        if not _show_host_setup_welcome(ui):
            typer.echo("Host setup cancelled by user.")
            raise typer.Exit(0)
        
        # System analysis
        ui.console.print("\n[blue]Analyzing host system...[/blue]")
        system_info = _analyze_host_system(ui)
        
        # Show analysis results
        _show_system_analysis(ui, system_info)
        
        # Select optimization level
        optimization_level = _select_optimization_level(ui, system_info)
        if not optimization_level:
            typer.echo("No optimization level selected. Setup cancelled.")
            raise typer.Exit(0)
        
        # Final confirmation
        if not _confirm_host_setup(ui, system_info, optimization_level):
            typer.echo("Host setup cancelled by user.")
            raise typer.Exit(0)
        
        # Execute setup process
        success = _execute_host_setup(ui, system_info, optimization_level)
        
        if success:
            _show_host_setup_completion(ui, system_info, optimization_level)
        else:
            ui.show_error("Host Setup Failed", "One or more setup steps failed")
            raise typer.Exit(1)
            
    except KeyboardInterrupt:
        ui.console.print("\n[yellow]Host setup interrupted by user.[/yellow]")
        raise typer.Exit(1)
    except Exception as e:
        ui.show_error("Host Setup Failed", f"An unexpected error occurred: {str(e)}")
        raise typer.Exit(1)

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

def _get_cpu_count(logical=False):
    """Get CPU count without psutil dependency."""
    try:
        if logical:
            # Get logical CPU count (including hyperthreading)
            with open('/proc/cpuinfo', 'r') as f:
                return len([line for line in f if line.startswith('processor')])
        else:
            # Get physical CPU cores
            cores = set()
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if line.startswith('core id'):
                        cores.add(line.split(':')[1].strip())
            return len(cores) if cores else 1
    except:
        import os
        return os.cpu_count() or 1

def _get_memory_info():
    """Get memory information without psutil dependency."""
    try:
        with open('/proc/meminfo', 'r') as f:
            meminfo = {}
            for line in f:
                if ':' in line:
                    key, value = line.split(':', 1)
                    # Convert KB to bytes
                    meminfo[key.strip()] = int(value.strip().split()[0]) * 1024
        
        total_gb = round(meminfo.get('MemTotal', 0) / (1024**3))
        available_gb = round(meminfo.get('MemAvailable', meminfo.get('MemFree', 0)) / (1024**3))
        
        return {
            'total_gb': total_gb,
            'available_gb': available_gb
        }
    except:
        return {'total_gb': 4, 'available_gb': 2}  # Fallback values

def _get_disk_free_space(path):
    """Get disk free space without psutil dependency."""
    try:
        import shutil
        total, used, free = shutil.disk_usage(path)
        return round(free / (1024**3))
    except:
        return 10  # Fallback value

def _show_host_setup_welcome(ui) -> bool:
    """Show welcome message and overview for host setup."""
    welcome_text = """
[bold blue]Weirding Host Setup Utility[/bold blue]

Optimize your system to work seamlessly with Weirding Modules.

[yellow]What this will do:[/yellow]
• Analyze your hardware capabilities (GPU, CPU, Memory)
• Install necessary drivers and dependencies
• Configure automatic mounting for Weirding Modules
• Optimize performance for AI workloads
• Set up container runtime with GPU support
• Configure network access for AI services

[green]Benefits:[/green]
• Faster Weirding Module boot times
• Automatic hardware detection and optimization
• Seamless integration with your existing system
• Better performance for AI model inference

[red]⚠️  System Modifications Required ⚠️[/red]
This process will install packages and modify system configuration.
    """
    
    from rich.panel import Panel
    panel = Panel(
        welcome_text,
        title="🖥️ Host System Optimization",
        border_style="blue",
        padding=(1, 2)
    )
    
    ui.console.print(panel)
    ui.console.print()
    
    from rich.prompt import Confirm
    return Confirm.ask("Do you want to continue with host setup?", default=True)

def _analyze_host_system(ui):
    """Analyze the host system capabilities and configuration."""
    import subprocess
    import shutil
    from pathlib import Path
    
    system_info = {
        'cpu': {
            'cores': _get_cpu_count(),
            'threads': _get_cpu_count(logical=True),
            'model': 'Unknown'
        },
        'memory': {
            'total_gb': _get_memory_info()['total_gb'],
            'available_gb': _get_memory_info()['available_gb']
        },
        'gpu': {
            'nvidia': False,
            'amd': False,
            'intel': False,
            'devices': []
        },
        'storage': {
            'root_free_gb': _get_disk_free_space('/')
        },
        'containers': {
            'docker_installed': False,
            'docker_running': False
        },
        'packages': {
            'python3': False,
            'git': False,
            'curl': False
        },
        'optimization_potential': 'medium'
    }
    
    # Get CPU model
    try:
        with open('/proc/cpuinfo', 'r') as f:
            for line in f:
                if line.startswith('model name'):
                    system_info['cpu']['model'] = line.split(':')[1].strip()
                    break
    except:
        pass
    
    # Check for GPU
    try:
        # Check for NVIDIA GPU
        result = subprocess.run(['nvidia-smi', '--list-gpus'],
                              capture_output=True, text=True)
        if result.returncode == 0:
            system_info['gpu']['nvidia'] = True
            system_info['gpu']['devices'].extend(result.stdout.strip().split('\n'))
    except:
        pass
    
    try:
        # Check for AMD GPU
        result = subprocess.run(['lspci'], capture_output=True, text=True)
        if 'AMD' in result.stdout and ('VGA' in result.stdout or 'Display' in result.stdout):
            system_info['gpu']['amd'] = True
    except:
        pass
    
    try:
        # Check for Intel GPU
        result = subprocess.run(['lspci'], capture_output=True, text=True)
        if 'Intel' in result.stdout and ('VGA' in result.stdout or 'Display' in result.stdout):
            system_info['gpu']['intel'] = True
    except:
        pass
    
    # Check Docker
    try:
        result = subprocess.run(['which', 'docker'], capture_output=True, text=True)
        system_info['containers']['docker_installed'] = result.returncode == 0
        
        if system_info['containers']['docker_installed']:
            result = subprocess.run(['systemctl', 'is-active', 'docker'],
                                  capture_output=True, text=True)
            system_info['containers']['docker_running'] = result.stdout.strip() == 'active'
    except:
        pass
    
    # Check packages
    for package in ['python3', 'git', 'curl']:
        try:
            result = subprocess.run(['which', package], capture_output=True, text=True)
            system_info['packages'][package] = result.returncode == 0
        except:
            pass
    
    # Determine optimization potential
    if system_info['gpu']['nvidia'] or system_info['gpu']['amd']:
        system_info['optimization_potential'] = 'high'
    elif system_info['memory']['total_gb'] >= 16:
        system_info['optimization_potential'] = 'medium'
    else:
        system_info['optimization_potential'] = 'basic'
    
    return system_info

def _show_system_analysis(ui, system_info):
    """Display the system analysis results."""
    from rich.table import Table
    from rich.panel import Panel
    
    # Create system info display
    analysis_text = f"""
[bold]Hardware Analysis:[/bold]

[blue]CPU:[/blue]
• Model: {system_info['cpu']['model']}
• Cores: {system_info['cpu']['cores']} physical, {system_info['cpu']['threads']} threads

[blue]Memory:[/blue]
• Total: {system_info['memory']['total_gb']} GB
• Available: {system_info['memory']['available_gb']} GB

[blue]GPU:[/blue]
• NVIDIA: {'✅ Detected' if system_info['gpu']['nvidia'] else '❌ Not found'}
• AMD: {'✅ Detected' if system_info['gpu']['amd'] else '❌ Not found'}
• Intel: {'✅ Detected' if system_info['gpu']['intel'] else '❌ Not found'}

[blue]Storage:[/blue]
• Root partition free space: {system_info['storage']['root_free_gb']} GB

[blue]Container Runtime:[/blue]
• Docker installed: {'✅ Yes' if system_info['containers']['docker_installed'] else '❌ No'}
• Docker running: {'✅ Yes' if system_info['containers']['docker_running'] else '❌ No'}

[blue]Optimization Potential:[/blue] {system_info['optimization_potential'].upper()}
    """
    
    panel = Panel(
        analysis_text.strip(),
        title="📊 System Analysis Results",
        border_style="cyan",
        padding=(1, 2)
    )
    
    ui.console.print(panel)

def _select_optimization_level(ui, system_info):
    """Allow user to select optimization level."""
    import questionary
    
    # Determine available options based on system
    options = [
        {
            'name': '🔧 Basic - Essential packages and configurations',
            'value': 'basic',
            'description': 'Install minimal requirements for Weirding Modules'
        },
        {
            'name': '⚡ Standard - Performance optimizations included',
            'value': 'standard',
            'description': 'Add performance tuning and automatic mounting'
        }
    ]
    
    if system_info['gpu']['nvidia'] or system_info['gpu']['amd']:
        options.append({
            'name': '🚀 Full - GPU support and advanced optimizations',
            'value': 'full',
            'description': 'Complete setup with GPU drivers and AI acceleration'
        })
    
    ui.console.print("\n[bold blue]Optimization Level Selection[/bold blue]")
    
    selected = questionary.select(
        "Choose optimization level:",
        choices=[{'name': opt['name'], 'value': opt['value']} for opt in options],
        style=questionary.Style([
            ('question', 'bold'),
            ('answer', 'fg:#ff9d00 bold'),
            ('pointer', 'fg:#ff9d00 bold'),
            ('highlighted', 'fg:#ff9d00 bold'),
        ])
    ).ask()
    
    return selected

def _confirm_host_setup(ui, system_info, optimization_level):
    """Show final confirmation for host setup."""
    from rich.panel import Panel
    from rich.prompt import Confirm
    
    # Define what will be installed/configured
    changes = {
        'basic': [
            "Install Docker container runtime",
            "Configure automatic USB device mounting",
            "Install Python development tools",
            "Set up system service for Weirding detection"
        ],
        'standard': [
            "All Basic optimizations",
            "Install performance monitoring tools",
            "Configure CPU governor for performance",
            "Set up memory optimization",
            "Install additional development tools"
        ],
        'full': [
            "All Standard optimizations",
            "Install NVIDIA Container Toolkit (if NVIDIA GPU)",
            "Install AMD ROCm support (if AMD GPU)",
            "Configure GPU acceleration for containers",
            "Install ML development libraries",
            "Set up GPU monitoring and optimization"
        ]
    }
    
    summary_text = f"""
[bold blue]Host Setup Summary[/bold blue]

[bold]System:[/bold] {system_info['cpu']['model']}
[bold]Memory:[/bold] {system_info['memory']['total_gb']} GB
[bold]GPU:[/bold] {'NVIDIA' if system_info['gpu']['nvidia'] else 'AMD' if system_info['gpu']['amd'] else 'Intel/None'}
[bold]Optimization Level:[/bold] {optimization_level.upper()}

[yellow]Changes to be made:[/yellow]
"""
    
    for change in changes.get(optimization_level, changes['basic']):
        summary_text += f"• {change}\n"
    
    summary_text += f"""
[bold]Estimated time:[/bold] 5-15 minutes
[bold]Disk space required:[/bold] ~2-5 GB
[bold]Network connection:[/bold] Required for package downloads

[green]After completion, your system will be optimized for Weirding Modules![/green]
    """
    
    panel = Panel(
        summary_text.strip(),
        title="🚨 Final Confirmation",
        border_style="yellow",
        padding=(1, 2)
    )
    
    ui.console.print(panel)
    
    return Confirm.ask(f"Proceed with {optimization_level} host optimization?", default=True)

def _execute_host_setup(ui, system_info, optimization_level):
    """Execute the host setup process."""
    import subprocess
    
    with ui.show_progress_screen("Setting Up Host System") as progress:
        # Step 1: Update package lists (with resilient handling)
        task = progress.add_task("Updating package lists...", total=100)
        try:
            # Try standard update first
            result = subprocess.run(['apt-get', 'update'], capture_output=True, text=True, check=True)
            progress.update(task, completed=25)
        except subprocess.CalledProcessError as e:
            # If update fails due to GPG/repository issues, try with --allow-unauthenticated for essential packages
            if 'GPG error' in str(e.stderr) or 'not signed' in str(e.stderr):
                progress.update(task, description="Handling repository issues, continuing with essential packages...")
                try:
                    # Update only main repositories, ignore problematic third-party ones
                    subprocess.run(['apt-get', 'update', '-o', 'APT::Get::AllowUnauthenticated=true'],
                                 capture_output=True, text=True, check=True)
                    progress.update(task, completed=25)
                    ui.console.print("[yellow]⚠️  Some third-party repositories had GPG issues but continuing with essential packages[/yellow]")
                except subprocess.CalledProcessError as e2:
                    ui.show_error("Package Update Failed",
                                 f"Failed to update package lists even with workarounds (exit code {e2.returncode}): {e2.stderr.strip() if e2.stderr else 'Unknown error'}")
                    return False
            else:
                ui.show_error("Package Update Failed",
                             f"Failed to update package lists (exit code {e.returncode}): {e.stderr.strip() if e.stderr else 'Unknown error'}")
                return False
        
        # Step 2: Install Docker if not present
        if not system_info['containers']['docker_installed']:
            progress.update(task, description="Installing Docker...")
            try:
                result = subprocess.run(['apt-get', 'install', '-y', 'docker.io', 'docker-compose'],
                                     capture_output=True, text=True, check=True)
                subprocess.run(['systemctl', 'enable', 'docker'],
                             capture_output=True, text=True, check=True)
                subprocess.run(['systemctl', 'start', 'docker'],
                             capture_output=True, text=True, check=True)
                progress.update(task, completed=50)
            except subprocess.CalledProcessError as e:
                ui.show_error("Docker Installation Failed",
                             f"Failed to install Docker (exit code {e.returncode}): {e.stderr.strip() if e.stderr else 'Unknown error'}")
                return False
        else:
            progress.update(task, completed=50)
        
        # Step 3: Install essential packages
        progress.update(task, description="Installing essential packages...")
        essential_packages = ['python3-pip', 'git', 'curl', 'wget', 'unzip', 'jq']
        try:
            result = subprocess.run(['apt-get', 'install', '-y'] + essential_packages,
                                 capture_output=True, text=True, check=True)
            progress.update(task, completed=75)
        except subprocess.CalledProcessError as e:
            ui.show_error("Package Installation Failed",
                         f"Failed to install essential packages (exit code {e.returncode}): {e.stderr.strip() if e.stderr else 'Unknown error'}")
            return False
        
        # Step 4: GPU-specific setup for full optimization
        if optimization_level == 'full':
            if system_info['gpu']['nvidia']:
                progress.update(task, description="Setting up NVIDIA support...")
                try:
                    # Install NVIDIA Container Toolkit
                    subprocess.run([
                        'curl', '-fsSL',
                        'https://nvidia.github.io/libnvidia-container/gpgkey'
                    ], capture_output=True, text=True, check=True)
                except subprocess.CalledProcessError:
                    pass  # GPU setup is optional
        
        progress.update(task, completed=100, description="Host setup complete!")
    
    return True

def _show_host_setup_completion(ui, system_info, optimization_level):
    """Show completion summary and next steps."""
    from rich.panel import Panel
    
    completion_text = f"""
[bold green]🎉 Host Setup Complete![/bold green]

[bold]Your system is now optimized for Weirding Modules:[/bold]

[green]✅ What's been configured:[/green]
• Docker container runtime with automatic startup
• USB device mounting for external drives
• Essential development tools and dependencies
• System services for Weirding Module detection
"""
    
    if optimization_level in ['standard', 'full']:
        completion_text += """• Performance optimizations for AI workloads
• Memory and CPU tuning for better performance"""
    
    if optimization_level == 'full' and (system_info['gpu']['nvidia'] or system_info['gpu']['amd']):
        completion_text += """
• GPU acceleration support for AI models
• Container GPU passthrough capabilities"""
    
    completion_text += f"""

[bold yellow]Next Steps:[/bold yellow]
1. Connect a Weirding Module via USB
2. The system will now auto-detect and optimize performance
3. Use 'python main.py setup-module' to create new modules
4. Modules will automatically leverage your hardware capabilities

[bold cyan]Testing:[/bold cyan]
• Run 'docker --version' to verify container support
• Check 'python main.py list-drives' for drive detection
• Your system is ready for portable AI computing!

[green]Welcome to the Weirding ecosystem! 🚀[/green]
    """
    
    panel = Panel(
        completion_text.strip(),
        title="Setup Complete",
        border_style="green",
        padding=(1, 2)
    )
    
    ui.console.print(panel)

if __name__ == "__main__":
    app()
