# Copyright (c) 2026 Ryusei Matsui
#
# This software is released under the MIT License.
from pathlib import Path

import pytest

from mcp_youtube_transcript import server


@pytest.mark.anyio
async def test_server_lifespan_initializes_store(tmp_path: Path) -> None:
    mcp = server(storage_path=tmp_path / "transcripts.db")
    async with mcp.settings.lifespan(mcp) as app_ctx:  # type: ignore
        assert app_ctx.store.path == tmp_path / "transcripts.db"
        assert app_ctx.store.list_videos() == []
