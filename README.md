# Podcast Summary System

A single-user, loopback-only web app that ingests local audio files, direct audio URLs,
or YouTube links and produces structured podcast summaries with Markdown, JSON, and
optional TTS audio digest outputs.

## Prerequisites

- Python 3.11+
- Node 20+
- ffmpeg and ffprobe on PATH
- Cloud API credentials for the default stack:
  - Volcengine / Doubao for ASR and TTS
  - DeepSeek for LLM summarization

On macOS, the assumed Homebrew packages are:

```bash
brew install python@3.11 node@20 ffmpeg
```

## Quick Start

```bash
make install
cp .env.example .env
make run
```

Then open `http://127.0.0.1:5173`. The backend API runs at
`http://127.0.0.1:8000`.

The copied `.env` contains non-secret placeholders so the local UI/API can start
from a clean checkout. Replace the `replace-me-*` values before processing real
episodes; otherwise cloud ASR/LLM/TTS stages will fail at provider call time.

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
- The server binds to `127.0.0.1`; this is not a multi-user or public deployment.
- Inputs over 6 hours or 1 GB must be rejected before cloud processing.
- YouTube extraction can fail for age-gated, region-locked, or DRM-restricted content.

## Troubleshooting

- `unsupported_media`: confirm the file is mp3, m4a, or wav, or that a direct URL returns `audio/*`.
- `upstream_failed`: check the provider key in `.env` and retry.
- SQLite lock errors: lower `MAX_CONCURRENCY` in `.env`.
