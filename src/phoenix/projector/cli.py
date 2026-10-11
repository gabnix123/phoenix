"""
PROJECTOR - Media library manager for movies and TV shows CLI
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

# Import our modules
from .models import MediaItem, ProjectorDB

# Setup logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

console = Console()


def get_db_path() -> Path:
    """Get the path to the SQLite database for PROJECTOR."""
    try:
        from appdirs import user_data_dir
        data_dir = Path(user_data_dir("phoenix", "projector"))
    except ImportError:
        # Fallback to ~/.phoenix/projector
        data_dir = Path.home() / ".phoenix" / "projector"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "library.db"


def get_db() -> ProjectorDB:
    """Get a database instance (singleton per command invocation)."""
    return ProjectorDB(str(get_db_path()))


@click.group()
def cli():
    """PROJECTOR: A terminal-based media library manager for movies and TV shows.

    Features:
    - Track movies, TV shows, episodes
    - Mark as watched, track watch count
    - Personal ratings and notes
    - Watchlist management
    - Mood-based recommendations
    - Library statistics
    - No telemetry. No tracking. No ads.
    """
    pass


# --------------------------
# Library Commands
# --------------------------

@cli.command()
@click.argument('media_dir', type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option('--recursive/--no-recursive', default=True, help='Scan subdirectories')
def add(media_dir: str, recursive: bool):
    """Add media files to the library from a directory."""
    db = get_db()
    media_path = Path(media_dir)
    pattern = "**/*" if recursive else "*"
    # Supported video extensions (common)
    extensions = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mpg', '.mpeg'}
    files = [p for p in media_path.glob(pattern) if p.suffix.lower() in extensions and p.is_file()]

    if not files:
        console.print(f"[yellow]No video files found in {media_dir}[/yellow]")
        db.close()
        return

    console.print(f"Found {len(files)} video files. Scanning...")
    added = 0
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        task = progress.add_task("Scanning files...", total=len(files))
        for f in files:
            item = MediaItem.from_file(str(f))
            if item:
                db.add_media_item(item)
                added += 1
            progress.update(task, advance=1)
    console.print(f"[green]Added {added} new media items to the library.[/green]")
    db.close()


@cli.command()
def list():
    """List all media items in the library."""
    db = get_db()
    items = db.get_all_media_items()
    db.close()

    if not items:
        console.print("[yellow]Library is empty. Use 'projector add <directory>' to add media.[/yellow]")
        return

    table = Table(title="Media Library", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="dim", width=6)
    table.add_column("Title", min_width=20)
    table.add_column("Type", width=8)
    table.add_column("Year", width=6)
    table.add_column("Genres", min_width=15)
    table.add_column("Watched", width=8)
    table.add_column("Rating", width=8)

    for item in items:
        year = item.release_date[:4] if item.release_date else ""
        genres = ", ".join(item.genres[:2]) + ("..." if len(item.genres) > 2 else "")
        watched = "✓" if item.watched else "✗"
        rating = f"{item.personal_rating:.1f}" if item.personal_rating is not None else "-"
        table.add_row(
            str(item.id) if hasattr(item, 'id') else '?',
            item.title[:30] + ("..." if len(item.title) > 30 else ""),
            item.media_type,
            year,
            genres,
            watched,
            rating
        )
    console.print(table)


@cli.command()
@click.argument('query')
def search(query: str):
    """Search media items by title or original title."""
    db = get_db()
    # Simple search across title and original_title
    all_items = db.get_all_media_items()
    matches = []
    query_lower = query.lower()
    for item in all_items:
        if (query_lower in item.title.lower() or
            query_lower in item.original_title.lower()):
            matches.append(item)
    db.close()

    if not matches:
        console.print(f"[yellow]No media items matching '{query}' found.[/yellow]")
        return

    table = Table(title=f"Search Results for '{query}'", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="dim", width=6)
    table.add_column("Title", min_width=20)
    table.add_column("Type", width=8)
    table.add_column("Year", width=6)
    table.add_column("Genres", min_width=15)

    for item in matches[:50]:  # Limit to 50 results
        year = item.release_date[:4] if item.release_date else ""
        genres = ", ".join(item.genres[:2]) + ("..." if len(item.genres) > 2 else "")
        table.add_row(
            str(item.id) if hasattr(item, 'id') else '?',
            item.title[:30] + ("..." if len(item.title) > 30 else ""),
            item.media_type,
            year,
            genres
        )
    if len(matches) > 50:
        console.print(f"[dim]Showing first 50 of {len(matches)} results[/dim]")
    console.print(table)


# --------------------------
# Watchlist Commands
# --------------------------

@cli.command()
@click.argument('identifier')
def watchlist_add(identifier: str):
    """Add a media item to the watchlist by ID or search term."""
    db = get_db()
    item: Optional[MediaItem] = None
    try:
        item_id = int(identifier)
        item = db.get_media_item_by_id(item_id)
    except ValueError:
        # Search
        all_items = db.get_all_media_items()
        matches = [i for i in all_items if identifier.lower() in i.title.lower() or identifier.lower() in i.original_title.lower()]
        if matches:
            item = matches[0]
        else:
            console.print(f"[red]No media item matching '{identifier}' found.[/red]")
            db.close()
            return

    if not item:
        console.print("[red]Could not find media item.[/red]")
        db.close()
        return

    db.add_to_watchlist(item.id)
    console.print(f"[green]Added '{item.title}' to watchlist[/green]")
    db.close()


@cli.command()
@click.argument('identifier')
def watchlist_remove(identifier: str):
    """Remove a media item from the watchlist by ID or search term."""
    db = get_db()
    item: Optional[MediaItem] = None
    try:
        item_id = int(identifier)
        item = db.get_media_item_by_id(item_id)
    except ValueError:
        # Search
        all_items = db.get_all_media_items()
        matches = [i for i in all_items if identifier.lower() in i.title.lower() or identifier.lower() in i.original_title.lower()]
        if matches:
            item = matches[0]
        else:
            console.print(f"[red]No media item matching '{identifier}' found.[/red]")
            db.close()
            return

    if not item:
        console.print("[red]Could not find media item.[/red]")
        db.close()
        return

    db.remove_from_watchlist(item.id)
    console.print(f"[yellow]Removed '{item.title}' from watchlist[/yellow]")
    db.close()


@cli.command()
def watchlist_show():
    """Show all media items in the watchlist."""
    db = get_db()
    items = db.get_watchlist()
    db.close()

    if not items:
        console.print("[yellow]Watchlist is empty.[/yellow]")
        return

    table = Table(title="Watchlist", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="dim", width=6)
    table.add_column("Title", min_width=20)
    table.add_column("Type", width=8)
    table.add_column("Year", width=6)
    table.add_column("Genres", min_width=15)

    for item in items:
        year = item.release_date[:4] if item.release_date else ""
        genres = ", ".join(item.genres[:2]) + ("..." if len(item.genres) > 2 else "")
        table.add_row(
            str(item.id) if hasattr(item, 'id') else '?',
            item.title[:30] + ("..." if len(item.title) > 30 else ""),
            item.media_type,
            year,
            genres
        )
    console.print(table)


# --------------------------
# Watched Commands
# --------------------------

@cli.command()
@click.argument('identifier')
@click.option('--rating', '-r', type=float, help='Personal rating (0-10)')
def mark_watched(identifier: str, rating: Optional[float]):
    """Mark a media item as watched."""
    db = get_db()
    item: Optional[MediaItem] = None
    try:
        item_id = int(identifier)
        item = db.get_media_item_by_id(item_id)
    except ValueError:
        # Search
        all_items = db.get_all_media_items()
        matches = [i for i in all_items if identifier.lower() in i.title.lower() or identifier.lower() in i.original_title.lower()]
        if matches:
            item = matches[0]
        else:
            console.print(f"[red]No media item matching '{identifier}' found.[/red]")
            db.close()
            return

    if not item:
        console.print("[red]Could not find media item.[/red]")
        db.close()
        return

    # Validate rating
    if rating is not None and (rating < 0 or rating > 10):
        console.print("[red]Rating must be between 0 and 10.[/red]")
        db.close()
        return

    db.mark_watched(item.id, rating)
    console.print(f"[green]Marked '{item.title}' as watched[/green]")
    if rating is not None:
        console.print(f"[dim]Personal rating set to {rating}[/dim]")
    db.close()


@cli.command()
@click.option('--limit', '-l', default=20, help='Number of items to show')
def history(limit: int):
    """Show watched history."""
    db = get_db()
    items = db.get_watched_history(limit)
    db.close()

    if not items:
        console.print("[yellow]No watched history.[/yellow]")
        return

    table = Table(title=f"Watched History (Last {limit})", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="dim", width=6)
    table.add_column("Title", min_width=20)
    table.add_column("Type", width=8)
    table.add_column("Year", width=6)
    table.add_column("Watch Count", width=12)
    table.add_column("Personal Rating", width=15)

    for item in items:
        year = item.release_date[:4] if item.release_date else ""
        table.add_row(
            str(item.id) if hasattr(item, 'id') else '?',
            item.title[:30] + ("..." if len(item.title) > 30 else ""),
            item.media_type,
            year,
            str(item.watch_count),
            f"{item.personal_rating:.1f}" if item.personal_rating is not None else "-"
        )
    console.print(table)


# --------------------------
# Recommendations
# --------------------------

@cli.command()
@click.option('--mood', '-m', multiple=True, help='Mood tags to match (e.g., --mood happy --mood exciting)')
@click.option('--limit', '-l', default=10, help='Maximum number of recommendations')
def recommend(mood: tuple, limit: int):
    """Get media recommendations based on mood tags."""
    db = get_db()
    all_items = db.get_all_media_items()
    db.close()

    if not all_items:
        console.print("[yellow]Library is empty. Add media first.[/yellow]")
        return

    mood_tags = list(mood) if mood else ["happy", "exciting", "thought-provoking"]
    mood_tags = [m.lower() for m in mood_tags]

    recommendations = db.get_recommendations(mood_tags, limit)

    if not recommendations:
        console.print(f"[yellow]No media items matching mood {mood_tags} found.[/yellow]")
        # Fallback: return some highly rated unwatched items
        unwatched = [i for i in all_items if not i.watched]
        unwatched.sort(key=lambda x: (-x.vote_average, x.watch_count))
        recommendations = unwatched[:limit]
        if not recommendations:
            console.print("[yellow]No unwatched items to recommend.[/yellow]")
            return

    table = Table(title=f"Recommendations for mood: {', '.join(mood_tags)}", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="dim", width=6)
    table.add_column("Title", min_width=20)
    table.add_column("Type", width=8)
    table.add_column("Year", width=6)
    table.add_column("Genres", min_width=15)
    table.add_column("Rating", width=8)
    table.add_column("Watch Count", width=12)

    for item in recommendations:
        year = item.release_date[:4] if item.release_date else ""
        genres = ", ".join(item.genres[:2]) + ("..." if len(item.genres) > 2 else "")
        table.add_row(
            str(item.id) if hasattr(item, 'id') else '?',
            item.title[:30] + ("..." if len(item.title) > 30 else ""),
            item.media_type,
            year,
            genres,
            f"{item.vote_average:.1f}",
            str(item.watch_count)
        )
    console.print(table)


# --------------------------
# Library Stats
# --------------------------

@cli.command()
def stats():
    """Show library statistics."""
    db = get_db()
    items = db.get_all_media_items()
    db.close()

    if not items:
        console.print("[yellow]Library is empty.[/yellow]")
        return

    total_items = len(items)
    movies = len([i for i in items if i.media_type == 'movie'])
    tv_shows = len([i for i in items if i.media_type == 'tv'])
    episodes = len([i for i in items if i.media_type == 'episode'])
    watched = len([i for i in items if i.watched])
    unwatched = total_items - watched
    ratings = [i.personal_rating for i in items if i.personal_rating is not None]
    avg_rating = sum(ratings) / len(ratings) if ratings else 0.0
    genres_set = set()
    for item in items:
        genres_set.update(item.genres)
    decades_set = set()
    for item in items:
        if item.release_date:
            try:
                year = int(item.release_date[:4])
                decade = (year // 10) * 10
                decades_set.add(decade)
            except ValueError:
                pass

    console.print(Panel.fit(
        f"[bold]Library Statistics[/bold]\n"
        f"Total Items: {total_items}\n"
        f"Movies: {movies}\n"
        f"TV Shows: {tv_shows}\n"
        f"Episodes: {episodes}\n"
        f"Watched: {watched}\n"
        f"Unwatched: {unwatched}\n"
        f"Average Personal Rating: {avg_rating:.1f}\n"
        f"Unique Genres: {len(genres_set)}\n"
        f"Decades Covered: {', '.join(str(d) for d in sorted(decades_set)) if decades_set else 'None'}",
        title="📊 Stats",
        border_style="green"
    ))


# --------------------------
# Letterboxd Integration (Read-Only)
# --------------------------

@cli.command()
@click.option('--username', '-u', help='Letterboxd username to fetch public data')
@click.option('--action', type=click.Choice(['import-watchlist', 'import-ratings']), default='import-watchlist', help='What to import')
def letterboxd(username: Optional[str], action: str):
    """Simulate Letterboxd integration (read-only). In a real implementation, this would fetch public data from Letterboxd API."""
    if not username:
        console.print("[red]Please provide a Letterboxd username with --username[/red]")
        return

    console.print(f"[yellow]Letterboxd integration is a placeholder.[/yellow]")
    console.print(f"In a real implementation, this would fetch your public '{action}' from Letterboxd user '{username}'.")
    console.print("[dim]No actual data is fetched or stored.[/dim]")
    # In a real version, we would use requests to call Letterboxd's public API (if available) or scrape (not recommended)
    # For now, we just inform the user.


# --------------------------
# Now Playing (Placeholder)
# --------------------------

@cli.command()
def nowplaying():
    """Show the currently playing media (placeholder)."""
    console.print("[dim]Now playing feature not implemented in this version.[/dim]")
    console.print("[dim]Use 'projector mark-watched' to track what you've watched.[/dim]")


def main():
    """Entry point for the PROJECTOR CLI."""
    cli()


if __name__ == '__main__':
    main()


# Expose the CLI group for import by whispernet
projector_cli = cli