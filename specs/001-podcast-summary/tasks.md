---
description: "Task list for 001-podcast-summary implementation"
---

# Tasks: Podcast Summary System

**Input**: Design documents from `/specs/001-podcast-summary/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md
**Tests**: Domain-layer unit tests are MANDATORY (Constitution III: ≥ 80% line coverage on `backend/src/podsum/domain/`). Integration tests are included where they exercise multi-stage pipeline behavior; pure I/O glue does not require dedicated test tasks beyond what is listed.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1 / US2 / US3 / US4)
- Setup, Foundational, and Polish tasks have NO story label.
- All file paths are repo-root–relative and match the structure in plan.md.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project skeleton, tooling, env wiring, and the two Chinese reports the constitution mandates.

- [X] T001 Create the top-level directory tree: `backend/src/podsum/{api,services,domain,persistence,exporters}`, `backend/tests/{unit,integration,fixtures}`, `frontend/src/{pages,components,api}`, `frontend/tests/`, `prompts/`, `data/` (gitignored), `scripts/`. Add an empty `__init__.py` to every Python package directory.
- [X] T002 Initialize the backend Python package with `backend/pyproject.toml` declaring Python ≥3.11 and the dependencies from plan.md "External Dependency Registry → Backend" (fastapi, uvicorn[standard], sqlalchemy, alembic, pydantic, pydantic-settings, httpx, tenacity, yt-dlp, openai, volcengine-python-sdk, dashscope, python-multipart, python-ulid). Pin minor versions; create `backend/requirements-dev.txt` with pytest, pytest-asyncio, pytest-cov, respx, ruff, black, mypy. Note: `volcengine-python-sdk` powers BOTH the default ASR (豆包语音识别大模型) and the default TTS (豆包语音合成); `openai` is retained only as the HTTP transport for DeepSeek's OpenAI-compatible LLM endpoint (no OpenAI account needed); `dashscope` is optional and only required if `ASR_PROVIDER=qwen`, `LLM_PROVIDER=qwen`, or `TTS_PROVIDER=qwen`.
- [X] T003 Initialize the frontend with `frontend/package.json` + `frontend/vite.config.ts` + `frontend/tsconfig.json` for a Vite + React + TypeScript SPA; declare `react`, `react-dom`, `vite`, `typescript`, `vitest`, `@types/react`, `@types/react-dom` per plan.md. Configure the dev server to proxy `/api` and `/api/ws` to `http://127.0.0.1:8000`.
- [X] T004 [P] Configure backend lint/format: `backend/.ruff.toml` (ruff: pyflakes + isort + bugbear), `backend/pyproject.toml` `[tool.black]` (line length 100), `backend/mypy.ini` (strict on `podsum.domain` only).
- [X] T005 [P] Configure frontend lint: `frontend/.eslintrc.cjs` (typescript-eslint recommended), `frontend/.prettierrc.json`. Add `tsc --noEmit` to lint script.
- [X] T006 [P] Author `.env.example` at repo root listing every env var read by `backend/src/podsum/config.py`:
  - **Core**: `DATA_DIR`, `DB_PATH`, `MAX_CONCURRENCY`, `LOG_LEVEL`.
  - **Provider selection**: `ASR_PROVIDER` (default `doubao`), `LLM_PROVIDER` (default `deepseek`), `TTS_PROVIDER` (default `doubao`).
  - **火山引擎 shared credentials (required for default ASR + TTS)**: `VOLC_ACCESS_KEY_ID`, `VOLC_SECRET_ACCESS_KEY`.
  - **ASR — 豆包语音识别大模型 (required for default)**: `DOUBAO_ASR_APP_ID`, `DOUBAO_ASR_ACCESS_TOKEN`, `DOUBAO_ASR_CLUSTER` (default `volcengine_streaming_common` or the model-specific cluster name from the volcengine console).
  - **LLM — DeepSeek (required for default)**: `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL` (default `https://api.deepseek.com`), `DEEPSEEK_MODEL` (default `deepseek-chat`).
  - **TTS — 豆包语音合成 (required for default)**: `DOUBAO_TTS_APP_ID`, `DOUBAO_TTS_ACCESS_TOKEN`, `DOUBAO_TTS_VOICE_TYPE_ZH` (default e.g. `BV700_streaming`), `DOUBAO_TTS_VOICE_TYPE_EN` (default e.g. `BV701_streaming`), `DOUBAO_TTS_CLUSTER` (default `volcano_tts`).
  - **Optional fallbacks (leave blank if unused)**: `OPENAI_API_KEY` (alt ASR — Whisper), `DEEPGRAM_API_KEY` (alt ASR), `ANTHROPIC_API_KEY` (alt LLM — Claude), `DASHSCOPE_API_KEY` (alt LLM — Qwen, **and** alt ASR — Paraformer/Qwen-Audio, **and** alt TTS — Qwen-TTS / CosyVoice).
  Each variable has an inline English comment describing its purpose and noting whether a value is required for the default configuration. Note: `DOUBAO_ASR_*` and `DOUBAO_TTS_*` may share the same AppID + AccessToken if the volcengine application has both 语音识别 and 语音合成 capabilities enabled in one app — document this in the comment. Commit `.env` to `.gitignore`.
