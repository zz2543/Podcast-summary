# UI Brief: Podcast Summary System

**Feature**: 001-podcast-summary
**Date**: 2026-05-07
**Audience**:
1. **The user** — uses fragments of this document as prompts for image-generation tools to produce visual mockups.
2. **The implementer (codex)** — uses this document as the binding spec for which components, copy, states, and interactions to build, once visual mockups arrive.

This document covers **information architecture, page composition, component inventory, every state variant, all copy strings, and interaction semantics**. It does **NOT** prescribe colors, typography, spacing, or illustration style — those are the user's job to drive via image generation per FR-017. After the user delivers visual mockups, codex implements against this brief + the visuals.

In-product UI strings are **Chinese** (input-language-agnostic UI; the *content* shown — summaries, transcripts, quotes — preserves the source language per FR-007). Code identifiers in this document are English.

---

## 1. Global navigation & shell

The app has only **two routes** in v1. There is no top-level navbar, no sidebar, no settings page. Header is a thin shell shared by both pages.

```
┌─────────────────────────────────────────────────────────────┐
│  AppHeader                                                   │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  <route content>                                             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

Routes:
- `/` → **EpisodeListPage** (home)
- `/episodes/:id` → **EpisodeDetailPage**

Routing library: `wouter` (lightweight) or React Router 6 — implementer's choice.

### 1.1 AppHeader

Always visible at the top, ~56 px tall.

| Slot | Content |
|------|---------|
| Left | Logo + product name "**播客摘要**" — clicking returns to `/` |
| Center | empty in v1 |
| Right | `QueueBadge` component (see §6.1); on detail pages also a "← 返回列表" text link |

---

## 2. Page A — EpisodeListPage (`/`)

**Purpose**: Submit episodes; browse all episodes by recency; jump into a detail view; delete or retry.

### 2.1 Layout (top → bottom)

1. **AppHeader**
2. **SubmitPanel** (always visible, full-width card, ~240 px tall)
3. **FilterBar** (sticky on scroll, 48 px)
4. **EpisodeGrid** (the list)
5. **EmptyState** OR **EpisodeGrid** (mutually exclusive based on count)

### 2.2 SubmitPanel

A card with **three tabs**, each tab is one input mode (FR-001 / FR-002 / FR-003):

| Tab | Label | Body |
|-----|-------|------|
| Tab 1 | "**本地文件**" (default) | Drag-drop dropzone + "选择文件" button. Accepts mp3/m4a/wav. Multi-file selection enabled (FR-018). Below dropzone: file chip list with remove ✕ buttons. |
| Tab 2 | "**音频链接**" | Multi-line textarea, one URL per line. Placeholder: "粘贴音频直链，每行一个；支持 .mp3 / .m4a / .wav" |
| Tab 3 | "**YouTube**" | Multi-line textarea, one YouTube URL per line. Placeholder: "粘贴 YouTube 视频链接，每行一个" |

Below the tab body, always visible:

- A small **concurrency hint** in muted text: "并发：N 个同时处理（在 .env 中调整 MAX_CONCURRENCY）"
- A primary action button **"开始处理"** (right-aligned). Disabled when nothing is selected/typed. On click: validates client-side (file extension / URL format), then `POST /api/episodes/batch`, then clears the panel.

#### 2.2.1 SubmitPanel client-side validation messages (inline, red text below input)

| Trigger | Message |
|---------|---------|
| Wrong file extension | "仅支持 mp3 / m4a / wav 格式" |
| File > 1 GB | "文件超过 1 GB 上限，请压缩后重试" |
| Malformed URL | "链接格式无效" |
| Empty submission | "请先选择文件或粘贴链接" |

Server-side rejections (HTTP 413 / 415) surface as a toast (§6.4) — see error code mapping in §7.

### 2.3 FilterBar

Single row, sticky:

- Left: status filter pills: **全部 (default)** / 处理中 / 已完成 / 部分完成 / 失败
- Right: search box (placeholder "在已处理的节目中搜索…", v1 may filter client-side over loaded items only)

### 2.4 EpisodeGrid

A vertical list of **EpisodeRow** items, sorted by `created_at DESC`.

#### 2.4.1 EpisodeRow

Single horizontal card per episode. Roughly 96 px tall.

```
┌────┬──────────────────────────────────────────┬──────────┬─────────┐
│ A  │ B title                                  │ C status │ D actions│
│    │   B subtitle (podcast / source / ⏱)     │          │          │
│    │ E hook (only when status=done|partial)   │          │          │
│    │ F progress bar (only when processing)    │          │          │
└────┴──────────────────────────────────────────┴──────────┴─────────┘
```

| Slot | Content |
|------|---------|
| A | Source-type icon: 🎵 local / 🔗 url / ▶️ YouTube (replace with proper icon set in mockup) |
| B title | `episode.title` if present, else fallback "未命名节目 — `<source_ref last segment>`" |
| B subtitle | Podcast name (if any) · source domain · duration in `mm:ss` |
| C status | `StatusBadge` — see §6.2 |
| D actions | Icon buttons: ▶️ "打开详情" (always), 🔁 "重试" (only when status=failed/partial), 🗑 "删除" (always) |
| E hook | Truncated to 1 line with ellipsis. Cyan/highlight tint to draw the eye. (Only present once `stage_status.hook="present"`) |
| F progress | Stage-aware progress bar (see §6.3). Only visible while status=processing. |

Clicking anywhere on the row except action icons navigates to `/episodes/:id`.

### 2.5 EmptyState (when no episodes ever submitted)

Centered placeholder occupying the EpisodeGrid area.

- Icon: cute illustration suggestion ("空空的耳机" / "headphones over an empty desk", supplied by the user via image gen)
- Headline: "**还没有节目**"
- Subtext: "把第一集播客丢进上面的提交区，几分钟后就能看到摘要。"

### 2.6 Page-level loading

While the initial `GET /api/episodes` is in flight (typically <100 ms): show a 3-row skeleton in the grid area. SubmitPanel and FilterBar remain interactive.

---

## 3. Page B — EpisodeDetailPage (`/episodes/:id`)

**Purpose**: Read the full structured summary, jump-listen to quotes, generate/play the audio digest, manage retention.

### 3.1 Layout (responsive ≥ 1024 px width)

```
┌───────────────────────────────────────────────────────────────┐
│ AppHeader (← 返回列表 link in right slot)                     │
├───────────────────────────────────────────────────────────────┤
│ MetaHeader  (title, podcast, guests, duration, source)        │
├───────────────────────────────────────────────────────────────┤
│ HookCard  (one big sentence, ≤ 50 chars, prominent)           │
├───────────────────────────────────────────────────────────────┤
│ ┌──────────────────────────────────┬─────────────────────┐   │
│ │ ThreeActSection                  │ EntityPanel (sticky)│   │
│ ├──────────────────────────────────┤                     │   │
│ │ ChapterOutline                   │                     │   │
│ │   - ChapterCard × N              │                     │   │
│ └──────────────────────────────────┴─────────────────────┘   │
├───────────────────────────────────────────────────────────────┤
│ ArtifactBar (downloads, digest, delete)                       │
├───────────────────────────────────────────────────────────────┤
│ StickyAudioBar (always at bottom while page open)             │
└───────────────────────────────────────────────────────────────┘
```

Below 1024 px width: EntityPanel becomes a collapsible bottom drawer instead of a sticky right column.

### 3.2 MetaHeader

Top metadata block, ~80 px tall:

- Line 1: `episode.title` as H1 (Chinese-or-English depending on source content)
- Line 2 (small, muted, separated by middle-dots): `podcast_name · 嘉宾：<list> · 时长 mm:ss · 来源：<domain or "本地文件">`
- Right side: a small `LanguageTag` chip — "中文" / "English" / "中英混杂"

### 3.3 HookCard

The most visually prominent single block on the page. The user uses the hook to decide whether to read further.

- Single sentence, font-size noticeably larger than three-act body (e.g. 24–28 px)
- Optional accent bar on the left edge
- Above the sentence in tiny muted caps: "**一句话摘要**"
- Below the sentence in tiny muted text: "Prompt 版本：<value from `prompt_versions.one_liner`>" (Constitution V — visible provenance)

If `stage_status.hook != "present"`: show a `MissingStagePlaceholder` (§6.5) saying "一句话摘要生成失败，可在下方点击重试".

### 3.4 ThreeActSection

Three sub-cards, vertically stacked OR a 3-column row at ≥ 1280 px width.

| Sub-card | Heading | Content |
|----------|---------|---------|
| 1 | "**背景**" | `three_act.background` |
| 2 | "**核心论点**" | `three_act.core_argument` |
| 3 | "**结论**" | `three_act.conclusion` |

Each sub-card heading carries a small Roman numeral I / II / III in muted color. Body text wraps naturally; no truncation.

If `stage_status.three_act != "present"`: replace this whole section with a `MissingStagePlaceholder`.

### 3.5 ChapterOutline

Vertical list of `ChapterCard`s, in original order.

#### 3.5.1 ChapterCard

```
┌──────────────────────────────────────────────────────────────┐
│ [▶ idx+1]  Chapter title                          mm:ss–mm:ss│
│            ▼ collapse caret                                  │
├──────────────────────────────────────────────────────────────┤
│ 核心观点                                                     │
│   • Key point 1 (preserves original order)                   │
│   • Key point 2                                              │
│   • Key point 3                                              │
│                                                              │
│ 金句                                                         │
│   ┌─────────────────────────────────────────────┐           │
│   │ ⏱ mm:ss   "Verbatim quote text..."          │  (×K)     │
│   └─────────────────────────────────────────────┘           │
└──────────────────────────────────────────────────────────────┘
```

- Chapter index button on the left (e.g. `▶ 1`) — clicking it seeks the StickyAudioBar to `chapter.start_ms` and starts playback.
- Time range on the right, monospaced.
- Collapse caret to fold/unfold the body. Default: first 3 chapters expanded, rest collapsed (UX decision; revisit after mockups).
- "**核心观点**" subsection — bulleted list, original order preserved.
- "**金句**" subsection — only present if at least one verified quote exists (FR-012):
  - Each quote is a `QuoteChip` (§6.6)
  - Clicking the chip seeks the audio player to `quote.start_ms` and plays. Visual feedback: brief 1 s highlight on the chip, brief flash on the StickyAudioBar.

If `stage_status.chapters != "present"`: the whole ChapterOutline section is replaced by `MissingStagePlaceholder`.

### 3.6 EntityPanel

Sticky right column on wide screens, bottom drawer on narrow screens. Three subsections:

| Subsection | Heading | Item template |
|------------|---------|---------------|
| 1 | "**人物**" | `name` · `(× count)` |
| 2 | "**书籍**" | `name` · `(× count)` |
| 3 | "**产品**" | `name` · `(× count)` |

Each item is a small chip; clicking a chip seeks the audio player to the **first sample timestamp** in `entity.sample_timestamps_ms` and plays.

States:
- `stage_status.entities = "present"` → render normally
- `stage_status.entities = "missing"` or `"failed_after_retries"` → grey-out the panel with text "实体识别未生成"; show inline "重试" link

### 3.7 ArtifactBar

Single horizontal row near the bottom, above the StickyAudioBar:

| Button | Label | Behavior |
|--------|-------|----------|
| ⬇️ | "下载 Markdown" | `GET /api/episodes/:id/files/markdown` (force-download) |
| ⬇️ | "下载 JSON" | `GET /api/episodes/:id/files/json` |
| 🎙 | "生成音频摘要" | If `stage_status.tts="present"` → label changes to "▶ 播放音频摘要" + a 🗑 "删除并重新生成" affordance. Otherwise triggers `POST /api/episodes/:id/digest` and shows a small spinner inside the button. |
| 🔁 | "重新处理" | `POST /api/episodes/:id/retry`. Only enabled when `episode.status ∈ {failed, partial}`. |
| 🗑 | "删除整集" | Opens `ConfirmDeleteDialog` (§6.7). |

### 3.8 StickyAudioBar

Always docked at the bottom of the viewport, ~64 px tall, full-width:

```
┌────────────────────────────────────────────────────────────────┐
│ ▶  ━━━━━━━━━━●─────────────────  mm:ss / mm:ss   1.0× ▾   ⤓  │
└────────────────────────────────────────────────────────────────┘
```

- Native `<audio>` element under the hood, controlled programmatically (FR-011 quote-jump uses `currentTime = ms/1000`)
- Range-request streaming from `GET /api/episodes/:id/files/audio`
- Speed selector: 0.75× / 1× / 1.25× / 1.5× / 2×
- Download button on the far right offers the original cached file
- When the digest is being played instead of the original audio, a small chip on the left says "音频摘要" and clicking it switches back to the original

### 3.9 Detail-page loading & error states

- Initial fetch of `GET /api/episodes/:id` running: skeleton boxes for MetaHeader / HookCard / ThreeActSection / one ChapterCard. EntityPanel skeleton too.
- 404: full-page empty state "节目不存在或已删除", with a button "返回列表".
- Partial-failure case (FR-026): every `MissingStagePlaceholder` carries a "重试此环节" inline button that maps to `POST /api/episodes/:id/retry` (server intelligently resumes only the failed stage).

---

## 4. Real-time progress (WebSocket)

A single `useJobs()` React hook owns the WebSocket lifecycle for the whole app (per `contracts/job-events.md`).

- On app mount: open `ws://127.0.0.1:8000/api/ws/jobs`. Receive `hello` then `snapshot`, hydrate global state.
- On every `job_update` / `stage_status_update`: dispatch to a small in-memory store; both pages re-render the affected episode/job.
- Disconnect handling: exponential backoff (250 ms → 4 s capped). When reconnected, the server resends `snapshot`, so we do **not** need a manual replay buffer.

