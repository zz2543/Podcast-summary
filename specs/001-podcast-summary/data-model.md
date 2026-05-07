# Data Model: Podcast Summary System

**Feature**: 001-podcast-summary
**Date**: 2026-05-07
**Storage**: SQLite (relational tables below) + filesystem (`data/<episode_id>/...` for large blobs).

All identifiers are ULIDs (sortable, URL-safe). All timestamps are TZ-aware UTC (`DATETIME` stored as ISO-8601 text). All tables are created/migrated by Alembic.

---

## ER overview

```text
Episode 1───*  Job
Episode 1───*  TranscriptSegment
Episode 1───*  Chapter
Chapter  1───*  Quote
Episode 1───*  Entity
Episode 1───1  SummaryArtifact   (one-to-one; created on first successful summarization)
```

---

## Tables

### `episode`

The user-visible entry. One row per submitted item; surviving across retries and restarts.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | TEXT (ULID) | PK | |
| `source_type` | TEXT | NOT NULL, CHECK in (`local_file`, `direct_url`, `youtube`) | FR-001/2/3 |
| `source_ref` | TEXT | NOT NULL | filename, URL, or YouTube ID |
| `title` | TEXT | NULL | populated from source metadata or LLM later |
| `podcast_name` | TEXT | NULL | best-effort |
| `guests` | TEXT (JSON array) | NULL | inferred best-effort |
| `duration_seconds` | INTEGER | NULL | filled after ingestion probe |
| `language` | TEXT | NULL, CHECK in (`zh`, `en`, `mixed`, NULL) | FR-007 |
| `status` | TEXT | NOT NULL, CHECK in (`pending`, `processing`, `done`, `failed`, `partial`) | aggregated from latest job |
| `created_at` | DATETIME | NOT NULL | |
| `updated_at` | DATETIME | NOT NULL | |
| `data_dir` | TEXT | NOT NULL, UNIQUE | `data/<id>/` |

**Indexes**: `idx_episode_status` on `status`; `idx_episode_created` on `created_at DESC`.

**Validation**:
- `source_ref` MUST be unique across non-deleted rows for `(source_type, source_ref)` of types `direct_url` and `youtube` (no double-submission).
- On insertion of a new episode, `duration_seconds` must already pass the FR-024 cap (≤ 21600 s = 6 h) AND file size on disk must be ≤ 1 GB; otherwise the row is never created.

**Status transitions** (driven by current Job): `pending → processing → {done | partial | failed}`. `partial` per FR-026 means required stages succeeded and at least one optional stage is missing.

---

### `job`

A run of the pipeline for an episode. New retries create new rows; old rows are kept for diagnostics.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | TEXT (ULID) | PK | |
| `episode_id` | TEXT | NOT NULL, FK → `episode.id` ON DELETE CASCADE | |
| `state` | TEXT | NOT NULL, CHECK in (`queued`, `fetching`, `transcribing`, `summarizing`, `tts`, `done`, `partial`, `failed`) | |
| `stage_progress` | TEXT (JSON) | NOT NULL, default `{}` | per-stage checkpoint blob, e.g. `{"transcribed_until_seconds": 1800}` |
| `error` | TEXT | NULL | last error message if failed |
| `started_at` | DATETIME | NULL | |
| `finished_at` | DATETIME | NULL | |
| `attempt` | INTEGER | NOT NULL DEFAULT 1 | |

**Indexes**: `idx_job_episode` on `episode_id`; `idx_job_state` on `state`.

**Resume rule (FR-006)**: On startup, the pipeline service queries `state IN ('queued','fetching','transcribing','summarizing','tts')`, marks all such rows `state='queued'`, and re-enqueues them. The new run picks up from `stage_progress`.

---

### `transcript_segment`

The smallest reusable unit of transcription, persisted so retries do not redo ASR.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | INTEGER | PK AUTOINCREMENT | |
| `episode_id` | TEXT | NOT NULL, FK → `episode.id` ON DELETE CASCADE | |
| `idx` | INTEGER | NOT NULL | 0-based ordering |
| `start_ms` | INTEGER | NOT NULL | |
| `end_ms` | INTEGER | NOT NULL, CHECK `end_ms > start_ms` | |
| `text` | TEXT | NOT NULL | |
| `language` | TEXT | NULL, CHECK in (`zh`, `en`, NULL) | per-segment label, used for mixed audio |

**Indexes**: `idx_segment_episode_idx` UNIQUE on `(episode_id, idx)`; `idx_segment_episode_start` on `(episode_id, start_ms)`.

**Note**: For very large episodes the raw ASR JSON (with all word-level timestamps if the provider returns them) is also written to `data/<id>/transcript.raw.json` so we keep word-level data without bloating the DB.

---