- [X] T007 Create `Makefile` at repo root with targets: `install` (venv + pip install + npm install), `run` (uvicorn + vite in parallel), `test` (pytest with `--cov=backend/src/podsum/domain --cov-fail-under=80`), `test-frontend` (vitest), `lint` (ruff + tsc), `build` (vite build → `frontend/dist`), `serve` (uvicorn serving the built SPA), `verify-quotes` (runs `python scripts/verify_quotes.py`). Each target prints what it runs.
- [X] T008 [P] Author `README.md` at repo root with one-click instructions: prerequisites (Python 3.11, Node 20, ffmpeg), `cp .env.example .env`, `make install`, `make run`. Include the cloud-only / loopback-only caveats and a short troubleshooting section. README is in English; `detail.md` and `report.md` are in Chinese per Constitution.
- [X] T009 [P] Seed `detail.md` (Chinese) at repo root with section skeletons: 实现日志、设计取舍、踩坑记录、性能数据、评估结果. Add a header note that this file is appended to throughout implementation.
- [X] T010 [P] Seed `report.md` (Chinese) at repo root with section skeletons: 项目概览、用户与场景、技术选型摘要（来自 research.md）、核心实现、评估与结果、未来工作. State that the file is updated continuously and is the evaluator-facing report.
- [X] T011 [P] Configure `backend/pyproject.toml` `[tool.pytest.ini_options]` and `[tool.coverage]` so `pytest` defaults to running `backend/tests/`, asyncio mode auto, coverage source = `backend/src/podsum/domain`, fail-under = 80. Mirror these flags in the `make test` recipe (T007).
- [X] T012 [P] Author `.gitignore` covering `data/`, `.env`, `__pycache__/`, `*.pyc`, `.venv/`, `frontend/node_modules/`, `frontend/dist/`, `.pytest_cache/`, `.coverage`. Author `.gitattributes` at repo root with `*.png binary` / `*.jpg binary` / `*.jpeg binary` / `*.mp3 binary` / `*.wav binary` / `*.m4a binary` so design mockups under `specs/001-podcast-summary/design/` and audio fixtures don't pollute git diffs.

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Configuration, persistence, prompt loader, cloud-adapter interfaces, and the pipeline skeleton — all required before any user-story phase can land. The pipeline state machine and partial-degradation semantics (FR-026) live here because every subsequent stage plugs into them.

