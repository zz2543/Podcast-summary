# Feature Specification: Podcast Summary System

**Feature Branch**: `001-podcast-summary`
**Created**: 2026-05-07
**Status**: Draft
**Input**: User description: "Podcast Summary System — accept local audio / direct audio URL / YouTube link, transcribe, and produce a structured Chinese-or-English summary (one-line hook, three-act summary, chapter outline with key points and verbatim quotes, named-entity list) plus Markdown / JSON outputs and a TTS-rendered audio digest, exposed through a polished web UI."

## Clarifications

### Session 2026-05-07

- Q: Deployment & user model — single-user local web vs. multi-user hosted? → A: Single-user local web app (loopback only, no auth, single shared local datastore).
- Q: Resume durability — process-lifetime only vs. across restarts? → A: Persist transcript segments AND job state across process/server restarts.
- Q: Hard input length / size limit per episode? → A: 6 hours / 1 GB hard cap; submissions exceeding either MUST be rejected before transcription.
- Q: Retention & deletion policy for processed episodes? → A: Retain indefinitely; UI provides per-episode manual delete that purges audio cache, transcript, Markdown/JSON, and TTS digest together. No automatic expiry.
- Q: Output policy when later pipeline stages keep failing after retries? → A: Partial degraded output — failed stages are marked missing in UI/JSON; succeeded stages remain visible and downloadable. Hook + three-act + chapter outline are required for an episode to be marked "done"; TTS is optional.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Triage New Episodes Overnight (Priority: P1)

A subscriber drops 5 newly released podcast episodes into the system in the evening. By next morning, each episode has a one-line hook (≤ 50 characters) and a three-act summary (Background / Core Argument / Conclusion). The user reads the hooks first, then opens the full summary only for episodes worth a deeper look — saving roughly an hour per low-value episode.

**Why this priority**: This is the core value proposition. Without fast, reliable triage output, the system has no reason to exist. It alone constitutes a viable MVP.

**Independent Test**: Submit a 60-minute MP3 file via the web UI; confirm the system completes processing within 10 minutes on the reference hardware and produces a one-line hook plus a three-act summary readable in the UI and downloadable as Markdown/JSON.

**Acceptance Scenarios**:

1. **Given** a 60-minute Chinese podcast MP3 uploaded, **When** processing finishes, **Then** the user sees a hook of ≤ 50 Chinese characters that is informationally distinct from (not a paraphrase of) the original episode title, plus a three-act Background/Core Argument/Conclusion summary in Chinese.
2. **Given** an English podcast direct-audio URL submitted, **When** processing finishes, **Then** all generated summary fields are in English (input language preserved, no translation).
3. **Given** processing fails midway through transcription, **When** the user retries the same job, **Then** already-transcribed segments are reused and only the failed work is repeated.

---

### User Story 2 - Deep Dive with Chapter Outline and Quotes (Priority: P2)

A user finds an episode worth studying. They open its detail page and see a chapter outline (auto-segmented with start/end timestamps), each chapter listing its key points in original-text order plus verbatim quotes with clickable timestamps that jump the embedded player to that moment. They also see a named-entity sidebar (people / books / products) with occurrence counts.

**Why this priority**: This turns the system from a triage tool into a study aid — high value, but useless without P1 working first.

**Independent Test**: Open the detail view of any successfully processed episode; click any quote timestamp and verify the player seeks to within ±10 seconds of the spoken phrase; verify each quote substring exactly matches a substring of the transcript.

**Acceptance Scenarios**:

1. **Given** a processed episode, **When** the user clicks a quote's timestamp, **Then** the audio player seeks to a position within ±10 seconds of where the quote was actually spoken.
2. **Given** a processed episode, **When** automated verification runs, **Then** every displayed quote string is found verbatim (substring match) in the transcript.
3. **Given** a processed episode, **When** the user opens the entity panel, **Then** people, books, and product names are listed separately with the number of times each appears in the transcript.

---

### User Story 3 - Listen to a Condensed Audio Digest (Priority: P2)

A commuter wants the gist of a 90-minute episode but cannot read on the go. They click "Generate audio digest" on the detail page; the system synthesizes a TTS rendering of the structured summary (hook + three-act + chapter key points) and exposes it as a playable / downloadable audio file.