### `chapter`

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | INTEGER | PK AUTOINCREMENT | |
| `episode_id` | TEXT | NOT NULL, FK → `episode.id` ON DELETE CASCADE | |
| `idx` | INTEGER | NOT NULL | 0-based ordering |
| `title` | TEXT | NOT NULL | |
| `start_ms` | INTEGER | NOT NULL | |
| `end_ms` | INTEGER | NOT NULL, CHECK `end_ms > start_ms` | |
| `key_points` | TEXT (JSON array<string>) | NOT NULL | ordered list per FR-011 |

**Indexes**: UNIQUE `(episode_id, idx)`.

---

### `quote`

A verified verbatim substring of the transcript shown in the UI.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | INTEGER | PK AUTOINCREMENT | |
| `chapter_id` | INTEGER | NOT NULL, FK → `chapter.id` ON DELETE CASCADE | |
| `idx` | INTEGER | NOT NULL | order within chapter |
| `text` | TEXT | NOT NULL | normalized form actually displayed |
| `start_ms` | INTEGER | NOT NULL | timestamp the player will seek to |
| `verified` | BOOLEAN | NOT NULL DEFAULT 0 | rows with `verified=0` MUST NOT leave the DB layer (FR-012, SC-004) |

**Validation**: A repository invariant — `Quote.verified` is set to `1` only by `quote_verifier.verify()` and only after the verbatim-substring check passes. Read paths filter `verified=1`.

---

### `entity`

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | INTEGER | PK AUTOINCREMENT | |
| `episode_id` | TEXT | NOT NULL, FK → `episode.id` ON DELETE CASCADE | |
| `name` | TEXT | NOT NULL | |
| `kind` | TEXT | NOT NULL, CHECK in (`person`, `book`, `product`) | |
| `count` | INTEGER | NOT NULL, CHECK > 0 | occurrences |
| `sample_timestamps_ms` | TEXT (JSON array<int>) | NOT NULL | up to 5 sample positions |

**Indexes**: UNIQUE `(episode_id, name, kind)`.

---

### `summary_artifact`

Aggregated outputs and per-stage availability, mirroring FR-026's partial-degradation semantics.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `episode_id` | TEXT | PK, FK → `episode.id` ON DELETE CASCADE | |
| `hook` | TEXT | NULL | one-line, ≤ 50 chars (validated at write time) |
| `three_act` | TEXT (JSON) | NULL | `{background, core_argument, conclusion}` |
| `markdown_path` | TEXT | NULL | `data/<id>/summary.md` |
| `json_path` | TEXT | NULL | `data/<id>/summary.json` |
| `tts_path` | TEXT | NULL | `data/<id>/digest.mp3` |
| `stage_status` | TEXT (JSON) | NOT NULL | `{ "hook": "present", "three_act": "present", "chapters": "present", "entities": "missing", "tts": "failed_after_retries" }` |
| `prompt_versions` | TEXT (JSON) | NOT NULL | `{ "one_liner": "v1", "three_act": "v1", "chapter_outline": "v1", "entity_extraction": "v1" }` (Constitution V) |

**Validation**: An episode reaches `episode.status='done'` only when `stage_status.hook = stage_status.three_act = stage_status.chapters = "present"`; if any of those is `missing`/`failed_after_retries`, `episode.status='failed'` instead.

---

## Filesystem layout (per episode)

```text
data/<episode_id>/
├── audio.original.<ext>         # cached audio (deleted on FR-025 deletion)
├── audio.normalized.mp3         # ffmpeg-normalized for ASR
├── transcript.raw.json          # provider-native ASR response (with word timestamps if available)
├── transcript.normalized.json   # post-processed segments (matches DB segments)
├── summary.md                   # human-readable export (FR-014)
├── summary.json                 # machine-readable export (FR-015)
└── digest.mp3                   # TTS audio digest (FR-016, optional)
```

Atomic episode delete (FR-025) = `DELETE FROM episode WHERE id = ?` (CASCADEs the lot) + `shutil.rmtree(data/<id>/)`, in that order, in a try/except that logs orphan dirs.

---

## Validation rules summary

| Rule | Source | Enforced where |
|------|--------|----------------|
| Hard input cap 6 h / 1 GB | FR-024 | `services/ingest.py` (rejected before episode row creation) |
| Audio MIME validation for direct URL | FR-002 | `services/ingest.py` |
| YouTube fail-fast on restricted videos | FR-003 | `services/ingest.py` |
| ≤ 50-char hook, distinct from title | FR-009 | `domain/structured_parser.py` (rejects + retriggers if violated) |
| Verbatim quote substring check | FR-012, SC-004 | `domain/quote_verifier.py` (only place `Quote.verified` becomes 1) |
| Required vs. optional stage gating | FR-026 | `services/pipeline.py` + `summary_artifact.stage_status` |
| Output language = source language | FR-007 | `domain/prompt_assembler.py` (binds `{lang}` slot) |
| Prompts versioned | Constitution V | `prompts/` only; `prompt_assembler.py` is the sole reader |
