"""
WHISPERNET - Unified CLI for the PHOENIX ecosystem
"""
import click
from .. import __version__

# Import module CLI groups when available
try:
    from ..songbird.cli import songbird_cli
except ImportError:
    songbird_cli = None

try:
    from ..projector.cli import projector_cli
except ImportError:
    projector_cli = None

try:
    from ..cipher.cli import cipher_cli
except ImportError:
    cipher_cli = None

try:
    from ..vinyl.cli import vinyl_cli
except ImportError:
    vinyl_cli = None

@click.group()
@click.version_option(version=__version__)
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.pass_context
def cli(ctx, verbose):
    """PHOENIX: A unified, privacy-first ecosystem of tools.

    WHISPERNET is the unified interface that provides access to all PHOENIX modules:
    - SONGBIRD: Music player and library manager
    - PROJECTOR: Film and TV tracking system
    - CIPHER: Network privacy and security toolkit
    - VINYL: Physical media cataloging system

    Use 'whispernet <module> --help' to see module-specific commands.
    """
    ctx.ensure_object(dict)
    ctx.obj['VERBOSE'] = verbose

    if verbose:
        click.echo("Verbose mode enabled")

@cli.command()
def banner():
    """Display the PHOENIX banner."""
    banner_text = """
  _____ _   _ _   _  _____ _____ _____ ____
 |  ___| | | | \ | |/ ____|_   _/ ____|  _ \
 | |_  | | | |  \| | |  _   | || |  _| |_) |
 |  _| | | | | . ` | | |_|  | || |_| |  _ <
 | |   | |_| | |\  | |__| |_| || |__| |_) |
 |_|    \___/|_| \_|\_____|_____|_____|____/
"""
    click.echo(click.style(banner_text, fg="cyan"))
    click.echo(click.style("A unified, privacy-first ecosystem for media, security, and self-defense", fg="white"))
    click.echo(click.style("PHOENIX", fg="cyan", bold=True))
    click.echo()

@cli.command()
def modules():
    """List available PHOENIX modules."""
    modules_info = {
        "songbird": "Music player and library manager",
        "projector": "Film and TV tracking system",
        "cipher": "Network privacy and security toolkit",
        "vinyl": "Physical media cataloging system",
    }

    click.echo("Available PHOENIX modules:")
    click.echo()
    for name, description in modules_info.items():
        click.echo(f"  {click.style(name, fg='green')}: {description}")
    click.echo()
    click.echo("Use 'whispernet <module> --help' to explore each module.")

# Subcommand groups will be added as modules are implemented
if songbird_cli:
    cli.add_command(songbird_cli, 'songbird')

if projector_cli:
    cli.add_command(projector_cli, 'projector')

if cipher_cli:
    cli.add_command(cipher_cli, 'cipher')

if vinyl_cli:
    cli.add_command(vinyl_cli, 'vinyl')

def main():
    """Entry point for the CLI."""
    cli()

if __name__ == '__main__':
    main()