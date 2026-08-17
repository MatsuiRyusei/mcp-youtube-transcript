# Copyright (c) 2025-2026 Junpei Kawamoto
# Copyright (c) 2026 Ryusei Matsui
#
# This software is released under the MIT License.
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class StoredSnippet:
    text: str
    start: float
    duration: float


@dataclass(frozen=True)
class SearchResult:
    video_id: str
    title: str
    url: str
    start: float
    end: float
    text: str
    rank: float


class TranscriptStore:
    """SQLite-backed transcript cache with FTS5 search."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def close(self) -> None:
        self.conn.close()

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE IF NOT EXISTS videos (
                video_id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                title TEXT NOT NULL,
                language TEXT NOT NULL,
                ingested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS segments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT NOT NULL REFERENCES videos(video_id) ON DELETE CASCADE,
                start REAL NOT NULL,
                end REAL NOT NULL,
                text TEXT NOT NULL
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS segments_fts USING fts5(
                text,
                content='segments',
                content_rowid='id'
            );
            CREATE TRIGGER IF NOT EXISTS segments_ai AFTER INSERT ON segments BEGIN
                INSERT INTO segments_fts(rowid, text) VALUES (new.id, new.text);
            END;
            CREATE TRIGGER IF NOT EXISTS segments_ad AFTER DELETE ON segments BEGIN
                INSERT INTO segments_fts(segments_fts, rowid, text) VALUES('delete', old.id, old.text);
            END;
            CREATE TRIGGER IF NOT EXISTS segments_au AFTER UPDATE ON segments BEGIN
                INSERT INTO segments_fts(segments_fts, rowid, text) VALUES('delete', old.id, old.text);
                INSERT INTO segments_fts(rowid, text) VALUES (new.id, new.text);
            END;
            """
        )
        self.conn.commit()

    def ingest(
        self,
        *,
        video_id: str,
        url: str,
        title: str,
        language: str,
        snippets: Iterable[StoredSnippet],
        chunk_seconds: float = 90.0,
    ) -> int:
        chunks: list[tuple[float, float, str]] = []
        chunk_text: list[str] = []
        chunk_start: float | None = None
        chunk_end = 0.0

        for snippet in snippets:
            if chunk_start is None:
                chunk_start = snippet.start
            projected_end = snippet.start + snippet.duration
            if chunk_text and projected_end - chunk_start > chunk_seconds:
                chunks.append((chunk_start, chunk_end, " ".join(chunk_text)))
                chunk_text = []
                chunk_start = snippet.start
            chunk_text.append(snippet.text)
            chunk_end = projected_end

        if chunk_text and chunk_start is not None:
            chunks.append((chunk_start, chunk_end, " ".join(chunk_text)))

        with self.conn:
            self.conn.execute("DELETE FROM videos WHERE video_id = ?", (video_id,))
            self.conn.execute(
                "INSERT INTO videos(video_id, url, title, language) VALUES (?, ?, ?, ?)",
                (video_id, url, title, language),
            )
            self.conn.executemany(
                "INSERT INTO segments(video_id, start, end, text) VALUES (?, ?, ?, ?)",
                [(video_id, start, end, text) for start, end, text in chunks],
            )
        return len(chunks)

    def search(self, query: str, *, video_id: str | None = None, limit: int = 5) -> list[SearchResult]:
        params: list[object] = [query]
        where = "segments_fts MATCH ?"
        if video_id is not None:
            where += " AND s.video_id = ?"
            params.append(video_id)
        params.append(limit)
        rows = self.conn.execute(
            f"""
            SELECT s.video_id, v.title, v.url, s.start, s.end, s.text,
                   bm25(segments_fts) AS rank
            FROM segments_fts
            JOIN segments s ON s.id = segments_fts.rowid
            JOIN videos v ON v.video_id = s.video_id
            WHERE {where}
            ORDER BY rank
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [SearchResult(**dict(row)) for row in rows]

    def get_segment(self, video_id: str, start: float, end: float) -> list[SearchResult]:
        rows = self.conn.execute(
            """
            SELECT s.video_id, v.title, v.url, s.start, s.end, s.text, 0.0 AS rank
            FROM segments s
            JOIN videos v ON v.video_id = s.video_id
            WHERE s.video_id = ? AND s.end >= ? AND s.start <= ?
            ORDER BY s.start
            """,
            (video_id, start, end),
        ).fetchall()
        return [SearchResult(**dict(row)) for row in rows]

    def list_videos(self) -> list[dict[str, object]]:
        rows = self.conn.execute(
            "SELECT video_id, url, title, language, ingested_at FROM videos ORDER BY ingested_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]

    def remove_video(self, video_id: str) -> bool:
        with self.conn:
            cur = self.conn.execute("DELETE FROM videos WHERE video_id = ?", (video_id,))
        return cur.rowcount > 0
