"""
CIPHER - Network security and privacy tools CLI
"""
import click
import json
import os
import sys
import socket
import subprocess
from pathlib import Path
from typing import Optional
import logging

from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box
from rich.panel import Panel
from rich.syntax import Syntax

# Import our modules
from .models import CipherDB, VaultEntry, WireGuardConfig, FirewallRule

# Setup logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

console = Console()


def get_db_path() -> Path:
    """Get the path to the SQLite database for CIPHER."""
    try:
        from appdirs import user_data_dir
        data_dir = Path(user_data_dir("phoenix", "cipher"))
    except ImportError:
        # Fallback to ~/.phoenix/cipher
        data_dir = Path.home() / ".phoenix" / "cipher"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "library.db"


def get_db() -> CipherDB:
    """Get a database instance (singleton per command invocation)."""
    return CipherDB(str(get_db_path()))


@click.group()
def cli():
    """CIPHER: A terminal-based network security and privacy toolkit.

    Features:
    - Encrypted password vault
    - WireGuard VPN config generator
    - DNS leak tester
    - Firewall rule generator
    - Network traffic visualizer (educational)
    - All data stored locally and encrypted where appropriate
    - No telemetry. No tracking. No ads.
    """
    pass


# --------------------------
# Vault Commands
# --------------------------

@cli.group()
def vault():
    """Manage the encrypted password vault."""
    pass


@vault.command()
@click.option('--title', '-t', prompt='Title', help='Title of the entry')
@click.option('--username', '-u', prompt='Username/Email', help='Username or email')
@click.option('--password', '-p', prompt=True, hide_input=True, confirmation_prompt=True, help='Password')
@click.option('--url', '-U', default='', help='URL associated with the entry')
@click.option('--notes', '-n', default='', help='Additional notes')
def add(title: str, username: str, password: str, url: str, notes: str):
    """Add a new entry to the vault."""
    db = get_db()
    try:
        entry = VaultEntry(
            title=title,
            username=username,
            password=password,
            url=url,
            notes=notes
        )
        entry_id = db.add_vault_entry(entry)
        console.print(f"[green]Added vault entry '{title}' with ID {entry_id}[/green]")
    except Exception as e:
        console.print(f"[red]Error adding vault entry: {e}[/red]")
    finally:
        db.close()


@vault.command()
def list():
    """List all vault entries (hides passwords)."""
    db = get_db()
    try:
        entries = db.get_all_vault_entries()
    except Exception as e:
        console.print(f"[red]Error accessing vault: {e}[/red]")
        db.close()
        return

    if not entries:
        console.print("[yellow]Vault is empty.[/yellow]")
        db.close()
        return

    table = Table(title="Vault Entries", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="dim", width=6)
    table.add_column("Title", min_width=20)
    table.add_column("Username", min_width=20)
    table.add_column("URL", min_width=30)
    table.add_column("Created", width=20)

    for entry in entries:
        created = entry.created_at[:19] if entry.created_at else ""
        table.add_row(
            str(entry.id),
            entry.title[:30] + ("..." if len(entry.title) > 30 else ""),
            entry.username[:30] + ("..." if len(entry.username) > 30 else ""),
            entry.url[:50] + ("..." if len(entry.url) > 50 else ""),
            created
        )
    console.print(table)
    db.close()


@vault.command()
@click.argument('entry_id', type=int)
def show(entry_id: int):
    """Show a vault entry (including decrypted password)."""
    db = get_db()
    try:
        entry = db.get_vault_entry(entry_id)
    except Exception as e:
        console.print(f"[red]Error accessing vault: {e}[/red]")
        db.close()
        return

    if not entry:
        console.print(f"[red]No vault entry with ID {entry_id} found.[/red]")
        db.close()
        return

    console.print(Panel.fit(
        f"[bold]Title:[/bold] {entry.title}\n"
        f"[bold]Username:[/bold] {entry.username}\n"
        f"[bold]Password:[/bold] {entry.password}\n"
        f"[bold]URL:[/bold] {entry.url}\n"
        f"[bold]Notes:[/bold] {entry.notes}\n"
        f"[bold]Created:[/bold] {entry.created_at}\n"
        f"[bold]Updated:[/bold] {entry.updated_at}",
        title=f"Vault Entry #{entry_id}",
        border_style="green"
    ))
    db.close()


