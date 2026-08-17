#  __init__.py
#
#  Copyright (c) 2025-2026 Junpei Kawamoto
#  Copyright (c) 2026 Ryusei Matsui
#
#  This software is released under the MIT License.
#
#  http://opensource.org/licenses/mit-license.php
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache, partial
from itertools import islice
from pathlib import Path
from typing import Any, Final
from urllib.parse import parse_qs, urlparse

import humanize
import requests
from bs4 import BeautifulSoup
from mcp import ServerSession
from mcp.server.mcpserver import Context, MCPServer
from pydantic import AwareDatetime, BaseModel, Field
from youtube_transcript_api import FetchedTranscriptSnippet, YouTubeTranscriptApi
from youtube_transcript_api.proxies import GenericProxyConfig, ProxyConfig, WebshareProxyConfig
from yt_dlp import YoutubeDL
from yt_dlp.extractor.youtube import YoutubeIE

from .storage import SearchResult, StoredSnippet, TranscriptStore

DEFAULT_STORAGE_PATH = Path.home() / ".cache" / "mcp-youtube-transcript" / "transcripts.db"


@dataclass(frozen=True)
class AppContext:
    http_client: requests.Session
    ytt_api: YouTubeTranscriptApi
    dlp: YoutubeDL
    store: TranscriptStore


@asynccontextmanager
async def _app_lifespan(
    _server: MCPServer, proxy_config: ProxyConfig | None, storage_path: str | Path
) -> AsyncIterator[AppContext]:
    ytdlp_params: dict[str, Any] = {"quiet": True}
    ytdlp_params.update(_proxy_config_to_ytdlp_params(proxy_config))

    store = TranscriptStore(storage_path)
    try:
        with requests.Session() as http_client, YoutubeDL(params=ytdlp_params, auto_init=False) as dlp:
            ytt_api = YouTubeTranscriptApi(http_client=http_client, proxy_config=proxy_config)
            dlp.add_info_extractor(YoutubeIE())
            yield AppContext(http_client=http_client, ytt_api=ytt_api, dlp=dlp, store=store)
    finally:
        store.close()


class Transcript(BaseModel):
    title: str = Field(description="Title of the video")
    transcript: str = Field(description="Transcript of the video")
    next_cursor: str | None = Field(description="Cursor to retrieve the next page of the transcript", default=None)


class TranscriptSnippet(BaseModel):
    text: str = Field(description="Text of the transcript snippet")
    start: float = Field(description="The timestamp at which this transcript snippet appears on screen in seconds.")
    duration: float = Field(description="The duration of how long the snippet in seconds.")

    def __len__(self) -> int:
        return len(self.model_dump_json())

    @classmethod
    def from_fetched_transcript_snippet(
        cls: type[TranscriptSnippet], snippet: FetchedTranscriptSnippet
    ) -> TranscriptSnippet:
        return cls(text=snippet.text, start=snippet.start, duration=snippet.duration)


class TimedTranscript(BaseModel):
    title: str = Field(description="Title of the video")
    snippets: list[TranscriptSnippet] = Field(description="Transcript snippets of the video")
    next_cursor: str | None = Field(description="Cursor to retrieve the next page of the transcript", default=None)


class VideoInfo(BaseModel):
    title: str = Field(description="Title of the video")
    description: str = Field(description="Description of the video")
    uploader: str = Field(description="Uploader of the video")
    upload_date: AwareDatetime = Field(description="Upload date of the video")
    duration: str = Field(description="Duration of the video")


class IngestResult(BaseModel):
    video_id: str
    title: str
    chunks: int
    language: str


class CachedSearchResult(BaseModel):
    video_id: str
    title: str
    url: str
    start: float
    end: float
    text: str
    rank: float

    @classmethod
    def from_store(cls, result: SearchResult) -> CachedSearchResult:
        return cls(**result.__dict__)


def _parse_time_info(date: int, timestamp: int, duration: int) -> tuple[datetime, str]:
    parsed_date = datetime.strptime(str(date), "%Y%m%d").date()  # noqa: DTZ007
    parsed_time = datetime.strptime(str(timestamp), "%H%M%S%f").time()  # noqa: DTZ007
    upload_date = datetime.combine(parsed_date, parsed_time, timezone.utc)
    duration_str = humanize.naturaldelta(timedelta(seconds=duration))
    return upload_date, duration_str


