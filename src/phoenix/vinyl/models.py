"""
Data models and database handling for VINYL.
"""
import sqlite3
import os
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict
import logging
from datetime import datetime

# For Discogs API
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    logging.warning("requests not installed. Discogs API integration will not be available.")

logger = logging.getLogger(__name__)


@dataclass
class VinylRecord:
    """Represents a vinyl record in the collection."""
    id: Optional[int] = None
    discogs_id: Optional[str] = None  # Discogs release ID
    barcode: Optional[str] = None     # UPC/EAN
    catalog_number: Optional[str] = None  # Label catalog number
    title: str = ""
    artist: str = ""
    year: Optional[int] = None
    genres: List[str] = field(default_factory=list)
    styles: List[str] = field(default_factory=list)
    format: str = ""  # e.g., "LP", "Album", "Single"
    condition: str = ""  # e.g., "Mint (M)", "Near Mint (NM)", etc.
    sleeve_condition: str = ""
    notes: str = ""
    purchased_from: str = ""
    purchase_price: float = 0.0
    purchase_date: str = field(default_factory=lambda: datetime.now().date().isoformat())
    # Playback statistics
    play_count: int = 0
    last_played: Optional[str] = None
    # Link to digital tracks (if any)
    digital_tracks: List[int] = field(default_factory=list)  # IDs of songs in songbird library
    # Additional metadata
    label: str = ""
    country: str = ""
    barcode_scanned: bool = False

    @classmethod
    def from_discogs(cls, discogs_data: Dict) -> "VinylRecord":
        """Create a VinylRecord from Discogs API response."""
        # Extract basic info
        discogs_id = str(discogs_data.get('id', ''))
        title = discogs_data.get('title', '')
        artist = discogs_data.get('artist', '')
        # Artist might be a list or dict; handle simply
        if isinstance(artist, list):
            artist = ", ".join([a.get('name', '') for a in artist if isinstance(a, dict)])
        elif isinstance(artist, dict):
            artist = artist.get('name', '')
        year = None
        if discogs_data.get('year'):
            try:
                year = int(discogs_data['year'])
            except ValueError:
                pass
        genres = discogs_data.get('genres', [])
        styles = discogs_data.get('styles', [])
        format_list = discogs_data.get('formats', [])
        format_str = ", ".join([f.get('name', '') for f in format_list if isinstance(f, dict)])
        label_list = discogs_data.get('labels', [])
        label = ", ".join([l.get('name', '') for l in label_list if isinstance(l, dict)])
        country = discogs_data.get('country', '')
        # Barcode/UPC
        barcode = None
        # Discogs may have barcodes in identifiers
        identifiers = discogs_data.get('identifiers', [])
        for id_dict in identifiers:
            if isinstance(id_dict, dict) and id_dict.get('type') == 'Barcode':
                barcode = id_dict.get('value')
                break
        # Catalog number
        catalog_number = None
        for id_dict in identifiers:
            if isinstance(id_dict, dict) and id_dict.get('type') == 'Catalog Number':
                catalog_number = id_dict.get('value')
                break

        return cls(
            discogs_id=discogs_id,
            barcode=barcode,
            catalog_number=catalog_number,
            title=title,
            artist=artist,
            year=year,
            genres=genres,
            styles=styles,
            format=format_str,
            label=label,
            country=country,
        )


