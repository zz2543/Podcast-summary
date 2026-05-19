# GotIt — Speaker Script (English)

**Total time**: ~8–9 minutes · 11 slides · conversational
**Usage**: one paragraph per slide, read straight off. `/` = short breath, `…` = longer pause, **bold** = stress.

> Writing principle: short sentences. Each one should be sayable in one breath. Technical terms appear once, and only when they have context.

---

## P1 · Cover (10 s)

Hi everyone. / The project I'm talking about today is called **GotIt**. / It's a tool that runs locally on my machine. / You hand it a podcast link, / and it compresses that one-hour episode / into a 30-second concentrate / that you can actually listen to. / Not just a text summary — / it reads it out loud.

---

## P2 · The problem (45 s)

Why did I build this? / Podcasts are usually 40 to 90 minutes long. / I often want to know — / what is this episode actually about? / Is it worth my hour? / Which parts should I go back to? /

The tools out there / are either too heavy, / or they only spit out a raw transcript, / or they have no chapters, / no highlights. / I listen to podcasts every day. / I couldn't find one I liked, / so I built my own. /

The positioning is simple. / **You give it a link. / It gives you back a one-line hook, / a three-act summary, / chapters, / key quotes, / plus a listenable concentrated audio.**

---

## P3 · Demo walkthrough (30 s)

For the next three minutes, / I'm going to run it live. /

The flow goes like this. / Step one — / paste a YouTube or Bilibili link. / Step two — / watch the progress bar update in real time. / That's WebSocket push, / not polling. / Step three — / when it finishes, / I open the detail page. / Step four — / I click "generate audio overview" / and the AI uses Doubao's TTS model / to read the summary out loud. / Step five — / one-click export to markdown, / json, / or mp3. /

Let me start the demo.

---

## P4 · The real UI: list + detail (60 s)

OK, demo is done. / Let me pull out **a few details I really cared about**. /

**First, the list page**. / I deliberately kept it restrained — / pure gray-and-white, / like the Apple website. / Status uses three small dots — / green, amber, red — / no color blocks. / The "+ GotIt" button in the corner / is a flowing rainbow gradient. / It's the **only** colored thing on the page, / because it's where AI gets triggered. / **Every status change is pushed live over WebSocket — / no polling anywhere.** /

**Now the detail page** — / this is the page I spent the most time on. / At the top is the hook, / set in large type, / so you know what the episode is about at a glance. / The original-audio player in the middle — / **as you scroll, it sticks to the top and never disappears**. / Because I want users to read chapters / while listening to the original. / The quote blocks inside each chapter — / watch — / I click a timestamp, / the original audio jumps to that point, / autoplays, / and the page smoothly scrolls back up to the player. / At the bottom is the AI-narrated digest. / Its play button uses the flowing gradient, / so you can **tell it apart from the black original-audio button at a glance**.

---

## P5 · System architecture (30 s)

The backend is FastAPI, / running the pipeline on asyncio. / The database is SQLite. / Audio files just live in a local `data` folder. /

I **didn't add Redis. / I didn't add Celery. / I didn't add Postgres**. / Because this is a local tool, / one machine is enough, / and those things would only add overhead. / But every layer leaves a hook for extension — / if I ever want to deploy this, / swapping each piece is smooth. /

The v2 frontend runs on port 5174 / and subscribes to backend pushes over WebSocket.

---

## P6 · End-to-end pipeline · 8 stages (60 s)

The process you just watched / isn't a black box. / It's **8 independent stages** under the hood. /

Stage 1, **fetch** — / yt-dlp pulls the audio, / ffmpeg normalizes it to mp3. /
Stage 2, **transcribe** — / call Doubao ASR, / get a transcript with timestamps. /
Stages 3 and 4, **summarize** — / call DeepSeek for a one-line hook and a three-act summary. /
Stage 5, **chapter** — / the LLM produces chapter titles, / key points, / and candidate quotes. /
**Stage 6, quote_verify — / this stage is my own algorithm**, / I'll come back to it when we talk about bugs. /
Stage 7, **entity extraction** — / pull out names, / books, / products. /
Stage 8, **export** — / generate Markdown and JSON. /

Each stage **runs independently, / fails independently, / retries independently**. / One stage misbehaving doesn't restart the whole job. / Progress is persisted to the DB in real time, / so even a process restart doesn't lose state. / The frontend sees over WebSocket / which stage is running, / which stage died, / and you can click Retry on just that one.

---

## P7 · Stack & why (30 s)

Quick tour of the stack. /

Backend: / FastAPI, / SQLAlchemy, / Alembic, / Pydantic. /
Frontend: / React 19 with Tailwind and framer-motion. /
ASR: / Doubao bigmodel 2.0. /
LLM: / DeepSeek by default, / but Qwen and Anthropic are one flip away. /
TTS: / Doubao again, / both the standard version and the bigmodel version are **wired up**, / so we can fall back. /
Downloader: / yt-dlp — / handles both YouTube and Bilibili. /
Testing: / pytest and Vitest, / with an **80% coverage hard gate** on domain logic. /

