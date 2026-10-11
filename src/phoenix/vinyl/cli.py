"""
VINYL - Vinyl record collection manager CLI
"""
import click
import json
import os
import sys
import time
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
from .models import VinylDB, VinylRecord

# Setup logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

console = Console()


def get_db_path() -> Path:
    """Get the path to the SQLite database for VINYL."""
    try:
        from appdirs import user_data_dir
        data_dir = Path(user_data_dir("phoenix", "vinyl"))
    except ImportError:
        # Fallback to ~/.phoenix/vinyl
        data_dir = Path.home() / ".phoenix" / "vinyl"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "library.db"


def get_db() -> VinylDB:
    """Get a database instance (singleton per command invocation)."""
    return VinylDB(str(get_db_path()))


@click.group()
def cli():
    """VINYL: A terminal-based vinyl record collection manager.

    Features:
    - Catalog vinyl records by barcode, Discogs ID, or manual entry
    - Track condition, playback statistics
    - Link to digital tracks (if using SONGBIRD)
    - Simulated barcode scanning
    - Read-only Discogs API integration
    - No telemetry. No tracking. No ads.
    """
    pass


# --------------------------
# Vinyl Records Commands
# --------------------------

@cli.command()
@click.option('--barcode', '-b', help='Barcode (UPC/EAN)')
@click.option('--discogs-id', '-d', help='Discogs release ID')
@click.option('--catalog-number', '-c', help='Label catalog number')
@click.option('--title', '-t', help='Title of the release')
@click.option('--artist', '-a', help='Artist name')
@click.option('--year', '-y', type=int, help='Release year')
@click.option('--genre', '-g', multiple=True, help='Genre(s)')
@click.option('--style', '-s', multiple=True, help='Style(s)')
@click.option('--format', '-f', help='Format (LP, Single, etc.)')
@click.option('--condition', '-C', help='Condition (Mint, Near Mint, etc.)')
@click.option('--sleeve', '-S', help='Sleeve condition')
@click.option('--notes', '-n', default='', help='Additional notes')
@click.option('--purchased-from', '-p', default='', help='Where purchased')
@click.option('--price', type=float, default=0.0, help='Purchase price')
@click.option('--purchased-date', '-d', help='Purchase date (YYYY-MM-DD)')
def add(barcode: Optional[str], discogs_id: Optional[str], catalog_number: Optional[str],
        title: Optional[str], artist: Optional[str], year: Optional[int],
        genre: tuple, style: tuple, format: Optional[str],
        condition: Optional[str], sleeve: Optional[str],
        notes: str, purchased_from: str, price: float, purchased_date: Optional[str]):
    """Add a vinyl record to the collection."""
    db = get_db()
    # If Discogs ID provided, try to fetch from Discogs (if requests available)
    if discogs_id and not title:
        if HAS_REQUESTS:
            try:
                console.print(f"[blue]Fetching release {discogs_id} from Discogs...[/blue]")
                response = requests.get(f"https://api.discogs.com/releases/{discogs_id}", timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    record = VinylRecord.from_discogs(data)
                    # Override with any manually provided fields
                    if barcode:
                        record.barcode = barcode
                    if catalog_number:
                        record.catalog_number = catalog_number
                    if title:
                        record.title = title
                    if artist:
                        record.artist = artist
                    if year:
                        record.year = year
                    if genre:
                        record.genres = list(genre)
                    if style:
                        record.styles = list(style)
                    if format:
                        record.format = format
                    if condition:
                        record.condition = condition
                    if sleeve:
                        record.sleeve_condition = sleeve
                    if notes:
                        record.notes = notes
                    if purchased_from:
                        record.purchased_from = purchased_from
                    if price:
                        record.purchase_price = price
                    if purchased_date:
                        record.purchase_date = purchased_date
                    # Mark barcode as scanned if barcode provided
                    if barcode:
                        record.barcode_scanned = True
                    record_id = db.add_vinyl_record(record)
                    console.print(f"[green]Added vinyl record '{record.title}' from Discogs with ID {record_id}[/green]")
                    db.close()
                    return
                else:
                    console.print(f"[yellow]Discogs API returned status {response.status_code}[/yellow]")
            except Exception as e:
                console.print(f"[yellow]Could not fetch from Discogs: {e}[/yellow]")
                console.print("[yellow]Falling back to manual entry.[/yellow]")
        else:
            console.print("[yellow]Requests not installed. Cannot fetch from Discogs.[/yellow]")
            console.print("[yellow]Falling back to manual entry.[/yellow]")

    # Manual entry or fallback
    if not title:
        title = Prompt.ask("Title")
    if not artist:
        artist = Prompt.ask("Artist")
    record = VinylRecord(
        barcode=barcode,
        discogs_id=discogs_id,
        catalog_number=catalog_number,
        title=title,
        artist=artist,
        year=year,
        genres=list(genre) if genre else [],
        styles=list(style) if style else [],
        format=format or "",
        condition=condition or "",
        sleeve_condition=sleeve or "",
        notes=notes,
        purchased_from=purchased_from,
        purchase_price=price,
        purchase_date=purchased_date or "",
        barcode_scanned=bool(barcode)  # if barcode provided, assume scanned
    )
    try:
        record_id = db.add_vinyl_record(record)
        console.print(f"[green]Added vinyl record '{record.title}' with ID {record_id}[/green]")
        if record.barcode:
            console.print(f"[dim]Barcode: {record.barcode}[/dim]")
    except Exception as e:
        console.print(f"[red]Error adding vinyl record: {e}[/red]")
    finally:
        db.close()


@cli.command()
def list():
    """List all vinyl records in the collection."""
    db = get_db()
    records = db.get_all_vinyl_records()
    db.close()

    if not records:
        console.print("[yellow]Collection is empty. Use 'vinyl add' to add records.[/yellow]")
        return

    table = Table(title="Vinyl Collection", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="dim", width=6)
    table.add_column("Title", min_width=25)
    table.add_column("Artist", min_width=25)
    table.add_column("Year", width=6)
    table.add_column("Format", width=10)
    table.add_column("Condition", width=12)
    table.add_column("Plays", width=8)

    for record in records:
        table.add_row(
            str(record.id),
            record.title[:30] + ("..." if len(record.title) > 30 else ""),
            record.artist[:30] + ("..." if len(record.artist) > 30 else ""),
            str(record.year) if record.year else "",
            record.format,
            record.condition or "-",
            str(record.play_count)
        )
    console.print(table)


@cli.command()
@click.argument('query')
def search(query: str):
    """Search vinyl records by title or artist."""
    db = get_db()
    # Search by title or artist
    results = db.search_vinyl_records(title=query) + db.search_vinyl_records(artist=query)
    # Remove duplicates
    seen = set()
    unique_results = []
    for r in results:
        if r.id not in seen:
            seen.add(r.id)
            unique_results.append(r)
    db.close()

    if not unique_results:
        console.print(f"[yellow]No vinyl records matching '{query}' found.[/yellow]")
        return

    table = Table(title=f"Search Results for '{query}'", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="dim", width=6)
    table.add_column("Title", min_width=25)
    table.add_column("Artist", min_width=25)
    table.add_column("Year", width=6)
    table.add_column("Format", width=10)

    for record in unique_results[:50]:
        table.add_row(
            str(record.id),
            record.title[:30] + ("..." if len(record.title) > 30 else ""),
            record.artist[:30] + ("..." if len(record.artist) > 30 else ""),
            str(record.year) if record.year else "",
            record.format
        )
    if len(unique_results) > 50:
        console.print(f"[dim]Showing first 50 of {len(unique_results)} results[/dim]")
    console.print(table)


@cli.command()
@click.argument('identifier')
def show(identifier: str):
    """Show details of a vinyl record."""
    db = get_db()
    record: Optional[VinylRecord] = None
    try:
        record_id = int(identifier)
        record = db.get_vinyl_record_by_id(record_id)
    except ValueError:
        # Try as barcode
        record = db.get_vinyl_record_by_barcode(identifier)
        if not record:
            # Search
            results = db.search_vinyl_records(title=identifier) + db.search_vinyl_records(artist=identifier)
            if results:
                record = results[0]
    db.close()

    if not record:
        console.print(f"[red]No vinyl record matching '{identifier}' found.[/red]")
        return

    # Format genres and styles
    genres = ", ".join(record.genres) if record.genres else "-"
    styles = ", ".join(record.styles) if record.styles else "-"
    # Format digital tracks link
    digital_links = f"{len(record.digital_tracks)} track(s)" if record.digital_tracks else "None"

    console.print(Panel.fit(
        f"[bold]Title:[/bold] {record.title}\n"
        f"[bold]Artist:[/bold] {record.artist}\n"
        f"[bold]Year:[/bold] {record.year or '-'}\n"
        f"[bold]Discogs ID:[/bold] {record.discogs_id or '-'}\n"
        f"[bold]Barcode:[/bold] {record.barcode or '-'}\n"
        f"[bold]Catalog Number:[/bold] {record.catalog_number or '-'}\n"
        f"[bold]Format:[/bold] {record.format}\n"
        f"[bold]Condition:[/bold] {record.condition or '-'}\n"
        f"[bold]Sleeve Condition:[/bold] {record.sleeve_condition or '-'}\n"
        f"[bold]Genres:[/bold] {genres}\n"
        f"[bold]Styles:[/bold] {styles}\n"
        f"[bold]Label:[/bold] {record.label or '-'}\n"
        f"[bold]Country:[/bold] {record.country or '-'}\n"
        f"[bold]Purchase Info:[/bold] {record.purchased_from} ({record.purchase_date}) - ${record.purchase_price:.2f}\n"
        f"[bold]Play Count:[/bold] {record.play_count}\n"
        f"[bold]Last Played:[/bold] {record.last_played or 'Never'}\n"
        f"[bold]Digital Tracks:[/bold] {digital_links}\n"
        f"[bold]Notes:[/bold] {record.notes or '-'}",
        title=f"Vinyl Record: {record.title}",
        border_style="blue"
    ))


@cli.command()
@click.argument('identifier')
def play(identifier: str):
    """Mark a vinyl record as played (increment play count)."""
    db = get_db()
    record: Optional[VinylRecord] = None
    try:
        record_id = int(identifier)
        record = db.get_vinyl_record_by_id(record_id)
    except ValueError:
        # Try as barcode
        record = db.get_vinyl_record_by_barcode(identifier)
        if not record:
            # Search
            results = db.search_vinyl_records(title=identifier) + db.search_vinyl_records(artist=identifier)
            if results:
                record = results[0]
    db.close()

    if not record:
        console.print(f"[red]No vinyl record matching '{identifier}' found.[/red]")
        return

    # Update play count
    db = get_db()
    db.increment_play_count(record.id)
    console.print(f"[green]Marked '{record.title}' as played.[/green]")
    console.print(f"[dim]New play count: {record.play_count}[/dim]")
    db.close()


# --------------------------
# Barcode Scanning (Simulated)
# --------------------------

@cli.command()
@click.option('--barcode', '-b', help='Barcode to process (if not provided, will prompt for simulated scan)')
def barcode(barcode: Optional[str]):
    """Simulate barcode scanning and add/lookup vinyl record."""
    if not barcode:
        barcode = Prompt.ask("Scan or enter barcode")
    # Remove common barcode formatting
    barcode = barcode.strip().replace("-", "").replace(" ", "")
    if not barcode.isdigit() or len(barcode) < 8 or len(barcode) > 15:
        console.print("[red]Invalid barcode format. Please enter a valid UPC/EAN.[/red]")
        return

    db = get_db()
    # Check if we already have this barcode
    existing = db.get_vinyl_record_by_barcode(barcode)
    if existing:
        console.print(f"[yellow]Barcode {barcode} already exists in collection:[/yellow]")
        show(str(existing.id))
        if Confirm.ask("Update this record?"):
            # We'll fall through to add/update with this barcode
            pass
        else:
            db.close()
            return

    # Try to fetch from Discogs using barcode
    if HAS_REQUESTS:
        try:
            console.print(f"[blue]Looking up barcode {barcode} on Discogs...[/blue]")
            # Discogs API endpoint for barcode search
            response = requests.get(f"https://api.discogs.com/database/search?barcode={barcode}&type=release", timeout=10)
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                if results:
                    # Take the first result
                    discogs_id = str(results[0].get('id'))
                    console.print(f"[green]Found Discogs release ID: {discogs_id}[/green]")
                    # Now fetch the full release details
                    release_response = requests.get(f"https://api.discogs.com/releases/{discogs_id}", timeout=10)
                    if release_response.status_code == 200:
                        release_data = release_response.json()
                        record = VinylRecord.from_discogs(release_data)
                        record.barcode = barcode
                        record.barcode_scanned = True
                        # Set other fields from the search result if needed
                        record.title = results[0].get('title', record.title)
                        record.artist = results[0].get('artist', record.artist)
                        record.year = results[0].get('year', record.year)
                        record.label = results[0].get('label', record.label)
                        record.format = results[0].get('format', record.format)
                        record.country = results[0].get('country', record.country)
                        # Add to database
                        record_id = db.add_vinyl_record(record)
                        console.print(f"[green]Added vinyl record '{record.title}' from barcode scan with ID {record_id}[/green]")
                        db.close()
                        return
                    else:
                        console.print(f"[yellow]Could not fetch release details from Discogs[/yellow]")
                else:
                    console.print(f"[yellow]No Discogs results found for barcode {barcode}[/yellow]")
            else:
                console.print(f"[yellow]Discogs API error: {response.status_code}[/yellow]")
        except Exception as e:
            console.print(f"[yellow]Error querying Discogs: {e}[/yellow]")
    else:
        console.print("[yellow]Requests not installed. Cannot query Discogs.[/yellow]")

    # If we get here, we couldn't auto-fill from Discogs, so prompt for manual entry
    console.print("[blue]Please enter the vinyl record details manually:[/blue]")
    # We'll reuse the add command logic but with barcode pre-filled
    # For simplicity, we'll just call the add function with the barcode and let the user fill in the rest
    # In a real CLI, we might invoke the add subcommand, but we'll just simulate by calling add with defaults
    # We'll instead prompt for the missing fields.
    title = Prompt.ask("Title")
    artist = Prompt.ask("Artist")
    year_str = Prompt.ask("Year (optional)", default="")
    year = int(year_str) if year_str.isdigit() else None
    genre_str = Prompt.ask("Genres (comma-separated, optional)", default="")
    genres = [g.strip() for g in genre_str.split(",")] if genre_str else []
    style_str = Prompt.ask("Styles (comma-separated, optional)", default="")
    styles = [s.strip() for s in style_str.split(",")] if style_str else []
    format_val = Prompt.ask("Format (LP, Single, etc.)", default="LP")
    condition_val = Prompt.ask("Condition (Mint, Near Mint, etc.)", default="")
    sleeve_val = Prompt.ask("Sleeve Condition", default="")
    notes_val = Prompt.ask("Notes", default="")
    purchased_from_val = Prompt.ask("Purchased from", default="")
    price_str = Prompt.ask("Purchase price", default="0")
    price = float(price_str) if price_str.replace(".", "", 1).isdigit() else 0.0
    date_val = Prompt.ask("Purchase date (YYYY-MM-DD)", default="")

    record = VinylRecord(
        barcode=barcode,
        discogs_id=None,  # we didn't get one from Discogs in this path
        catalog_number=None,
        title=title,
        artist=artist,
        year=year,
        genres=genres,
        styles=styles,
        format=format_val,
        condition=condition_val,
        sleeve_condition=sleeve_val,
        notes=notes_val,
        purchased_from=purchased_from_val,
        purchase_price=price,
        purchase_date=date_val,
        barcode_scanned=True
    )
    try:
        record_id = db.add_vinyl_record(record)
        console.print(f"[green]Added vinyl record '{record.title}' with ID {record_id}[/green]")
    except Exception as e:
        console.print(f"[red]Error adding vinyl record: {e}[/red]")
    finally:
        db.close()


# --------------------------
# Discogs Integration (Read-Only)
# --------------------------

@cli.command()
@click.argument('query')
@click.option('--type', 'search_type', type=click.Choice(['release', 'artist', 'label']), default='release', help='Search type')
def discogs(query: str, search_type: str):
    """Search Discogs database (read-only). Requires requests."""
    if not HAS_REQUESTS:
        console.print("[red]Requests not installed. Cannot use Discogs integration.[/red]")
        return
    console.print(f"[blue]Searching Discogs for '{query}' (type: {search_type})...[/blue]")
    try:
        params = {
            'q': query,
            'type': search_type,
            'per_page': 5
        }
        response = requests.get("https://api.discogs.com/database/search", params=params, timeout=10)
        if response.status_code != 200:
            console.print(f"[red]Discogs API error: {response.status_code}[/red]")
            return
        data = response.json()
        results = data.get('results', [])
        if not results:
            console.print("[yellow]No results found.[/yellow]")
            return

        console.print(f"[green]Found {len(results)} results:[/green]")
        table = Table(title=f"Discogs Search Results for '{query}'", show_header=True, header_style="bold magenta")
        table.add_column("ID", style="dim")
        table.add_column("Title", min_width=30)
        table.add_column("Artist", min_width=30)
        table.add_column("Year", width=6)
        table.add_column("Format", width=15)
        table.add_column("Label", min_width=20)

        for result in results:
            # Extract artist from the result (might be a string or list)
            artist_val = result.get('artist', '')
            if isinstance(artist_val, list):
                artist_val = ", ".join([a.get('name', '') for a in artist_val if isinstance(a, dict)])
            table.add_row(
                str(result.get('id', '')),
                str(result.get('title', ''))[:30] + ("..." if len(str(result.get('title', ''))) > 30 else ""),
                str(artist_val)[:30] + ("..." if len(str(artist_val)) > 30 else ""),
                str(result.get('year', '')),
                str(result.get('format', '')),
                str(result.get('label', ''))[:20] + ("..." if len(str(result.get('label', ''))) > 20 else "")
            )
        console.print(table)
        console.print("[dim]Use 'vinyl barcode' or 'vinyl add' with --discogs-id to import a result.[/dim]")
    except Exception as e:
        console.print(f"[red]Error searching Discogs: {e}[/red]")


# --------------------------
# Statistics
# --------------------------

@cli.command()
def stats():
    """Show vinyl collection statistics."""
    db = get_db()
    records = db.get_all_vinyl_records()
    db.close()

    if not records:
        console.print("[yellow]Collection is empty.[/yellow]")
        return

    total_records = len(records)
    total_plays = sum(r.play_count for r in records)
    avg_plays = total_plays / total_records if total_records > 0 else 0
    most_played = db.get_most_played(5)
    recently_played = db.get_recently_played(5)
    formats = {}
    conditions = {}
    decades = {}
    for r in records:
        fmt = r.format or "Unknown"
        formats[fmt] = formats.get(fmt, 0) + 1
        cond = r.condition or "Unknown"
        conditions[cond] = conditions.get(cond, 0) + 1
        if r.year:
            decade = (r.year // 10) * 10
            decades[decade] = decades.get(decade, 0) + 1

    console.print(Panel.fit(
        f"[bold]Vinyl Collection Statistics[/bold]\n"
        f"Total Records: {total_records}\n"
        f"Total Plays: {total_plays}\n"
        f"Average Plays per Record: {avg_plays:.1f}\n"
        f"Unique Formats: {len(formats)}\n"
        f"Unique Conditions: {len(conditions)}\n"
        f"Decades Covered: {', '.join(str(d) for d in sorted(decades.keys())) if decades else 'None'}\n"
        f"Most Played: {most_played[0].title if most_played else 'None'} ({most_played[0].play_count} plays) if most_played else 'None'\n"
        f"Recently Played: {len(recently_played)} record(s) in last plays",
        title="📊 Stats",
        border_style="green"
    ))


# --------------------------
# Now Spinning Display
# --------------------------

@cli.command()
def nowspinning():
    """Show the 'Now Spinning' display (placeholder)."""
    db = get_db()
    # Get the most recently played record
    recent = db.get_recently_played(1)
    db.close()
    if recent:
        record = recent[0]
        console.print(Panel.fit(
            f"[bold]Now Spinning[/bold]\n"
            f"[bold]{record.title}[/bold]\n"
            f"by [bold]{record.artist}[/bold]\n"
            f"({record.year}) - {record.format}\n"
            f"Play Count: {record.play_count}\n"
            f"Condition: {record.condition or '-'}",
            title="🎵 Now Spinning",
            border_style="red"
        ))
    else:
        console.print("[yellow]No play history. Play a record first with 'vinyl play <identifier>'[/yellow]")


def main():
    """Entry point for the VINYL CLI."""
    cli()


if __name__ == '__main__':
    main()


# Expose the CLI group for import by whispernet
vinyl_cli = cli