class VinylDB:
    """SQLite database for VINYL collection."""
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
        # Vinyl records table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vinyl_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discogs_id TEXT,
                barcode TEXT UNIQUE,
                catalog_number TEXT,
                title TEXT NOT NULL,
                artist TEXT,
                year INTEGER,
                genres TEXT,  -- JSON list
                styles TEXT,  -- JSON list
                format TEXT,
                condition TEXT,
                sleeve_condition TEXT,
                notes TEXT,
                purchased_from TEXT,
                purchase_price REAL,
                purchase_date TEXT,
                play_count INTEGER DEFAULT 0,
                last_played TIMESTAMP,
                digital_tracks TEXT,  -- JSON list of song IDs from songbird
                label TEXT,
                country TEXT,
                barcode_scanned INTEGER DEFAULT 0
            )
        ''')
        # Optional: table for linking to songbird songs (if we want to track which digital files correspond to which vinyl)
        # We already have digital_tracks as JSON, but we could normalize. For simplicity, we keep JSON.
        conn.commit()

    def add_vinyl_record(self, record: VinylRecord) -> int:
        """Add a vinyl record to the collection."""
        conn = self._get_conn()
        cursor = conn.cursor()
        # Check if barcode already exists (if provided)
        if record.barcode:
            cursor.execute("SELECT id FROM vinyl_records WHERE barcode = ?", (record.barcode,))
            row = cursor.fetchone()
            if row:
                # Update existing
                record_id = row['id']
                cursor.execute('''
                    UPDATE vinyl_records SET
                        discogs_id = ?, title = ?, artist = ?, year = ?,
                        genres = ?, styles = ?, format = ?, condition = ?,
                        sleeve_condition = ?, notes = ?, purchased_from = ?,
                        purchase_price = ?, purchase_date = ?, play_count = ?,
                        last_played = ?, digital_tracks = ?, label = ?, country = ?,
                        barcode_scanned = ?
                    WHERE id = ?
                ''', (
                    record.discogs_id, record.title, record.artist, record.year,
                    json.dumps(record.genres), json.dumps(record.styles), record.format,
                    record.condition, record.sleeve_condition, record.notes,
                    record.purchased_from, record.purchase_price, record.purchase_date,
                    record.play_count, record.last_played,
                    json.dumps(record.digital_tracks), record.label, record.country,
                    1 if record.barcode_scanned else 0, record_id
                ))
                conn.commit()
                return record_id
        # Insert new
        cursor.execute('''
            INSERT INTO vinyl_records (
                discogs_id, barcode, catalog_number, title, artist, year,
                genres, styles, format, condition, sleeve_condition, notes,
                purchased_from, purchase_price, purchase_date, play_count, last_played,
                digital_tracks, label, country, barcode_scanned
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            record.discogs_id, record.barcode, record.catalog_number, record.title, record.artist,
            record.year, json.dumps(record.genres), json.dumps(record.styles), record.format,
            record.condition, record.sleeve_condition, record.notes,
            record.purchased_from, record.purchase_price, record.purchase_date,
            record.play_count, record.last_played,
            json.dumps(record.digital_tracks), record.label, record.country,
            1 if record.barcode_scanned else 0
        ))
        conn.commit()
        return cursor.lastrowid

    def get_vinyl_record_by_id(self, record_id: int) -> Optional[VinylRecord]:
        """Get a vinyl record by ID."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM vinyl_records WHERE id = ?", (record_id,))
        row = cursor.fetchone()
        if row:
            return self._row_to_vinyl_record(row)
        return None

    def get_vinyl_record_by_barcode(self, barcode: str) -> Optional[VinylRecord]:
        """Get a vinyl record by barcode."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM vinyl_records WHERE barcode = ?", (barcode,))
        row = cursor.fetchone()
        if row:
            return self._row_to_vinyl_record(row)
        return None

    def search_vinyl_records(self, **kwargs) -> List[VinylRecord]:
        """Search vinyl records by field values."""
        conn = self._get_conn()
        cursor = conn.cursor()
        where_clauses = []
        params = []
        for key, value in kwargs.items():
            if hasattr(VinylRecord, key):
                if isinstance(value, list):
                    # For list fields, we'll do JSON containment (simplified)
                    where_clauses.append(f"{key} LIKE ?")
                    params.append(f"%{json.dumps(value)}%")
                else:
                    where_clauses.append(f"{key} = ?")
                    params.append(value)
        if not where_clauses:
            cursor.execute("SELECT * FROM vinyl_records")
        else:
            where = " AND ".join(where_clauses)
            cursor.execute(f"SELECT * FROM vinyl_records WHERE {where}", params)
        rows = cursor.fetchall()
        return [self._row_to_vinyl_record(row) for row in rows]

    def get_all_vinyl_records(self) -> List[VinylRecord]:
        """Get all vinyl records."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM vinyl_records ORDER BY artist, title")
        rows = cursor.fetchall()
        return [self._row_to_vinyl_record(row) for row in rows]

    def _row_to_vinyl_record(self, row: sqlite3.Row) -> VinylRecord:
        """Convert a database row to a VinylRecord dataclass."""
        genres = []
        if row['genres']:
            try:
                genres = json.loads(row['genres'])
            except json.JSONDecodeError:
                genres = []
        styles = []
        if row['styles']:
            try:
                styles = json.loads(row['styles'])
            except json.JSONDecodeError:
                styles = []
        digital_tracks = []
        if row['digital_tracks']:
            try:
                digital_tracks = json.loads(row['digital_tracks'])
            except json.JSONDecodeError:
                digital_tracks = []
        return VinylRecord(
            id=row['id'],
            discogs_id=row['discogs_id'],
            barcode=row['barcode'],
            catalog_number=row['catalog_number'],
            title=row['title'] or '',
            artist=row['artist'] or '',
            year=row['year'],
            genres=genres,
            styles=styles,
            format=row['format'] or '',
            condition=row['condition'] or '',
            sleeve_condition=row['sleeve_condition'] or '',
            notes=row['notes'] or '',
            purchased_from=row['purchased_from'] or '',
            purchase_price=row['purchase_price'] or 0.0,
            purchase_date=row['purchase_date'] or '',
            play_count=row['play_count'] or 0,
            last_played=row['last_played'],
            digital_tracks=digital_tracks,
            label=row['label'] or '',
            country=row['country'] or '',
            barcode_scanned=bool(row['barcode_scanned'])
        )

    def increment_play_count(self, record_id: int):
        """Increment the play count and update last played time."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE vinyl_records SET
                play_count = play_count + 1,
                last_played = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (record_id,))
        conn.commit()

    def get_most_played(self, limit: int = 10) -> List[VinylRecord]:
        """Get most played vinyl records."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM vinyl_records
            ORDER BY play_count DESC
            LIMIT ?
        ''', (limit,))
        rows = cursor.fetchall()
        return [self._row_to_vinyl_record(row) for row in rows]

    def get_recently_played(self, limit: int = 10) -> List[VinylRecord]:
        """Get recently played vinyl records."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM vinyl_records
            WHERE last_played IS NOT NULL
            ORDER BY last_played DESC
            LIMIT ?
        ''', (limit,))
        rows = cursor.fetchall()
        return [self._row_to_vinyl_record(row) for row in rows]

    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None