def _proxy_config_to_ytdlp_params(proxy_config: ProxyConfig | None) -> dict[str, str]:
    if proxy_config is None:
        return {}
    proxy_dict = proxy_config.to_requests_dict()
    if proxy_dict.get("https"):
        return {"proxy": proxy_dict["https"]}
    if proxy_dict.get("http"):
        return {"proxy": proxy_dict["http"]}
    return {}


def _parse_video_id(url: str) -> str:
    parsed_url = urlparse(url)
    if parsed_url.hostname == "youtu.be":
        return parsed_url.path.lstrip("/")
    if parsed_url.path.startswith(("/shorts/", "/embed/", "/live/")):
        return parsed_url.path.split("/")[2]
    q = parse_qs(parsed_url.query).get("v")
    if q is None:
        raise ValueError(f"couldn't find a video ID from the provided URL: {url}.")
    return q[0]


@lru_cache
def _get_transcript_snippets(ctx: AppContext, video_id: str, lang: str) -> tuple[str, list[FetchedTranscriptSnippet]]:
    languages = ["en"] if lang == "en" else [lang, "en"]
    page = ctx.http_client.get(
        f"https://www.youtube.com/watch?v={video_id}", headers={"Accept-Language": ",".join(languages)}
    )
    page.raise_for_status()
    soup = BeautifulSoup(page.text, "html.parser")
    title = soup.title.string if soup.title and soup.title.string else "Transcript"
    transcripts = ctx.ytt_api.fetch(video_id, languages=languages)
    return title, transcripts.snippets


@lru_cache
def _get_video_info(ctx: AppContext, video_url: str) -> VideoInfo:
    res = ctx.dlp.extract_info(video_url, download=False)
    upload_date, duration = _parse_time_info(res["upload_date"], res["timestamp"], res["duration"])
    return VideoInfo(
        title=res["title"], description=res["description"], uploader=res["uploader"], upload_date=upload_date, duration=duration
    )


@lru_cache
def _get_available_languages(ctx: AppContext, video_id: str) -> list[str]:
    return [str(t) for t in ctx.ytt_api.list(video_id)]


