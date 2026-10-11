"""
SONGBIRD - Music player and library manager CLI
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

# Import our modules
from .models import Song, SongbirdDB
from .player import Player

# Setup logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

console = Console()

def get_db_path() -> Path:
    """Get the path to the SQLite database for SONGBIRD."""
    try:
        from appdirs import user_data_dir
        data_dir = Path(user_data_dir("phoenix", "songbird"))
    except ImportError:
        # Fallback to ~/.phoenix/songbird
        data_dir = Path.home() / ".phoenix" / "songbird"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "library.db"

def get_db() -> SongbirdDB:
    """Get a database instance (singleton per command invocation)."""
    # In a real app, we might use a connection pool or reuse.
    # For simplicity, we create a new DB per command group.
    return SongbirdDB(str(get_db_path()))

@click.group()
def cli():
    """SONGBIRD: A terminal-based music player and library manager.

    Features:
    - Lossless audio playback
    - Vinyl collection cataloging
    - Spotify/Last.fm integration (read-only, privacy-preserving)
    - Intelligent playlist generation based on mood, time of day, and listening history
    - Support for FLAC, ALAC, WAV, MP3, OGG
    - No telemetry. No tracking. No ads.
    """
    pass


# --------------------------
# Introductory Commands
# --------------------------

@cli.command()
def hello():
    """Welcome to SONGBIRD."""
    console.print("[bold cyan]Welcome to SONGBIRD![/bold cyan]")
    console.print("A terminal-based music player and library manager.")
    console.print("\nUse 'songbird --help' to see available commands.")

# --------------------------
# Library Commands
# --------------------------

@cli.command()
@click.argument('music_dir', type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option('--recursive/--no-recursive', default=True, help='Scan subdirectories')
def add(music_dir: str, recursive: bool):
    """Add music files to the library from a directory."""
    db = get_db()
    music_path = Path(music_dir)
    pattern = "**/*" if recursive else "*"
    # Supported extensions
    extensions = {'.flac', '.wav', '.mp3', '.ogg', '.m4a', '.aac', '.alac'}
    files = [p for p in music_path.glob(pattern) if p.suffix.lower() in extensions and p.is_file()]

    if not files:
        console.print(f"[yellow]No audio files found in {music_dir}[/yellow]")
        return

    console.print(f"Found {len(files)} audio files. Scanning...")
    added = 0
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        task = progress.add_task("Scanning files...", total=len(files))
        for f in files:
            song = Song.from_file(str(f))
            if song:
                db.add_song(song)
                added += 1
            progress.update(task, advance=1)
    console.print(f"[green]Added {added} new songs to the library.[/green]")
    db.close()

@cli.command()
def list():
    """List all songs in the library."""
    db = get_db()
    songs = db.get_all_songs()
    db.close()

    if not songs:
        console.print("[yellow]Library is empty. Use 'songbird add <directory>' to add music.[/yellow]")
        return

    table = Table(title="Music Library", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="dim", width=6)
    table.add_column("Title", min_width=20)
    table.add_column("Artist", min_width=20)
    table.add_column("Album", min_width=20)
    table.add_column("Duration", width=8)
    table.add_column("Track", width=6)

    for song in songs:
        table.add_row(
            str(song.id) if hasattr(song, 'id') else '?',
            song.title[:30] + ("..." if len(song.title) > 30 else ""),
            song.artist[:30] + ("..." if len(song.artist) > 30 else ""),
            song.album[:30] + ("..." if len(song.album) > 30 else ""),
            f"{int(song.duration//60):02d}:{int(song.duration%60):02d}",
            str(song.track_number) if song.track_number else ""
        )
    console.print(table)

@cli.command()
@click.argument('query')
def search(query: str):
    """Search songs by title, artist, or album."""
    db = get_db()
    # Simple search across multiple fields
    all_songs = db.get_all_songs()
    matches = []
    query_lower = query.lower()
    for song in all_songs:
        if (query_lower in song.title.lower() or
            query_lower in song.artist.lower() or
            query_lower in song.album.lower()):
            matches.append(song)
    db.close()

    if not matches:
        console.print(f"[yellow]No songs matching '{query}' found.[/yellow]")
        return

    table = Table(title=f"Search Results for '{query}'", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="dim", width=6)
    table.add_column("Title", min_width=20)
    table.add_column("Artist", min_width=20)
    table.add_column("Album", min_width=20)
    table.add_column("Duration", width=8)

    for song in matches[:50]:  # Limit to 50 results
        table.add_row(
            str(song.id) if hasattr(song, 'id') else '?',
            song.title[:30] + ("..." if len(song.title) > 30 else ""),
            song.artist[:30] + ("..." if len(song.artist) > 30 else ""),
            song.album[:30] + ("..." if len(song.album) > 30 else ""),
            f"{int(song.duration//60):02d}:{int(song.duration%60):02d}"
        )
    if len(matches) > 50:
        console.print(f"[dim]Showing first 50 of {len(matches)} results[/dim]")
    console.print(table)

# --------------------------
# Playback Commands
# --------------------------

@cli.command()
@click.argument('identifier', required=False)
def play(identifier: Optional[str]):
    """Play a song by ID, or start playback from library.

    If no identifier given, plays the first song in library.
    """
    db = get_db()
    player = Player()

    if not player.is_available():
        console.print("[red]Audio playback not available. Install pydub and ffmpeg.[/red]")
        db.close()
        return

    song: Optional[Song] = None
    if identifier is None:
        # Get first song
        songs = db.get_all_songs()
        if not songs:
            console.print("[yellow]Library is empty. Add music first.[/yellow]")
            db.close()
            return
        song = songs[0]
    else:
        # Try to parse as ID
        try:
            song_id = int(identifier)
            song = db.get_song_by_id(song_id)
        except ValueError:
            # Treat as search term
            all_songs = db.get_all_songs()
            matches = [s for s in all_songs if identifier.lower() in s.title.lower() or identifier.lower() in s.artist.lower()]
            if matches:
                song = matches[0]
            else:
                console.print(f"[red]No song matching '{identifier}' found.[/red]")
                db.close()
                return

    if not song:
        console.print("[red]Could not find song.[/red]")
        db.close()
        return

    if not player.load_song(song.path):
        db.close()
        return

    console.print(f"[green]Playing:[/green] {song.title} by {song.artist}")
    player.display_now_playing(song)
    player.play()
    # Wait for playback to finish or user interrupt
    try:
        while player.is_playing():
            time.sleep(0.5)
    except KeyboardInterrupt:
        console.print("\n[yellow]Playback stopped by user.[/yellow]")
        player.stop()
    finally:
        db.close()

@cli.command()
def stop():
    """Stop playback."""
    player = Player()
    player.stop()
    console.print("[yellow]Playback stopped.[/yellow]")

# --------------------------
# Playlist Commands
# --------------------------

@cli.command()
@click.argument('name')
def playlist_create(name: str):
    """Create a new playlist."""
    db = get_db()
    pid = db.add_playlist(name)
    if pid:
        console.print(f"[green]Created playlist '{name}' with ID {pid}[/green]")
    else:
        console.print(f"[yellow]Playlist '{name}' already exists.[/yellow]")
        # Get existing ID
        conn = db._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM playlists WHERE name = ?", (name,))
        row = cursor.fetchone()
        pid = row['id'] if row else None
    db.close()

@cli.command()
@click.argument('playlist_name')
@click.argument('song_identifier')
def playlist_add(playlist_name: str, song_identifier: str):
    """Add a song to a playlist."""
    db = get_db()
    # Get playlist ID
    conn = db._get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM playlists WHERE name = ?", (playlist_name,))
    row = cursor.fetchone()
    if not row:
        console.print(f"[red]Playlist '{playlist_name}' not found.[/red]")
        db.close()
        return
    playlist_id = row['id']

    # Get song ID
    song: Optional[Song] = None
    try:
        song_id = int(song_identifier)
        song = db.get_song_by_id(song_id)
    except ValueError:
        # Search
        all_songs = db.get_all_songs()
        matches = [s for s in all_songs if song_identifier.lower() in s.title.lower() or song_identifier.lower() in s.artist.lower()]
        if matches:
            song = matches[0]
        else:
            console.print(f"[red]No song matching '{song_identifier}' found.[/red]")
            db.close()
            return

    if not song:
        console.print("[red]Could not find song.[/red]")
        db.close()
        return

    db.add_song_to_playlist(playlist_id, song.id)
    console.print(f"[green]Added '{song.title}' to playlist '{playlist_name}'[/green]")
    db.close()

@cli.command()
@click.argument('playlist_name')
def playlist_show(playlist_name: str):
    """Show songs in a playlist."""
    db = get_db()
    conn = db._get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM playlists WHERE name = ?", (playlist_name,))
    row = cursor.fetchone()
    if not row:
        console.print(f"[red]Playlist '{playlist_name}' not found.[/red]")
        db.close()
        return
    playlist_id = row['id']
    songs = db.get_playlist_songs(playlist_id)
    db.close()

    if not songs:
        console.print(f"[yellow]Playlist '{playlist_name}' is empty.[/yellow]")
        return

    table = Table(title=f"Playlist: {playlist_name}", show_header=True, header_style="bold magenta")
    table.add_column("Pos", width=6)
    table.add_column("Title", min_width=20)
    table.add_column("Artist", min_width=20)
    table.add_column("Album", min_width=20)
    table.add_column("Duration", width=8)

    for idx, song in enumerate(songs, start=1):
        table.add_row(
            str(idx),
            song.title[:30] + ("..." if len(song.title) > 30 else ""),
            song.artist[:30] + ("..." if len(song.artist) > 30 else ""),
            song.album[:30] + ("..." if len(song.album) > 30 else ""),
            f"{int(song.duration//60):02d}:{int(song.duration%60):02d}"
        )
    console.print(table)

# --------------------------
# Mood-based Playlist Generation
# --------------------------

@cli.command()
@click.option('--mood', '-m', multiple=True, help='Mood tags to match (e.g., --mood happy --mood energetic)')
@click.option('--limit', '-l', default=20, help='Maximum number of songs')
def mood(mood: tuple, limit: int):
    """Generate a playlist based on mood tags.

    If no mood specified, uses a default uplifting mix.
    """
    db = get_db()
    all_songs = db.get_all_songs()
    db.close()

    if not all_songs:
        console.print("[yellow]Library is empty. Add music first.[/yellow]")
        return

    # Default mood if none specified
    mood_tags = list(mood) if mood else ["happy", "upbeat", "energetic"]
    # Normalize to lower
    mood_tags = [m.lower() for m in mood_tags]

    matched = []
    for song in all_songs:
        # Check if any of the song's mood tags match requested moods
        song_moods = [tag.lower() for tag in song.mood_tags]
        if any(m in song_moods for m in mood_tags):
            matched.append(song)

    if not matched:
        console.print(f"[yellow]No songs matching mood {mood_tags} found.[/yellow]")
        # Fallback: return some random songs
        import random
        matched = random.sample(all_songs, min(limit, len(all_songs)))
    else:
        # Limit results
        if len(matched) > limit:
            matched = matched[:limit]

    if not matched:
        console.print("[yellow]No songs to include.[/yellow]")
        return

    # Create a temporary playlist
    db = get_db()
    playlist_name = f"Mood: {', '.join(mood_tags)}"
    pid = db.add_playlist(playlist_name)
    for song in matched:
        db.add_song_to_playlist(pid, song.id)
    db.close()

    console.print(f"[green]Generated mood playlist '{playlist_name}' with {len(matched)} songs.[/green]")
    console.print(f"Use 'songbird playlist_show \"{playlist_name}\"' to view it.")

# --------------------------
# Vinyl Integration
# --------------------------

@cli.command()
@click.argument('song_identifier')
@click.argument('vinyl_id')
@click.option('--notes', '-n', default='', help='Notes about this vinyl link')
def vinyl_link(song_identifier: str, vinyl_id: str, notes: str):
    """Link a song to a vinyl record in your collection."""
    db = get_db()
    # Get song
    song: Optional[Song] = None
    try:
        song_id = int(song_identifier)
        song = db.get_song_by_id(song_id)
    except ValueError:
        all_songs = db.get_all_songs()
        matches = [s for s in all_songs if song_identifier.lower() in s.title.lower() or song_identifier.lower() in s.artist.lower()]
        if matches:
            song = matches[0]
        else:
            console.print(f"[red]No song matching '{song_identifier}' found.[/red]")
            db.close()
            return

    if not song:
        console.print("[red]Could not find song.[/red]")
        db.close()
        return

    db.link_vinyl(song.id, vinyl_id, notes)
    console.print(f"[green]Linked '{song.title}' to vinyl ID '{vinyl_id}'[/green]")
    if notes:
        console.print(f"[dim]Notes: {notes}[/dim]")
    db.close()

@cli.command()
@click.argument('song_identifier')
def vinyl_show(song_identifier: str):
    """Show vinyl links for a song."""
    db = get_db()
    song: Optional[Song] = None
    try:
        song_id = int(song_identifier)
        song = db.get_song_by_id(song_id)
    except ValueError:
        all_songs = db.get_all_songs()
        matches = [s for s in all_songs if song_identifier.lower() in s.title.lower() or song_identifier.lower() in s.artist.lower()]
        if matches:
            song = matches[0]
        else:
            console.print(f"[red]No song matching '{song_identifier}' found.[/red]")
            db.close()
            return

    if not song:
        console.print("[red]Could not find song.[/red]")
        db.close()
        return

    links = db.get_vinyl_links(song.id)
    db.close()

    if not links:
        console.print(f"[yellow]No vinyl links found for '{song.title}'.[/yellow]")
        return

    table = Table(title=f"Vinyl Links for: {song.title}", show_header=True, header_style="bold magenta")
    table.add_column("Vinyl ID")
    table.add_column("Notes")
    for link in links:
        table.add_row(link["vinyl_id"], link["notes"] or "")
    console.print(table)

# --------------------------
# Now Playing Display
# --------------------------

@cli.command()
def nowplaying():
    """Show the currently playing song (if any)."""
    player = Player()
    # We don't have access to the current song from player alone.
    # For simplicity, we'll just show player status.
    if player.is_available():
        if player.is_playing():
            console.print("[green]Playback is active[/green]")
            # We could try to get the last played song from a global state, but skip.
            console.print("[dim]Use 'songbird play' to start playback.[/dim]")
        else:
            console.print("[dim]No playback active.[/dim]")
    else:
        console.print("[red]Audio playback not available.[/red]")

# --------------------------
# Library Stats
# --------------------------

@cli.command()
def stats():
    """Show library statistics."""
    db = get_db()
    songs = db.get_all_songs()
    db.close()

    if not songs:
        console.print("[yellow]Library is empty.[/yellow]")
        return

    total_duration = sum(s.duration for s in songs)
    total_size = sum(s.filesize for s in songs)
    artists = set(s.artist for s in songs if s.artist)
    albums = set(s.album for s in songs if s.album)
    genres = set(s.genre for s in songs if s.genre)

    console.print(Panel.fit(
        f"[bold]Library Statistics[/bold]\n"
        f"Songs: {len(songs)}\n"
        f"Artists: {len(artists)}\n"
        f"Albums: {len(albums)}\n"
        f"Genres: {len(genres)}\n"
        f"Total Duration: {int(total_duration//3600):02d}:{int((total_duration%3600)//60):02d}:{int(total_duration%60):02d}\n"
        f"Total Size: {total_size / (1024**3):.2f} GB",
        title="📊 Stats",
        border_style="green"
    ))

def main():
    """Entry point for the SONGBIRD CLI."""
    cli()

if __name__ == '__main__':
    main()

# Expose the CLI group for import by whispernet
songbird_cli = cli