A small dot indicator in the AppHeader shows connection state:

| State | Indicator |
|-------|-----------|
| connected | green dot, no label |
| reconnecting | yellow dot, label "正在重连…" |
| disconnected (max attempts hit) | red dot, label "实时连接断开，刷新页面重试" |

---

## 5. Empty / loading / error principles (cross-cutting)

| Scenario | UX |
|----------|----|
| First-time user with no episodes | EpisodeGrid EmptyState (§2.5) — friendly illustration + 1-line CTA |
| Page initial load | Skeleton placeholders matching the final layout shape (no spinners on full pages) |
| Single component slow (e.g. fetching detail) | Inline skeleton inside that component only |
| Action button busy | Replace label with mini-spinner + button stays disabled |
| Retry-able failure | `MissingStagePlaceholder` with "重试此环节" affordance |
| Hard failure (404, 500) | Full-page empty state with explanatory copy + recovery CTA |
| Toast (transient) | 3-second dismissible toast at top-right; never blocks input |

---

## 6. Shared components

### 6.1 QueueBadge (in AppHeader, right slot)

- Hidden when `total_active_jobs == 0`
- Visible: pill saying "队列：N 处理中 / M 等待中" (driven by WS snapshot)
- Click: smooth-scrolls EpisodeListPage's grid to the first processing row (no-op on detail page beyond visual flash)

