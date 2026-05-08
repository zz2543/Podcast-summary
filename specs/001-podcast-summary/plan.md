# Implementation Plan: Podcast Summary System

**Branch**: `001-podcast-summary` | **Date**: 2026-05-07 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/001-podcast-summary/spec.md`

## Summary

A single-user, locally hosted web application that ingests one of {local audio file, direct audio URL, YouTube link}, transcribes the audio via a cloud ASR API, produces a structured Chinese-or-English summary (one-line hook, three-act summary, chapter outline with verbatim quotes, named-entity list) via a cloud LLM, optionally synthesizes a TTS audio digest via a cloud TTS API, and exposes the artifacts through a polished web UI. The pipeline is resumable across process restarts, supports configurable concurrency, and degrades partially rather than failing whole episodes when optional stages cannot be produced. Hard input cap: 6 hours / 1 GB. Episodes are retained indefinitely with a manual delete action that purges all artifacts.

## Technical Context

**Language/Version**: Python 3.11+ (backend, per Constitution II); TypeScript 5.x for the SPA frontend (justified in Complexity Tracking).
**Primary Dependencies (backend)**: FastAPI (HTTP + WebSocket progress streaming), SQLAlchemy 2.x + Alembic (persistence), pydantic 2.x (schemas / JSON output), httpx (async HTTP for cloud APIs, Doubao recording-file ASR submit/query, and direct-audio fetch), yt-dlp (YouTube audio extraction), tenacity (retry policies), python-dotenv (`.env` loading per Constitution IV). The cloud stack is consolidated on **two providers**: **火山引擎 (volcengine)** for both ASR (豆包录音文件识别模型 2.0 by default) and TTS (豆包语音合成), and **DeepSeek** for LLM. The `openai` Python SDK is retained as the HTTP transport for DeepSeek's OpenAI-compatible endpoint (no OpenAI account required).
**Primary Dependencies (frontend)**: Vite + React + TypeScript + a minimal CSS layer (Tailwind or plain CSS) — the visual design is authored externally per FR-017, so the frontend stack is chosen for flexibility, not opinionated visuals.
**Storage**: SQLite (single-user local, embedded, ACID, sufficient for the spec's durability requirement) for jobs/episodes/segments/chapters/quotes/entities + a `data/` directory tree on disk for audio cache, transcript JSON, generated Markdown, generated JSON, and TTS audio.
**Testing**: pytest + pytest-asyncio + pytest-cov (coverage gate ≥ 80% on domain logic per Constitution III); httpx ASGI client for FastAPI integration tests; respx for outbound HTTP mocking; Vitest for the few frontend unit tests (route guards, quote-jump math).
**Target Platform**: macOS (reference: Apple M2 MacBook), Linux (best-effort). Server binds to 127.0.0.1 only (FR-022). Python 3.11+, Node 20+ for the build step.
**Project Type**: Web application (Python backend + TypeScript SPA frontend, single repo).
**Performance Goals**: 60-min episode end-to-end ≤ 10 minutes on M2 (FR-019 / SC-006); concurrency configurable (default 2, max 8); WebSocket progress updates ≤ 500 ms latency.
**Constraints**: Cloud-only in v1 (no local model fallback); loopback-only HTTP binding; 6h / 1 GB hard input cap (FR-024); persistent across restart (FR-006); partial-degraded outputs when optional stages fail (FR-026); all prompts versioned in `prompts/` per Constitution V; all keys via env per Constitution IV.
**Scale/Scope**: Single concurrent operator; expected library size 10–500 episodes over time on a single laptop disk; ≤ 8 concurrent in-flight jobs.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle / Constraint | Status | Notes |
|---|------------------------|--------|-------|
| I | English-first delivery | ✅ | spec.md, plan.md, research.md, data-model.md, contracts/, quickstart.md, code comments will be in English. UI in-product strings follow source-language convention separately and do not violate the artifact rule. (Constitution exception: `detail.md` and `report.md` are explicitly Chinese per the Delivery section.) |
| II | Python 3.11+ as primary language | ⚠ justified | Backend is Python 3.11+. Frontend uses TypeScript — see Complexity Tracking. |
| III | Domain-logic test coverage ≥ 80% (NON-NEGOTIABLE) | ✅ (planned) | Domain modules (`transcript_postprocess`, `chapter_segmenter`, `prompt_assembler`, `structured_parser`, `quote_verifier`, `entity_extractor`) all unit-tested with pytest; I/O layer (HTTP, file, model calls) mocked with respx. CI fails under 80% on `backend/src/podsum/domain/`. |
| IV | Configuration externalized | ✅ | `.env` + `.env.example`; pydantic-settings reads all keys (`OPENAI_API_KEY`, `DEEPGRAM_API_KEY`, `ANTHROPIC_API_KEY`, `ELEVENLABS_API_KEY`, `DATA_DIR`, `DB_PATH`, `MAX_CONCURRENCY`). No literals in source. |
| V | Prompt versioning, files in `prompts/` | ✅ | All prompts live in `prompts/<role>.v<N>.md` with frontmatter `version:`. `prompt_assembler.py` is the sole reader; inline multi-line prompts are forbidden by an import-time lint. |
| Delivery: README one-click run | ✅ (planned) | `make run` (or `./run.sh`) brings up backend + frontend dev server after `cp .env.example .env`. |
| Delivery: `detail.md` + `report.md` (Chinese) | ✅ (planned) | Both files seeded at `/speckit-tasks` and updated continuously. |
| SDD: full spec → plan → tasks → implement | ✅ | This file is the plan stage. |
| SDD: ≥ 2 candidates per key tech choice | ✅ | See research.md (ASR, LLM, TTS, persistence, frontend stack, YouTube extractor). |
| SDD: dependency registry (purpose / license / activity) | ✅ | See "External Dependency Registry" section below. |

**Verdict**: PASS. One justified deviation (TypeScript frontend) recorded in Complexity Tracking.

### Post-Design Re-check (after Phase 1)

After completing `research.md`, `data-model.md`, `contracts/`, and `quickstart.md`, the gate is re-evaluated:

- **No new dependencies** added beyond those listed in the External Dependency Registry. ✅
- **No inline prompts** introduced; `prompt_versions` is a first-class field in both the data model and the JSON contract. ✅
- **Domain isolation** preserved: every FR mapped to enforcement is enforced inside `backend/src/podsum/domain/` modules whose I/O surface is mockable (data-model.md "Validation rules summary"). ✅
- **80% coverage feasibility**: each domain module is small (single responsibility, pure functions) — no integration coupling that would block unit testing. ✅
- **One-click run**: `make run` covers backend + frontend from a clean `.env`. ✅

Verdict: still PASS, no new violations.

## External Dependency Registry

Per Constitution rule 10. Detailed alternatives & rationale live in `research.md`; this table is the binding registry — no runtime dependency may be added without an update here.

### Backend (Python)

| Package | Purpose | License | Maintenance Activity |
|---------|---------|---------|----------------------|
| fastapi | HTTP + WebSocket server | MIT | Active; releases monthly; >75k stars |
| uvicorn[standard] | ASGI server | BSD-3 | Active; bundled with FastAPI ecosystem |
| sqlalchemy | ORM / Core for SQLite | MIT | Active; 2.x mainline |
| alembic | DB migrations | MIT | Active; SQLAlchemy companion |
| pydantic | Settings + JSON schemas | MIT | Active; 2.x mainline |
| pydantic-settings | `.env`-driven configuration | MIT | Active |
| httpx | Async HTTP client (cloud APIs, direct audio) | BSD-3 | Active; releases quarterly |
| tenacity | Retry policies for cloud API calls | Apache-2.0 | Active |
| yt-dlp | YouTube audio extraction | Unlicense | Very active (frequent releases tracking YouTube changes) |
| openai | HTTP transport for DeepSeek LLM via OpenAI-compatible endpoint (custom `base_url`); no OpenAI account needed | Apache-2.0 | Active (official SDK) |
| volcengine-python-sdk | Shared Volcengine credential wiring for speech services; TTS uses the speech SDK path while ASR defaults to HTTP AUC submit/query | Apache-2.0 | Active (official SDK from ByteDance) |
| dashscope | Optional fallback for LLM (Qwen) and TTS (Qwen-TTS / CosyVoice) via Alibaba DashScope | Apache-2.0 | Active (official SDK from Alibaba) |
| python-multipart | File uploads | Apache-2.0 | Active |
| python-socks[asyncio] | SOCKS proxy support for async WebSocket/HTTP speech connections when macOS or Linux system proxy is enabled | Apache-2.0 | Active; maintained helper library used by Python async network stacks |
| pytest, pytest-asyncio, pytest-cov | Testing | MIT | Active |
| respx | httpx mock for tests | BSD-3 | Active |

### Frontend (TypeScript)

| Package | Purpose | License | Maintenance Activity |
|---------|---------|---------|----------------------|
| react, react-dom | UI runtime | MIT | Very active |
| vite | Build / dev server | MIT | Very active |
| typescript | Type system | Apache-2.0 | Very active |
| vitest | Test runner | MIT | Active |
| (CSS layer TBD when visual design arrives) | | | |

### System binaries (assumed installed by README)

| Tool | Purpose | License | Notes |
|------|---------|---------|-------|
| ffmpeg | Audio container/format normalization (m4a/mp3/wav → standardized PCM/MP3 for ASR) | LGPL/GPL | Standard on macOS via Homebrew; required by yt-dlp |

## Project Structure

### Documentation (this feature)

```text
specs/001-podcast-summary/
├── plan.md              # This file
├── spec.md              # Existing
├── research.md          # Phase 0 output (this run)
├── data-model.md        # Phase 1 output (this run)
├── quickstart.md        # Phase 1 output (this run)
├── contracts/           # Phase 1 output (this run)
│   ├── http-api.md
│   ├── job-events.md
│   └── episode-output.schema.json
└── checklists/
    └── requirements.md  # Existing