**Why this priority**: Differentiated value vs. plain text summarizers, but depends on P1 outputs existing first.

**Independent Test**: Trigger audio digest generation on a processed episode; confirm a playable audio file is produced and that listening to it conveys the hook, three-act summary, and chapter key points in the same language as the source.

**Acceptance Scenarios**:

1. **Given** a processed English episode, **When** the user requests an audio digest, **Then** a playable audio file is produced whose narration is in English and covers hook + three-act + chapter key points.
2. **Given** a processed Chinese episode, **When** the user requests an audio digest, **Then** the digest is narrated in Chinese with natural prosody (no obvious robotic mispronunciation of common Chinese words).

---

### User Story 4 - Batch Submission with Parallel Processing (Priority: P3)

A power user submits 5 episodes at once and configures concurrency. The system processes them in parallel (up to the configured limit), shows per-episode progress, and lets the user start reading finished summaries while later ones are still running.

**Why this priority**: Quality-of-life for heavy users; the system is still usable serially without it.

**Independent Test**: Submit 5 episodes with concurrency = 3; verify at most 3 are processing simultaneously and finished episodes become readable while others remain in progress.

**Acceptance Scenarios**:

1. **Given** a configured concurrency limit of N, **When** more than N episodes are submitted, **Then** at most N are in the "processing" state at any time and the rest are queued.
2. **Given** one episode in a batch fails, **When** the failure is reported, **Then** the remaining episodes continue to completion and the failed one can be retried independently.

---

### Edge Cases

- **YouTube link unavailable / age-gated / region-locked**: System surfaces a clear error indicating the link could not be resolved, without leaving a half-created job.
- **Direct audio URL returns non-audio content** (HTML page, paywall, redirect loop): System validates content type and rejects the job before transcription with an actionable error.
- **Mixed Chinese/English podcast** (e.g., tech shows): Transcript and summary preserve the original mixed text; no forced translation in either direction.
- **Very short audio (< 2 minutes)**: System still produces all required outputs; the chapter outline may legitimately contain a single chapter.
- **Very long audio**: A hard cap of **6 hours duration** AND **1 GB file size** applies; submissions exceeding either limit are rejected at ingestion with a clear length/size error rather than starting transcription. The 10-minute performance SLA (FR-019 / SC-006) only applies to the 60-minute reference case; episodes longer than 60 minutes process on a best-effort basis.
- **Quote that the LLM "almost" matches but is not verbatim**: Programmatic verification rejects it; the system either drops the quote or regenerates rather than displaying a fabricated one.
- **Network drop mid-transcription**: On retry, already-transcribed segments are reused (no duplicated ASR cost or wall time).
- **Audio with long silences or non-speech segments**: The chapter splitter does not produce zero-length or absurdly short chapters from silence alone.
- **Title with no useful keywords**: The one-line hook still conveys the actual content (its job is to differ from the title in informational value).

## Requirements *(mandatory)*

### Functional Requirements

**Input ingestion**

- **FR-001**: System MUST accept local audio file uploads in mp3, m4a, and wav formats via the web UI, subject to the input limits in FR-024.
- **FR-002**: System MUST accept a direct audio URL and resolve it by (a) issuing an HTTP HEAD/GET, (b) verifying the response Content-Type is an audio MIME, and (c) rejecting non-audio responses with an actionable error before any transcription work begins.
- **FR-003**: System MUST accept a YouTube video URL, extract its audio track, and proceed with the audio-only pipeline; non-resolvable / restricted videos MUST fail fast with a clear reason.
- **FR-004**: System MUST treat every submission as a discrete *job* with a stable identifier so progress, retries, and outputs can be referenced unambiguously.

**Input limits**

- **FR-024**: System MUST enforce a hard input cap of **6 hours of audio duration** AND **1 GB of file/transferred size** per episode. Submissions exceeding either threshold MUST be rejected at the ingestion stage with an actionable error and MUST NOT consume any ASR/LLM/TTS API budget.

**Transcription & resumability**