- [X] T013 Implement `backend/src/podsum/config.py` using `pydantic-settings` to read every variable from `.env.example` (T006) into a frozen `Settings` model. Provide a `get_settings()` cached accessor. Reject startup if a required key is missing (per Constitution IV — no hard-coded defaults for secrets).
- [X] T014 Implement `backend/src/podsum/persistence/models.py` with SQLAlchemy 2.x declarative models for the seven tables defined in `data-model.md` (`episode`, `job`, `transcript_segment`, `chapter`, `quote`, `entity`, `summary_artifact`), including all CHECK constraints, FK ON DELETE CASCADE, indexes, and JSON columns. ULID primary keys via `python-ulid`.
- [X] T015 Initialize Alembic at `backend/src/podsum/persistence/migrations/`. Configure `env.py` to read DB URL from `Settings`. Generate `versions/0001_initial.py` matching the models from T014.
- [X] T016 Implement `backend/src/podsum/persistence/repo.py` with one repository class per aggregate root (EpisodeRepo, JobRepo, SegmentRepo, ChapterRepo, EntityRepo, SummaryArtifactRepo). Quote rows are written exclusively via `QuoteRepo.insert_verified(...)` — that method is the only path that sets `verified=True` and it MUST call into `domain.quote_verifier.verify()` first; document this invariant in the docstring (FR-012, SC-004).
- [X] T017 Implement `backend/src/podsum/main.py`: FastAPI app factory, mounts API routers, configures the WebSocket route, binds to 127.0.0.1 only (FR-022). Expose `create_app(settings: Settings)` for testability.
- [X] T018 [P] Implement `backend/src/podsum/api/_logging.py` with structured logging (timestamp, level, job_id, episode_id, stage). Wire into `main.py`.
- [X] T019 Implement `backend/src/podsum/api/ws_progress.py`: WebSocket connection manager with `hello` / `snapshot` / `job_update` / `stage_status_update` frames per `contracts/job-events.md`. Debounce job_update to ≤ 2/sec/job. Expose `Broadcaster.publish_*` methods used by the pipeline.
- [X] T020 Implement `backend/src/podsum/domain/prompt_assembler.py`: loads prompts from the `prompts/` directory by `(role, version)`, parses YAML frontmatter (must include `version:` matching `vN`), substitutes named slots (e.g. `{lang}`, `{transcript}`, `{episode_title}`). Inline prompt strings of more than 80 characters anywhere in `backend/src/` are forbidden — add a ruff custom rule or a unit-test enforcement (Constitution V).
- [X] T021 [P] [unit-test] Author `backend/tests/unit/test_prompt_assembler.py` covering: load by role+version, missing version → error, slot substitution, missing slot → error, frontmatter validation. Counts toward 80% domain coverage gate.
- [X] T022 [P] Seed prompt files in `prompts/` with placeholders that match the slots used by `prompt_assembler.py`: `prompts/one_liner.v1.md`, `prompts/three_act_summary.v1.md`, `prompts/chapter_outline.v1.md`, `prompts/entity_extraction.v1.md`. Each file has frontmatter `---\nrole: <id>\nversion: v1\nlang_aware: true\n---` and an English+Chinese-aware instruction body. Real prompt tuning happens during US1/US2 implementation; these are the versioned skeletons.
- [X] T023 Implement abstract adapter interfaces (no provider impl yet): `backend/src/podsum/services/asr_client.py` (`ASRClient.transcribe(audio_path, language_hint) -> list[TranscriptSegment]`), `backend/src/podsum/services/llm_client.py` (`LLMClient.complete_json(prompt, schema) -> dict`), `backend/src/podsum/services/tts_client.py` (`TTSClient.synthesize(text, lang, out_path)`). Adapter selection driven by `Settings.ASR_PROVIDER` / `LLM_PROVIDER` / `TTS_PROVIDER`.
- [X] T024 Implement `backend/src/podsum/services/pipeline.py` skeleton: a `Pipeline` class wrapping the job state machine described in `data-model.md` (states queued → fetching → transcribing → summarizing → tts → done/partial/failed). Stages register themselves as `(name, required: bool, run: Callable)`. After per-stage `tenacity` retry budget exhaustion: required stage → mark job `failed`; optional stage → mark `summary_artifact.stage_status[stage] = "failed_after_retries"` and continue (FR-026). Persists `stage_progress` JSON after every stage step so resume-after-crash (FR-006) is byte-checkpointed.
- [X] T025 Wire pipeline restart recovery into `main.py` startup: on app start, query jobs in any non-terminal state, set them back to `queued`, and re-enqueue (FR-006 / SC-007). Cover with `backend/tests/integration/test_restart_recovery.py` using a mocked ASR client that records call counts.

## Phase 3: User Story 1 — Triage New Episodes Overnight (Priority P1) 🎯 MVP

**Story goal**: Submit an audio source (file / direct URL / YouTube), get back a one-line hook (≤ 50 chars, distinct from title) plus a three-act summary, exported as Markdown and JSON, persisted across restarts. This phase alone is a viable MVP.

**Independent test**: Upload a 1–2 minute MP3 fixture; observe the episode reach `done` with a hook ≤ 50 chars and a three-act block, downloadable as both Markdown and JSON. Kill the server mid-run and confirm resume on restart skips re-transcription.

