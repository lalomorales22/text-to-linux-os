"""SQLite persistence layer.

Plain sqlite3 with a connection-per-operation context manager. Column names in
dynamic UPDATE statements are validated against per-table whitelists so caller
kwargs can never inject SQL.
"""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator, Optional

from backend.config import get_settings


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def get_db() -> Iterator[sqlite3.Connection]:
    settings = get_settings()
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.database_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    draft_config TEXT,
    theme_config TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    config TEXT NOT NULL,
    theme_config TEXT,
    iso_path TEXT,
    iso_size INTEGER,
    iso_sha256 TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS builds (
    id TEXT PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    version_id INTEGER NOT NULL REFERENCES versions(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'queued',
    progress INTEGER NOT NULL DEFAULT 0,
    step TEXT NOT NULL DEFAULT 'Queued',
    log_path TEXT,
    error TEXT,
    boot_test TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS packages (
    name TEXT PRIMARY KEY,
    version TEXT,
    installed_size_kb INTEGER,
    download_size_bytes INTEGER,
    section TEXT,
    description TEXT
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def init_db() -> None:
    with get_db() as conn:
        conn.executescript(SCHEMA)


def _update(conn: sqlite3.Connection, table: str, allowed: set[str],
            row_id: Any, id_column: str, fields: dict[str, Any]) -> None:
    bad = set(fields) - allowed
    if bad:
        raise ValueError(f"Unknown column(s) for {table}: {', '.join(sorted(bad))}")
    if not fields:
        return
    assignments = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(
        f"UPDATE {table} SET {assignments} WHERE {id_column} = ?",
        [*fields.values(), row_id],
    )


class ProjectDB:
    UPDATABLE = {"name", "status", "draft_config", "theme_config", "updated_at"}

    @staticmethod
    def create(name: str, status: str = "draft") -> int:
        with get_db() as conn:
            cur = conn.execute(
                "INSERT INTO projects (name, status, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (name, status, _now(), _now()),
            )
            return cur.lastrowid

    @staticmethod
    def get(project_id: int) -> Optional[dict]:
        with get_db() as conn:
            row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            return ProjectDB._hydrate(row) if row else None

    @staticmethod
    def list_all() -> list[dict]:
        with get_db() as conn:
            rows = conn.execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall()
            return [ProjectDB._hydrate(r) for r in rows]

    @staticmethod
    def update(project_id: int, **fields: Any) -> None:
        for key in ("draft_config", "theme_config"):
            if key in fields and isinstance(fields[key], (dict, list)):
                fields[key] = json.dumps(fields[key])
        fields["updated_at"] = _now()
        with get_db() as conn:
            _update(conn, "projects", ProjectDB.UPDATABLE, project_id, "id", fields)

    @staticmethod
    def delete(project_id: int) -> None:
        with get_db() as conn:
            conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))

    @staticmethod
    def _hydrate(row: sqlite3.Row) -> dict:
        data = dict(row)
        for key in ("draft_config", "theme_config"):
            data[key] = json.loads(data[key]) if data.get(key) else None
        return data


class VersionDB:
    UPDATABLE = {"config", "theme_config", "iso_path", "iso_size", "iso_sha256"}

    @staticmethod
    def create(project_id: int, config: dict, theme_config: Optional[dict] = None) -> int:
        with get_db() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(version_number), 0) + 1 AS next FROM versions WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            cur = conn.execute(
                """INSERT INTO versions (project_id, version_number, config, theme_config, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (project_id, row["next"], json.dumps(config),
                 json.dumps(theme_config) if theme_config else None, _now()),
            )
            return cur.lastrowid

    @staticmethod
    def get(version_id: int) -> Optional[dict]:
        with get_db() as conn:
            row = conn.execute("SELECT * FROM versions WHERE id = ?", (version_id,)).fetchone()
            return VersionDB._hydrate(row) if row else None

    @staticmethod
    def latest_for_project(project_id: int) -> Optional[dict]:
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM versions WHERE project_id = ? ORDER BY version_number DESC LIMIT 1",
                (project_id,),
            ).fetchone()
            return VersionDB._hydrate(row) if row else None

    @staticmethod
    def list_for_project(project_id: int) -> list[dict]:
        with get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM versions WHERE project_id = ? ORDER BY version_number DESC",
                (project_id,),
            ).fetchall()
            return [VersionDB._hydrate(r) for r in rows]

    @staticmethod
    def update(version_id: int, **fields: Any) -> None:
        for key in ("config", "theme_config"):
            if key in fields and isinstance(fields[key], (dict, list)):
                fields[key] = json.dumps(fields[key])
        with get_db() as conn:
            _update(conn, "versions", VersionDB.UPDATABLE, version_id, "id", fields)

    @staticmethod
    def _hydrate(row: sqlite3.Row) -> dict:
        data = dict(row)
        data["config"] = json.loads(data["config"])
        data["theme_config"] = json.loads(data["theme_config"]) if data.get("theme_config") else None
        return data


class ConversationDB:
    @staticmethod
    def add_message(project_id: int, role: str, content: str) -> None:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO conversations (project_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (project_id, role, content, _now()),
            )

    @staticmethod
    def get_history(project_id: int) -> list[dict]:
        with get_db() as conn:
            rows = conn.execute(
                "SELECT role, content, created_at FROM conversations WHERE project_id = ? ORDER BY id ASC",
                (project_id,),
            ).fetchall()
            return [dict(r) for r in rows]


class BuildDB:
    UPDATABLE = {"status", "progress", "step", "log_path", "error", "boot_test", "updated_at"}
    ACTIVE_STATUSES = ("queued", "running", "testing")

    @staticmethod
    def create(build_id: str, project_id: int, version_id: int, log_path: str) -> None:
        with get_db() as conn:
            conn.execute(
                """INSERT INTO builds (id, project_id, version_id, status, log_path, created_at, updated_at)
                   VALUES (?, ?, ?, 'queued', ?, ?, ?)""",
                (build_id, project_id, version_id, log_path, _now(), _now()),
            )

    @staticmethod
    def get(build_id: str) -> Optional[dict]:
        with get_db() as conn:
            row = conn.execute("SELECT * FROM builds WHERE id = ?", (build_id,)).fetchone()
            return BuildDB._hydrate(row) if row else None

    @staticmethod
    def update(build_id: str, **fields: Any) -> None:
        if "boot_test" in fields and isinstance(fields["boot_test"], dict):
            fields["boot_test"] = json.dumps(fields["boot_test"])
        fields["updated_at"] = _now()
        with get_db() as conn:
            _update(conn, "builds", BuildDB.UPDATABLE, build_id, "id", fields)

    @staticmethod
    def active_for_project(project_id: int) -> Optional[dict]:
        with get_db() as conn:
            row = conn.execute(
                f"""SELECT * FROM builds WHERE project_id = ?
                    AND status IN ({','.join('?' * len(BuildDB.ACTIVE_STATUSES))})
                    ORDER BY created_at DESC LIMIT 1""",
                (project_id, *BuildDB.ACTIVE_STATUSES),
            ).fetchone()
            return BuildDB._hydrate(row) if row else None

    @staticmethod
    def latest_for_project(project_id: int) -> Optional[dict]:
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM builds WHERE project_id = ? ORDER BY created_at DESC LIMIT 1",
                (project_id,),
            ).fetchone()
            return BuildDB._hydrate(row) if row else None

    @staticmethod
    def mark_stale_builds_failed() -> int:
        """After a server restart no build subprocess survives; mark leftovers failed."""
        with get_db() as conn:
            cur = conn.execute(
                f"""UPDATE builds SET status = 'failed',
                    error = 'Build interrupted by server restart', updated_at = ?
                    WHERE status IN ({','.join('?' * len(BuildDB.ACTIVE_STATUSES))})""",
                (_now(), *BuildDB.ACTIVE_STATUSES),
            )
            conn.execute(
                f"""UPDATE projects SET status = 'failed', updated_at = ?
                    WHERE status = 'building' """,
                (_now(),),
            )
            return cur.rowcount

    @staticmethod
    def _hydrate(row: sqlite3.Row) -> dict:
        data = dict(row)
        data["boot_test"] = json.loads(data["boot_test"]) if data.get("boot_test") else None
        return data


class PackageDB:
    @staticmethod
    def replace_all(rows: list[tuple]) -> None:
        """rows: (name, version, installed_size_kb, download_size_bytes, section, description)"""
        with get_db() as conn:
            conn.execute("DELETE FROM packages")
            conn.executemany(
                "INSERT OR REPLACE INTO packages VALUES (?, ?, ?, ?, ?, ?)", rows
            )

    @staticmethod
    def get(name: str) -> Optional[dict]:
        with get_db() as conn:
            row = conn.execute("SELECT * FROM packages WHERE name = ?", (name,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_many(names: list[str]) -> dict[str, dict]:
        if not names:
            return {}
        with get_db() as conn:
            placeholders = ",".join("?" * len(names))
            rows = conn.execute(
                f"SELECT * FROM packages WHERE name IN ({placeholders})", names
            ).fetchall()
            return {r["name"]: dict(r) for r in rows}

    @staticmethod
    def search(query: str, limit: int = 25) -> list[dict]:
        with get_db() as conn:
            rows = conn.execute(
                """SELECT * FROM packages WHERE name LIKE ? ORDER BY
                   CASE WHEN name = ? THEN 0 WHEN name LIKE ? THEN 1 ELSE 2 END, name LIMIT ?""",
                (f"%{query}%", query, f"{query}%", limit),
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def count() -> int:
        with get_db() as conn:
            return conn.execute("SELECT COUNT(*) AS n FROM packages").fetchone()["n"]


class MetaDB:
    @staticmethod
    def get(key: str) -> Optional[str]:
        with get_db() as conn:
            row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else None

    @staticmethod
    def set(key: str, value: str) -> None:
        with get_db() as conn:
            conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value))
