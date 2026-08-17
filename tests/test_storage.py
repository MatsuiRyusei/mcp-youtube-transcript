# Copyright (c) 2026 Ryusei Matsui
#
# This software is released under the MIT License.
from pathlib import Path

from mcp_youtube_transcript.storage import StoredSnippet, TranscriptStore


def test_ingest_search_segment_and_remove(tmp_path: Path) -> None:
    store = TranscriptStore(tmp_path / "transcripts.db")
    try:
        count = store.ingest(
            video_id="abc123",
            url="https://www.youtube.com/watch?v=abc123",
            title="Example",
            language="en",
            snippets=[
                StoredSnippet("hello world", 0.0, 10.0),
                StoredSnippet("react server components", 20.0, 10.0),
                StoredSnippet("sqlite full text search", 120.0, 10.0),
            ],
            chunk_seconds=60,
        )
        assert count == 2

        results = store.search("react", video_id="abc123")
        assert len(results) == 1
        assert results[0].video_id == "abc123"
        assert "react server components" in results[0].text

        segments = store.get_segment("abc123", 15.0, 30.0)
        assert len(segments) == 1
        assert segments[0].start == 0.0
        assert segments[0].end == 30.0

        videos = store.list_videos()
        assert len(videos) == 1
        assert videos[0]["video_id"] == "abc123"

        assert store.remove_video("abc123") is True
        assert store.list_videos() == []
        assert store.remove_video("abc123") is False
    finally:
        store.close()


def test_reingest_replaces_existing_segments(tmp_path: Path) -> None:
    store = TranscriptStore(tmp_path / "transcripts.db")
    try:
        store.ingest(
            video_id="abc123",
            url="https://youtu.be/abc123",
            title="Old title",
            language="en",
            snippets=[StoredSnippet("old transcript", 0.0, 10.0)],
        )
        store.ingest(
            video_id="abc123",
            url="https://youtu.be/abc123",
            title="New title",
            language="en",
            snippets=[StoredSnippet("new transcript", 0.0, 10.0)],
        )

        assert store.search("old") == []
        results = store.search("new")
        assert len(results) == 1
        assert results[0].title == "New title"
    finally:
        store.close()