def server(
    response_limit: int | None = None,
    webshare_proxy_username: str | None = None,
    webshare_proxy_password: str | None = None,
    http_proxy: str | None = None,
    https_proxy: str | None = None,
    storage_path: str | Path = DEFAULT_STORAGE_PATH,
) -> MCPServer:
    """Initializes the MCP server."""
    proxy_config: ProxyConfig | None = None
    if webshare_proxy_username and webshare_proxy_password:
        proxy_config = WebshareProxyConfig(webshare_proxy_username, webshare_proxy_password)
    elif http_proxy or https_proxy:
        proxy_config = GenericProxyConfig(http_proxy, https_proxy)

    mcp = MCPServer(
        "Youtube Transcript",
        lifespan=partial(_app_lifespan, proxy_config=proxy_config, storage_path=storage_path),
    )

    @mcp.tool()
    async def get_transcript(
        ctx: Context[ServerSession, AppContext],
        url: str = Field(description="The URL of the YouTube video"),
        lang: str = Field(description="The preferred language for the transcript", default="en"),
        next_cursor: str | None = Field(description="Cursor to retrieve the next page of the transcript", default=None),
    ) -> Transcript:
        title, snippets = _get_transcript_snippets(ctx.request_context.lifespan_context, _parse_video_id(url), lang)
        transcripts = (item.text for item in snippets)
        if response_limit is None or response_limit <= 0:
            return Transcript(title=title, transcript="\n".join(transcripts))
        res = ""
        cursor = None
        for i, line in islice(enumerate(transcripts), int(next_cursor or 0), None):
            if len(res) + len(line) + 1 > response_limit:
                cursor = str(i)
                break
            res += f"{line}\n"
        return Transcript(title=title, transcript=res[:-1], next_cursor=cursor)

    @mcp.tool()
    async def get_timed_transcript(
        ctx: Context[ServerSession, AppContext],
        url: str = Field(description="The URL of the YouTube video"),
        lang: str = Field(description="The preferred language for the transcript", default="en"),
        next_cursor: str | None = Field(description="Cursor to retrieve the next page of the transcript", default=None),
    ) -> TimedTranscript:
        title, snippets = _get_transcript_snippets(ctx.request_context.lifespan_context, _parse_video_id(url), lang)
        if response_limit is None or response_limit <= 0:
            return TimedTranscript(title=title, snippets=[TranscriptSnippet.from_fetched_transcript_snippet(s) for s in snippets])
        res = []
        size = len(title) + 1
        cursor = None
        for i, s in islice(enumerate(snippets), int(next_cursor or 0), None):
            snippet = TranscriptSnippet.from_fetched_transcript_snippet(s)
            if size + len(snippet) + 1 > response_limit:
                cursor = str(i)
                break
            res.append(snippet)
            size += len(snippet) + 1
        return TimedTranscript(title=title, snippets=res, next_cursor=cursor)

    @mcp.tool()
    def get_video_info(ctx: Context[ServerSession, AppContext], url: str = Field(description="The URL of the YouTube video")) -> VideoInfo:
        return _get_video_info(ctx.request_context.lifespan_context, url)

    @mcp.tool()
    def get_available_languages(
        ctx: Context[ServerSession, AppContext], url: str = Field(description="The URL of the YouTube video")
    ) -> list[str]:
        return _get_available_languages(ctx.request_context.lifespan_context, _parse_video_id(url))

    @mcp.tool()
    async def ingest_video(
        ctx: Context[ServerSession, AppContext],
        url: str = Field(description="The URL of the YouTube video to cache"),
        lang: str = Field(description="Preferred transcript language", default="en"),
        chunk_seconds: float = Field(description="Approximate maximum duration of a cached chunk", default=90.0),
    ) -> IngestResult:
        app = ctx.request_context.lifespan_context
        video_id = _parse_video_id(url)
        title, snippets = _get_transcript_snippets(app, video_id, lang)
        chunks = app.store.ingest(
            video_id=video_id,
            url=url,
            title=title,
            language=lang,
            snippets=(StoredSnippet(text=s.text, start=s.start, duration=s.duration) for s in snippets),
            chunk_seconds=chunk_seconds,
        )
        return IngestResult(video_id=video_id, title=title, chunks=chunks, language=lang)

    @mcp.tool()
    def search_video(
        ctx: Context[ServerSession, AppContext],
        query: str = Field(description="Full-text query to search cached transcripts"),
        video_id: str | None = Field(description="Optional YouTube video ID to restrict the search", default=None),
        limit: int = Field(description="Maximum number of matches", default=5),
    ) -> list[CachedSearchResult]:
        return [CachedSearchResult.from_store(r) for r in ctx.request_context.lifespan_context.store.search(query, video_id=video_id, limit=limit)]

    @mcp.tool()
    def get_segment(
        ctx: Context[ServerSession, AppContext],
        video_id: str = Field(description="YouTube video ID"),
        start: float = Field(description="Start time in seconds"),
        end: float = Field(description="End time in seconds"),
    ) -> list[CachedSearchResult]:
        return [CachedSearchResult.from_store(r) for r in ctx.request_context.lifespan_context.store.get_segment(video_id, start, end)]

    @mcp.tool()
    def list_cached_videos(ctx: Context[ServerSession, AppContext]) -> list[dict[str, object]]:
        return ctx.request_context.lifespan_context.store.list_videos()

    @mcp.tool()
    def remove_cached_video(
        ctx: Context[ServerSession, AppContext], video_id: str = Field(description="YouTube video ID to remove")
    ) -> bool:
        return ctx.request_context.lifespan_context.store.remove_video(video_id)

    return mcp


__all__: Final = [
    "CachedSearchResult",
    "IngestResult",
    "TimedTranscript",
    "Transcript",
    "TranscriptSnippet",
    "VideoInfo",
    "server",
]