- **FR-005**: System MUST transcribe submitted audio with word- or segment-level timestamps sufficient to back the ±10-second quote-jump requirement.
- **FR-006**: System MUST preserve already-transcribed segments AND job state (queue position, current stage, per-stage progress markers) across process/server restarts. After an unclean shutdown, restarting the server MUST recover the same set of jobs in their previous states; in-progress jobs MUST resume from the latest persisted checkpoint without re-running already-completed stages (in particular, ASR work already done MUST NOT be repeated).
- **FR-007**: System MUST detect the source language (Chinese, English, or mixed) and preserve the original language in all downstream outputs without translating.

**Summarization outputs (per episode)**

- **FR-008**: System MUST produce **metadata** for each episode: title, podcast name, guest(s) (if discoverable from the transcript or source metadata), duration, and original source link.
- **FR-009**: System MUST produce a **one-line hook** of ≤ 50 characters (Chinese characters or English words counted appropriately) whose informational content differs from the original episode title — i.e., it tells the reader what the episode is *about*, not just what it is *called*.
- **FR-010**: System MUST produce a **three-act summary** with explicit Background / Core Argument / Conclusion sections.
- **FR-011**: System MUST produce a **chapter outline** by auto-segmenting the episode; each chapter MUST include a chapter title, start time, end time, an ordered list of key points faithful to the original sequence, and zero or more verbatim quotes each carrying a timestamp.
- **FR-012**: Every quote shown to users MUST be verifiable as a verbatim substring of the transcript via an automated check; quotes failing the check MUST NOT be displayed.
- **FR-013**: System MUST produce an **entity list** of people, books, and products mentioned, each with an occurrence count.

**Output formats**

- **FR-014**: System MUST emit a Markdown file per episode containing all outputs (metadata, hook, three-act summary, chapter outline with quotes, entity list) suitable for human reading.
- **FR-015**: System MUST emit a JSON file per episode containing the same outputs in a machine-readable schema (schema details deferred to plan phase) with stable field names so downstream tooling can rely on them.
- **FR-016**: System MUST be able to synthesize a TTS audio digest covering hook + three-act summary + chapter key points, in the source language, on user request.

**Web UI**

- **FR-017**: The web UI MUST allow submitting any supported input type, viewing per-job progress, browsing finished episodes, opening a detail view, jumping the player to a quote timestamp, downloading Markdown / JSON / audio-digest artifacts, and **deleting an episode** (see FR-025). The visual design will be authored externally by the user from a written description and is therefore out of scope for this spec to dictate.

**Partial-failure & degraded output**

- **FR-026**: After a configurable number of automatic retries, the system MUST adopt **partial-degraded output** semantics rather than fail the whole episode:
  - **Required stages** for an episode to reach status "done": hook, three-act summary, chapter outline (with at least one chapter). If any of these cannot be produced after retries, the episode MUST be marked "failed" and any partially-generated artifacts MUST be retained for inspection but MUST NOT be presented as a finished summary.
  - **Optional stages** (TTS audio digest, individual chapter quotes, entity extraction): persistent failure of any of these MUST mark only that artifact as "missing" / "unavailable" in both the UI and the JSON output, while all successful artifacts remain visible and downloadable.
  - The JSON output MUST encode the status of each artifact explicitly (e.g., `present` / `missing` / `failed_after_retries`) so downstream tooling can detect partial output.
  - Quote-verbatim verification (FR-012) MUST still apply to every quote that *is* shown, regardless of which other stages succeeded or failed.

**Retention & deletion**

- **FR-025**: System MUST retain processed episodes and all of their artifacts indefinitely (no automatic expiry, archival, or cleanup). The UI MUST expose a per-episode delete action that, when invoked, atomically removes the cached audio, transcript segments, chapter/quote/entity data, generated Markdown, generated JSON, and any generated TTS digest for that episode; after deletion the episode MUST no longer appear in any listing.

**Batching & performance**

- **FR-018**: System MUST support batch submission and process jobs in parallel up to a user-configurable concurrency limit; jobs above the limit MUST be queued and started as slots free up.
- **FR-019**: For a 60-minute episode on the reference hardware (Apple M2 MacBook), end-to-end processing (audio acquisition through structured outputs) MUST complete in ≤ 10 minutes. v1 is **cloud-only**: ASR, summarization, and TTS are all served by cloud APIs. A fully local execution mode is **explicitly out of scope for v1** and may be revisited in a later version.

**Deployment & user model**

