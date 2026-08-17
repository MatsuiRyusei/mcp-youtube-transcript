# YouTube Transcript MCP Server — Video Context Fork

[English README](README.md)

このリポジトリは `jkawamoto/mcp-youtube-transcript` のMITライセンスforkです。元の字幕取得機能を維持しつつ、Codex / Antigravity / GitHub Copilot など複数のMCPクライアントから共通利用できる、ローカルの動画コンテキスト検索機能を追加しています。

## 現在の開発状況

作業ブランチ: `agent/video-context-v0.1`

### 実装済み

- 元の字幕取得系MCPツールを維持。
- SQLiteベースのローカル字幕キャッシュ。
- SQLite FTS5による全文検索。外部Vector DBは不要。
- おおよその時間幅で字幕をchunk化（デフォルト90秒）。
- 同じ動画を再取り込みした場合は既存キャッシュを置換。
- 動画の取り込み、検索、時間範囲取得、キャッシュ一覧、削除のMCPツールを追加。
- `--storage-path` または `MCP_YOUTUBE_TRANSCRIPT_DB` でDB保存先を変更可能。
- storage/search層の初期ユニットテストを追加。

### 未実装

- 利用可能な字幕を取得できない動画向けの音声fallback。
- `ffmpeg` 統合。
- 音声認識による文字起こしfallback。
- シーンチェンジ検出と必要箇所のみのframe抽出。
- 画像/映像フレームのVision解析。
- Embedding、または FTS + semantic search のハイブリッド検索。
- チャンネル/プレイリスト単位の取り込み。
- Codex / Antigravity / GitHub Copilot 3環境での本番相当の動作検証。

### 次に進める作業

1. upstream由来の既存テスト一式を実行し、互換性の問題を修正する。
2. 新しいMCP toolに対するMCPレベルのテストを追加する。
3. Codex / Antigravity / GitHub Copilot の各環境で設定・起動を検証する。
4. 検索結果にYouTubeの該当時刻へ飛びやすい情報を追加する。
5. 字幕取得不可時のfallbackを、利用権限のあるローカルメディア/音声を対象として追加する。

## MCPツール

### 元からあるツール

- `get_transcript(url, lang?, next_cursor?)`
- `get_timed_transcript(url, lang?, next_cursor?)`
- `get_video_info(url)`
- `get_available_languages(url)`

### このforkで追加したツール

#### `ingest_video`
YouTube URLから時間情報付き字幕を取得し、ローカルSQLiteへ保存します。

引数:
- `url`: YouTube動画URL。
- `lang`: 優先する字幕言語。デフォルト `en`。
- `chunk_seconds`: chunkのおおよその最大時間。デフォルト `90` 秒。

#### `search_video`
キャッシュ済み字幕をSQLite FTS5で検索します。

引数:
- `query`: 全文検索クエリ。
- `video_id`: 任意。特定動画だけに検索対象を絞る場合のYouTube video ID。
- `limit`: 最大結果数。デフォルト `5`。

返り値には video ID、タイトル、元URL、開始/終了秒、字幕テキスト、FTS rankを含みます。

#### `get_segment`
指定した時間範囲と重なるキャッシュ済み字幕chunkを返します。

#### `list_cached_videos`
現在ローカルDBに登録されている動画一覧を返します。

#### `remove_cached_video`
指定動画とその字幕chunkをキャッシュから削除します。

## 保存先

デフォルトDB:

```text
~/.cache/mcp-youtube-transcript/transcripts.db
```

変更する場合:

```bash
mcp-youtube-transcript --storage-path /path/to/transcripts.db
```

または:

```bash
export MCP_YOUTUBE_TRANSCRIPT_DB=/path/to/transcripts.db
```

同じPC上のCodex / Antigravity / GitHub Copilotから同じDBファイルを指定すれば、取り込んだ動画ライブラリを共有できます。

## 開発ブランチを使うMCP設定例

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

設定ファイルの場所はMCPクライアントごとに異なります。

## 設計方針

基本は **音声/字幕優先、映像解析は必要になった時だけ** です。

```text
YouTube URL
  -> 利用可能な字幕があれば取得
  -> 時間付きchunk
  -> SQLite + FTS5
  -> 質問に関連するchunkだけLLMへ返す

字幕取得不可の場合（今後）:
  -> 利用権限のあるローカル動画/音声
  -> ffmpegで音声抽出
  -> 音声認識
  -> 同じSQLite indexへ格納

映像情報が必要な場合（今後）:
  -> 関連する時間範囲だけ特定
  -> scene/frame抽出
  -> 必要な画像だけVision解析
```

長時間動画の全文や全フレームを毎回モデルへ渡さず、モデルのコンテキスト消費を抑えることが目的です。

## 開発メモ

v0.1では意図的にVector DBを導入していません。まずPython標準の `sqlite3` とSQLite FTS5だけで軽量かつ導入しやすくし、語彙検索だけで精度が不足することが確認できてからEmbeddingを追加する方針です。

## ライセンスと帰属

MIT Licenseを継続します。fork元から継承したソースファイル内のJunpei Kawamoto氏の著作権表示・ライセンス表示は保持します。このforkで新規追加したコードには新しい著作権表示を追加し、同じMIT Licenseの下で公開します。