### 6.2 StatusBadge

| `episode.status` | Color hint | Label |
|------------------|------------|-------|
| `pending` | grey | "等待中" |
| `processing` | blue | "处理中" |
| `done` | green | "已完成" |
| `partial` | amber | "部分完成" |
| `failed` | red | "失败" |

Color hints are guidance for the visual designer; final palette is the user's call.

### 6.3 JobProgressBar

Stage-aware bar: 5 segments (fetch / transcribe / summarize / chapter+entity / tts).

- Each segment fills 0–100% based on `job.stage_progress` for that stage
- Current stage's segment animates with a subtle indeterminate stripe
- Hovering shows a tooltip with the stage name + percentage, e.g. "转写：42%"

### 6.4 Toast

Non-blocking, top-right, auto-dismiss in 3 s, dismiss-on-click. Used for: server-side validation failures, network hiccups, "已删除", "已加入队列", "音频摘要生成中…".

### 6.5 MissingStagePlaceholder

A subdued box used wherever a stage's data should appear but is `missing` or `failed_after_retries`:

```
┌──────────────────────────────────────┐
│ ⚠  此环节未生成（<stage_label>）      │
│    错误码：failed_after_retries       │
│    [ 重试此环节 ]                     │
└──────────────────────────────────────┘
```

`stage_label` map: hook→"一句话摘要", three_act→"三段式摘要", chapters→"章节大纲", entities→"实体识别", tts→"音频摘要".

