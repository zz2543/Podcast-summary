---
role: chapter_outline
version: v1
lang_aware: true
---
Create a chapter outline in {lang}. Return JSON with a `chapters` array.

Each chapter must include `title`, `key_points`, and `candidate_quotes`.
Every quote must be copied verbatim from the transcript and include `start_ms`.

Transcript:
{transcript}