- [X] T026 [US1] Implement `backend/src/podsum/services/ingest.py::ingest_local_file(upload, settings)`: stream-write upload to `data/<id>/audio.original.<ext>`, validate MIME via magic bytes against {mp3, m4a, wav}, run `ffmpeg` to produce `audio.normalized.mp3`, probe duration via ffprobe, **enforce FR-024 hard caps** (reject before any DB row creation if duration > 21600 s or file > 1 GB → raise `PayloadTooLarge`).
- [X] T027 [P] [US1] Implement `backend/src/podsum/services/ingest.py::ingest_direct_url(url, settings)`: HEAD probe, validate `Content-Type` is `audio/*` (FR-002, raise `UnsupportedMedia` otherwise), GET stream to `data/<id>/audio.original.<ext>`, then proceed via ffmpeg as in T026 with the same caps.
- [X] T028 [P] [US1] Implement `backend/src/podsum/services/ingest.py::ingest_youtube(url, settings)`: invoke yt-dlp Python API to extract bestaudio + metadata (title, channel as podcast_name, duration); fail fast with `UnsupportedMedia` on age-gate / region-lock / DRM (FR-003).
- [X] T029 [US1] Implement `backend/src/podsum/services/asr_client.py::DoubaoASR` using `volcengine-python-sdk` to call 豆包语音识别大模型 (火山引擎 streaming ASR). Authenticates via `Settings.VOLC_ACCESS_KEY_ID` + `Settings.VOLC_SECRET_ACCESS_KEY` + `Settings.DOUBAO_ASR_APP_ID` + `Settings.DOUBAO_ASR_ACCESS_TOKEN`. Cluster name from `Settings.DOUBAO_ASR_CLUSTER`. Returns segment-level results with `start_ms` / `end_ms` / `text` / per-segment language tag (the model emits zh/en labels for code-switched audio, satisfying FR-007). Persist the raw provider response (JSON) to `data/<id>/transcript.raw.json`. Honour the Settings retry budget via tenacity. Adapter selection in `services/asr_client.py` honors `Settings.ASR_PROVIDER` ∈ {`doubao` (default), `openai_whisper` (alt), `qwen` (alt — Paraformer/Qwen-Audio via DashScope)}; the alternative implementations are registered in the same file as `WhisperASR` and `QwenASR` and selected by the env switch.
- [X] T030 [US1] Implement `backend/src/podsum/domain/transcript_postprocess.py`: pure function `normalize(raw_segments, language_hint) -> list[NormalizedSegment]` that merges adjacent same-language fragments, collapses internal whitespace runs, NFKC-normalizes, tags per-segment `language` ∈ {zh, en}, drops zero-length segments. No I/O.
- [X] T031 [P] [US1] [unit-test] `backend/tests/unit/test_transcript_postprocess.py` — covers: pure-Chinese, pure-English, mixed code-switched, leading/trailing whitespace, repeated-space collapsing, zero-length drop, ordering preserved.
- [X] T032 [US1] Implement `backend/src/podsum/services/llm_client.py::DeepSeekLLM` calling DeepSeek (`deepseek-chat` by default) via the `openai` SDK with `base_url=Settings.DEEPSEEK_BASE_URL` and `api_key=Settings.DEEPSEEK_API_KEY`. Expose `complete_json(prompt, schema) -> dict` that uses DeepSeek's JSON-mode (`response_format={"type": "json_object"}`) and validates against the caller-supplied pydantic schema before returning. Tenacity retry on transient errors. Adapter selection in `services/llm_client.py` honors `Settings.LLM_PROVIDER` ∈ {`deepseek` (default), `qwen` (DashScope), `anthropic` (Claude, optional)}.
- [X] T033 [US1] Implement `backend/src/podsum/domain/structured_parser.py::parse_one_liner(raw_json, episode_title, lang) -> str`: validates ≤ 50 chars (Unicode-aware: Chinese counts per char, English counts per word ≤ 50? — clarify: per spec FR-009 "≤ 50 characters" applies as code-point count for both languages), validates **informational distinctness from `episode_title`** (Levenshtein ratio ≤ 0.6 against the lowercased title), raises `RetriableValidationError` on failure so the pipeline asks the LLM again with the corrective hint.
- [X] T034 [US1] Implement `backend/src/podsum/domain/structured_parser.py::parse_three_act(raw_json) -> ThreeAct`: strict pydantic validation of `{background, core_argument, conclusion}` non-empty strings; rejects extra keys; rejects whitespace-only fields.
- [X] T035 [P] [US1] [unit-test] `backend/tests/unit/test_structured_parser_us1.py` — exhaustive cases for `parse_one_liner` (51-char Chinese, 51-char English, identical-to-title, near-paraphrase of title, valid case) and `parse_three_act` (missing key, extra key, whitespace-only, valid case).
- [X] T036 [US1] Wire pipeline stages for US1 in `services/pipeline.py`:
  1. `fetch` (calls T026/T027/T028 based on `episode.source_type`),
  2. `transcribe` (T029 → T030 → write `transcript_segment` rows),
  3. `summarize_hook` (calls `prompt_assembler` → `llm_client` → `parse_one_liner`),
  4. `summarize_three_act` (same path with the three-act prompt),
  5. `export` (T037 + T038).
  Stages 3 and 4 are `required=True`; failures here mark the job failed.
