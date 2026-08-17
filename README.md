# YouTube Transcript MCP Server — Video Context Fork

[日本語 README](README.ja.md)

This repository is a fork of `jkawamoto/mcp-youtube-transcript`, licensed under the MIT License. The original transcript retrieval behavior is retained while this fork adds a local, searchable video-context layer intended for Codex, Antigravity, GitHub Copilot, and other MCP clients.

## Current development status

Branch: `agent/video-context-v0.1`

### Implemented

- Existing transcript tools remain available.
- SQLite-backed local transcript cache.
- SQLite FTS5 full-text search; no external vector database required.
- Transcript chunking by approximate time window (default: 90 seconds).
- Re-ingesting a video replaces its cached transcript.
- MCP tools for ingesting, searching, retrieving a time range, listing cached videos, and removing cached videos.
- Configurable database path through `--storage-path` or `MCP_YOUTUBE_TRANSCRIPT_DB`.
- Initial unit tests for the storage/search layer.

### Not implemented yet

- Audio fallback for videos where usable subtitles cannot be retrieved.
- `ffmpeg` integration.
- Speech-to-text fallback.
- Scene-change detection and on-demand frame extraction.
- Vision analysis of video frames.
- Embedding or hybrid FTS + semantic search.
- Channel/playlist ingestion.
- Production validation across Codex, Antigravity, and GitHub Copilot.

### Next planned work

1. Run the complete upstream test suite and fix compatibility regressions.
2. Add MCP-level tests for the new tools.
3. Validate installation/configuration with Codex, Antigravity, and GitHub Copilot.
4. Add timestamp-friendly result URLs and better search result formatting.
5. Add subtitle-missing fallback using local media/audio processing where permitted.

## Tools

### Original tools

- `get_transcript(url, lang?, next_cursor?)`
- `get_timed_transcript(url, lang?, next_cursor?)`
- `get_video_info(url)`
- `get_available_languages(url)`

### Video context tools added by this fork

#### `ingest_video`
Fetches a timed transcript and stores it in the local SQLite cache.

Parameters:
- `url`: YouTube video URL.
- `lang`: Preferred transcript language. Default: `en`.
- `chunk_seconds`: Approximate maximum chunk duration. Default: `90`.

#### `search_video`
Searches cached transcript chunks using SQLite FTS5.

Parameters:
- `query`: Full-text search query.
- `video_id`: Optional YouTube video ID filter.
- `limit`: Maximum result count. Default: `5`.

Results include video ID, title, source URL, start/end timestamps, text, and FTS rank.

#### `get_segment`
Returns cached transcript chunks overlapping a requested time range.

#### `list_cached_videos`
Lists videos currently stored in the local database.

#### `remove_cached_video`
Removes one video and its transcript chunks from the cache.

## Storage

The default database is:

```text
~/.cache/mcp-youtube-transcript/transcripts.db
```

Override it with:

```bash
mcp-youtube-transcript --storage-path /path/to/transcripts.db
```

or:

```bash
export MCP_YOUTUBE_TRANSCRIPT_DB=/path/to/transcripts.db
```

Because the database is local, multiple MCP clients on the same machine can point to the same file and share an ingested video library.

## Example MCP configuration

During development, point the MCP client at this fork/branch:

```json
{
  "mcpServers": {
    "youtube-video-context": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/MatsuiRyusei/mcp-youtube-transcript@agent/video-context-v0.1",
        "mcp-youtube-transcript"
      ]
    }
  }
}
```

The exact configuration location differs between MCP clients.

## Design direction

The intended architecture is audio/text first and vision on demand:

```text
YouTube URL
  -> usable transcript when available
  -> timed chunks
  -> SQLite + FTS5
  -> only relevant chunks returned to the LLM

If transcript retrieval is unavailable (future work):
  -> permitted local media/audio source
  -> ffmpeg audio extraction
  -> speech-to-text
  -> same SQLite index

If visual context is required (future work):
  -> inspect only the relevant time range
  -> scene/frame extraction
  -> vision analysis on demand
```

This keeps model context usage low instead of sending entire long transcripts or videos on every question.

## Development notes

The fork intentionally avoids adding a vector database in v0.1. Python's standard `sqlite3` module and SQLite FTS5 are used first so the MCP remains easy to install and portable. Embeddings can be added later if lexical search proves insufficient.

## License and attribution

This project remains under the MIT License. Original copyright and license notices from Junpei Kawamoto are preserved in inherited source files. New fork-specific code includes its own copyright notice while remaining under the same MIT License.