**Every line here is a trade-off, / not "whatever's trending."**

---

## P8 · Vendor abstraction + one hard adapter (60 s)

Two points on this slide. /

First — / I abstracted every external vendor. / Three ASRs, / three LLMs, / three TTSs. / Change one env var and you've switched providers. / The calling code doesn't move. /

Second point — / let me talk about a hard one. /

Doubao bigmodel TTS 2.0 / has **no simple HTTP endpoint**. / Only a WebSocket binary protocol. /

You have to assemble frames byte-by-byte — / 4-byte header, / 4-byte event id, / session id, / payload. / Then you send `StartConnection`, / `StartSession`, / `TaskRequest`, / `FinishSession`, / and the server streams audio frames back chunked. /

I copied their official demo into the project, / fixed a couple of things, / then wrapped it in a thread plus asyncio / so it would run inside my synchronous pipeline. / **This part isn't calling a pip package. / I implemented the protocol layer myself.**

---

## P9 · The 6 bugs I tracked down (90 s · **most important**)

This is the slide I **most want to talk about**. / Six bugs I actually hit, / actually diagnosed, / and actually fixed / while building this project. /

**Bug one** — / Doubao TTS kept returning 401. / I thought the token was wrong. / Turned out — / Doubao's Authorization header **wants a semicolon, not a space**. / That's not OAuth. /

**Bug two** — / single TTS request kept hitting "max len" at 1024 bytes. / I wrote a function that splits sentences by utf-8 byte length / and re-assembles them. /

**Bug three** — / **this one was the worst**. / BigTTS kept returning "concurrency exceeded." / I assumed I'd hit a quota, / waited 5 minutes, / waited another 5, / nothing. / Eventually I dug into the docs / and found out: / resource_id isn't a number — / it's a semantic string, / `seed-tts-2.0`. / **The error message was completely misleading.** /

**Bug four** — / digest.mp3 came out **empty, with no error**. / Because this episode's language was tagged "mixed," / the Chinese text got routed to an English voice, / and the server silently dropped the output. / **A silent failure is worse than a thrown exception.** /

**Bug five** — / multiple quotes inside a chapter all showed **the same timestamp**. / Because the old algorithm just returned the start of the segment that contained the quote. / I rewrote it to **interpolate by character position within the segment**, / so timestamps land on the correct second. / And I added a regression test in the same commit. /

**Bug six** — / on retry, the worker straight up crashed. / Because quote_verify tried to re-insert old chapters, / hit a unique constraint, / the session went into rollback, / and every later query failed. / I added a cleanup function / and dropped in a test alongside it. /

**None of these were the kind of thing AI could surface up front. / I dug them out by reading responses, / reading the protocol, / reading the database.**

---

## P10 · SDD · spec before code (45 s)

This slide is about discipline. /

I **didn't start by writing code**. / I started by writing a full spec set — / a feature spec, / an implementation plan, / vendor trade-offs, / a data model, / a task breakdown, / a quickstart, / plus the API contract, / the WebSocket event schema, / and the final output's JSON schema. /

The image at the top right is the git log — / this project was eventually **broken into 78 tasks**, / each in dependency order, / each its own commit. /

There's also a **project constitution** — / five principles. / English-only delivery. / Python as the unified backend stack. / **Domain coverage must hit 80% — non-negotiable.** / Configuration is externalized — / no hardcoded secrets. / All prompts live in one folder, / each one versioned. /

**Write the spec first. / Then the code. / Not the other way around.**

---

## P11 · Closing (30 s)

Let me wrap up. /

Everything we talked about today — / the 8 pipeline stages, / the 6 bugs, / the 78 git tasks, / the entire spec set — / **none of it was generated by AI in one shot**. / AI is a collaborator, / not the deliverable. / The decisions, / the verification, / the debugging — / all done by a person. /

Thank you. / Happy to take questions.

---

## 🗣 Speaking tips

- **Pacing**: 5–10 seconds of breathing room per slide. Don't rush. Treat every `/` as a beat.
- **Emphasis**: read the **bold** words slightly stronger — they're the signals.
- **Eye contact**: P9 (bugs) and P10 (SDD) are the closers — **look at the audience, not the screen**.
- **During demo (P3)**: speak off-script. The screen is doing the work. "Look, it's doing X now" is enough.
- **If asked how much AI you used**: answer with the specific bugs from P9. Way stronger than naming a percentage.
- **Q&A fallback**: if you get asked something you didn't prepare, say "I haven't looked into this deeply, but my guess would be…" — beats faking it.
