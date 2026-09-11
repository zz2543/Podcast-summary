---
role: chapter_outline
version: v3
lang_aware: true
---
Create a chapter outline in {lang}. Write every field in that language and do not
translate the episode into another one; keep product names, library names and
other technical terms exactly as they are spoken.

Return JSON with a `chapters` array. Each chapter has `title`, `key_points` and
`key_moments`, and may have `summary`.

`title` — what this stretch of the episode is actually about, not a generic label.

`key_points` — four to six entries. Each is a complete sentence that carries the
specific thing that was said: the tool, the number, the step, the rule, the
trade-off, the reason a decision went that way. "Write two hard rules into
AGENTS.md: every change needs its own commit, and tests must be written and
passing before handing back" is a key point. "AI writes code and runs tests" is
not — it names a topic and drops the content. Never merge two distinct examples
into one generic point.

`summary` — optional, two to four sentences. Include it only where the points
alone lose the thread: the causal chain, the reasoning behind a choice, what the
speaker tried first and why it failed. Omit the field entirely when the points
already stand on their own.

`key_moments` — two to three per chapter. Each has `quote` and `takeaway`.
`quote` must be copied from the transcript character for character; it is used to
locate the moment in the audio, so an approximation is useless. `takeaway` is one
sentence in {lang} saying what the listener actually gets at that moment. Choose
moments that state a conclusion, a rule, a number, a definition, a trade-off or a
concrete instruction. Never choose a rhetorical question, a topic announcement, a
transition, or a line that only makes sense with the surrounding paragraph.

{style_directive}
Transcript:
{transcript}