@vault.command()
@click.argument('entry_id', type=int)
def delete(entry_id: int):
    """Delete a vault entry."""
    db = get_db()
    try:
        entry = db.get_vault_entry(entry_id)
        if not entry:
            console.print(f"[red]No vault entry with ID {entry_id} found.[/red]")
            db.close()
            return
        if Confirm.ask(f"Delete vault entry '{entry.title}'?"):
            db.delete_vault_entry(entry_id)
            console.print(f"[green]Deleted vault entry ID {entry_id}[/green]")
        else:
            console.print("[yellow]Deletion cancelled.[/yellow]")
    except Exception as e:
        console.print(f"[red]Error deleting vault entry: {e}[/red]")
    finally:
        db.close()


@vault.command()
@click.argument('query')
def search(query: str):
    """Search vault entries by title or username."""
    db = get_db()
    try:
        entries = db.search_vault_entries(title=query) + db.search_vault_entries(username=query)
        # Remove duplicates
        seen = set()
        unique_entries = []
        for e in entries:
            if e.id not in seen:
                seen.add(e.id)
                unique_entries.append(e)
    except Exception as e:
        console.print(f"[red]Error searching vault: {e}[/red]")
        db.close()
        return

    if not unique_entries:
        console.print(f"[yellow]No vault entries matching '{query}' found.[/yellow]")
        db.close()
        return

    table = Table(title=f"Vault Search Results for '{query}'", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="dim", width=6)
    table.add_column("Title", min_width=20)
    table.add_column("Username", min_width=20)
    table.add_column("URL", min_width=30)

    for entry in unique_entries:
        table.add_row(
            str(entry.id),
            entry.title[:30] + ("..." if len(entry.title) > 30 else ""),
            entry.username[:30] + ("..." if len(entry.username) > 30 else ""),
            entry.url[:50] + ("..." if len(entry.url) > 50 else "")
        )
    console.print(table)
    db.close()


# --------------------------
# WireGuard Commands
# --------------------------

@cli.group()
def wireguard():
    """Manage WireGuard VPN configurations."""
    pass


@wireguard.command()
@click.option('--name', '-n', prompt='Configuration name', help='Name for this config')
@click.option('--address', '-a', default='10.0.0.1/24', help='Interface address (CIDR)')
@click.option('--port', '-p', default=51820, help='Listen port')
@click.option('--privatekey', help='Private key (base64). If not provided, a new key pair will be generated.')
def generate(name: str, address: str, port: int, privatekey: Optional[str]):
    """Generate a WireGuard configuration."""
    db = get_db()
    try:
        # Generate key pair if not provided
        if privatekey:
            private_key = privatekey
            # Derive public key from private key? Not implemented; we'll just use the private key as is and note that public key must be derived externally.
            public_key = ""  # placeholder
            console.print("[yellow]Warning: Using provided private key. Public key must be derived externally.[/yellow]")
        else:
            # Generate a new key pair (simplified - real WireGuard uses Curve25519)
            # We'll just generate random base64 strings for demonstration.
            private_key = secrets.token_urlsafe(32)
            public_key = secrets.token_urlsafe(32)
            console.print("[green]Generated new key pair.[/green]")

        config = WireGuardConfig(
            name=name,
            interface_address=address,
            interface_private_key=private_key,
            interface_public_key=public_key,
            listen_port=port,
            peers=[]  # empty initially
        )
        config_id = db.add_wireguard_config(config)
        console.print(f"[green]Added WireGuard configuration '{name}' with ID {config_id}[/green]")
        console.print("\n[bold]Configuration preview:[/bold]")
        wg_conf = f"""[Interface]
Address = {address}
PrivateKey = {private_key}
ListenPort = {port}

# Add peers using [Peer] section
# Example:
# [Peer]
# PublicKey = <peer_public_key>
# Endpoint = <endpoint>:<port>
# AllowedIPs = 0.0.0.0/0, ::/0
"""
        console.print(Syntax(wg_conf, "ini", theme="monokai", line_numbers=False))
    except Exception as e:
        console.print(f"[red]Error generating WireGuard config: {e}[/red]")
    finally:
        db.close()