```

### Source Code (repository root)

```text
backend/                         # Python 3.11+ FastAPI service
├── src/
│   └── podsum/
│       ├── api/                 # FastAPI routers (HTTP + WebSocket); thin I/O layer
│       │   ├── episodes.py
│       │   ├── jobs.py
│       │   └── ws_progress.py
│       ├── services/            # Orchestration; I/O allowed; mockable
│       │   ├── ingest.py        # local file / direct URL / YouTube → standardized audio
│       │   ├── asr_client.py    # cloud ASR adapter (interface + provider impls)
│       │   ├── llm_client.py    # cloud LLM adapter
│       │   ├── tts_client.py    # cloud TTS adapter
│       │   └── pipeline.py      # job state machine, retries, partial degradation
│       ├── domain/              # Pure logic, ≥ 80% pytest coverage REQUIRED
│       │   ├── transcript_postprocess.py
│       │   ├── chapter_segmenter.py
│       │   ├── prompt_assembler.py     # reads prompts/ files, no inline prompts
│       │   ├── structured_parser.py    # parse + validate LLM JSON output
│       │   ├── quote_verifier.py       # verbatim-substring check (FR-012, SC-004)
│       │   └── entity_extractor.py
│       ├── persistence/         # SQLAlchemy models + repositories
│       │   ├── models.py
│       │   ├── migrations/      # Alembic
│       │   └── repo.py
│       ├── exporters/           # Markdown + JSON renderers
│       │   ├── markdown.py
│       │   └── json_export.py
│       ├── config.py            # pydantic-settings; reads .env
│       ├── main.py              # FastAPI app factory
│       └── __init__.py
└── tests/
    ├── unit/                    # mirrors src/podsum/domain
    ├── integration/             # API + persistence with mocked cloud
    └── fixtures/                # canned transcripts, sample audio metadata

