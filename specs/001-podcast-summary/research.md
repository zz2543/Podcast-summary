# Research: Podcast Summary System

**Feature**: 001-podcast-summary
**Date**: 2026-05-07
**Purpose**: Resolve all key technology choices required by the constitution (≥ 2 candidates each, with explicit rationale).

Each section follows the format mandated by the project: **Decision / Rationale / Alternatives considered**.

---

## R1. Cloud ASR provider

**Decision**: Default provider is **豆包录音文件识别模型 2.0 (Doubao AUC file ASR)** via 火山引擎 (volcengine). Long/public audio URLs use the recording-file submit/query API (`/api/v3/auc/bigmodel/submit` + `/query`, resource `volc.seedasr.auc`); local loopback uploads use the flash file endpoint with base64 audio because Volcengine cannot fetch `127.0.0.1` files. Adapter interface keeps **OpenAI Whisper (`whisper-1`)** and **Alibaba Paraformer / Qwen-Audio (DashScope)** as registered alternatives. Legacy Doubao streaming ASR is no longer the default because it is designed for real-time paced audio, not instant-upload podcast files.

**Rationale**:
- **Vendor consolidation**: TTS (R3) is already on 火山引擎. Putting ASR on the same vendor means **one fewer account, one fewer billing surface, one set of `VOLC_*` credentials** — directly simplifies Constitution IV's `.env` story and the README "one-click run" promise.
- 豆包 ASR 大模型 is Chinese-native, with strong code-switched zh/en support — matches FR-007 (preserve original language, no translation) without forcing a per-language model split.
- Provides segment-level timestamps directly, comfortably under the ±10 s SC-003 budget for quote jumps.
- Recording-file ASR matches the product's input model: users submit complete podcast files or URLs, then wait for a batch-style transcript. This avoids the failure mode where a long MP3 is pushed into a real-time streaming endpoint faster than playback time and only the first seconds are recognized.
- Pricing on 火山引擎 is approximately ¥0.5 / minute on the standard tier — comparable order of magnitude to Whisper, well within course-project budget.
- File-mode HTTP APIs make retries and polling explicit and easier to checkpoint than a long-lived WebSocket session.

**Alternatives considered**:
- **OpenAI Whisper (`whisper-1`)**: most battle-tested for code-switched podcast audio; segment timestamps within ±2 s typical. Rejected as default purely on the vendor-consolidation argument above. Kept as a registered alternative (`ASR_PROVIDER=openai_whisper`) for users who already have an OpenAI account or prefer Whisper's well-known behaviour on noisy English audio.
- **Alibaba Paraformer / Qwen-Audio (DashScope)**: also Chinese-native, comparable quality. Kept as `ASR_PROVIDER=qwen` — useful for users who already use DashScope for the Qwen LLM/TTS fallbacks; same SDK covers all three services.
- **Deepgram Nova-3**: fastest wall-clock, word-level timestamps. Rejected: third foreign vendor; weaker Chinese; we don't need word-level granularity for a ±10 s seek tolerance.
- **AssemblyAI Universal-2**: comparable English quality, good diarization (which we explicitly do not need per FR-020). Rejected: yet another vendor, no compelling differentiator.
- **Local faster-whisper / MLX Whisper**: explicitly out of scope per spec resolution Q1 (cloud-only in v1).

---

## R2. Cloud LLM for summarization

**Decision**: Default provider is **DeepSeek `deepseek-chat` (V3 series)** accessed via the OpenAI-compatible HTTP endpoint (`https://api.deepseek.com`) using the `openai` Python SDK with a custom `base_url`. Adapter interface keeps **DeepSeek `deepseek-reasoner` (R1)** as a swap for chapter-outline tasks where step-by-step thinking helps, and **Qwen `qwen-max` (DashScope)** as a third-party fallback.

**Rationale**:
- DeepSeek-V3 is the best price-to-Chinese-quality ratio in 2026 — roughly 1/30 the cost of Claude Sonnet at comparable Chinese summarization fidelity, and follows JSON-output instructions reliably (matters for `structured_parser.py`).
- OpenAI-compatible endpoint means **zero new SDK dependency**: we already have `openai` in the registry for Whisper ASR; the same client object with `base_url="https://api.deepseek.com"` and `api_key=DEEPSEEK_API_KEY` services the LLM calls.
- 64K context (V3) fits a 60-min transcript (≈8–12K tokens) plus prompt comfortably; chapter-by-chapter passes leave ample headroom.
- Stable Chinese tokenization matters for FR-009's "≤ 50 characters" hook constraint — DeepSeek's tokenizer is Chinese-native, so the model's character budgeting matches what we measure in `structured_parser.py`.

