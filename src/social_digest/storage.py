from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from .models import Post
from .utils import ensure_parent


class Storage:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        ensure_parent(db_path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_name TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    author TEXT NOT NULL,
                    published_at TEXT NOT NULL,
                    inserted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(source_name, external_id)
                );

                CREATE TABLE IF NOT EXISTS state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )

    def upsert_posts(self, posts: list[Post]) -> list[Post]:
        inserted: list[Post] = []
        with self._connect() as conn:
            for post in posts:
                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO items (
                        source_name, platform, external_id, url, title, content,
                        summary, author, published_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        post.source_name,
                        post.platform,
                        post.external_id,
                        post.url,
                        post.title,
                        post.content,
                        post.summary,
                        post.author,
                        post.published_at.isoformat(),
                    ),
                )
                if cursor.rowcount:
                    inserted.append(post)
        return inserted

    def recent_posts(self, since: datetime) -> list[Post]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT source_name, platform, external_id, url, title, content,
                       summary, author, published_at
                FROM items
                WHERE published_at >= ?
                ORDER BY published_at DESC
                """,
                (since.isoformat(),),
            ).fetchall()
        return [self._row_to_post(row) for row in rows]

    def get_state(self, key: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM state WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def set_state(self, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO state (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )

    @staticmethod
    def _row_to_post(row: sqlite3.Row) -> Post:
        return Post(
            source_name=row["source_name"],
            platform=row["platform"],
            external_id=row["external_id"],
            url=row["url"],
            title=row["title"],
            content=row["content"],
            summary=row["summary"],
            author=row["author"],
            published_at=datetime.fromisoformat(row["published_at"]),
        )
