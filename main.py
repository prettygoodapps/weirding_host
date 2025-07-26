import typer

app = typer.Typer()

@app.command()
def setup_module():
    """Set up a new Weirding Module."""
    print("Setting up a new Weirding Module...")

@app.command()
def setup_host():
    """Prepare the current system to work with a Weirding Module."""
    print("Setting up the host system...")

if __name__ == "__main__":
    app()
