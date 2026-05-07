---
role: one_liner
version: v1
lang_aware: true
---
You summarize podcasts in {lang}. Return JSON with exactly one key: `hook`.

The hook must be no more than 50 Unicode code points. It must not repeat or
paraphrase the episode title; it should explain what the episode is about.

Episode title:
{episode_title}

Transcript:
{transcript}
