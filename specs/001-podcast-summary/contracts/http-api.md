# Contract: HTTP API

**Feature**: 001-podcast-summary
**Date**: 2026-05-07
**Base URL**: `http://127.0.0.1:8000` (loopback only; FR-022)
**Content-Type**: `application/json` unless stated.
**Auth**: none (FR-023).

All non-2xx responses share the shape:
```json
{ "error": { "code": "string", "message": "string", "details": {} } }
```

Error codes used: `bad_input`, `not_found`, `conflict`, `payload_too_large`, `unsupported_media`, `upstream_failed`, `internal`.

---

## POST `/api/episodes`

Create a new episode and enqueue a job. Accepts either a JSON body (URL/YouTube) or a multipart form (file upload).

**Body — variant A: URL / YouTube**
```json
{
  "source_type": "direct_url" | "youtube",
  "source_ref": "https://example.com/ep01.mp3",
  "summary_style": "default | study_notes | business_insight | debate | quick_skim",
  "style_note": "optional, ≤ 200 chars",
  "detail_level": "concise | standard | detailed"
}
```

**Body — variant B: file upload (`multipart/form-data`)**
- `source_type=local_file`
- `file`: the audio file (mp3 / m4a / wav)
- `summary_style`, `style_note`, `detail_level`: optional, same values as variant A

**Summary style** (all three optional, both variants). `summary_style` names a section
of `prompts/summary_style.v2.md` and says *how* to write; `detail_level` says *how
much* (`standard` is what the summary prompts already describe, so it sends no
directive); `style_note` is the reader's own instruction. All three are stored on the
episode and composed into the `style_directive` slot of the summary prompts, which
shapes tone, emphasis and depth only — output keys, language and factual grounding are
unaffected. Omitting all three produces exactly the pre-style prompt text. All three
are validated before the audio is fetched, and they are reused verbatim on retry.

**201 Created**
```json
{
  "episode": { ...EpisodeSummary },
  "job": { ...Job }
}
```

**400 `bad_input`** unsupported `source_type`, malformed URL, unknown `summary_style` or `detail_level`, or `style_note` longer than 200 characters.
**413 `payload_too_large`** file > 1 GB OR (after probe) duration > 6 h (FR-024).
**415 `unsupported_media`** direct URL Content-Type not `audio/*` (FR-002), or YouTube link unresolvable (FR-003), or file extension not in {mp3, m4a, wav} (FR-001).
**409 `conflict`** an active (non-deleted) episode already exists for the same `(source_type, source_ref)` of types `direct_url` / `youtube`.

---

## GET `/api/episodes`

List episodes (most recent first). Pagination via `?limit=` (default 50, max 200) and `?cursor=` (opaque).

**200 OK**
```json
{
  "items": [ ...EpisodeSummary ],
  "next_cursor": "string | null"
}
```

Optional filters: `?status=pending|processing|done|partial|failed`, `?band=must_listen|worth_listening|skimmable|skippable` (FR-027; episodes whose `stage_status.usefulness != "present"` are excluded when this filter is set), and `?min_score=<0-100>`.

Optional sort: `?sort=created_at` (default, newest first) or `?sort=usefulness_score` (highest score first). Under `sort=usefulness_score`, unscored episodes sort last, ties broken by `created_at DESC`.

---

## GET `/api/episodes/{id}`

Full detail view: episode metadata + chapters with quotes + entities + artifact paths + per-stage status.

**200 OK** — `EpisodeDetail` (see schema in `episode-output.schema.json`).
**404 `not_found`**.

---

## DELETE `/api/episodes/{id}`

Atomic delete per FR-025: removes DB rows (CASCADE) and `data/<id>/` directory.

**204 No Content** on success.
**404 `not_found`**.

---

## POST `/api/episodes/{id}/retry`

Create a new `job` for the same episode, resuming from the latest persisted checkpoint (FR-006).

**202 Accepted** with the new `Job` object.
**404 `not_found`**.
**409 `conflict`** if a job is already in a non-terminal state.

---

## POST `/api/episodes/{id}/digest`

Trigger TTS audio digest generation (FR-016). Idempotent: if already present, returns 200 with the existing path; if previously `failed_after_retries`, kicks off a new attempt.

**200 OK**
```json
{ "tts_path": "data/<id>/digest.mp3", "status": "present" }
```

**202 Accepted** — synthesis kicked off, poll via `GET /api/episodes/{id}` or subscribe to WebSocket.

---

## GET `/api/episodes/{id}/files/markdown`

Stream the generated `summary.md`. **200** `text/markdown`. **404** if not yet present.

## GET `/api/episodes/{id}/files/json`

Stream the generated `summary.json` matching `episode-output.schema.json`. **200** `application/json`. **404** if not yet present.

## GET `/api/episodes/{id}/files/digest`

Stream the TTS digest. **200** `audio/mpeg`. **404** if not yet present.

## GET `/api/episodes/{id}/files/audio`

Stream the cached normalized audio for the in-page player (supports HTTP `Range` for seek). **200** / **206** `audio/mpeg`.

---

## GET `/api/health`

**200**
```json
{ "status": "ok", "version": "0.1.0" }
```

---

## Object schemas (response shapes)

`EpisodeSummary`:
```json
{
  "id": "ULID",
  "title": "string | null",
  "podcast_name": "string | null",
  "source_type": "local_file | direct_url | youtube",
  "duration_seconds": 0,
  "language": "zh | en | mixed | null",
  "status": "pending | processing | done | partial | failed",
  "stage_status": {
    "hook": "pending | present | missing | failed_after_retries",
    "three_act": "...",
    "chapters": "...",
    "entities": "...",
    "usefulness": "...",
    "tts": "..."
  },
  "usefulness": {
    "score": 78,
    "band": "must_listen | worth_listening | skimmable | skippable",
    "rationale": "string"
  },
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601"
}
```

`usefulness` is `null` (not an object with null fields) whenever `stage_status.usefulness != "present"` — the list view renders "未评分" in that case rather than a zero score.

`EpisodeDetail` extends `EpisodeSummary` with `hook`, `three_act`, `chapters[]`, `entities[]`, and `artifact_paths` (markdown/json/tts), plus `prompt_versions` (which includes `usefulness_score`). Authoritative shape lives in `episode-output.schema.json`.

`Job`:
```json
{
  "id": "ULID",
  "episode_id": "ULID",
  "state": "queued | fetching | transcribing | summarizing | tts | done | partial | failed",
  "stage_progress": { "transcribed_until_seconds": 0, "...": "..." },
  "attempt": 1,
  "error": "string | null",
  "started_at": "ISO-8601 | null",
  "finished_at": "ISO-8601 | null"
}
```
