"""
Data models and database handling for PROJECTOR.
"""
import sqlite3
import os
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict
import logging

# Import mutagen modules with fallbacks for video metadata (if needed)
try:
    from mutagen import File as MutagenFile
except ImportError:
    MutagenFile = None

try:
    from mutagen.mp4 import MP4
except ImportError:
    MP4 = None

try:
    from mutagen.flac import FLAC  # for audio in video? not needed but keep
except ImportError:
    FLAC = None

logger = logging.getLogger(__name__)


@dataclass
class MediaItem:
    """Represents a movie or TV show."""
    path: str  # file path or identifier (e.g., URL, discogs id)
    title: str = ""
    original_title: str = ""
    overview: str = ""
    release_date: str = ""  # YYYY-MM-DD
    genres: List[str] = field(default_factory=list)
    runtime: Optional[int] = None  # in minutes
    vote_average: float = 0.0
    vote_count: int = 0
    poster_path: Optional[bytes] = None  # poster image data
    media_type: str = "movie"  # movie, tv, episode
    tv_show_id: Optional[int] = None  # for episodes
    episode_number: Optional[int] = None
    season_number: Optional[int] = None
    # Additional fields for tracking
    watched: bool = False
    watch_count: int = 0
    last_watched: Optional[str] = None  # timestamp
    personal_rating: Optional[float] = None  # 0-10
    notes: str = ""
    # Mood tags for recommendation
    mood_tags: List[str] = field(default_factory=list)

    @classmethod
    def from_file(cls, file_path: str) -> Optional["MediaItem"]:
        """Extract metadata from media file using mutagen (basic)."""
        if MutagenFile is None:
            logger.error("mutagen not available")
            return None
        try:
            audio = MutagenFile(file_path)
            if audio is None:
                logger.warning(f"Could not read file as media: {file_path}")
                return None

            # Basic info
            path = os.path.abspath(file_path)
            # For video files, we might not have duration in mutagen? but we'll try
            duration = 0.0
            if hasattr(audio, 'info') and hasattr(audio.info, 'length'):
                duration = audio.info.length  # in seconds

            # Initialize metadata
            title = ""
            original_title = ""
            overview = ""
            release_date = ""
            genres = []
            runtime = None
            vote_average = 0.0
            vote_count = 0
            poster_path = None

            # Handle different formats
            if hasattr(audio, 'tags') and audio.tags:
                tags = audio.tags
                # ID3 (MP3) - not typical for video, but maybe for audio files
                if 'TIT2' in tags:
                    title = str(tags['TIT2'])
                if 'TALB' in tags:
                    original_title = str(tags['TALB'])  # using album as original title?
                # TODO: map more ID3 fields

            # MP4 (M4A, ALAC, MP4 video)
            if MP4 is not None and isinstance(audio, MP4):
                if audio.tags:
                    if '\xa9nam' in audio.tags:
                        title = str(audio.tags['\xa9nam'][0])
                    if '\xa9day' in audio.tags:
                        # year only
                        year_str = str(audio.tags['\xa9day'][0])
                        if year_str:
                            release_date = f"{year_str}-01-01"
                    if '\xa9gen' in audio.tags:
                        genre_str = str(audio.tags['\xa9gen'][0])
                        if genre_str:
                            genres = [g.strip() for g in genre_str.split(';')]
                    # TODO: more MP4 tags

            # Default mood tags (can be enhanced later)
            mood_tags = []
            if genres:
                mood_tags.extend([g.lower() for g in genres])
            if release_date:
                try:
                    year = int(release_date[:4])
                    if year >= 2020:
                        mood_tags.append("modern")
                    elif year >= 2010:
                        mood_tags.append("contemporary")
                    elif year >= 2000:
                        mood_tags.append("2000s")
                    elif year >= 1990:
                        mood_tags.append("90s")
                    else:
                        mood_tags.append("vintage")
                except ValueError:
                    pass

            return cls(
                path=path,
                title=title,
                original_title=original_title,
                overview=overview,
                release_date=release_date,
                genres=genres,
                runtime=runtime,
                vote_average=vote_average,
                vote_count=vote_count,
                poster_path=poster_path,
                mood_tags=mood_tags,
            )
        except Exception as e:
            logger.error(f"Error reading metadata from {file_path}: {e}")
            return None