**Alternatives considered**:
- **Anthropic Claude Sonnet 4.6**: stronger nuanced reasoning, prompt caching support; rejected as default purely on cost (≈30× DeepSeek-V3 for our token mix). Re-considered as a future eval-time swap if SC-001 (key-point accuracy ≥ 80%) misses on DeepSeek.
- **OpenAI GPT-4o / GPT-4.1**: comparable Chinese summarization quality, lower-latency in some regions. Rejected: same vendor as ASR creates a single-point dependency; cost ≈ 5–10× DeepSeek.
- **Qwen `qwen-max` (Alibaba DashScope)**: strong Chinese-native model. Kept as registered alternative (`LLM_PROVIDER=qwen`) — useful if DeepSeek service quality regresses or if we need a domestic-only path.
- **Google Gemini 1.5 Pro**: rejected — yet another vendor, and DeepSeek already covers the Chinese-native quality angle at lower cost.

---

## R3. Cloud TTS for the audio digest

**Decision**: Default provider is **ByteDance 豆包 TTS (Doubao Voice)** accessed via 火山引擎 (volcengine) using the official `volcengine-python-sdk`. Adapter interface keeps **Alibaba Qwen-TTS (DashScope `qwen-tts` / `cosyvoice-v2`)** as the registered alternative.

**Rationale**:
- 豆包 TTS is **Chinese-native**: prosody, polyphone disambiguation, and code-switched zh/en pronunciation are noticeably better than non-Chinese-trained voices on podcast-style content. SC-005 ("fluent and natural" rating ≥ 80% per language) is materially easier to hit on Chinese with a domestic voice model.
- 火山引擎 supports streaming MP3 / WAV output directly, matching our `data/<id>/digest.mp3` storage layout — no transcoding pass needed.
- Pricing is roughly ¥30 / 百万字符 (≈ $4 / M chars) on the standard voice tier; a 5-minute digest (~1500 zh chars) costs about ¥0.05 — well within the course-project budget.
- Multi-voice library (multiple male/female timbres + emotional variants) gives us room to tune SC-005 without changing vendors.

**Alternatives considered**:
- **Qwen-TTS (Alibaba DashScope `qwen-tts` / `cosyvoice-v2`)**: also Chinese-native, comparable quality, comes from the same DashScope account that hosts the Qwen LLM fallback (R2). Kept as `TTS_PROVIDER=qwen` — useful for users who already have a DashScope account and want one fewer vendor.
- **OpenAI TTS (`tts-1-hd`)**: cheapest and shares an SDK with ASR, but Chinese prosody is markedly weaker — pilot tests show frequent tone errors on common 4-character idioms, putting SC-005 at risk for the Chinese half of the eval set. Rejected as default.
- **ElevenLabs Multilingual v2**: best raw quality globally but ~5× the cost and an extra non-Chinese vendor. Rejected.
- **Microsoft Azure TTS / Google Cloud TTS**: comparable Neural voices but heavier IAM setup (service accounts, project IDs); marginal quality gain over 豆包 on Chinese does not justify the integration cost for v1.

---

## R4. YouTube audio extraction

**Decision**: **yt-dlp**, invoked as a Python library (not a subprocess) where possible, with ffmpeg installed via the README's brew/apt instructions.

**Rationale**:
- Tracks YouTube changes weekly; the only practical option that stays working in 2026.
- Permissive Unlicense; no concerns for course delivery.
- Library API gives us direct access to metadata (title, duration, channel) for FR-008.

**Alternatives considered**:
- **pytube**: pure Python, no ffmpeg dep. Rejected: routinely breaks for weeks at a time when YouTube changes its player; unacceptable for a demo system.
- **YouTube Data API + custom audio fetch**: official, but the API does not return audio URLs — would still need yt-dlp for the actual stream, doubling the surface area.

---

## R5. Persistence layer

**Decision**: **SQLite** (via SQLAlchemy 2.x) for relational data (Episode / Job / Segment / Chapter / Quote / Entity), plus a **`data/<episode_id>/` directory tree** on disk for large blobs (cached audio, raw transcript JSON, generated Markdown, generated JSON, TTS MP3).

