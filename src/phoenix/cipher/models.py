"""
Data models and database handling for CIPHER.
"""
import sqlite3
import os
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict
import logging
from datetime import datetime

# For encryption
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    import base64
    import secrets
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    logging.warning("cryptography not installed. Encrypted vault will not be available.")

logger = logging.getLogger(__name__)


@dataclass
class VaultEntry:
    """Represents an entry in the encrypted password vault."""
    id: Optional[int] = None
    title: str = ""
    username: str = ""
    password: str = ""  # encrypted
    url: str = ""
    notes: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class WireGuardConfig:
    """Represents a WireGuard VPN configuration."""
    id: Optional[int] = None
    name: str = ""
    interface_address: str = ""  # e.g., "10.0.0.1/24"
    interface_private_key: str = ""  # base64
    interface_public_key: str = ""  # base64
    listen_port: int = 51820
    peers: List[Dict] = field(default_factory=list)  # each peer: {public_key, endpoint, allowed_ips, persistent_keepalive}
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class FirewallRule:
    """Represents a firewall rule."""
    id: Optional[int] = None
    name: str = ""
    rule_type: str = ""  # 'allow', 'deny', 'reject'
    protocol: str = ""   # 'tcp', 'udp', 'icmp', 'any'
    port_from: Optional[int] = None
    port_to: Optional[int] = None
    source_ip: str = ""  # e.g., "192.168.1.0/24"
    destination_ip: str = ""  # e.g., "any"
    action: str = ""     # 'allow', 'deny', 'reject'
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class CipherDB:
    """SQLite database for CIPHER components."""
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = None
        self._init_db()
        # Initialize encryption key if vault is to be used
        self.cipher_key = None
        if HAS_CRYPTO:
            self._init_cipher_key()

    def _get_conn(self):
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
        return self.conn

    def _init_db(self):
        """Create tables if they don't exist."""
        conn = self._get_conn()
        cursor = conn.cursor()
        # Vault entries table (encrypted)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vault_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                username TEXT,
                password TEXT NOT NULL,  -- encrypted
                url TEXT,
                notes TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        ''')
        # WireGuard configs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wireguard_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                interface_address TEXT,
                interface_private_key TEXT,
                interface_public_key TEXT,
                listen_port INTEGER,
                peers TEXT,  -- JSON list
                created_at TIMESTAMP
            )
        ''')
        # Firewall rules table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS firewall_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                rule_type TEXT,
                protocol TEXT,
                port_from INTEGER,
                port_to INTEGER,
                source_ip TEXT,
                destination_ip TEXT,
                action TEXT,
                created_at TIMESTAMP
            )
        ''')
        conn.commit()

    def _init_cipher_key(self):
        """Initialize or load the encryption key for the vault."""
        # In a real app, we would derive the key from a master password.
        # For simplicity, we'll generate a key and store it in a file.
        # We'll use a key file in the same directory as the database.
        key_file = Path(self.db_path).parent / ".vault_key"
        if key_file.exists():
            try:
                self.cipher_key = key_file.read_bytes()
                # Ensure it's 32 bytes for Fernet
                if len(self.cipher_key) != 32:
                    raise ValueError("Invalid key length")
            except Exception as e:
                logger.warning(f"Could not load vault key: {e}. Generating new.")
                self.cipher_key = Fernet.generate_key()
                key_file.write_bytes(self.cipher_key)
        else:
            self.cipher_key = Fernet.generate_key()
            key_file.write_bytes(self.cipher_key)
        # Ensure the key file is not readable by others (Unix only)
        try:
            os.chmod(key_file, 0o600)
        except Exception:
            pass

    def _encrypt(self, plaintext: str) -> str:
        """Encrypt a plaintext string using Fernet."""
        if not HAS_CRYPTO or not self.cipher_key:
            raise RuntimeError("Encryption not available")
        f = Fernet(self.cipher_key)
        encrypted = f.encrypt(plaintext.encode('utf-8'))
        return base64.urlsafe_b64encode(encrypted).decode('utf-8')

    def _decrypt(self, encrypted_text: str) -> str:
        """Decrypt an encrypted string."""
        if not HAS_CRYPTO or not self.cipher_key:
            raise RuntimeError("Encryption not available")
        f = Fernet(self.cipher_key)
        decoded = base64.urlsafe_b64decode(encrypted_text.encode('utf-8'))
        decrypted = f.decrypt(decoded)
        return decrypted.decode('utf-8')

    def add_vault_entry(self, entry: VaultEntry) -> int:
        """Add an entry to the encrypted vault."""
        if not HAS_CRYPTO:
            raise RuntimeError("Encryption not available. Install cryptography.")
        conn = self._get_conn()
        cursor = conn.cursor()
        encrypted_password = self._encrypt(entry.password)
        cursor.execute('''
            INSERT INTO vault_entries (
                title, username, password, url, notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            entry.title, entry.username, encrypted_password, entry.url, entry.notes,
            entry.created_at, entry.updated_at
        ))
        conn.commit()
        entry_id = cursor.lastrowid
        return entry_id

    def get_vault_entry(self, entry_id: int) -> Optional[VaultEntry]:
        """Get a vault entry by ID (decrypts password)."""
        if not HAS_CRYPTO:
            raise RuntimeError("Encryption not available")
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM vault_entries WHERE id = ?", (entry_id,))
        row = cursor.fetchone()
        if row:
            return self._row_to_vault_entry(row)
        return None

    def get_all_vault_entries(self) -> List[VaultEntry]:
        """Get all vault entries (decrypts passwords)."""
        if not HAS_CRYPTO:
            raise RuntimeError("Encryption not available")
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM vault_entries ORDER BY updated_at DESC")
        rows = cursor.fetchall()
        return [self._row_to_vault_entry(row) for row in rows]

    def search_vault_entries(self, **kwargs) -> List[VaultEntry]:
        """Search vault entries by title, username, etc."""
        if not HAS_CRYPTO:
            raise RuntimeError("Encryption not available")
        conn = self._get_conn()
        cursor = conn.cursor()
        where_clauses = []
        params = []
        for key, value in kwargs.items():
            if hasattr(VaultEntry, key):
                where_clauses.append(f"{key} = ?")
                params.append(value)
        if not where_clauses:
            cursor.execute("SELECT * FROM vault_entries")
        else:
            where = " AND ".join(where_clauses)
            cursor.execute(f"SELECT * FROM vault_entries WHERE {where}", params)
        rows = cursor.fetchall()
        return [self._row_to_vault_entry(row) for row in rows]

    def update_vault_entry(self, entry_id: int, entry: VaultEntry):
        """Update a vault entry."""
        if not HAS_CRYPTO:
            raise RuntimeError("Encryption not available")
        conn = self._get_conn()
        cursor = conn.cursor()
        encrypted_password = self._encrypt(entry.password)
        cursor.execute('''
            UPDATE vault_entries SET
                title = ?, username = ?, password = ?, url = ?, notes = ?, updated_at = ?
            WHERE id = ?
        ''', (
            entry.title, entry.username, encrypted_password, entry.url, entry.notes,
            entry.updated_at, entry_id
        ))
        conn.commit()

    def delete_vault_entry(self, entry_id: int):
        """Delete a vault entry."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM vault_entries WHERE id = ?", (entry_id,))
        conn.commit()

    def _row_to_vault_entry(self, row: sqlite3.Row) -> VaultEntry:
        """Convert a database row to a VaultEntry dataclass (decrypts password)."""
        decrypted_password = self._decrypt(row['password'])
        return VaultEntry(
            id=row['id'],
            title=row['title'] or '',
            username=row['username'] or '',
            password=decrypted_password,
            url=row['url'] or '',
            notes=row['notes'] or '',
            created_at=row['created_at'] or '',
            updated_at=row['updated_at'] or ''
        )

    # WireGuard config methods
    def add_wireguard_config(self, config: WireGuardConfig) -> int:
        """Add a WireGuard configuration."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO wireguard_configs (
                name, interface_address, interface_private_key, interface_public_key,
                listen_port, peers, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            config.name, config.interface_address, config.interface_private_key,
            config.interface_public_key, config.listen_port,
            json.dumps(config.peers), config.created_at
        ))
        conn.commit()
        return cursor.lastrowid

    def get_wireguard_config(self, config_id: int) -> Optional[WireGuardConfig]:
        """Get a WireGuard configuration by ID."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM wireguard_configs WHERE id = ?", (config_id,))
        row = cursor.fetchone()
        if row:
            return self._row_to_wireguard_config(row)
        return None

    def get_all_wireguard_configs(self) -> List[WireGuardConfig]:
        """Get all WireGuard configurations."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM wireguard_configs ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return [self._row_to_wireguard_config(row) for row in rows]

    def _row_to_wireguard_config(self, row: sqlite3.Row) -> WireGuardConfig:
        """Convert a database row to a WireGuardConfig dataclass."""
        peers = []
        if row['peers']:
            try:
                peers = json.loads(row['peers'])
            except json.JSONDecodeError:
                peers = []
        return WireGuardConfig(
            id=row['id'],
            name=row['name'] or '',
            interface_address=row['interface_address'] or '',
            interface_private_key=row['interface_private_key'] or '',
            interface_public_key=row['interface_public_key'] or '',
            listen_port=row['listen_port'] or 51820,
            peers=peers,
            created_at=row['created_at'] or ''
        )

    # Firewall rule methods
    def add_firewall_rule(self, rule: FirewallRule) -> int:
        """Add a firewall rule."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO firewall_rules (
                name, rule_type, protocol, port_from, port_to,
                source_ip, destination_ip, action, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            rule.name, rule.rule_type, rule.protocol, rule.port_from, rule.port_to,
            rule.source_ip, rule.destination_ip, rule.action, rule.created_at
        ))
        conn.commit()
        return cursor.lastrowid

    def get_firewall_rule(self, rule_id: int) -> Optional[FirewallRule]:
        """Get a firewall rule by ID."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM firewall_rules WHERE id = ?", (rule_id,))
        row = cursor.fetchone()
        if row:
            return self._row_to_firewall_rule(row)
        return None

    def get_all_firewall_rules(self) -> List[FirewallRule]:
        """Get all firewall rules."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM firewall_rules ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return [self._row_to_firewall_rule(row) for row in rows]

    def _row_to_firewall_rule(self, row: sqlite3.Row) -> FirewallRule:
        """Convert a database row to a FirewallRule dataclass."""
        return FirewallRule(
            id=row['id'],
            name=row['name'] or '',
            rule_type=row['rule_type'] or '',
            protocol=row['protocol'] or '',
            port_from=row['port_from'],
            port_to=row['port_to'],
            source_ip=row['source_ip'] or '',
            destination_ip=row['destination_ip'] or '',
            action=row['action'] or '',
            created_at=row['created_at'] or ''
        )

    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None