### 6.6 QuoteChip

Quote display + clickable timestamp:

```
┌────────────────────────────────────────────────┐
│ ⏱ 12:34   "原文金句逐字逐句..."                 │
└────────────────────────────────────────────────┘
```

Time prefix is monospaced; quote text is rendered with original quotation marks. On hover: faint background tint suggesting clickability. On click: seeks player + flashes both this chip and the player. Long quotes wrap; no truncation (the full verbatim text is the value).

### 6.7 ConfirmDeleteDialog

Modal, centered:

- Title: "**确认删除整集？**"
- Body: "这会同时删除：缓存的音频、转写文本、Markdown / JSON 导出、音频摘要。此操作不可撤销。"
- Buttons: "取消" (secondary) · "确认删除" (destructive)
- Confirming → `DELETE /api/episodes/:id` → toast "已删除" → navigate back to `/`

---

## 7. Server-error → user-facing copy mapping

| HTTP code | `error.code` | Toast / inline copy |
|-----------|--------------|---------------------|
| 400 | `bad_input` | "提交内容格式不正确" |
| 404 | `not_found` | "节目不存在或已删除" |
| 409 | `conflict` | "该节目已经在处理中或已存在" |
| 413 | `payload_too_large` | "文件超过 1 GB / 6 小时上限" |
| 415 | `unsupported_media` | "不支持的链接或文件类型（仅支持 mp3 / m4a / wav 直链或 YouTube 链接）" |
| 502 | `upstream_failed` | "云服务暂时不可用，已自动重试…" |
| 500 | `internal` | "出错了，请刷新重试" |