- [X] T037 [US1] Implement `backend/src/podsum/exporters/markdown.py::render(episode_detail) -> str`: emits H1 title, metadata block, hook line, three-act block. (Chapters/quotes/entities added in US2 — keep the function feature-flag friendly so US2 just adds sections.)
- [X] T038 [P] [US1] Implement `backend/src/podsum/exporters/json_export.py::render(episode_detail) -> dict` returning a structure that **validates** against `specs/001-podcast-summary/contracts/episode-output.schema.json` (load the schema at import time and assert in tests). For US1, populate `hook`, `three_act`, `stage_status`, `prompt_versions`; leave `chapters: []` and `entities: []` until US2.
- [X] T039 [P] [US1] [unit-test] `backend/tests/unit/test_json_export_schema.py` — loads the JSON Schema from `contracts/`, runs `jsonschema.validate` on a synthesized US1 export. Catches schema drift early.
- [X] T040 [US1] Implement `backend/src/podsum/api/episodes.py`:
  - `POST /api/episodes` (multipart for local_file, JSON for direct_url/youtube) → calls ingest + creates Episode + Job rows + enqueues pipeline (per `contracts/http-api.md`).
  - `GET /api/episodes` (cursor pagination, optional `?status=`).
  - `GET /api/episodes/{id}` → returns `EpisodeDetail` shape from `episode-output.schema.json`.
  - `DELETE /api/episodes/{id}` (FR-025: atomic DB CASCADE + `shutil.rmtree(data/<id>/)`).
  - `POST /api/episodes/{id}/retry` (FR-006, returns `Job`).
  - File-streaming endpoints: `GET /api/episodes/{id}/files/markdown`, `…/files/json`, `…/files/audio` with HTTP `Range` support for the audio.
- [X] T041 [US1] Implement `backend/src/podsum/api/jobs.py` if needed for poll-style `GET /api/jobs/{id}` (used by the smoke test); WebSocket is the primary channel.
- [X] T042 [US1] Wire WS broadcasts: emit `job_update` from `pipeline.py` after every state transition and every `stage_progress` update; emit `stage_status_update` whenever `summary_artifact.stage_status[*]` changes.
- [X] T043 [P] [US1] [integration-test] `backend/tests/integration/test_us1_end_to_end.py` — uses respx to mock OpenAI ASR + Anthropic LLM, drives one upload through to `done`, asserts hook ≤ 50 chars, three-act non-empty, JSON validates against schema, Markdown contains hook line.
- [X] T044 [P] [US1] [integration-test] `backend/tests/integration/test_us1_resume.py` — submit, kill mid-transcribe (use a mock that hangs forever on first call, returns immediately on second), restart `create_app`, assert ASR call count remains 1 (verifies SC-007 resume guarantee).
- [X] T045 [US1] Frontend `frontend/src/api/client.ts` — typed HTTP + WebSocket client matching `contracts/http-api.md` and `contracts/job-events.md`. Single `useJobs()` React hook owns the WS lifecycle (auto-reconnect with backoff per contract).
- [X] T046 [US1] Frontend `frontend/src/pages/EpisodeListPage.tsx` — submit form (file / URL / YouTube tabs), episode list with status + progress bar driven by WS, per-row delete and retry actions. Visual layout binds to `specs/001-podcast-summary/design/selected/list-page.png` and `…/selected/empty-state.png`; component composition and copy follow `specs/001-podcast-summary/ui-brief.md` §2 / §6. Do not start this task if those `selected/*.png` files are absent — flag back to the user.
- [X] T047 [US1] Frontend `frontend/src/pages/EpisodeDetailPage.tsx` (US1 slice) — metadata, hook, three-act block, download buttons (Markdown / JSON / audio). The chapters/quotes/entity panels stub-out for US2. Visual layout binds to `specs/001-podcast-summary/design/selected/detail-page.png` and `…/selected/audio-bar.png`; component composition and copy follow `specs/001-podcast-summary/ui-brief.md` §3 / §6. Do not start this task if those `selected/*.png` files are absent — flag back to the user.

**Checkpoint**: After Phase 3 completes, the system delivers FR-001/2/3, 004, 005, 006, 007, 008, 009, 010, 014, 015, 017 (basic), 022, 023, 024, 025 (delete), and the SC-001..SC-007 metrics measurable via the Phase 3 fixtures (excluding chapter/quote/entity/TTS specifics). MVP demo is shippable.

---

## Phase 4: User Story 2 — Deep Dive with Chapters, Quotes, Entities (Priority P2)

**Story goal**: A processed episode shows a chapter outline with timestamps, key points in original order, and verbatim quotes whose timestamps drive the embedded `<audio>` player. A side panel lists named entities (people / books / products) with counts.

**Independent test**: From any US1-processed episode, click any quote timestamp → player seeks within ±10 s; run `make verify-quotes` → 100% of stored quotes pass verbatim check; entity panel shows counts > 0.

