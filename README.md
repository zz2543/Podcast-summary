# Podcast Summary System

A single-user, loopback-only web app that ingests local audio files, direct audio URLs,
or YouTube links and produces structured podcast summaries with Markdown, JSON, and
optional TTS audio digest outputs.

## macOS native client

There is also a SwiftUI client that replaces the browser front end and runs the
backend as its own child process — one `.app`, no dev servers. It ships with no
API credentials of any kind: you enter your own endpoint, model and keys in
Settings (⌘,) on first launch, and the keys go to the Keychain rather than a
plaintext `.env`.

```bash
open macos-client/Podsum.xcodeproj          # develop
python3 macos-client/package.py             # build a self-contained .app
```

See `specs/002-macos-native/README.md`.

Prebuilt DMG (懂听 / GotIt): [GotIt releases](https://github.com/zz2543/GotIt.An-open-source-app-for-native-Mac-video-transcription-summaries/releases/latest).

## Web version (macOS / Windows / Linux)

The web version runs the same backend locally and opens the UI in your browser.
It needs:

- Python 3.11+ (Windows: tick "Add python.exe to PATH" in the installer)
- Node.js 20+
- ffmpeg and ffprobe on PATH — macOS `brew install ffmpeg`, Windows `winget install Gyan.FFmpeg`
- Recommended for YouTube: Deno — macOS `brew install deno`, Windows `winget install DenoLand.Deno`
- Your own cloud API keys (see below)

```bash
git clone https://github.com/zz2543/Podcast-summary.git
cd Podcast-summary
python3 scripts/web.py install    # Windows: py scripts\web.py install
# edit .env: replace the replace-me-* values with your own keys
python3 scripts/web.py            # Windows: py scripts\web.py
```

Or double-click `start-web.command` (macOS) / `start-web.bat` (Windows): the
first run installs everything and opens `.env`; the next run starts the servers.

The launcher starts the backend on `http://127.0.0.1:8000` and the UI on
`http://127.0.0.1:5174`, then opens the browser. Closing the window or pressing
Ctrl+C stops both.

Minimum `.env` for the default stack:

| What | Keys |
|---|---|
| Summaries (LLM) | `DEEPSEEK_API_KEY` (any OpenAI-compatible endpoint via `DEEPSEEK_BASE_URL` / `DEEPSEEK_MODEL`), or `LLM_PROVIDER=qwen` + `DASHSCOPE_API_KEY`, or `LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY` |
| Transcription (ASR) | `VOLC_ACCESS_KEY_ID`, `VOLC_SECRET_ACCESS_KEY`, `DOUBAO_ASR_APP_ID`, `DOUBAO_ASR_ACCESS_TOKEN` — or `ASR_PROVIDER=openai_whisper` / `deepgram` / `qwen` with that provider's key |
| Audio digest (TTS) | optional; set `TTS_ENABLED=false` if you don't use it |

For Doubao ASR, the Volcengine app must enable **豆包录音文件识别模型2.0**
(`volc.seedasr.auc`, used for links) and the recording-file **极速版**
(`volc.bigasr.auc_turbo`, used for uploaded files).

## Development

The Makefile targets below assume a POSIX shell (macOS / Linux).

```bash
make install         # .venv + backend dev deps + frontend (v1) deps
make install-v2      # frontend-v2 deps
cp .env.example .env
make run-v2          # backend with --reload + frontend-v2 on 5174
```

## Commands

```bash
make install         # create .venv and install backend/frontend dependencies
make run             # apply DB migrations, start backend and Vite dev server
make db-upgrade      # apply SQLite schema migrations
make test            # backend pytest with >=80% domain coverage
make test-frontend   # frontend Vitest
make lint            # backend Ruff plus frontend TypeScript/ESLint
make build           # build frontend/dist
make serve           # serve the built SPA from FastAPI
make verify-quotes   # verify stored quotes against transcripts
```

## Caveats

- v1 is cloud-only for actual processing. ASR, LLM summarization, and TTS require network access and provider keys.
- The default Doubao ASR path requires the Volcengine app to enable recording-file ASR 2.0 (`DOUBAO_ASR_RESOURCE_ID=volc.seedasr.auc`). Public direct-audio URLs use submit/query polling. Local uploads use the flash file endpoint (`DOUBAO_ASR_FLASH_RESOURCE_ID=volc.bigasr.auc_turbo`), so enable that capability too if you upload files from the browser.
- The server binds to `127.0.0.1`; this is not a multi-user or public deployment.
- Inputs over 6 hours or 1 GB must be rejected before cloud processing.
- YouTube extraction can fail for age-gated, region-locked, or DRM-restricted content.

## Troubleshooting

- `unsupported_media`: confirm the file is mp3, m4a, or wav, or that a direct URL returns `audio/*`.
- `upstream_failed`: check the provider key in `.env` and retry.
- SOCKS proxy enabled on macOS/Linux: run `make install` after pulling this version so the backend installs `python-socks[asyncio]`; restart `make run` if a server was already running.
- SQLite lock errors: lower `MAX_CONCURRENCY` in `.env`.