---

## 8. Visual style direction (guidance for the user's image-gen prompts)

Hard constraints (must hold no matter the visual style):

- Hierarchy: **HookCard is the most visually prominent block on the detail page** — bigger than three-act, bigger than chapter content. The whole product's value lives in that one sentence.
- Density: list rows should fit ≥ 5 episodes on a 1080p screen without scroll
- Player visibility: the StickyAudioBar at the bottom must always be visible while the detail page is open (do not let any modal cover it during playback)
- Quote chips must visibly *afford* clicking (they are the most surprising affordance — a quote is a button)
- Status colors must be distinguishable for red/green color-blindness (don't encode status by color alone — keep the text label)

Soft suggestions (the user can override freely):

- Calm, reading-friendly palette — this is a product about consuming long-form thought, not about action games
- Generous line-height in summary bodies; tight line-height in metadata
- A subtle audio motif (sound-wave detail, rounded "play" shapes) is welcome but not required
- Avoid full-bleed photos behind text — bad for readability of summaries

---

## 9. Out of scope for v1 (do **not** ask the image-gen tool to draw these)

- Login / signup / profile screens (FR-023)
- Settings / admin / preferences pages (no settings — everything is in `.env`)
- Sharing buttons (single-user local; nothing to share to)
- Comments, ratings, history, library tags
- Mobile-app shells (web-only per spec)
- Speaker waveform / diarization timeline (FR-020 explicit non-goal)
- Audio editing, trimming, denoising (FR-021 explicit non-goal)

---

## 10. Suggested image-generation prompt fragments (you can copy-paste into Midjourney / SD / etc.)

### A. EpisodeListPage hero shot
> Web app dashboard, light theme. Top: thin header with logo "播客摘要" left-aligned, a small green status dot right-aligned. Below: a wide submission card with three tabs ("本地文件", "音频链接", "YouTube"), the first tab showing a drag-drop dropzone with a cloud-up arrow icon; a primary CTA button "开始处理" bottom-right of the card. Below the card: a row of filter pills ("全部", "处理中", "已完成", "部分完成", "失败"). Below: a vertical list of 5 episode rows, each row showing a source icon, title, podcast subtitle, status badge ("已完成" green / "处理中" blue / "部分完成" amber), three small icon buttons (open / retry / delete). One row in "处理中" state shows a horizontal segmented progress bar. Calm reading-app aesthetic, generous whitespace, sans-serif. 16:10.

### B. EpisodeDetailPage with quote
> Web app reading view, light theme. Top header with "← 返回列表" link. Title H1 "AI Coding Tools 的下一步：从助手到队友" with a subtitle "Lex Fridman Podcast · 嘉宾：Geoffrey Hinton · 时长 1:23:40 · 来源 lexfridman.com" and a small "English" language chip. Below: a HUGE prominent card labeled "一句话摘要" containing one bold sentence in cyan accent. Below: a 3-column "三段式摘要" with "背景" / "核心论点" / "结论" cards bearing small Roman numerals I / II / III. Below that: a chapter outline with collapsible cards, one expanded showing a bulleted "核心观点" list and a "金句" subsection containing two clickable quote chips with monospace timestamps "⏱ 12:34" prefixing verbatim text in quotation marks. A right sidebar titled "人物 / 书籍 / 产品" with chips and counts. A sticky audio player docked at the bottom with play button, scrubber, time, speed selector. Reading-app aesthetic, calm palette. 16:10.

### C. EmptyState
> Centered illustration of a pair of headphones resting on a tidy wooden desk next to a closed notebook, soft pastel palette. Below the illustration in centered Chinese text: a headline "还没有节目" and a subtext "把第一集播客丢进上面的提交区，几分钟后就能看到摘要。" Minimal background, lots of whitespace.

### D. Sticky audio player detail
> Wide horizontal bar docked at the bottom of a browser window. Left: round play button. Center: thin progress slider with a circular thumb at ~30%, time text "12:34 / 41:08" in a small sans-serif. Right: a "1.0×" speed dropdown and a download icon. The bar has a subtle drop-shadow lifting it from the page above. Calm, modern, soft.

---

## 11. Hand-off checklist (when the user finishes mockups)

Mockups live in `specs/001-podcast-summary/design/`. See that directory's `README.md` for naming conventions and the canonical filenames the implementer expects in `selected/`. Before starting Phase-3 frontend tasks (T045–T047), verify:

- [ ] `design/selected/list-page.png` — default list page
- [ ] `design/selected/empty-state.png` — list page empty state
- [ ] `design/selected/detail-page.png` — detail page with all stages present
- [ ] `design/selected/audio-bar.png` — sticky audio player close-up
- [ ] `design/selected/quote-chip.png` — quote chip close-up
- [ ] At least one mockup in `design/states/` shows a `MissingStagePlaceholder` or `failed` row (FR-026)
- [ ] All `selected/` mockups honor the §8 hard constraints (HookCard most prominent; player always visible; quote affordance clear; status not color-only)

If any of the required items above are missing, do **not** start the frontend tasks — flag back to the user and wait.