**Rationale**:
- Single-user local app (FR-022) — SQLite is exactly the right tool: zero ops, ACID, embedded, supported by every Python testing tool.
- Atomic deletes (FR-025) are easy: one transaction to drop rows + one `shutil.rmtree(data/<id>/)` in the same workflow.
- Survives process restarts trivially (FR-006 / SC-007).
- Alembic gives us a migration story for v2.

**Alternatives considered**:
- **Postgres (in Docker)**: overkill for a single-user local tool; adds container ops to the README's "one-click" promise.
- **Pure JSON files (no SQL)**: tempting for simplicity but makes "show me jobs in `transcribing` state across restarts" require ad-hoc indexing code. SQLite costs us nothing extra and gets indexes for free.
- **DuckDB**: great for analytics, weak for transactional updates that the job state machine performs.

---

## R6. Frontend stack

**Decision**: **Vite + React + TypeScript**, served as a static SPA from FastAPI in production and from the Vite dev server in development.

**Rationale**:
- The most ubiquitous stack — easiest to get image-brief-driven visual designs implemented quickly when the user delivers them.
- React's audio + state ecosystem (custom `<audio>` ref + `currentTime` programmatic seeks) is a 5-line implementation for the quote-jump requirement (FR-011 / SC-003).
- Vitest + jsdom give us a small, fast unit-test setup matching what we already use on the backend for non-I/O logic.

**Alternatives considered**:
- **HTMX + server-rendered Jinja2**: keeps everything Python. Rejected: dynamic audio scrubbing, progressive WebSocket updates per job, and rich quote-jump interactivity get awkward in HTMX without committing to a parallel JS layer anyway. The simplification is illusory.
- **Streamlit / NiceGUI / Gradio**: Python-only. Rejected per Complexity Tracking — they constrain the externally-designed visual style FR-017 anticipates.
- **Svelte**: smaller bundle. Rejected: lower familiarity → slower iteration; bundle size is irrelevant on loopback localhost.

---

## R7. Concurrency / job execution model

**Decision**: An in-process **asyncio task queue** with a configurable semaphore (`MAX_CONCURRENCY`), backed by SQLite for durable state. On startup, the pipeline service scans for jobs in non-terminal states and resumes them from their last checkpoint.

**Rationale**:
- Single-user, single-process design (FR-022) — no need for Celery/Redis/RQ.
- FastAPI is already async; reusing the event loop avoids Python sub-process overhead.
- Semaphore controls satisfy FR-018 deterministically and are trivial to assert in tests.
- Persistence-driven recovery (FR-006) becomes a small startup hook.

**Alternatives considered**:
- **Celery + Redis**: industrial-strength but enormous operational footprint for a one-user app; conflicts with the README "one-click run" rule.
- **APScheduler**: cron-style, not the right primitive for a queue.
- **Dramatiq**: nice middle-ground, but still adds a broker dependency.

---

## R8. Quote verbatim verification (FR-012 / SC-004)

**Decision**: Verification function performs **whitespace-tolerant substring match** against the joined transcript text:
1. Normalize transcript and candidate quote: strip surrounding whitespace, collapse internal whitespace runs to single spaces, normalize Unicode (NFKC), keep punctuation.
2. The candidate must appear as an exact substring of the normalized transcript.
3. Failures cause the candidate to be silently dropped; log to debug + emit a per-episode "rejected_quote" counter for evaluation.

**Rationale**: A pure `in` check is too brittle (newlines, double spaces) and too lenient (case-insensitive would let paraphrases through). The rule above lets us say "every shown quote is verbatim" with high confidence and is trivially unit-testable in `quote_verifier.py` (Constitution III).

**Alternatives considered**:
- **Token-overlap heuristic (e.g., ROUGE-L > 0.95)**: easier to satisfy for the LLM, but admits paraphrases and violates the spec's "verbatim" promise.
- **Fuzzy match (Levenshtein within N edits)**: same problem.
- **No verification, trust the LLM**: explicitly excluded by FR-012 and SC-004.

---

## Resolved spec clarifications check

- ✅ Cloud-only in v1 → drives R1/R2/R3/R7.
- ✅ Single-user local web → drives R5/R7.
- ✅ Cross-restart durability → drives R5/R7.
- ✅ 6h / 1GB hard cap → enforced at ingestion (`services/ingest.py`).
- ✅ Indefinite retention with manual delete → drives R5 directory layout.
- ✅ Partial-degraded output → drives R7 state machine and exporter logic.

No `NEEDS CLARIFICATION` markers remain.
