# Quickstart: Podcast Summary System

**Feature**: 001-podcast-summary
**Audience**: a developer who just cloned the repo and wants to run the demo locally.

This document is the *plan-stage* quickstart, used to verify the design end-to-end. The user-facing one-click instructions live in `README.md` (mandated by the project constitution); the two should stay consistent.

---

## Prerequisites

- macOS (M-series reference) or Linux
- Python **3.11+**
- Node **20+** (frontend build only)
- ffmpeg installed: `brew install ffmpeg` (macOS) or `apt install ffmpeg` (Debian/Ubuntu)
- API keys for the default-stack providers (only **two** accounts needed):
  - **火山引擎 (volcengine)** — powers BOTH default ASR (豆包语音识别大模型) and default TTS (豆包语音合成).
    Required: `VOLC_ACCESS_KEY_ID`, `VOLC_SECRET_ACCESS_KEY`, `DOUBAO_ASR_APP_ID`, `DOUBAO_ASR_ACCESS_TOKEN`, `DOUBAO_TTS_APP_ID`, `DOUBAO_TTS_ACCESS_TOKEN`.
    Sign up at https://console.volcengine.com, open **语音技术 → 语音识别大模型** and **语音技术 → 语音合成**, create one application with both capabilities enabled (the ASR and TTS pairs may share the same AppID + AccessToken in that case), and grab the AccessKey pair from **访问控制 → API 访问密钥**.
  - **DeepSeek** (LLM): `DEEPSEEK_API_KEY` registered at https://platform.deepseek.com.
  - Optional fallbacks (`OPENAI_API_KEY` for Whisper ASR, `ANTHROPIC_API_KEY` for Claude LLM, `DASHSCOPE_API_KEY` for Qwen ASR/LLM/TTS, `DEEPGRAM_API_KEY` for Deepgram ASR) may be left blank.

## One-time setup

```bash
# 1. Clone and enter
git clone <repo-url> Podcast-summary
cd Podcast-summary

# 2. Configure (Constitution IV: env-only)
cp .env.example .env
$EDITOR .env  # set OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.

# 3. Install
make install   # creates a Python venv, installs backend + frontend deps
```

`.env.example` enumerates every supported variable; any value left blank falls back to a safe default where one exists.

## Run

```bash
make run
```

Equivalent to:
- `uvicorn podsum.main:app --host 127.0.0.1 --port 8000 --reload` (backend)
- `npm --prefix frontend run dev` (frontend dev server with proxy to backend)

The web UI is at `http://127.0.0.1:5173` in dev. The backend serves the built SPA from `/` in production (`make build && make serve`).

## Smoke test (acceptance walkthrough)

This sequence exercises every required FR end-to-end and is the manual gate before `/speckit-tasks` finishes.

1. **US1 / FR-001 / FR-009 / FR-010** — open the UI, upload a 1–2 minute MP3 (English fixture in `backend/tests/fixtures/`), wait for status `done`, confirm a hook ≤ 50 chars and a three-act block render.
2. **US1 / FR-007** — repeat with a Chinese fixture; confirm output text is in Chinese.
3. **US1 / FR-006 / SC-007** — kill the backend mid-transcription on a fresh upload; restart with `make run`; confirm the job resumes and that the ASR-stage time on the second run is dramatically lower than from-scratch.
4. **US2 / FR-011 / FR-012 / SC-003 / SC-004** — open the detail page, click any quote timestamp, confirm the embedded player seeks within ±10 s; run `make verify-quotes` (a CLI that re-runs the verbatim check across every stored quote) and confirm 100% pass.
5. **US3 / FR-016 / SC-005** — click "Generate audio digest", play the resulting MP3, confirm same-language narration covering hook + three-act + chapter key points.
6. **US4 / FR-018** — set `MAX_CONCURRENCY=2` in `.env`, submit 5 URLs, confirm at most 2 are processing at any moment.
7. **FR-024** — submit a > 1 GB file (or a > 6 h YouTube video); confirm rejection at ingestion with `413 payload_too_large` and no `data/<id>/` created.
8. **FR-025** — delete an episode from the UI; confirm the row disappears and `data/<id>/` is gone from disk.
9. **FR-026** — temporarily break the TTS API key (`OPENAI_API_KEY=invalid`), trigger a digest; confirm `stage_status.tts="failed_after_retries"` while the rest of the episode remains usable.

## Test commands

```bash
make test             # backend pytest with coverage report
make test-frontend    # vitest
make lint             # ruff + tsc
make verify-quotes    # offline replay of FR-012 verifier across the DB
```

`make test` fails the build if `backend/src/podsum/domain/` coverage falls below 80% (Constitution III).

## Troubleshooting

- **`unsupported_media` on a YouTube link**: the video may be age-gated or region-locked (FR-003 requires fail-fast behavior); try a different link.
- **`upstream_failed` from the ASR stage**: check the API key in `.env` and the provider's status page.
- **Database locked errors during heavy concurrent writes**: lower `MAX_CONCURRENCY`. SQLite is fine for the single-user model at concurrency ≤ 8.
