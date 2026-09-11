---
role: three_act_summary
version: v3
lang_aware: true
---
Summarize this podcast in {lang}. Write every field in that language and do not
translate the episode into another one; keep product names, library names and
other technical terms exactly as they are spoken.

Return JSON with exactly these keys: `background`, `core_argument`, and
`conclusion`.

Ground every claim in the transcript and keep the specifics — names, numbers,
tools, steps, conditions — rather than abstracting them away. `background` sets
up the problem the episode is answering. `core_argument` carries the actual
reasoning, including the conditions and trade-offs the speaker attaches to it,
not just the position. `conclusion` is what the speaker ends up recommending and
what they explicitly leave open.

{style_directive}
Transcript:
{transcript}
