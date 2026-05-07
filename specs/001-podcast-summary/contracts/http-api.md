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
  "source_ref": "https://example.com/ep01.mp3"
}
```

**Body — variant B: file upload (`multipart/form-data`)**
- `source_type=local_file`
- `file`: the audio file (mp3 / m4a / wav)

**201 Created**
```json
{
  "episode": { ...EpisodeSummary },
  "job": { ...Job }
}
```

**400 `bad_input`** unsupported `source_type`, malformed URL.
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

Optional filters: `?status=pending|processing|done|partial|failed`.

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
    "tts": "..."
  },
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601"
}
```

`EpisodeDetail` extends `EpisodeSummary` with `hook`, `three_act`, `chapters[]`, `entities[]`, and `artifact_paths` (markdown/json/tts), plus `prompt_versions`. Authoritative shape lives in `episode-output.schema.json`.

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
