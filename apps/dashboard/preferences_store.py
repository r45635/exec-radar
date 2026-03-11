"""Persistence layer for dashboard job preferences.

Stores favorites and dismissed jobs in a small SQLite database so
preferences survive reloads and are shared by all clients using the
same backend instance.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

_ALLOWED_STATUS = {"favorite", "dismissed"}


class PreferenceStore:
    """Simple SQLite store for job preferences."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dashboard_preferences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                    UNIQUE(user_id, job_id)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_dashboard_prefs_user "
                "ON dashboard_preferences(user_id)"
            )

    def get_preferences(self, *, user_id: str) -> tuple[set[str], set[str]]:
        favorites: set[str] = set()
        dismissed: set[str] = set()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT job_id, status FROM dashboard_preferences WHERE user_id = ?",
                (user_id,),
            ).fetchall()
        for row in rows:
            status = row["status"]
            if status == "favorite":
                favorites.add(row["job_id"])
            elif status == "dismissed":
                dismissed.add(row["job_id"])
        return favorites, dismissed

    def toggle(self, *, user_id: str, job_id: str, action: str) -> tuple[bool, bool]:
        """Toggle favorite/dismissed status and return current booleans.

        Returns:
            (favorited, dismissed)
        """
        if action not in _ALLOWED_STATUS:
            msg = f"Unsupported preference action: {action}"
            raise ValueError(msg)

        with self._connect() as conn:
            existing = conn.execute(
                "SELECT status FROM dashboard_preferences WHERE user_id = ? AND job_id = ?",
                (user_id, job_id),
            ).fetchone()

            if existing is None:
                conn.execute(
                    "INSERT INTO dashboard_preferences(user_id, job_id, status) VALUES(?, ?, ?)",
                    (user_id, job_id, action),
                )
                status = action
            elif existing["status"] == action:
                conn.execute(
                    "DELETE FROM dashboard_preferences WHERE user_id = ? AND job_id = ?",
                    (user_id, job_id),
                )
                status = ""
            else:
                conn.execute(
                    """
                    UPDATE dashboard_preferences
                    SET status = ?, updated_at = datetime('now')
                    WHERE user_id = ? AND job_id = ?
                    """,
                    (action, user_id, job_id),
                )
                status = action

        return status == "favorite", status == "dismissed"