- [X] T048 [US2] Implement `backend/src/podsum/domain/chapter_segmenter.py::segment(transcript_segments, target_minutes=10) -> list[ChapterSpan]` — splits the transcript on natural boundaries (long pauses ≥ 1.5 s, topic-shift cues from heuristics + LLM hint). Pure function; emits start_ms / end_ms / text-window. Falls back to even time-buckets if no good signals (covers very-short audio edge case from spec).
- [X] T049 [P] [US2] [unit-test] `backend/tests/unit/test_chapter_segmenter.py` — ≥ 1 chapter for short audio, no zero-length chapters in audio with long silences, ordering preserved, monotonic timestamps.
- [X] T050 [US2] Extend `backend/src/podsum/domain/structured_parser.py` with `parse_chapter_payload(raw_json) -> list[ChapterDraft]` (each chapter: title, key_points: list[str], candidate_quotes: list[{text, start_ms}]). Reject empty key_points, reject quotes without timestamps.
- [X] T051 [P] [US2] [unit-test] `backend/tests/unit/test_structured_parser_us2.py` — empty key_points, missing timestamp, valid case, extra fields ignored.
- [X] T052 [US2] Implement `backend/src/podsum/domain/quote_verifier.py::verify(candidate_text, transcript_text) -> bool`: NFKC normalize both, strip outer whitespace, collapse internal whitespace runs to single spaces (preserve punctuation), check `candidate in transcript`. Also expose `verify_against_segments(candidate, segments) -> tuple[bool, int|None]` returning the matched segment's `start_ms` for storage.
- [X] T053 [P] [US2] [unit-test] `backend/tests/unit/test_quote_verifier.py` — verbatim ✓, paraphrase ✗, case-mismatch ✗, NFKC-equivalent ✓, double-space tolerated ✓, leading newline tolerated ✓, missing punctuation ✗, partial substring at segment boundary ✓.
- [X] T054 [US2] Implement `backend/src/podsum/domain/entity_extractor.py::extract(transcript_segments, llm) -> list[Entity]`. Calls the entity-extraction prompt, parses JSON list, *post-verifies* each entity's count by re-scanning the transcript (LLM-reported counts are advisory only; the persisted count is the ground-truth scan count). Pure-ish: takes an injected `LLMClient` so it remains unit-testable with mocks.
- [X] T055 [P] [US2] [unit-test] `backend/tests/unit/test_entity_extractor.py` — count-correction (LLM says 5, transcript has 3 → store 3), classification preserved, dedupe by (name, kind), sample_timestamps_ms ≤ 5.
- [X] T056 [US2] Extend `services/pipeline.py` with three new stages added after `summarize_three_act`: `chapter_outline` (required), `quote_verify` (required — runs `quote_verifier` against every candidate, persists only verified rows), `entity_extract` (optional → on retry exhaustion → `stage_status.entities = "failed_after_retries"` per FR-026).
- [X] T057 [US2] Extend `backend/src/podsum/exporters/markdown.py` to render Chapters section (title + start/end timestamp + key-points list + quotes with timestamp anchors) and Entities section (grouped by kind, with counts).
- [X] T058 [P] [US2] Extend `backend/src/podsum/exporters/json_export.py` to populate `chapters[]` and `entities[]` per the JSON Schema, ensuring every emitted quote has `verified=True` in DB before serialization (defense-in-depth on FR-012). Update `test_json_export_schema.py` cases.
- [X] T059 [US2] Frontend `frontend/src/components/ChapterOutline.tsx` (+ `ChapterCard.tsx`, `QuoteChip.tsx`) — renders chapters with clickable timestamps; clicking calls `audioRef.current.currentTime = start_ms/1000` and `play()` on the shared `<audio>` element from `EpisodeDetailPage`. Visuals follow `specs/001-podcast-summary/design/selected/quote-chip.png` (and any chapter-card mockup the user dropped under `design/components/` or `design/detail-page/`); component behavior follows `ui-brief.md` §3.5 / §6.6.
- [X] T060 [US2] Frontend `frontend/src/components/EntityPanel.tsx` — sidebar with three sections (people / books / products), counts, click-to-jump to a sample timestamp. Visual layout follows the entity-panel slice of `design/selected/detail-page.png` (or a dedicated `design/components/entity-panel.png` if the user supplied one); behavior follows `ui-brief.md` §3.6.
- [X] T061 [P] [US2] Backend audio file endpoint: confirm `GET /api/episodes/{id}/files/audio` correctly handles `Range:` requests with 206 responses (FastAPI/Starlette's `FileResponse` does this via `stream-range`; if not, write `backend/src/podsum/api/_range.py` helper). Required for SC-003 quote seek to feel instant.
- [X] T062 [P] [US2] CLI utility `scripts/verify_quotes.py` — connects to the SQLite DB, iterates all `quote` rows, replays `quote_verifier.verify()` against the stored transcript, prints PASS/FAIL totals, exits non-zero if any FAIL. Wired into `make verify-quotes` (T007). This is the SC-004 evaluation tool.
- [X] T063 [P] [US2] [integration-test] `backend/tests/integration/test_us2_quote_jump_math.py` — fabricates a fake transcript + chapter with a quote whose `start_ms = 90_000`, asserts the JSON export carries `start_ms: 90000` (frontend trust on the value drives ±10 s; backend correctness is what we test).

**Checkpoint**: System now delivers FR-011, 012, 013 fully; SC-003, SC-004 measurable on the eval set.

---

## Phase 5: User Story 3 — Audio Digest via TTS (Priority P2)

**Story goal**: Generate a TTS audio digest covering hook + three-act + chapter key points, in the source language, on user request.

**Independent test**: Click "Generate audio digest" on a US1+US2-processed episode, receive a playable MP3 in the same language whose narration covers the four required content blocks.

- [X] T064 [US3] Implement `backend/src/podsum/services/tts_client.py::DoubaoTTS` — uses `volcengine-python-sdk` to call 豆包语音合成 (火山引擎). Authenticates via `Settings.VOLC_ACCESS_KEY_ID` + `Settings.VOLC_SECRET_ACCESS_KEY` + `Settings.DOUBAO_TTS_APP_ID` + `Settings.DOUBAO_TTS_ACCESS_TOKEN` (these may equal the `DOUBAO_ASR_*` pair if both capabilities are enabled in a single volcengine application). Voice selection driven by source language: Chinese → `Settings.DOUBAO_TTS_VOICE_TYPE_ZH`, English → `Settings.DOUBAO_TTS_VOICE_TYPE_EN`. Streams MP3 bytes to the target file path. Tenacity retry budget configurable via `Settings`. Adapter selection in `services/tts_client.py` honors `Settings.TTS_PROVIDER` ∈ {`doubao` (default), `qwen` (DashScope `qwen-tts` / `cosyvoice-v2`)}; the Qwen-TTS implementation is registered in the same file as `QwenTTS` and selected by the env switch.
- [X] T065 [US3] Implement `backend/src/podsum/services/digest_script.py::build(episode_detail, lang) -> str` — composes the narration script: hook → three-act (each act prefaced) → "Chapter N: <title> — <key point 1>; <key point 2>" loop. Strict text-only output (no SSML in v1).
- [X] T066 [US3] Add the `tts` stage to `services/pipeline.py` as **optional** (FR-026): on retry exhaustion sets `summary_artifact.stage_status.tts = "failed_after_retries"` without failing the episode. Stage runs only when explicitly requested (lazy generation, not auto on first job) — triggered by `POST /api/episodes/{id}/digest`.
- [X] T067 [US3] Implement `POST /api/episodes/{id}/digest` and `GET /api/episodes/{id}/files/digest` in `api/episodes.py` per `contracts/http-api.md`. POST is idempotent: if `tts_path` exists and `stage_status.tts="present"`, return 200 with the path; otherwise enqueue and return 202.
- [X] T068 [P] [US3] [integration-test] `backend/tests/integration/test_us3_digest.py` — mocks the OpenAI TTS call to return a fixture MP3, asserts the digest endpoint returns 200 on the second call, asserts `stage_status.tts="failed_after_retries"` when the mock raises after retries.
- [X] T069 [US3] Frontend: add a "生成音频摘要" button + `<audio>` digest player + download link to `EpisodeDetailPage.tsx`. Disabled state when `stage_status.tts === "failed_after_retries"` until the user explicitly retries. Visuals follow the ArtifactBar slice of `design/selected/detail-page.png` and `ui-brief.md` §3.7.

**Checkpoint**: FR-016 delivered; SC-005 measurable.

---

## Phase 6: User Story 4 — Batch Submission & Concurrency (Priority P3)

**Story goal**: Submit multiple episodes at once with a configurable concurrency limit; finished episodes become readable while later ones are still in progress; one failure does not block the rest.

**Independent test**: Set `MAX_CONCURRENCY=2`, submit 5 URLs, observe at most 2 in `processing` state at any time, finished ones appear immediately.

- [ ] T070 [US4] Replace pipeline's serial driver with an asyncio queue + `asyncio.Semaphore(Settings.MAX_CONCURRENCY)`. Each in-flight job is one task; the queue persists in SQLite (jobs in `state='queued'`) so the in-memory queue is just a cache (FR-006 + FR-018).
- [ ] T071 [US4] Implement `POST /api/episodes/batch` in `api/episodes.py` accepting `{ items: [{source_type, source_ref}|file] }`; creates N episode+job rows in one transaction, returns the list of `{episode, job}` tuples.
- [ ] T072 [P] [US4] [integration-test] `backend/tests/integration/test_us4_concurrency.py` — submit 5 jobs with `MAX_CONCURRENCY=2`, mock ASR to sleep 200 ms, assert that at every 50 ms tick the count of `state='transcribing'` rows is ≤ 2.
- [ ] T073 [US4] Frontend: batch submit form (multi-line URL paste + multi-file picker) + a small "队列：N 处理中 / M 等待中" badge (`QueueBadge`) in the header bound to WS snapshot. Visuals follow the SubmitPanel slice of `design/selected/list-page.png` and `ui-brief.md` §2.2 / §6.1.

**Checkpoint**: FR-018 delivered; full feature-set complete.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T074 [P] Coverage gate: confirm `make test` fails when domain coverage < 80% (Constitution III). Add a CI workflow at `.github/workflows/ci.yml` running `make lint && make test && make test-frontend && make verify-quotes` (verify-quotes against a seeded fixture DB).
- [ ] T075 [P] Quickstart smoke-test script `scripts/smoke_test.sh` automating the 9-step walkthrough in `quickstart.md`. Used in CI nightly, not on every PR (because it hits cloud APIs — gated behind a `RUN_SMOKE=1` env flag).
- [ ] T076 [P] `detail.md` (Chinese): fill in 实现日志 / 设计取舍 / 踩坑记录 / 性能数据（M2 上 60 分钟样本的实际秒数）/ 评估结果（5 集中英文测试集的 SC-001..SC-005 数字）.
- [ ] T077 [P] `report.md` (Chinese): final 精修 — 项目概览、用户与场景、核心实现摘要（要点级，不抄 plan.md）、评估结果与图表、未来工作。Cross-link to `detail.md` for深度细节。
- [ ] T078 [P] README final pass: confirm `make install && cp .env.example .env && make run` brings up a working demo on a clean checkout. Note any assumed homebrew packages.
- [ ] T079 Manual evaluation — assemble the 5-episode mixed Chinese/English test set referenced by SC-001/SC-002/SC-005, run end-to-end through the deployed app, record scores in `detail.md`. Required to declare the feature done.
- [ ] T080 [P] Production-mode build: verify `make build && make serve` serves the SPA from FastAPI at `127.0.0.1:8000` (no Vite dev server required), suitable for the demo recording.

---

## Dependencies

```text
Phase 1 (Setup) ──► Phase 2 (Foundational) ──► Phase 3 (US1 — MVP)
                                                  │
                                                  ├─► Phase 4 (US2)  ─┐
                                                  │                   ├─► Phase 7 (Polish)
                                                  ├─► Phase 5 (US3) ──┤
                                                  │                   │
                                                  └─► Phase 6 (US4) ──┘
```

- Phases 4, 5, 6 each depend on Phase 3 outputs (Episode/Job/Pipeline scaffolding) but are independent of each other; they can be implemented in any order or in parallel by separate agents.
- Phase 7 depends on all stories being merged.
- Inside each phase, parallelism is marked with `[P]` per task; the rule is "different file, no dependency on an incomplete same-phase task."

## Parallel Execution Examples

**Setup** (Phase 1) — after T001/T002/T003 land, the following can run in parallel:
T004, T005, T006, T008, T009, T010, T011, T012.

**Foundational** (Phase 2) — after T013–T020 (sequential where they touch the same files), in parallel:
T018 (logging), T021 (prompt_assembler tests), T022 (prompt skeletons).

**US1** — after T026 + T029 + T030 + T032 land, in parallel:
T027 (URL ingest), T028 (YouTube ingest), T031 (postprocess tests), T033/T034 sequentially → T035 (parser tests), T037 (markdown) and T038 (json) → T039 (schema test), then T043/T044 integration tests in parallel with T045/T046/T047 frontend.

**US2** — T048 + T052 + T054 are independent (segmenter, verifier, extractor) → parallel; their tests (T049, T053, T055) parallel; T059 + T060 + T061 + T062 + T063 all parallel after the backend stages land.

## Implementation Strategy

1. **MVP first** (P1 only): finish Phases 1 → 2 → 3 → minimal Phase 7 (T078). Ship a demo where US1 works end-to-end. This is the lowest-risk path to a shippable course deliverable.
2. **Incremental delivery**: add Phases 4, 5, 6 in any order based on what unblocks evaluation; SC-001 (key-point accuracy) requires Phase 4; SC-005 (TTS quality) requires Phase 5.
3. **Coverage discipline**: every domain task has a paired `[unit-test]` task in the same phase. Do not let coverage drift below 80% — `make test` enforces this on every commit (Constitution III).
4. **Documentation discipline**: `detail.md` is appended to after every phase; `report.md` is rewritten at MVP completion and again at final submission.
5. **Cloud cost discipline**: every cloud API call goes through tenacity with bounded retries and a per-stage budget; resume-on-restart (T025) makes long debugging sessions cheap.