class ProjectorDB:
    """SQLite database for PROJECTOR media library."""
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
        # Media items table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS media_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                title TEXT,
                original_title TEXT,
                overview TEXT,
                release_date TEXT,
                genres TEXT,  -- JSON list
                runtime INTEGER,
                vote_average REAL,
                vote_count INTEGER,
                poster_path BLOB,  -- optional
                media_type TEXT DEFAULT 'movie',
                tv_show_id INTEGER,
                episode_number INTEGER,
                season_number INTEGER,
                watched INTEGER DEFAULT 0,  -- boolean
                watch_count INTEGER DEFAULT 0,
                last_watched TIMESTAMP,
                personal_rating REAL,
                notes TEXT,
                mood_tags TEXT  -- JSON list
            )
        ''')
        # Watchlist table (separate for simplicity, but we can use watched flag)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                media_item_id INTEGER NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (media_item_id) REFERENCES media_items(id),
                UNIQUE(media_item_id)
            )
        ''')
        conn.commit()

    def add_media_item(self, item: MediaItem) -> int:
        """Add a media item to the library, returns item ID."""
        conn = self._get_conn()
        cursor = conn.cursor()
        # Check if already exists
        cursor.execute("SELECT id FROM media_items WHERE path = ?", (item.path,))
        row = cursor.fetchone()
        if row:
            item_id = row['id']
            # Update metadata
            cursor.execute('''
                UPDATE media_items SET
                    title = ?, original_title = ?, overview = ?, release_date = ?,
                    genres = ?, runtime = ?, vote_average = ?, vote_count = ?,
                    poster_path = ?, media_type = ?, tv_show_id = ?,
                    episode_number = ?, season_number = ?
                WHERE id = ?
            ''', (
                item.title, item.original_title, item.overview, item.release_date,
                json.dumps(item.genres), item.runtime, item.vote_average, item.vote_count,
                sqlite3.Binary(item.poster_path) if item.poster_path else None,
                item.media_type, item.tv_show_id, item.episode_number, item.season_number,
                item_id
            ))
        else:
            cursor.execute('''
                INSERT INTO media_items (
                    path, title, original_title, overview, release_date,
                    genres, runtime, vote_average, vote_count, poster_path,
                    media_type, tv_show_id, episode_number, season_number
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                item.path, item.title, item.original_title, item.overview, item.release_date,
                json.dumps(item.genres), item.runtime, item.vote_average, item.vote_count,
                sqlite3.Binary(item.poster_path) if item.poster_path else None,
                item.media_type, item.tv_show_id, item.episode_number, item.season_number
            ))
            item_id = cursor.lastrowid
        conn.commit()
        return item_id

    def get_media_item_by_path(self, path: str) -> Optional[MediaItem]:
        """Retrieve a media item by its file path/identifier."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM media_items WHERE path = ?", (path,))
        row = cursor.fetchone()
        if row:
            return self._row_to_media_item(row)
        return None

    def get_media_item_by_id(self, item_id: int) -> Optional[MediaItem]:
        """Retrieve a media item by its database ID."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM media_items WHERE id = ?", (item_id,))
        row = cursor.fetchone()
        if row:
            return self._row_to_media_item(row)
        return None

    def search_media_items(self, **kwargs) -> List[MediaItem]:
        """Search media items by field values (e.g., title='', genres=[''])."""
        conn = self._get_conn()
        cursor = conn.cursor()
        where_clauses = []
        params = []
        for key, value in kwargs.items():
            # Simple validation: allow known fields
            if hasattr(MediaItem, key):
                if isinstance(value, list):
                    # For list fields like genres, we need to check if the JSON contains the value?
                    # For simplicity, we'll do string matching on the JSON string.
                    where_clauses.append(f"{key} LIKE ?")
                    params.append(f"%{json.dumps(value)}%")
                else:
                    where_clauses.append(f"{key} = ?")
                    params.append(value)
        if not where_clauses:
            cursor.execute("SELECT * FROM media_items")
        else:
            where = " AND ".join(where_clauses)
            cursor.execute(f"SELECT * FROM media_items WHERE {where}", params)
        rows = cursor.fetchall()
        return [self._row_to_media_item(row) for row in rows]

    def get_all_media_items(self) -> List[MediaItem]:
        """Get all media items in the library."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM media_items")
        rows = cursor.fetchall()
        return [self._row_to_media_item(row) for row in rows]

    def _row_to_media_item(self, row: sqlite3.Row) -> MediaItem:
        """Convert a database row to a MediaItem dataclass."""
        genres = []
        if row['genres']:
            try:
                genres = json.loads(row['genres'])
            except json.JSONDecodeError:
                genres = []
        mood_tags = []
        if row['mood_tags']:
            try:
                mood_tags = json.loads(row['mood_tags'])
            except json.JSONDecodeError:
                mood_tags = []
        return MediaItem(
            path=row['path'],
            title=row['title'] or '',
            original_title=row['original_title'] or '',
            overview=row['overview'] or '',
            release_date=row['release_date'] or '',
            genres=genres,
            runtime=row['runtime'],
            vote_average=row['vote_average'] or 0.0,
            vote_count=row['vote_count'] or 0,
            poster_path=row['poster_path'] if row['poster_path'] else None,
            media_type=row['media_type'] or 'movie',
            tv_show_id=row['tv_show_id'],
            episode_number=row['episode_number'],
            season_number=row['season_number'],
            watched=bool(row['watched']),
            watch_count=row['watch_count'] or 0,
            last_watched=row['last_watched'],
            personal_rating=row['personal_rating'],
            notes=row['notes'] or '',
            mood_tags=mood_tags,
        )

    def add_to_watchlist(self, media_item_id: int):
        """Add a media item to the watchlist."""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO watchlist (media_item_id) VALUES (?)", (media_item_id,))
            conn.commit()
        except sqlite3.IntegrityError:
            # Already in watchlist
            pass

    def remove_from_watchlist(self, media_item_id: int):
        """Remove a media item from the watchlist."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM watchlist WHERE media_item_id = ?", (media_item_id,))
        conn.commit()

    def get_watchlist(self) -> List[MediaItem]:
        """Get all media items in the watchlist."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT m.* FROM media_items m
            JOIN watchlist w ON m.id = w.media_item_id
            ORDER BY w.added_at
        ''')
        rows = cursor.fetchall()
        return [self._row_to_media_item(row) for row in rows]

    def mark_watched(self, media_item_id: int, rating: Optional[float] = None):
        """Mark a media item as watched."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE media_items SET
                watched = 1,
                watch_count = watch_count + 1,
                last_watched = CURRENT_TIMESTAMP,
                personal_rating = COALESCE(?, personal_rating)
            WHERE id = ?
        ''', (rating, media_item_id))
        conn.commit()

    def get_watched_history(self, limit: int = 50) -> List[MediaItem]:
        """Get recently watched media items."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM media_items
            WHERE watched = 1
            ORDER BY last_watched DESC
            LIMIT ?
        ''', (limit,))
        rows = cursor.fetchall()
        return [self._row_to_media_item(row) for row in rows]

    def get_recommendations(self, mood_tags: List[str], limit: int = 10) -> List[MediaItem]:
        """Get media items matching mood tags (simple intersection)."""
        conn = self._get_conn()
        cursor = conn.cursor()
        # We'll get all items and filter in Python for simplicity
        cursor.execute("SELECT * FROM media_items")
        rows = cursor.fetchall()
        items = [self._row_to_media_item(row) for row in rows]
        # Normalize mood tags
        mood_tags = [m.lower() for m in mood_tags]
        matched = []
        for item in items:
            item_moods = [m.lower() for m in item.mood_tags]
            if any(m in item_moods for m in mood_tags):
                matched.append(item)
        # Sort by vote_average descending, then by watch_count ascending (less watched first)
        matched.sort(key=lambda x: (-x.vote_average, x.watch_count))
        return matched[:limit]

    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None