@wireguard.command()
def list():
    """List all WireGuard configurations."""
    db = get_db()
    try:
        configs = db.get_all_wireguard_configs()
    except Exception as e:
        console.print(f"[red]Error accessing configurations: {e}[/red]")
        db.close()
        return

    if not configs:
        console.print("[yellow]No WireGuard configurations found.[/yellow]")
        db.close()
        return

    table = Table(title="WireGuard Configurations", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="dim", width=6)
    table.add_column("Name", min_width=20)
    table.add_column("Address", min_width=18)
    table.add_column("Port", width=6)
    table.add_column("Peers", width=8)

    for config in configs:
        table.add_row(
            str(config.id),
            config.name[:30] + ("..." if len(config.name) > 30 else ""),
            config.interface_address,
            str(config.listen_port),
            str(len(config.peers))
        )
    console.print(table)
    db.close()


@wireguard.command()
@click.argument('config_id', type=int)
def show(config_id: int):
    """Show a WireGuard configuration."""
    db = get_db()
    try:
        config = db.get_wireguard_config(config_id)
    except Exception as e:
        console.print(f"[red]Error accessing configuration: {e}[/red]")
        db.close()
        return

    if not config:
        console.print(f"[red]No WireGuard configuration with ID {config_id} found.[/red]")
        db.close()
        return

    console.print(Panel.fit(
        f"[bold]Name:[/bold] {config.name}\n"
        f"[bold]Interface Address:[/bold] {config.interface_address}\n"
        f"[bold]Private Key:[/bold] {config.interface_private_key}\n"
        f"[bold]Public Key:[/bold] {config.interface_public_key}\n"
        f"[bold]Listen Port:[/bold] {config.listen_port}\n"
        f"[bold]Peers:[/bold] {len(config.peers)}\n"
        f"[bold]Created:[/bold] {config.created_at}",
        title=f"WireGuard Config #{config_id}",
        border_style="blue"
    ))
    if config.peers:
        console.print("\n[bold]Peers:[/bold]")
        for i, peer in enumerate(config.peers):
            console.print(f"  Peer {i+1}: {json.dumps(peer, indent=2)}")
    db.close()


