"""
Database connection and initialization
"""
import sqlite3
import json
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager


DATABASE_PATH = os.getenv("DATABASE_URL", "sqlite:///./data/text-to-linux-os.db").replace("sqlite:///", "")


@contextmanager
def get_db():
    """Get database connection context manager"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Initialize database schema"""
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)

    with get_db() as conn:
        cursor = conn.cursor()

        # Projects table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                current_version INTEGER DEFAULT 1,
                status TEXT DEFAULT 'draft'
            )
        """)

        # Versions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                version_number INTEGER,
                config TEXT NOT NULL,
                theme_config TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                iso_path TEXT,
                iso_size INTEGER,
                build_logs TEXT,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            )
        """)

        # Conversations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                version_id INTEGER,
                role TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id),
                FOREIGN KEY (version_id) REFERENCES versions(id)
            )
        """)

        # Package cache table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS package_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                package_name TEXT UNIQUE NOT NULL,
                version TEXT,
                download_url TEXT,
                file_hash TEXT,
                cached_path TEXT,
                last_used TIMESTAMP
            )
        """)

        conn.commit()


class ProjectDB:
    """Project database operations"""

    @staticmethod
    def create(name: str, status: str = "draft") -> int:
        """Create a new project"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO projects (name, status) VALUES (?, ?)",
                (name, status)
            )
            return cursor.lastrowid

    @staticmethod
    def get(project_id: int) -> Optional[Dict[str, Any]]:
        """Get project by ID"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    def list_all() -> List[Dict[str, Any]]:
        """List all projects"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM projects ORDER BY updated_at DESC")
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def update(project_id: int, **kwargs):
        """Update project"""
        with get_db() as conn:
            cursor = conn.cursor()
            kwargs['updated_at'] = datetime.now().isoformat()
            fields = ", ".join(f"{k} = ?" for k in kwargs.keys())
            values = list(kwargs.values()) + [project_id]
            cursor.execute(f"UPDATE projects SET {fields} WHERE id = ?", values)

    @staticmethod
    def delete(project_id: int):
        """Delete project and all related data"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM conversations WHERE project_id = ?", (project_id,))
            cursor.execute("DELETE FROM versions WHERE project_id = ?", (project_id,))
            cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))


class VersionDB:
    """Version database operations"""

    @staticmethod
    def create(project_id: int, version_number: int, config: Dict[str, Any],
               theme_config: Optional[Dict[str, Any]] = None) -> int:
        """Create a new version"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO versions
                   (project_id, version_number, config, theme_config)
                   VALUES (?, ?, ?, ?)""",
                (project_id, version_number, json.dumps(config),
                 json.dumps(theme_config) if theme_config else None)
            )
            return cursor.lastrowid

    @staticmethod
    def get(version_id: int) -> Optional[Dict[str, Any]]:
        """Get version by ID"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM versions WHERE id = ?", (version_id,))
            row = cursor.fetchone()
            if row:
                data = dict(row)
                data['config'] = json.loads(data['config'])
                if data['theme_config']:
                    data['theme_config'] = json.loads(data['theme_config'])
                return data
            return None

    @staticmethod
    def get_by_project(project_id: int) -> List[Dict[str, Any]]:
        """Get all versions for a project"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM versions WHERE project_id = ? ORDER BY version_number DESC",
                (project_id,)
            )
            versions = []
            for row in cursor.fetchall():
                data = dict(row)
                data['config'] = json.loads(data['config'])
                if data['theme_config']:
                    data['theme_config'] = json.loads(data['theme_config'])
                versions.append(data)
            return versions

    @staticmethod
    def update(version_id: int, **kwargs):
        """Update version"""
        with get_db() as conn:
            cursor = conn.cursor()
            # Convert dicts to JSON strings
            if 'config' in kwargs:
                kwargs['config'] = json.dumps(kwargs['config'])
            if 'theme_config' in kwargs and kwargs['theme_config']:
                kwargs['theme_config'] = json.dumps(kwargs['theme_config'])

            fields = ", ".join(f"{k} = ?" for k in kwargs.keys())
            values = list(kwargs.values()) + [version_id]
            cursor.execute(f"UPDATE versions SET {fields} WHERE id = ?", values)


class ConversationDB:
    """Conversation database operations"""

    @staticmethod
    def add_message(project_id: int, role: str, message: str, version_id: Optional[int] = None):
        """Add a message to conversation"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO conversations (project_id, version_id, role, message) VALUES (?, ?, ?, ?)",
                (project_id, version_id, role, message)
            )

    @staticmethod
    def get_history(project_id: int, version_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get conversation history"""
        with get_db() as conn:
            cursor = conn.cursor()
            if version_id:
                cursor.execute(
                    "SELECT * FROM conversations WHERE project_id = ? AND version_id = ? ORDER BY timestamp ASC",
                    (project_id, version_id)
                )
            else:
                cursor.execute(
                    "SELECT * FROM conversations WHERE project_id = ? ORDER BY timestamp ASC",
                    (project_id,)
                )
            return [dict(row) for row in cursor.fetchall()]


class PackageCacheDB:
    """Package cache database operations"""

    @staticmethod
    def add(package_name: str, version: Optional[str] = None,
            cached_path: Optional[str] = None):
        """Add package to cache"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT OR REPLACE INTO package_cache
                   (package_name, version, cached_path, last_used)
                   VALUES (?, ?, ?, ?)""",
                (package_name, version, cached_path, datetime.now().isoformat())
            )

    @staticmethod
    def get(package_name: str) -> Optional[Dict[str, Any]]:
        """Get cached package"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM package_cache WHERE package_name = ?", (package_name,))
            row = cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    def update_last_used(package_name: str):
        """Update last used timestamp"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE package_cache SET last_used = ? WHERE package_name = ?",
                (datetime.now().isoformat(), package_name)
            )
