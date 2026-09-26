---
role: three_act_summary
version: v4
lang_aware: true
---
Summarize this podcast in {lang}. Write every field in that language and do not
translate the episode into another one; keep product names, library names and
other technical terms exactly as they are spoken.

Return JSON with exactly these keys: `background`, `core_argument`, and
`conclusion`.

This is a short overview, not a transcript rewrite. Stay inside these budgets:

- `background`: at most 2 sentences. The problem the episode is answering.
- `core_argument`: at most 5 sentences. The reasoning itself, plus the main
  condition or trade-off the speaker attaches to it.
- `conclusion`: at most 3 sentences. What the speaker recommends and what they
  explicitly leave open.

Keep each field under roughly 110 words, or 180 characters for Chinese, Japanese
and Korean.

Ground every claim in the transcript. Because the budget is tight, select the
specifics that carry the argument — the decisive name, number, tool, step or
condition — instead of enumerating every one the speaker mentions; the chapter
outline is where the full detail belongs. Never pad to fill the budget, and
never replace a dropped specific with a vague generality: a shorter concrete
sentence beats a longer abstract one.

{style_directive}
Transcript:
{transcript}
