"""
Data models and database handling for SONGBIRD.
"""
import sqlite3
import os
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict
import logging

# Import mutagen modules with fallbacks
try:
    from mutagen import File as MutagenFile
except ImportError:
    MutagenFile = None

try:
    from mutagen.id3 import ID3NoHeaderError as IDNoHeaderError
except ImportError:
    try:
        from mutagen.id3 import IDNoHeaderError
    except ImportError:
        class IDNoHeaderError(Exception):
            pass

try:
    from mutagen.flac import FLAC
except ImportError:
    FLAC = None

try:
    from mutagen.mp4 import MP4
except ImportError:
    MP4 = None

try:
    from mutagen.oggvorbis import OggVorbis
except ImportError:
    OggVorbis = None

try:
    from mutagen.oggopus import Opus
except ImportError:
    Opus = None

try:
    from mutagen.aac import AAC
except ImportError:
    AAC = None

logger = logging.getLogger(__name__)

@dataclass
class Song:
    """Represents a music file with metadata."""
    path: str
    title: str = ""
    artist: str = ""
    album: str = ""
    album_artist: str = ""
    track_number: Optional[int] = None
    disc_number: Optional[int] = None
    year: Optional[int] = None
    genre: str = ""
    duration: float = 0.0  # in seconds
    bitrate: Optional[int] = None
    filesize: int = 0
    # Additional fields for mood/generation
    mood_tags: List[str] = field(default_factory=list)
    # Album art data (bytes) if embedded
    album_art: Optional[bytes] = None

    @classmethod
    def from_file(cls, file_path: str) -> Optional["Song"]:
        """Extract metadata from audio file using mutagen."""
        if MutagenFile is None:
            logger.error("mutagen not available")
            return None
        try:
            audio = MutagenFile(file_path)
            if audio is None:
                logger.warning(f"Could not read file as audio: {file_path}")
                return None

            # Basic info
            path = os.path.abspath(file_path)
            filesize = os.path.getsize(path)
            duration = audio.info.length if hasattr(audio.info, 'length') else 0.0
            bitrate = getattr(audio.info, 'bitrate', None)

            # Initialize metadata
            title = ""
            artist = ""
            album = ""
            album_artist = ""
            track_number = None
            disc_number = None
            year = None
            genre = ""
            album_art = None

            # Handle different formats
            if hasattr(audio, 'tags') and audio.tags:
                tags = audio.tags
                # ID3 (MP3)
                if 'TIT2' in tags:
                    title = str(tags['TIT2'])
                if 'TPE1' in tags:
                    artist = str(tags['TPE1'])
                if 'TALB' in tags:
                    album = str(tags['TALB'])
                if 'TPE2' in tags:
                    album_artist = str(tags['TPE2'])
                if 'TRCK' in tags:
                    try:
                        track_number = int(str(tags['TRCK']).split('/')[0])
                    except ValueError:
                        pass
                if 'TPOS' in tags:
                    try:
                        disc_number = int(str(tags['TPOS']).split('/')[0])
                    except ValueError:
                        pass
                if 'TYER' in tags:
                    try:
                        year = int(str(tags['TYER']))
                    except ValueError:
                        pass
                if 'TCON' in tags:
                    genre = str(tags['TCON'])

                # Album art (ID3)
                if 'APIC:' in tags:
                    apic = tags['APIC:']
                    album_art = apic.data

            # FLAC
            if FLAC is not None and isinstance(audio, FLAC):
                if audio.tags:
                    if 'title' in audio.tags:
                        title = str(audio.tags['title'][0])
                    if 'artist' in audio.tags:
                        artist = str(audio.tags['artist'][0])
                    if 'album' in audio.tags:
                        album = str(audio.tags['album'][0])
                    if 'albumartist' in audio.tags:
                        album_artist = str(audio.tags['albumartist'][0])
                    if 'tracknumber' in audio.tags:
                        try:
                            track_number = int(str(audio.tags['tracknumber'][0]).split('/')[0])
                        except ValueError:
                            pass
                    if 'discnumber' in audio.tags:
                        try:
                            disc_number = int(str(audio.tags['discnumber'][0]).split('/')[0])
                        except ValueError:
                            pass
                    if 'date' in audio.tags:
                        try:
                            year = int(str(audio.tags['date'][0])[:4])
                        except ValueError:
                            pass
                    if 'genre' in audio.tags:
                        genre = str(audio.tags['genre'][0])
                    # Album art in FLAC
                    if audio.pictures:
                        picture = audio.pictures[0]
                        album_art = picture.data

            # MP4 (M4A, ALAC)
            if MP4 is not None and isinstance(audio, MP4):
                if audio.tags:
                    if '\xa9nam' in audio.tags:
                        title = str(audio.tags['\xa9nam'][0])
                    if '\xa9ART' in audio.tags:
                        artist = str(audio.tags['\xa9ART'][0])
                    if '\xa9alb' in audio.tags:
                        album = str(audio.tags['\xa9alb'][0])
                    if 'aART' in audio.tags:
                        album_artist = str(audio.tags['aART'][0])
                    if 'trkn' in audio.tags:
                        track_tuple = audio.tags['trkn'][0]
                        if track_tuple:
                            track_number = track_tuple[0]
                    if 'disk' in audio.tags:
                        disk_tuple = audio.tags['disk'][0]
                        if disk_tuple:
                            disc_number = disk_tuple[0]
                    if '\xa9day' in audio.tags:
                        year_str = str(audio.tags['\xa9day'][0])
                        try:
                            year = int(year_str[:4])
                        except ValueError:
                            pass
                    if '\xa9gen' in audio.tags:
                        genre = str(audio.tags['\xa9gen'][0])
                    # Album art in MP4
                    if 'covr' in audio.tags:
                        covr = audio.tags['covr'][0]
                        album_art = bytes(covr)

            # Ogg Vorbis (OGG)
            if OggVorbis is not None and isinstance(audio, OggVorbis):
                if audio.tags:
                    if 'title' in audio.tags:
                        title = str(audio.tags['title'][0])
                    if 'artist' in audio.tags:
                        artist = str(audio.tags['artist'][0])
                    if 'album' in audio.tags:
                        album = str(audio.tags['album'][0])
                    if 'albumartist' in audio.tags:
                        album_artist = str(audio.tags['albumartist'][0])
                    if 'tracknumber' in audio.tags:
                        try:
                            track_number = int(str(audio.tags['tracknumber'][0]))
                        except ValueError:
                            pass
                    if 'discnumber' in audio.tags:
                        try:
                            disc_number = int(str(audio.tags['discnumber'][0]))
                        except ValueError:
                            pass
                    if 'date' in audio.tags:
                        try:
                            year = int(str(audio.tags['date'][0])[:4])
                        except ValueError:
                            pass
                    if 'genre' in audio.tags:
                        genre = str(audio.tags['genre'][0])
                    # Ogg Vorbis doesn't typically embed album art in tags

            # Opus
            if Opus is not None and isinstance(audio, Opus):
                if audio.tags:
                    if 'title' in audio.tags:
                        title = str(audio.tags['title'][0])
                    if 'artist' in audio.tags:
                        artist = str(audio.tags['artist'][0])
                    if 'album' in audio.tags:
                        album = str(audio.tags['album'][0])
                    if 'albumartist' in audio.tags:
                        album_artist = str(audio.tags['albumartist'][0])
                    if 'tracknumber' in audio.tags:
                        try:
                            track_number = int(str(audio.tags['tracknumber'][0]))
                        except ValueError:
                            pass
                    if 'discnumber' in audio.tags:
                        try:
                            disc_number = int(str(audio.tags['discnumber'][0]))
                        except ValueError:
                            pass
                    if 'date' in audio.tags:
                        try:
                            year = int(str(audio.tags['date'][0])[:4])
                        except ValueError:
                            pass
                    if 'genre' in audio.tags:
                        genre = str(audio.tags['genre'][0])

            # AAC
            if AAC is not None and isinstance(audio, AAC):
                # Similar to MP4
                if audio.tags:
                    if '\xa9nam' in audio.tags:
                        title = str(audio.tags['\xa9nam'][0])
                    if '\xa9ART' in audio.tags:
                        artist = str(audio.tags['\xa9ART'][0])
                    if '\xa9alb' in audio.tags:
                        album = str(audio.tags['\xa9alb'][0])
                    if 'aART' in audio.tags:
                        album_artist = str(audio.tags['aART'][0])
                    if 'trkn' in audio.tags:
                        track_tuple = audio.tags['trkn'][0]
                        if track_tuple:
                            track_number = track_tuple[0]
                    if 'disk' in audio.tags:
                        disk_tuple = audio.tags['disk'][0]
                        if disk_tuple:
                            disc_number = disk_tuple[0]
                    if '\xa9day' in audio.tags:
                        year_str = str(audio.tags['\xa9day'][0])
                        try:
                            year = int(year_str[:4])
                        except ValueError:
                            pass
                    if '\xa9gen' in audio.tags:
                        genre = str(audio.tags['\xa9gen'][0])
                    if 'covr' in audio.tags:
                        covr = audio.tags['covr'][0]
                        album_art = bytes(covr)

            # Default mood tags (can be enhanced later)
            mood_tags = []
            if genre:
                mood_tags.append(genre.lower())
            if year:
                # Assign mood based on decade? simplistic
                decade = (year // 10) * 10
                if decade >= 2020:
                    mood_tags.append("modern")
                elif decade >= 2010:
                    mood_tags.append("contemporary")
                elif decade >= 2000:
                    mood_tags.append("2000s")
                elif decade >= 1990:
                    mood_tags.append("90s")
                else:
                    mood_tags.append("vintage")

            return cls(
                path=path,
                title=title,
                artist=artist,
                album=album,
                album_artist=album_artist,
                track_number=track_number,
                disc_number=disc_number,
                year=year,
                genre=genre,
                duration=duration,
                bitrate=bitrate,
                filesize=filesize,
                mood_tags=mood_tags,
                album_art=album_art,
            )
        except Exception as e:
            logger.error(f"Error reading metadata from {file_path}: {e}")
            return None

class SongbirdDB:
    """SQLite database for SONGBIRD library."""
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = None
        self._init_db()

    def _get_conn(self):
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
        return self.conn

    def _init_db(self):
        """Create tables if they don't exist."""
        conn = self._get_conn()
        cursor = conn.cursor()
        # Songs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS songs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                title TEXT,
                artist TEXT,
                album TEXT,
                album_artist TEXT,
                track_number INTEGER,
                disc_number INTEGER,
                year INTEGER,
                genre TEXT,
                duration REAL,
                bitrate INTEGER,
                filesize INTEGER,
                mood_tags TEXT,  -- JSON list
                album_art BLOB   -- optional
            )
        ''')
        # Playlists table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS playlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Playlist items (many-to-many)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS playlist_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                playlist_id INTEGER NOT NULL,
                song_id INTEGER NOT NULL,
                position INTEGER,
                FOREIGN KEY (playlist_id) REFERENCES playlists(id),
                FOREIGN KEY (song_id) REFERENCES songs(id),
                UNIQUE(playlist_id, song_id)
            )
        ''')
        # Vinyl collection table (linking digital songs to physical media)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vinyl_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                song_id INTEGER NOT NULL,
                vinyl_id TEXT NOT NULL,  -- e.g., Discogs ID or local ID
                notes TEXT,
                FOREIGN KEY (song_id) REFERENCES songs(id),
                UNIQUE(song_id, vinyl_id)
            )
        ''')
        # Scrobbling cache (optional Last.fm)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scrobble_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                song_id INTEGER NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (song_id) REFERENCES songs(id)
            )
        ''')
        conn.commit()

    def add_song(self, song: Song) -> int:
        """Add a song to the library, returns song ID."""
        conn = self._get_conn()
        cursor = conn.cursor()
        # Check if already exists
        cursor.execute("SELECT id FROM songs WHERE path = ?", (song.path,))
        row = cursor.fetchone()
        if row:
            song_id = row['id']
            # Update metadata
            cursor.execute('''
                UPDATE songs SET
                    title = ?, artist = ?, album = ?, album_artist = ?,
                    track_number = ?, disc_number = ?, year = ?, genre = ?,
                    duration = ?, bitrate = ?, filesize = ?, mood_tags = ?,
                    album_art = ?
                WHERE id = ?
            ''', (
                song.title, song.artist, song.album, song.album_artist,
                song.track_number, song.disc_number, song.year, song.genre,
                song.duration, song.bitrate, song.filesize,
                json.dumps(song.mood_tags),
                sqlite3.Binary(song.album_art) if song.album_art else None,
                song_id
            ))
        else:
            cursor.execute('''
                INSERT INTO songs (
                    path, title, artist, album, album_artist,
                    track_number, disc_number, year, genre,
                    duration, bitrate, filesize, mood_tags, album_art
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                song.path, song.title, song.artist, song.album, song.album_artist,
                song.track_number, song.disc_number, song.year, song.genre,
                song.duration, song.bitrate, song.filesize,
                json.dumps(song.mood_tags),
                sqlite3.Binary(song.album_art) if song.album_art else None
            ))
            song_id = cursor.lastrowid
        conn.commit()
        return song_id

    def get_song_by_path(self, path: str) -> Optional[Song]:
        """Retrieve a song by its file path."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM songs WHERE path = ?", (path,))
        row = cursor.fetchone()
        if row:
            return self._row_to_song(row)
        return None

    def get_song_by_id(self, song_id: int) -> Optional[Song]:
        """Retrieve a song by its database ID."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM songs WHERE id = ?", (song_id,))
        row = cursor.fetchone()
        if row:
            return self._row_to_song(row)
        return None

    def search_songs(self, **kwargs) -> List[Song]:
        """Search songs by field values (e.g., artist='', genre='')."""
        conn = self._get_conn()
        cursor = conn.cursor()
        where_clauses = []
        params = []
        for key, value in kwargs.items():
            if hasattr(Song, key):  # simple validation
                where_clauses.append(f"{key} = ?")
                params.append(value)
        if not where_clauses:
            cursor.execute("SELECT * FROM songs")
        else:
            where = " AND ".join(where_clauses)
            cursor.execute(f"SELECT * FROM songs WHERE {where}", params)
        rows = cursor.fetchall()
        return [self._row_to_song(row) for row in rows]

    def get_all_songs(self) -> List[Song]:
        """Get all songs in the library."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM songs")
        rows = cursor.fetchall()
        return [self._row_to_song(row) for row in rows]

    def _row_to_song(self, row: sqlite3.Row) -> Song:
        """Convert a database row to a Song dataclass."""
        mood_tags = []
        if row['mood_tags']:
            try:
                mood_tags = json.loads(row['mood_tags'])
            except json.JSONDecodeError:
                mood_tags = []
        return Song(
            path=row['path'],
            title=row['title'] or '',
            artist=row['artist'] or '',
            album=row['album'] or '',
            album_artist=row['album_artist'] or '',
            track_number=row['track_number'],
            disc_number=row['disc_number'],
            year=row['year'],
            genre=row['genre'] or '',
            duration=row['duration'] or 0.0,
            bitrate=row['bitrate'],
            filesize=row['filesize'] or 0,
            mood_tags=mood_tags,
            album_art=row['album_art'] if row['album_art'] else None
        )

    def add_playlist(self, name: str) -> int:
        """Create a new playlist, returns playlist ID."""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO playlists (name) VALUES (?)", (name,))
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # Playlist name already exists
            cursor.execute("SELECT id FROM playlists WHERE name = ?", (name,))
            row = cursor.fetchone()
            return row['id'] if row else None

    def add_song_to_playlist(self, playlist_id: int, song_id: int, position: Optional[int] = None):
        """Add a song to a playlist."""
        conn = self._get_conn()
        cursor = conn.cursor()
        if position is None:
            # Get max position
            cursor.execute("SELECT MAX(position) FROM playlist_items WHERE playlist_id = ?", (playlist_id,))
            row = cursor.fetchone()
            pos = (row[0] if row[0] is not None else -1) + 1
        else:
            pos = position
        cursor.execute('''
            INSERT OR IGNORE INTO playlist_items (playlist_id, song_id, position)
            VALUES (?, ?, ?)
        ''', (playlist_id, song_id, pos))
        conn.commit()

    def get_playlist_songs(self, playlist_id: int) -> List[Song]:
        """Get songs in a playlist in order."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT s.* FROM songs s
            JOIN playlist_items pi ON s.id = pi.song_id
            WHERE pi.playlist_id = ?
            ORDER BY pi.position
        ''', (playlist_id,))
        rows = cursor.fetchall()
        return [self._row_to_song(row) for row in rows]

    def link_vinyl(self, song_id: int, vinyl_id: str, notes: str = ""):
        """Link a song to a vinyl record."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO vinyl_links (song_id, vinyl_id, notes)
            VALUES (?, ?, ?)
        ''', (song_id, vinyl_id, notes))
        conn.commit()

    def get_vinyl_links(self, song_id: int) -> List[Dict]:
        """Get vinyl links for a song."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT vinyl_id, notes FROM vinyl_links WHERE song_id = ?
        ''', (song_id,))
        rows = cursor.fetchall()
        return [{"vinyl_id": row['vinyl_id'], "notes": row['notes']} for row in rows]

    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None