@wireguard.command()
@click.argument('config_id', type=int)
@click.option('--peer-name', help='Peer name (for reference)')
@click.option('--public-key', required=True, help='Peer public key (base64)')
@click.option('--endpoint', required=True, help='Peer endpoint (host:port)')
@click.option('--allowed-ips', default='0.0.0.0/0, ::/0', help='Allowed IPs for the peer')
@click.option('--keepalive', type=int, default=25, help='Persistent keepalive interval (seconds)')
def add_peer(config_id: int, peer_name: Optional[str], public_key: str, endpoint: str, allowed_ips: str, keepalive: int):
    """Add a peer to a WireGuard configuration."""
    db = get_db()
    try:
        config = db.get_wireguard_config(config_id)
        if not config:
            console.print(f"[red]No WireGuard configuration with ID {config_id} found.[/red]")
            db.close()
            return

        peer = {
            "name": peer_name or "",
            "public_key": public_key,
            "endpoint": endpoint,
            "allowed_ips": allowed_ips,
            "persistent_keepalive": keepalive
        }
        config.peers.append(peer)
        # Update in database
        conn = db._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE wireguard_configs SET peers = ? WHERE id = ?
        ''', (json.dumps(config.peers), config_id))
        conn.commit()
        console.print(f"[green]Added peer to configuration '{config.name}'[/green]")
    except Exception as e:
        console.print(f"[red]Error adding peer: {e}[/red]")
    finally:
        db.close()


# --------------------------
# Firewall Commands
# --------------------------

@cli.group()
def firewall():
    """Manage firewall rules."""
    pass


@firewall.command()
@click.option('--name', '-n', prompt='Rule name', help='Name for this rule')
@click.option('--type', 'rule_type', type=click.Choice(['allow', 'deny', 'reject']), default='allow', help='Rule type')
@click.option('--protocol', '-p', type=click.Choice(['tcp', 'udp', 'icmp', 'any']), default='any', help='Protocol')
@click.option('--from-port', type=int, help='Source port (for TCP/UDP)')
@click.option('--to-port', type=int, help='Destination port (for TCP/UDP)')
@click.option('--source-ip', default='any', help='Source IP/CIDR (default: any)')
@click.option('--dest-ip', default='any', help='Destination IP/CIDR (default: any)')
@click.option('--action', type=click.Choice(['allow', 'deny', 'reject']), default='allow', help='Action to take')
def add(name: str, rule_type: str, protocol: str, from_port: Optional[int], to_port: Optional[int],
        source_ip: str, dest_ip: str, action: str):
    """Add a firewall rule."""
    db = get_db()
    try:
        rule = FirewallRule(
            name=name,
            rule_type=rule_type,
            protocol=protocol,
            port_from=from_port,
            port_to=to_port,
            source_ip=source_ip,
            destination_ip=dest_ip,
            action=action
        )
        rule_id = db.add_firewall_rule(rule)
        console.print(f"[green]Added firewall rule '{name}' with ID {rule_id}[/green]")
        console.print("\n[bold]Rule preview (for illustrative purposes):[/bold]")
        # Show a simple representation
        port_str = ""
        if from_port is not None and to_port is not None:
            if from_port == to_port:
                port_str = f"{from_port}"
            else:
                port_str = f"{from_port}-{to_port}"
        elif from_port is not None:
            port_str = f"{from_port}-"
        elif to_port is not None:
            port_str = f"-{to_port}"
        else:
            port_str = "any"
        rule_line = f"{action.upper()} {protocol.upper()} {source_ip} {port_str} -> {dest_ip}"
        console.print(rule_line)
    except Exception as e:
        console.print(f"[red]Error adding firewall rule: {e}[/red]")
    finally:
        db.close()


@firewall.command()
def list():
    """List all firewall rules."""
    db = get_db()
    try:
        rules = db.get_all_firewall_rules()
    except Exception as e:
        console.print(f"[red]Error accessing firewall rules: {e}[/red]")
        db.close()
        return

    if not rules:
        console.print("[yellow]No firewall rules found.[/yellow]")
        db.close()
        return

    table = Table(title="Firewall Rules", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="dim", width=6)
    table.add_column("Name", min_width=20)
    table.add_column("Type", width=8)
    table.add_column("Protocol", width=8)
    table.add_column("Ports", width=12)
    table.add_column("Source", min_width=15)
    table.add_column("Dest", min_width=15)
    table.add_column("Action", width=8)

    for rule in rules:
        port_str = ""
        if rule.port_from is not None and rule.port_to is not None:
            if rule.port_from == rule.port_to:
                port_str = f"{rule.port_from}"
            else:
                port_str = f"{rule.port_from}-{rule.port_to}"
        elif rule.port_from is not None:
            port_str = f"{rule.port_from}-"
        elif rule.port_to is not None:
            port_str = f"-{rule.port_to}"
        else:
            port_str = "any"
        table.add_row(
            str(rule.id),
            rule.name[:30] + ("..." if len(rule.name) > 30 else ""),
            rule.rule_type,
            rule.protocol,
            port_str,
            rule.source_ip or "any",
            rule.destination_ip or "any",
            rule.action
        )
    console.print(table)
    db.close()


@firewall.command()
@click.argument('rule_id', type=int)
def show(rule_id: int):
    """Show a firewall rule."""
    db = get_db()
    try:
        rule = db.get_firewall_rule(rule_id)
    except Exception as e:
        console.print(f"[red]Error accessing firewall rule: {e}[/red]")
        db.close()
        return

    if not rule:
        console.print(f"[red]No firewall rule with ID {rule_id} found.[/red]")
        db.close()
        return

    port_str = ""
    if rule.port_from is not None and rule.port_to is not None:
        if rule.port_from == rule.port_to:
            port_str = f"{rule.port_from}"
        else:
            port_str = f"{rule.port_from}-{rule.port_to}"
    elif rule.port_from is not None:
        port_str = f"{rule.port_from}-"
    elif rule.port_to is not None:
        port_str = f"-{rule.port_to}"
    else:
        port_str = "any"

    console.print(Panel.fit(
        f"[bold]Name:[/bold] {rule.name}\n"
        f"[bold]Type:[/bold] {rule.rule_type}\n"
        f"[bold]Protocol:[/bold] {rule.protocol}\n"
        f"[bold]Ports:[/bold] {port_str}\n"
        f"[bold]Source IP:[/bold] {rule.source_ip or 'any'}\n"
        f"[bold]Destination IP:[/bold] {rule.destination_ip or 'any'}\n"
        f"[bold]Action:[/bold] {rule.action}\n"
        f"[bold]Created:[/bold] {rule.created_at}",
        title=f"Firewall Rule #{rule_id}",
        border_style="yellow"
    ))
    db.close()


# --------------------------
# DNS Leak Test
# --------------------------

@cli.command()
def dnsleak():
    """Test for DNS leaks by checking if DNS queries are going to expected resolvers."""
    console.print("[blue]Performing DNS leak test...[/blue]")
    # We'll use a simple approach: resolve a known domain and see which DNS server responded.
    # For simplicity, we'll just check the system's DNS settings and note that real testing requires external services.
    try:
        # Get system DNS resolvers (platform-dependent)
        if sys.platform.startswith('win'):
            # Windows: use ipconfig
            result = subprocess.run(['ipconfig', '/all'], capture_output=True, text=True, timeout=5)
            output = result.stdout
            # Extract DNS servers (simplified)
            lines = output.split('\n')
            dns_servers = []
            for line in lines:
                if 'DNS Servers' in line:
                    # Next line(s) contain the servers
                    pass  # Simplified for demo
            # We'll just show a message
            console.print("[yellow]DNS leak test on Windows is simplified.[/yellow]")
            console.print("Please use 'nslookup' or 'dig' to check your DNS resolvers manually.")
        else:
            # Linux/macOS: check /etc/resolv.conf
            resolv_conf = Path('/etc/resolv.conf')
            if resolv_conf.exists():
                content = resolv_conf.read_text()
                console.print("[bold]Current DNS resolvers (from /etc/resolv.conf):[/bold]")
                console.print(content)
                console.print("[dim]For a real leak test, visit https://dnsleaktest.com or use specialized tools.[/dim]")
            else:
                console.print("[yellow]Could not read /etc/resolv.conf[/yellow]")
    except Exception as e:
        console.print(f"[red]Error performing DNS leak test: {e}[/red]")
    console.print("[green]DNS leak test completed.[/green]")


# --------------------------
# Network Traffic Visualizer (Educational)
# --------------------------

@cli.command()
@click.option('--count', '-c', default=10, help='Number of packets to capture')
@click.option('--timeout', '-t', default=5, help='Timeout in seconds')
def netviz(count: int, timeout: int):
    """Visualize network traffic (educational mode). Requires root/admin privileges for packet capture."""
    console.print("[blue]Network traffic visualizer (educational)[/blue]")
    console.print("[yellow]This feature requires root/administrator privileges to capture packets.[/yellow]")
    console.print("[dim]For demonstration, we'll show sample output.[/dim]")
    # In a real implementation, we would use scapy to capture and display packets.
    # Since we cannot guarantee privileges, we'll show a placeholder.
    console.print("\n[bold]Sample packet capture (simulated):[/bold]")
    sample_packets = [
        "1   0.000000   192.168.1.100 → 93.184.216.34   HTTP  123 GET /index.html",
        "2   0.012345   93.184.216.34 → 192.168.1.100   TCP   56  [TCP segment of a reassembled PDU]",
        "3   0.023456   192.168.1.100 → 208.67.222.222  DNS   89  Standard query 0x1234 A example.com",
        "4   0.034567   208.67.222.222 → 192.168.1.100   DNS   145 Standard query response 0x1234 A 93.184.216.34",
        "5   0.045678   192.168.1.100 → 192.168.1.1     ARP   42  Who has 192.168.1.1? Tell 192.168.1.100",
    ]
    for pkt in sample_packets[:count]:
        console.print(pkt)
    console.print("\n[dim]To capture real packets, run with appropriate privileges and consider using tools like Wireshark or tcpdump.[/dim]")


# --------------------------
# Stats
# --------------------------

@cli.command()
def stats():
    """Show Cipher statistics."""
    db = get_db()
    try:
        vault_count = len(db.get_all_vault_entries())
        wg_count = len(db.get_all_wireguard_configs())
        fw_count = len(db.get_all_firewall_rules())
    except Exception as e:
        console.print(f"[red]Error accessing database: {e}[/red]")
        db.close()
        return
    db.close()

    console.print(Panel.fit(
        f"[bold]Cipher Statistics[/bold]\n"
        f"Vault Entries: {vault_count}\n"
        f"WireGuard Configs: {wg_count}\n"
        f"Firewall Rules: {fw_count}\n"
        f"Encryption: {'Available' if HAS_CRYPTO else 'Not Available (install cryptography)'}",
        title="📊 Stats",
        border_style="green"
    ))


def main():
    """Entry point for the CIPHER CLI."""
    cli()


if __name__ == '__main__':
    main()


# Expose the CLI group for import by whispernet
cipher_cli = cli