- **FR-022**: System MUST run as a single-user local web application: the server MUST bind to loopback (127.0.0.1) by default and MUST NOT expose its UI or API to non-loopback interfaces in v1. There is no login system, no per-user data isolation, and no multi-tenant concept; all jobs and artifacts live in one shared local datastore for the single operator on the machine.

**Non-goals (binding)**

- **FR-020**: System MUST NOT perform speaker diarization in v1; speaker attribution is limited to "host vs. guest" inferred from prompt context only.
- **FR-021**: System MUST NOT perform audio denoising or pre-processing in v1.
- **FR-023**: System MUST NOT implement authentication, authorization, multi-user accounts, or network-exposed deployment in v1.

### Key Entities

- **Episode**: A single submitted podcast item. Attributes: id, source type (local file | direct audio URL | YouTube), source reference, language, duration, ingest timestamp, status, metadata block.
- **Job**: A processing run for an episode (an episode may have repeated jobs on retry). Attributes: id, episode id, state machine (queued / fetching / transcribing / summarizing / done / failed), per-stage progress markers used to support resume.
- **Transcript Segment**: A unit of transcription output carrying text, start time, end time, and language tag; the smallest unit reused on retry.
- **Chapter**: A contiguous segment of an episode produced by auto-segmentation. Attributes: title, start time, end time, ordered key points, list of Quote references.
- **Quote**: A verbatim substring of the transcript displayed to users. Attributes: text, timestamp, parent chapter, verified flag (must be true to be displayed).
- **Entity**: A named-entity mention. Attributes: name, type ∈ {person, book, product}, occurrence count, sample timestamps.
- **Summary Artifact**: The per-episode output bundle. Attributes: hook, three-act summary, chapter list, entity list, Markdown export, JSON export, optional TTS audio digest.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a 5-episode mixed Chinese/English evaluation set, **≥ 80%** of generated key points are judged accurate by a human reviewer (faithful to the original, no hallucinated content).
- **SC-002**: On the same evaluation set, **100%** of pilot users (≥ 3 reviewers) report that the one-line hook alone gave them a confident go/no-go decision on whether to listen to the full episode.
- **SC-003**: For every quote timestamp clicked across the evaluation set, the player seeks within **±10 seconds** of the actual spoken phrase.
- **SC-004**: **100%** of displayed quotes pass the verbatim-substring check against the transcript (no fabricated quotes ever shown).
- **SC-005**: Audio-digest narration is rated "fluent and natural" (no obvious mispronunciation, awkward prosody, or robotic dropouts) by a human reviewer on **≥ 80%** of evaluation episodes per language (Chinese and English evaluated separately).
- **SC-006**: A 60-minute episode completes end-to-end processing in **≤ 10 minutes** on the reference Apple M2 MacBook configuration.
- **SC-007**: When a job is retried after a mid-pipeline failure **or after a server restart**, wall-clock time spent in the ASR stage on the retry is **≤ 20%** of the cost of a from-scratch run, demonstrating effective resume across both same-process retries and cold restarts.

## Assumptions

- The reference hardware for the performance budget is an Apple M2 MacBook (per user input). Other hardware MAY be supported but is not held to the 10-minute SLA.
- Source-link metadata (podcast name, guest names) is best-effort: when the input is a raw audio file with no metadata, the system MAY leave those fields empty rather than fabricate them.
- Web UI visuals will be designed externally by the user using image-generation tools after we deliver a written interface description; the spec therefore does not prescribe colors, typography, or layout.
- "Direct audio URL" means a URL whose response is the audio bytes themselves (Content-Type audio/*), not an RSS feed or a podcast-platform episode page; RSS / platform-specific scraping is out of scope for v1.
- YouTube ingestion uses publicly available audio extraction; videos requiring login, age-gating, or active DRM are out of scope and expected to fail fast.
- Speaker diarization beyond host-vs-guest prompt inference is out of scope (per user input non-goals).
- Persistent storage of past episodes and their artifacts is in scope (jobs and outputs survive process restarts); specific storage technology choice is deferred to the planning phase per project constitution.
- v1 is cloud-only (ASR, summarization, TTS via cloud APIs). Local-only execution is explicitly deferred to a future version. Specific cloud vendors are still selected in research.md per constitution.
- Internet connectivity to the chosen cloud APIs is assumed available during processing; offline operation is not supported in v1.