frontend/                        # Vite + React + TypeScript SPA
├── src/
│   ├── pages/
│   ├── components/
│   ├── api/                     # typed client for backend HTTP/WS
│   └── main.tsx
├── tests/                       # vitest
├── package.json
└── vite.config.ts

prompts/                         # Constitution V — all LLM prompts live here
├── one_liner.v1.md
├── three_act_summary.v1.md
├── chapter_outline.v1.md
└── entity_extraction.v1.md

data/                            # gitignored runtime artifacts (audio cache, transcripts, exports)
.env.example
README.md                        # one-click run script (Constitution: delivery)
detail.md                        # Chinese implementation log (Constitution: delivery)
report.md                        # Chinese review report (Constitution: delivery)
Makefile                         # `make run`, `make test`, `make lint`
```

**Structure Decision**: Web-application layout (`backend/` + `frontend/` siblings). Domain logic is rigorously separated from I/O so the 80% coverage gate (Constitution III) applies cleanly to `backend/src/podsum/domain/` without dragging in cloud-API mocking concerns.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| TypeScript / Node toolchain on the frontend (deviates from Constitution II "Python primary") | FR-017 requires a polished web UI with audio player + clickable timestamp seeks; browsers cannot execute Python. | Python-only alternatives (Streamlit, NiceGUI, Gradio) were evaluated but each constrains the visual flexibility the user plans to drive from externally generated image briefs (per FR-017). Node is build-time only; runtime served to the browser is static JS/CSS, with all business logic remaining in Python. |
