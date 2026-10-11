"""
Audio playback functionality for SONGBIRD.
"""
import threading
import time
import sys
from pathlib import Path
from typing import Optional
import logging

from rich.console import Console
from rich.live import Live
from rich.text import Text
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.align import Align
from rich import box

try:
    from pydub import AudioSegment
    from pydub.playback import _play_with_simpleaudio as play_audio
    HAS_PYDUB = True
except ImportError:
    HAS_PYDUB = False
    logging.warning("pydub not installed. Audio playback will not be available.")

try:
    from PIL import Image
    import io
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

logger = logging.getLogger(__name__)

class Player:
    """Handles audio playback and now-playing display."""
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self._current_song: Optional[Path] = None
        self._is_playing = False
        self._is_paused = False
        self._stop_event = threading.Event()
        self._play_thread: Optional[threading.Thread] = None
        self._start_time: float = 0.0
        self._paused_at: float = 0.0

    def is_available(self) -> bool:
        """Check if playback dependencies are available."""
        return HAS_PYDUB

    def load_song(self, song_path: str) -> bool:
        """Load a song for playback.
        Returns True if successful.
        """
        if not self.is_available():
            self.console.print("[red]Audio playback not available. Install pydub and ffmpeg.[/red]")
            return False
        path = Path(song_path)
        if not path.exists():
            self.console.print(f"[red]File not found: {song_path}[/red]")
            return False
        try:
            self._audio_segment = AudioSegment.from_file(str(path))
            self._current_song = path
            return True
        except Exception as e:
            self.console.print(f"[red]Error loading audio file: {e}[/red]")
            logger.error(f"Failed to load {song_path}: {e}")
            return False

    def _playback_thread(self):
        """Internal thread for playing audio and updating display."""
        try:
            # Play audio using pydub's playback (blocking)
            play_audio(self._audio_segment)
        except Exception as e:
            logger.error(f"Playback error: {e}")
        finally:
            self._is_playing = False
            self._is_paused = False
            self._stop_event.set()

    def play(self):
        """Start playback of the loaded song."""
        if not self._current_song or not self.is_available():
            return False
        if self._is_playing:
            return True  # already playing

        self._stop_event.clear()
        self._is_playing = True
        self._is_paused = False
        self._start_time = time.time()
        self._play_thread = threading.Thread(target=self._playback_thread, daemon=True)
        self._play_thread.start()
        return True

    def pause(self):
        """Pause playback."""
        if self._is_playing and not self._is_paused:
            # Note: pydub playback cannot be paused easily; we would need to implement
            # our own playback loop with pyaudio or simpleaudio. For simplicity,
            # we'll note that pause is not implemented in this version.
            self.console.print("[yellow]Pause not fully implemented in this version.[/yellow]")
            # We'll set a flag but actual pause requires stopping and resuming from position.
            # For now, we'll just indicate.
            self._is_paused = True
            return True
        return False

    def resume(self):
        """Resume playback."""
        if self._is_paused:
            self.console.print("[yellow]Resume not fully implemented in this version.[/yellow]")
            self._is_paused = False
            return True
        return False

    def stop(self):
        """Stop playback."""
        self._stop_event.set()
        self._is_playing = False
        self._is_paused = False
        if self._play_thread and self._play_thread.is_alive():
            # Wait a bit for thread to finish
            self._play_thread.join(timeout=1.0)
        self._play_thread = None

    def is_playing(self) -> bool:
        """Return True if playback is active."""
        return self._is_playing and not self._is_paused

    def get_position(self) -> float:
        """Get current playback position in seconds."""
        if not self._is_playing:
            return 0.0
        if self._is_paused:
            return self._paused_at
        elapsed = time.time() - self._start_time
        # Clamp to song duration
        if hasattr(self, '_audio_segment'):
            duration_sec = len(self._audio_segment) / 1000.0
            return min(elapsed, duration_sec)
        return elapsed

    def get_duration(self) -> float:
        """Get song duration in seconds."""
        if hasattr(self, '_audio_segment'):
            return len(self._audio_segment) / 1000.0
        return 0.0

    def display_now_playing(self, song: Optional['Song'] = None):
        """Display now-playing information with album art ASCII."""
        if not self._current_song:
            self.console.print("[dim]No song loaded[/dim]")
            return

        # Create layout
        if song is None:
            # Try to get song object from library? We'll just show file info.
            song_info = f"[bold]{self._current_song.name}[/bold]"
            artist = "Unknown Artist"
            album = "Unknown Album"
            duration = self.get_duration()
            position = self.get_position()
            album_art_bytes = None
        else:
            song_info = f"[bold]{song.title}[/bold]" if song.title else f"[bold]{Path(song.path).name}[/bold]"
            artist = song.artist or "Unknown Artist"
            album = song.album or "Unknown Album"
            duration = song.duration
            position = self.get_position()
            album_art_bytes = song.album_art

        # Convert album art to ASCII if available
        ascii_art = ""
        if album_art_bytes and HAS_PIL:
            try:
                image = Image.open(io.BytesIO(album_art_bytes))
                # Resize to reasonable width for terminal
                max_width = 50
                if image.width > max_width:
                    ratio = max_width / float(image.width)
                    new_height = int(float(image.height) * ratio)
                    image = image.resize((max_width, new_height))
                # Convert to ASCII using a simple method
                # We'll use ascii_magic if available, else fallback
                try:
                    import ascii_magic
                    ascii_art = ascii_magic.from_pillow(image)
                except ImportError:
                    # Fallback: grayscale to ASCII
                    ascii_art = self._image_to_ascii(image)
            except Exception as e:
                logger.debug(f"Could not process album art: {e}")
                ascii_art = ""

        # Build panels
        info_text = Text()
        info_text.append(f"Now Playing\n", style="bold")
        info_text.append(f"{song_info}\n", style="cyan")
        info_text.append(f"by {artist}\n", style="green")
        info_text.append(f"from {album}\n", style="magenta")
        info_text.append(f"Duration: {self._format_time(duration)}", style="yellow")

        if ascii_art:
            # Show ASCII art on left, info on right? We'll put ASCII art above info for simplicity.
            layout = Panel.fit(
                Text(ascii_art, style="white"),
                title="Album Art",
                border_style="dim",
            )
            self.console.print(layout)
        self.console.print(Panel(info_text, title="🎶 Now Playing", border_style="blue"))

        # Progress bar
        if duration > 0:
            progress = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(bar_width=None),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
            )
            with progress:
                task = progress.add_task("Playback", total=duration)
                while self.is_playing() and not self._stop_event.is_set():
                    pos = self.get_position()
                    progress.update(task, completed=pos)
                    time.sleep(0.5)
                # Ensure progress reaches end if stopped naturally
                if not self._stop_event.is_set():
                    progress.update(task, completed=duration)

    def _format_time(self, seconds: float) -> str:
        """Format seconds as MM:SS."""
        if seconds < 0:
            seconds = 0
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"

    def _image_to_ascii(self, image: Image.Image) -> str:
        """Convert PIL image to ASCII art (simple version)."""
        # Grayscale
        gray_image = image.convert('L')
        width, height = gray_image.size
        pixels = gray_image.getdata()
        # ASCII characters from dark to light
        ascii_chars = "@%#*+=-:. "
        # Resize to fit terminal width (approx)
        max_width = 80
        if width > max_width:
            # Adjust height to keep aspect ratio
            height = int(height * max_width / width)
            width = max_width
            gray_image = gray_image.resize((width, height))
            pixels = gray_image.getdata()
        # Map pixel values to ascii_chars
        ascii_str = ''
        for i, pixel in enumerate(pixels):
            if i % width == 0 and i != 0:
                ascii_str += '\n'
            idx = int(pixel / 255 * (len(ascii_chars) - 1))
            ascii_str += ascii_chars[idx]
        return ascii_str
