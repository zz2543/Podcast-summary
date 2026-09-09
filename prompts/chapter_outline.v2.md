---
role: chapter_outline
version: v2
lang_aware: true
---
Create a chapter outline in {lang}. Return JSON with a `chapters` array.

Each chapter must include `title`, `key_points`, and `candidate_quotes`.
Every quote must be copied verbatim from the transcript and include `start_ms`.
The directive below may shape titles and key points; it never changes how quotes
are selected, which stay verbatim with an accurate `start_ms`.

{style_directive}
Transcript:
{transcript}
