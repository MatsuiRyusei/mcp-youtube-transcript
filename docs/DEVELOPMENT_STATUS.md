# Development Status / 開発状況

This file complements `README.md` and `README.ja.md` with a compact implementation checklist.
このファイルは `README.md` / `README.ja.md` を補完する簡易チェックリストです。

## v0.1

- [x] Fork upstream MIT project / MITライセンスfork作成
- [x] Create development branch / 開発ブランチ作成
- [x] Add SQLite transcript cache / SQLite字幕キャッシュ追加
- [x] Add SQLite FTS5 search / FTS5全文検索追加
- [x] Add timed transcript chunking / 時間ベースchunk化
- [x] Add `ingest_video`
- [x] Add `search_video`
- [x] Add `get_segment`
- [x] Add `list_cached_videos`
- [x] Add `remove_cached_video`
- [x] Add configurable DB path / DB保存先指定
- [x] Add storage unit tests / storage単体テスト追加
- [x] Add English and Japanese README status / 英日README更新
- [ ] Run full upstream test suite / upstream全テスト実行
- [ ] Add MCP-level tests / MCPレベルテスト追加
- [ ] Validate Codex configuration / Codex動作検証
- [ ] Validate Antigravity configuration / Antigravity動作検証
- [ ] Validate GitHub Copilot configuration / GitHub Copilot動作検証
- [ ] Add timestamp deep links / YouTube時刻リンク追加

## Later phases / 今後

- [ ] Subtitle-unavailable fallback / 字幕取得不可fallback
- [ ] ffmpeg integration
- [ ] Speech-to-text fallback / 音声認識fallback
- [ ] Scene detection / シーン検出
- [ ] On-demand frame extraction / 必要箇所frame抽出
- [ ] Vision analysis / 映像理解
- [ ] Hybrid lexical + semantic retrieval / FTS + semantic検索
- [ ] Channel or playlist ingestion / チャンネル・プレイリスト取り込み
