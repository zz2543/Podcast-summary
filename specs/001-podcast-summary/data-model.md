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
| `summary_style` | TEXT | NOT NULL, DEFAULT `default` | preset id chosen in the submit modal; one of the sections of `prompts/summary_style.v1.md` |
| `style_note` | TEXT | NULL | reader's own instruction, ≤ 200 chars after normalization |
| `detail_level` | TEXT | NOT NULL, DEFAULT `standard` | `concise` / `standard` / `detailed`; how much gets written, independent of `summary_style` |
| `created_at` | DATETIME | NOT NULL | |
| `updated_at` | DATETIME | NOT NULL | |
| `data_dir` | TEXT | NOT NULL, UNIQUE | `data/<id>/` |

**Indexes**: `idx_episode_status` on `status`; `idx_episode_created` on `created_at DESC`.

**Validation**:
- `summary_style` MUST be one of `default`, `study_notes`, `business_insight`, `debate`, `quick_skim`; anything else is rejected at submission with `400 bad_input`.
- `detail_level` MUST be one of `concise`, `standard`, `detailed`; anything else is rejected the same way.
- `language` is decided by weighing CJK characters against Latin words, not by the per-utterance ASR labels: an episode is only `mixed` when the minority language carries ≥ 20% of the content. A Chinese episode that borrows English product names stays `zh`, because the value is fed to the summary prompts and `mixed` is not a language a model can write in.
- `style_note` is normalized before storage: control characters and newlines collapse to single spaces (so a note cannot forge its own instruction block in the assembled prompt), surrounding whitespace is trimmed, an empty result becomes NULL, and anything longer than 200 characters is rejected with `400 bad_input`.
- Both fields are fixed at submission time and reused verbatim on retry, so a retried episode is re-summarized in the style it was submitted with.
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
| `start_ms` | INTEGER | NOT NULL | see **Timing** below |
| `end_ms` | INTEGER | NOT NULL, CHECK `end_ms > start_ms` | see **Timing** below |
| `key_points` | TEXT (JSON array<string>) | NOT NULL | ordered list per FR-011 |
| `summary` | TEXT | NULL | optional prose; written only where the key points alone lose the causal thread |

**Indexes**: UNIQUE `(episode_id, idx)`.

**Timing**: the outline stage can only guess a chapter's range — it maps the Nth
chapter onto the Nth segmenter span, and the model may return more chapters than
there are spans, which used to leave every chapter after the first sharing one
identical range. The quote-verify stage therefore re-times chapters from their
verified key moments: chapter 0 starts at the episode start, every later chapter
starts at its earliest verified moment, chapters with no verified moment are
interpolated between their neighbours, and each chapter ends where the next one
begins. When no moment verifies at all, the span-based guess stands.

---

### `quote`

A key moment: a verified verbatim substring of the transcript plus the one-line
reading of it shown in the UI. The verbatim anchor is what gives the moment an
accurate timestamp, so it is stored even though `takeaway` is what the reader
sees first.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | INTEGER | PK AUTOINCREMENT | |
| `chapter_id` | INTEGER | NOT NULL, FK → `chapter.id` ON DELETE CASCADE | |
| `idx` | INTEGER | NOT NULL | order within chapter |
| `text` | TEXT | NOT NULL | the verbatim anchor, normalized |
| `takeaway` | TEXT | NULL | one sentence on what the listener gets here; NULL for rows written before key moments existed |
| `start_ms` | INTEGER | NOT NULL | timestamp the player will seek to; interpolated from where the anchor sits in the transcript |
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
| `usefulness_score` | INTEGER | NULL, CHECK (`usefulness_score IS NULL OR usefulness_score BETWEEN 0 AND 100`) | FR-027; NULL when `stage_status.usefulness != 'present'` |
| `usefulness_band` | TEXT | NULL, CHECK in (`must_listen`, `worth_listening`, `skimmable`, `skippable`, NULL) | FR-027; derived from the score by code, never written from the model response |
| `usefulness_rationale` | TEXT | NULL | one sentence, source language (FR-007) |
| `markdown_path` | TEXT | NULL | `data/<id>/summary.md` |
| `json_path` | TEXT | NULL | `data/<id>/summary.json` |
| `tts_path` | TEXT | NULL | `data/<id>/digest.mp3` |
| `stage_status` | TEXT (JSON) | NOT NULL | `{ "hook": "present", "three_act": "present", "chapters": "present", "entities": "missing", "usefulness": "present", "tts": "failed_after_retries" }` |
| `prompt_versions` | TEXT (JSON) | NOT NULL | `{ "one_liner": "v1", "three_act": "v1", "chapter_outline": "v1", "entity_extraction": "v1", "usefulness_score": "v1" }` (Constitution V) |

**Validation**:
- An episode reaches `episode.status='done'` only when `stage_status.hook = stage_status.three_act = stage_status.chapters = "present"`; if any of those is `missing`/`failed_after_retries`, `episode.status='failed'` instead. `usefulness` is optional and never gates `done`; like any other optional-stage failure it degrades the episode to `partial` (FR-026/FR-027).
- The three `usefulness_*` columns are written together in one transaction: either all three are non-NULL and `stage_status.usefulness = "present"`, or all three are NULL and `stage_status.usefulness ∈ {pending, missing, failed_after_retries}`. No partially-scored row. A failed re-run clears all three, so a stale score never outlives the run that produced it.
- `usefulness_band` is computed from `usefulness_score` by `domain/usefulness_scorer.py::band_for(score)` — `85-100 → must_listen`, `70-84 → worth_listening`, `50-69 → skimmable`, `0-49 → skippable`. The model never chooses the band.

**Backfill**: Episodes processed before this feature landed keep `usefulness_score IS NULL` and `stage_status.usefulness = "missing"`. They are re-scored only when the user retries the episode; the migration (`0003_usefulness_score`) does not call the LLM. SQLite cannot add the CHECK constraints to an existing table, so on migrated databases the range/band invariants rest on `parse_usefulness` and `band_for`, which are the only writers.

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
| Usefulness score is an integer in 0-100 | FR-027 | `domain/structured_parser.py::parse_usefulness` (rejects + retriggers; never clamps) |
| Usefulness band derived from score, not from the model | FR-027 | `domain/usefulness_scorer.py::band_for` (sole writer of `usefulness_band`) |
| Verbatim quote substring check | FR-012, SC-004 | `domain/quote_verifier.py` (only place `Quote.verified` becomes 1) |
| Required vs. optional stage gating | FR-026 | `services/pipeline.py` + `summary_artifact.stage_status` |
| Output language = source language | FR-007 | `domain/prompt_assembler.py` (binds `{lang}` slot) |
| Prompts versioned | Constitution V | `prompts/` only; `prompt_assembler.py` is the sole reader |
