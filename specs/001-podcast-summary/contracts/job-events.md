# Contract: WebSocket Job Events

**Feature**: 001-podcast-summary
**Date**: 2026-05-07
**URL**: `ws://127.0.0.1:8000/api/ws/jobs`

The frontend opens a single WebSocket on app load and receives push updates for every job state change in the system (single-user, single tab is the assumed model — fan-out is trivial).

## Frames

All frames are JSON objects with a `type` discriminator.

### Server → Client

`hello` — sent immediately after the connection opens.
```json
{ "type": "hello", "server_version": "0.1.0", "now": "ISO-8601" }
```

`snapshot` — current state of every active job, sent right after `hello` so the frontend can render without a separate REST call.
```json
{
  "type": "snapshot",
  "jobs": [ ...Job ]
}
```

`job_update` — emitted on any state or `stage_progress` change.
```json
{
  "type": "job_update",
  "job": { ...Job },
  "episode_status": "processing | done | partial | failed"
}
```

`stage_status_update` — emitted when an individual stage transitions in `summary_artifact.stage_status`.
```json
{
  "type": "stage_status_update",
  "episode_id": "ULID",
  "stage": "hook | three_act | chapters | entities | tts",
  "status": "present | missing | failed_after_retries"
}
```

`error` — terminal: server is closing the connection due to an internal failure.
```json
{ "type": "error", "code": "string", "message": "string" }
```

### Client → Server

The client does not need to send anything; the connection is one-way push. If the client sends any frame, the server ignores it.

## Cadence guarantees

- `job_update` is debounced server-side to at most 2 messages per second per job (the `stage_progress` updates inside one stage are coalesced).
- WebSocket disconnect: client reconnects with exponential backoff (250ms → 4s); on reconnect, the server resends `snapshot` so no events are missed even if `job_update`s were dropped.
