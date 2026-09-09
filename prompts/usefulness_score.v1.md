---
role: usefulness_score
version: v1
lang_aware: true
---
Rate how useful this podcast episode is to a listener who is deciding whether to
spend time on it. Return JSON with exactly two keys: `score` and `rationale`.

`score` is an integer from 0 to 100. `rationale` is one sentence in {lang}
explaining the score with concrete grounds taken from the transcript.

Scoring bands (use the full range; do not cluster every episode in 70-85):

- 85-100: dense, verifiable, original insight; worth listening end to end.
- 70-84: a clear argument backed by evidence, with some filler.
- 50-69: a few useful points; reading the summary is enough for most listeners.
- 30-49: mostly common knowledge, repetition, chit-chat, or promotion.
- 0-29: almost no informational gain.

Judge only the informational value of what is said. Ignore audio quality, the
fame of the host or guests, production polish, and episode length — a long
episode is not more useful for being long, and a short one is not less useful
for being short. Do not reward confident delivery that is unsupported by
specifics.

Episode title:
{episode_title}

Transcript:
{transcript}
