const pptxgen = require("pptxgenjs");
const path = require("path");

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.3 x 7.5
pres.author = "group 1";
pres.title = "GotIt / Podsum";

const SLIDE_W = 13.3;
const SLIDE_H = 7.5;

const BG = "FFFFFF";
const BG_DARK = "1D1D1F";
const TEXT = "1D1D1F";
const MUTED = "6E6E73";
const ACCENT = "0071E3";
const ACCENT_SOFT = "F5F5F7";
const RULE = "D2D2D7";
const WARN = "FF3B30";

const FONT_H = "Helvetica Neue";
const FONT_B = "Helvetica Neue";

const ASSETS = path.join(__dirname, "en_assets");
const IMG = {
  cover: path.join(ASSETS, "image1.png"),       // 1924×1268  — detail-page hero
  listPage: path.join(ASSETS, "image2.png"),    // 1710×1108  — list page screenshot
  detailPage: path.join(ASSETS, "image3.png"),  // 1936×1200  — detail page screenshot
  demoFrame: path.join(ASSETS, "image4.png"),   // 1882×690   — demo screencast still
  taskList: path.join(ASSETS, "image5.png"),    // 564×3580   — full task list sidebar
  taskZoom: path.join(ASSETS, "image6.png"),    // 552×198    — task cluster zoom
  demoVideo: path.join(ASSETS, "media1.mp4"),
};

function addPageNumber(slide, n, total) {
  slide.addText(`${n} / ${total}`, {
    x: SLIDE_W - 1.2, y: SLIDE_H - 0.45, w: 1.0, h: 0.3,
    fontSize: 10, fontFace: FONT_B, color: MUTED, align: "right",
  });
}
function addBrand(slide, dark = false) {
  slide.addText("GotIt · Podsum", {
    x: 0.5, y: SLIDE_H - 0.45, w: 3, h: 0.3,
    fontSize: 10, fontFace: FONT_B, color: dark ? "8E8E93" : MUTED,
    align: "left", margin: 0,
  });
}
function addTitle(slide, title, eyebrow) {
  if (eyebrow) {
    slide.addText(eyebrow, {
      x: 0.6, y: 0.45, w: 12, h: 0.3,
      fontSize: 12, fontFace: FONT_H, color: ACCENT, bold: true,
      charSpacing: 2, margin: 0,
    });
  }
  slide.addText(title, {
    x: 0.6, y: eyebrow ? 0.8 : 0.55, w: 12, h: 0.75,
    fontSize: 30, fontFace: FONT_H, bold: true, color: TEXT, margin: 0,
  });
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0.6, y: eyebrow ? 1.65 : 1.4, w: 0.6, h: 0.04,
    fill: { color: ACCENT }, line: { type: "none" },
  });
}

const TOTAL = 11;

// ============ S1 · Cover ============
{
  const s = pres.addSlide();
  s.background = { color: BG_DARK };

  s.addText("GotIt", {
    x: 0.8, y: 2.0, w: 8, h: 1.6,
    fontSize: 96, fontFace: FONT_H, bold: true, color: "FFFFFF", margin: 0,
  });
  s.addText("Local end-to-end podcast summarization tool", {
    x: 0.8, y: 3.6, w: 5.8, h: 1.0,
    fontSize: 20, fontFace: FONT_H, color: "FFFFFF", margin: 0,
  });
  s.addText("Compress an hour of podcast into a few minutes you can actually digest", {
    x: 0.8, y: 4.6, w: 5.8, h: 0.9,
    fontSize: 14, fontFace: FONT_B, color: "8E8E93", margin: 0,
  });

  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.8, y: 5.7, w: 0.8, h: 0.06,
    fill: { color: ACCENT }, line: { type: "none" },
  });
  s.addText("group 1   ·   2026.05", {
    x: 0.8, y: 5.85, w: 5, h: 0.4,
    fontSize: 13, fontFace: FONT_B, color: "8E8E93", charSpacing: 2, margin: 0,
  });

  // cover image — preserve aspect ratio 1924×1268
  const imgW = 6.0, imgH = imgW * (1268 / 1924); // ≈3.95
  s.addImage({
    path: IMG.cover,
    x: SLIDE_W - imgW - 0.6, y: (SLIDE_H - imgH) / 2, w: imgW, h: imgH,
  });

  addBrand(s, true);
  addPageNumber(s, 1, TOTAL);
}

// ============ S2 · Motivation ============
{
  const s = pres.addSlide();
  s.background = { color: BG };
  addTitle(s, "The problem we want to solve", "P2  ·  MOTIVATION");

  const items = [
    "1 podcast episode = 40 – 90 minutes",
    "Want to know what it covers / is it worth listening / which parts to revisit",
    "Brain handles a 30-second summary far better than a 1-hour audio",
    "Existing tools: too heavy (Otter), no chapters (YT auto-captions), no compression (raw transcript)",
  ];
  s.addText(
    items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1 } })),
    { x: 0.6, y: 2.0, w: 12.1, h: 2.5, fontSize: 16, fontFace: FONT_B, color: TEXT, paraSpaceAfter: 8 }
  );

  // tagline card — full width since image was removed from this slide in user's edit
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.6, y: 5.0, w: 12.1, h: 1.6,
    fill: { color: ACCENT_SOFT }, line: { type: "none" },
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.6, y: 5.0, w: 0.08, h: 1.6,
    fill: { color: ACCENT }, line: { type: "none" },
  });
  s.addText("ONE-LINE POSITIONING", {
    x: 0.85, y: 5.1, w: 6, h: 0.3,
    fontSize: 11, fontFace: FONT_H, color: ACCENT, bold: true, charSpacing: 2, margin: 0,
  });
  s.addText(
    "Drop in a link. 10 minutes later you get a hook, three-act, chapters, quotes, named entities, plus a 30-second listenable TTS digest.",
    {
      x: 0.85, y: 5.4, w: 12.0, h: 1.1,
      fontSize: 16, fontFace: FONT_B, color: TEXT, italic: true, margin: 0,
    }
  );

  addBrand(s);
  addPageNumber(s, 2, TOTAL);
}

// ============ S3 · Demo ============
{
  const s = pres.addSlide();
  s.background = { color: BG };
  addTitle(s, "Demo walkthrough", "P3  ·  LIVE DEMO");

  const steps = [
    { n: "01", t: "Paste a link", d: "YouTube / Bilibili / mp3" },
    { n: "02", t: "Watch live progress", d: "WebSocket push · fetch → ASR → summary → chapters → TTS" },
    { n: "03", t: "Open the detail page", d: "hook · three acts · chapter timeline · click a quote to jump back into the audio" },
    { n: "04", t: "Audio overview", d: "Doubao bigmodel TTS narrates the summary" },
    { n: "05", t: "One-click export", d: ".md / .json / .mp3" },
  ];
  const startY = 2.2;
  const rowH = 0.85;
  steps.forEach((step, i) => {
    const y = startY + i * rowH;
    s.addText(step.n, {
      x: 0.6, y, w: 1.0, h: 0.7,
      fontSize: 36, fontFace: FONT_H, bold: true, color: ACCENT, margin: 0, valign: "middle",
    });
    s.addText(step.t, {
      x: 1.7, y: y + 0.05, w: 4.5, h: 0.4,
      fontSize: 18, fontFace: FONT_H, bold: true, color: TEXT, margin: 0,
    });
    s.addText(step.d, {
      x: 1.7, y: y + 0.42, w: 6, h: 0.35,
      fontSize: 12, fontFace: FONT_B, color: MUTED, margin: 0,
    });
  });

  // demo video (embedded mp4)
  s.addMedia({
    type: "video",
    path: IMG.demoVideo,
    x: 8.0, y: 2.2, w: 4.7, h: 4.3,
  });

  addBrand(s);
  addPageNumber(s, 3, TOTAL);
}

// ============ S4 · UI ============
{
  const s = pres.addSlide();
  s.background = { color: BG };
  addTitle(s, "The real UI: list + detail", "P4  ·  UI");

  // headings
  s.addText("LIST PAGE", {
    x: 0.6, y: 2.0, w: 6, h: 0.4,
    fontSize: 14, fontFace: FONT_H, bold: true, color: TEXT, charSpacing: 2, margin: 0,
  });
  const listItems = [
    "Apple-style restrained status dots (green / amber / red)",
    "Live task bar · search · 5 status filters",
    "Submit modal with three tabs: local / URL / YT-BB",
    "“+ GotIt” primary button with AI rainbow gradient",
  ];
  s.addText(
    listItems.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < listItems.length - 1 } })),
    { x: 0.6, y: 2.5, w: 5.8, h: 1.5, fontSize: 12, fontFace: FONT_B, color: TEXT, paraSpaceAfter: 4 }
  );

  s.addText("DETAIL PAGE  ·  the most polished one", {
    x: 6.8, y: 2.0, w: 6, h: 0.4,
    fontSize: 14, fontFace: FONT_H, bold: true, color: TEXT, charSpacing: 2, margin: 0,
  });
  const detailItems = [
    [{ text: "Hook quote in large type", options: { bold: true } }, { text: " — one-line positioning under 30 chars" }],
    [{ text: "Sticky original audio player", options: { bold: true } }, { text: " — pinned to the top, never disappears on scroll" }],
    [{ text: "Clickable chapter quotes", options: { bold: true } }, { text: " — interpolated timestamps · seek + autoplay on click" }],
    [{ text: "AI Digest player", options: { bold: true } }, { text: " — flowing rainbow button, visually distinct from the original" }],
  ];
  const richList = [];
  detailItems.forEach((parts, idx) => {
    parts.forEach((p, j) => {
      richList.push({
        text: p.text,
        options: {
          ...(p.options || {}),
          bullet: j === 0 ? true : false,
          breakLine: j === parts.length - 1 && idx < detailItems.length - 1,
        },
      });
    });
  });
  s.addText(richList, {
    x: 6.8, y: 2.5, w: 5.9, h: 1.5, fontSize: 12, fontFace: FONT_B, color: TEXT, paraSpaceAfter: 4,
  });

  // screenshots
  // image4 (1882×690) is wide-short — list page area
  const lW = 5.9, lH = lW * (690 / 1882);
  s.addImage({ path: IMG.demoFrame, x: 0.6, y: 4.2, w: lW, h: lH });

  // image3 (1936×1200) — detail page
  const dW = 5.9, dH = dW * (1200 / 1936);
  s.addImage({ path: IMG.detailPage, x: 6.8, y: 4.2, w: dW, h: dH });

  addBrand(s);
  addPageNumber(s, 4, TOTAL);
}

// ============ S5 · Architecture ============
{
  const s = pres.addSlide();
  s.background = { color: BG };
  addTitle(s, "System architecture", "P6  ·  ARCHITECTURE");

  function block(x, y, w, h, title, items, fillColor) {
    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w, h, fill: { color: fillColor }, line: { color: RULE, width: 0.75 },
    });
    s.addText(title, {
      x: x + 0.15, y: y + 0.12, w: w - 0.3, h: 0.35,
      fontSize: 12, fontFace: FONT_H, bold: true, color: ACCENT, charSpacing: 1, margin: 0,
    });
    s.addText(
      items.map((t, i) => ({ text: t, options: { breakLine: i < items.length - 1 } })),
      {
        x: x + 0.15, y: y + 0.5, w: w - 0.3, h: h - 0.55,
        fontSize: 12, fontFace: FONT_B, color: TEXT, margin: 0,
      }
    );
  }

  block(0.6, 2.0, 11.0, 1.4, "FRONTEND", [
    "React 19 + Tailwind + framer-motion + Aceternity  · :5174",
  ], "FFFFFF");

  s.addText("↓   HTTP /api    ·    WS /api/ws/jobs   ↓", {
    x: 0.6, y: 3.45, w: 11.0, h: 0.3,
    fontSize: 11, fontFace: "Menlo", color: MUTED, italic: true, align: "center", margin: 0,
  });

  block(0.6, 3.85, 11.0, 1.9, "FASTAPI  ·  uvicorn :8000", [
    "Pipeline runner (asyncio)",
    "•  8 stages · tenacity retries · stage_progress → SQLite",
    "•  event bus → WebSocket broadcast",
  ], ACCENT_SOFT);

  block(0.6, 5.85, 11.0, 1.0, "External services (see P8 stack)", [
    "yt-dlp / ffmpeg    ·    Doubao ASR / TTS    ·    DeepSeek LLM",
  ], "FFFFFF");

  addBrand(s);
  addPageNumber(s, 5, TOTAL);
}

// ============ S6 · Pipeline ============
{
  const s = pres.addSlide();
  s.background = { color: BG };
  addTitle(s, "End-to-end pipeline · 8 stages", "P7  ·  PIPELINE");

  const stages = [
    { n: "1", t: "fetch", c: "F39C12" },
    { n: "2", t: "transcribe", c: "3498DB" },
    { n: "3", t: "summarize_hook", c: "9B59B6" },
    { n: "4", t: "three_act", c: "9B59B6" },
    { n: "5", t: "chapter", c: "9B59B6" },
    { n: "6", t: "quote_verify ⚠", c: "E74C3C" },
    { n: "7", t: "entity", c: "9B59B6" },
    { n: "8", t: "export", c: "7F8C8D" },
  ];
  const pX = 0.6, pY = 2.0, pW = 12.1, pH = 1.0;
  const cellW = pW / stages.length;
  stages.forEach((st, i) => {
    s.addShape(pres.shapes.RECTANGLE, {
      x: pX + i * cellW, y: pY, w: cellW - 0.05, h: pH,
      fill: { color: st.c }, line: { type: "none" },
    });
    s.addText(
      [
        { text: st.n + "\n", options: { fontSize: 11, color: "FFFFFF", bold: true, breakLine: true } },
        { text: st.t, options: { fontSize: 11, color: "FFFFFF", bold: true } },
      ],
      {
        x: pX + i * cellW, y: pY, w: cellW - 0.05, h: pH,
        align: "center", valign: "middle", fontFace: FONT_B, margin: 0,
      }
    );
  });

  s.addText("+ tts (separate sub-flow, on-demand, never blocks the main pipeline — see P9)", {
    x: 0.6, y: 3.15, w: 12.1, h: 0.3,
    fontSize: 11, fontFace: FONT_B, color: MUTED, italic: true, align: "center", margin: 0,
  });

  const pillars = [
    { t: "Independent retry", d: "tenacity exponential backoff · a failed stage doesn't restart the whole job" },
    { t: "Persisted progress", d: "stage_progress lands in SQLite · resumable across restarts" },
    { t: "Live events", d: "/api/ws/jobs pushes to every client · single-stage Retry button" },
  ];
  const pgY = 3.7, pgH = 1.6, pgW = 3.95;
  pillars.forEach((p, i) => {
    const x = 0.6 + i * (pgW + 0.1);
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: pgY, w: pgW, h: pgH,
      fill: { color: ACCENT_SOFT }, line: { type: "none" },
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: pgY, w: 0.08, h: pgH,
      fill: { color: ACCENT }, line: { type: "none" },
    });
    s.addText(p.t, {
      x: x + 0.25, y: pgY + 0.2, w: pgW - 0.35, h: 0.5,
      fontSize: 16, fontFace: FONT_H, bold: true, color: TEXT, margin: 0,
    });
    s.addText(p.d, {
      x: x + 0.25, y: pgY + 0.75, w: pgW - 0.35, h: pgH - 0.85,
      fontSize: 12, fontFace: FONT_B, color: MUTED, margin: 0,
    });
  });

  s.addText("⚠ stage 6 quote_verify is custom: NFKC + substring match + per-character interpolation for timestamps — see P10 bug #5", {
    x: 0.6, y: 5.6, w: 12.1, h: 0.4,
    fontSize: 12, fontFace: FONT_B, color: WARN, italic: true, margin: 0,
  });

  addBrand(s);
  addPageNumber(s, 6, TOTAL);
}

// ============ S7 · Stack ============
{
  const s = pres.addSlide();
  s.background = { color: BG };
  addTitle(s, "Stack & why we picked each piece", "P8  ·  STACK");

  const headerRow = ["Layer", "Choice", "Why this one"].map((t) => ({
    text: t,
    options: { bold: true, color: "FFFFFF", fill: { color: BG_DARK }, fontSize: 12, valign: "middle" },
  }));
  const dataRows = [
    ["Backend", "FastAPI + SQLAlchemy 2 + Alembic + Pydantic 2", "Strict types · async-friendly · controlled migrations"],
    ["Orchestration", "asyncio + tenacity", "No extra queue — local tool, this is enough"],
    ["Frontend v1", "React 19 + Vite + plain CSS", "Feature-complete · minimal deps"],
    ["Frontend v2", "React 19 + Tailwind + framer-motion + Aceternity", "Visual A/B experiment"],
    ["ASR", "Doubao bigmodel 2.0 (streaming / file)", "Strong on Chinese · pay-per-char pricing"],
    ["LLM", "DeepSeek (default) · Qwen · Anthropic", "Cost-effective + multi-vendor abstraction (see P9)"],
    ["TTS", "Doubao v1 standard · Doubao bigmodel 2.0 (WS)", "Dual track with fallback"],
    ["Downloader", "yt-dlp + ffmpeg", "Handles YouTube and Bilibili"],
    ["Testing", "pytest + Vitest · domain ≥ 80%", "Pure-functional domain · CI hard gate"],
  ];
  const tableData = [headerRow].concat(
    dataRows.map((row, i) =>
      row.map((cell, j) => ({
        text: cell,
        options: {
          fontSize: 12,
          color: TEXT,
          fill: { color: i % 2 === 0 ? "FFFFFF" : ACCENT_SOFT },
          bold: j === 0,
          valign: "middle",
        },
      }))
    )
  );
  s.addTable(tableData, {
    x: 0.6, y: 2.0, w: 12.1, colW: [1.8, 5.8, 4.5],
    rowH: 0.45,
    fontFace: FONT_B,
    border: { pt: 0.5, color: RULE },
  });

  addBrand(s);
  addPageNumber(s, 7, TOTAL);
}

// ============ S8 · Protocol ============
{
  const s = pres.addSlide();
  s.background = { color: BG };
  addTitle(s, "Multi-vendor abstraction + one tricky adapter", "P9  ·  PROTOCOL");

  s.addText("ABSTRACTION", {
    x: 0.6, y: 2.0, w: 5.5, h: 0.4,
    fontSize: 14, fontFace: FONT_H, bold: true, color: TEXT, charSpacing: 2, margin: 0,
  });
  const absItems = [
    "ASR: doubao / openai_whisper / qwen — flip one env var",
    "LLM: deepseek / qwen / anthropic — same",
    "TTS: doubao legacy / bigmodel / qwen — same",
    "create_xxx_client() factory + Protocol interface · callers stay oblivious",
  ];
  s.addText(
    absItems.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < absItems.length - 1 } })),
    { x: 0.6, y: 2.5, w: 5.7, h: 2.2, fontSize: 13, fontFace: FONT_B, color: TEXT, paraSpaceAfter: 4 }
  );

  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.6, y: 5.0, w: 5.7, h: 1.85,
    fill: { color: ACCENT_SOFT }, line: { type: "none" },
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.6, y: 5.0, w: 0.08, h: 1.85,
    fill: { color: ACCENT }, line: { type: "none" },
  });
  s.addText("WHAT I DID", {
    x: 0.85, y: 5.1, w: 5.4, h: 0.3,
    fontSize: 11, fontFace: FONT_H, bold: true, color: ACCENT, charSpacing: 1, margin: 0,
  });
  s.addText(
    [
      { text: "Ported the official demo into _doubao_bigtts_protocol.py · fixed X-Api-App-Key → X-Api-App-Id", options: { bullet: true, breakLine: true } },
      { text: "thread + asyncio.run to bridge the async WS into a sync pipeline stage", options: { bullet: true, breakLine: true } },
      { text: "On failure, dump the first 500 chars of the server response straight into job.error", options: { bullet: true } },
    ],
    { x: 0.85, y: 5.4, w: 5.4, h: 1.4, fontSize: 11, fontFace: FONT_B, color: TEXT, paraSpaceAfter: 2 }
  );

  s.addText("DOUBAO BIGMODEL TTS 2.0 PROTOCOL", {
    x: 6.6, y: 2.0, w: 6.2, h: 0.4,
    fontSize: 14, fontFace: FONT_H, bold: true, color: TEXT, charSpacing: 2, margin: 0,
  });
  s.addText("No HTTP one-shot endpoint — only a WebSocket binary stream:", {
    x: 6.6, y: 2.45, w: 6.2, h: 0.3,
    fontSize: 12, fontFace: FONT_B, color: MUTED, margin: 0,
  });

  s.addShape(pres.shapes.RECTANGLE, {
    x: 6.6, y: 2.85, w: 6.2, h: 1.7,
    fill: { color: BG_DARK }, line: { type: "none" },
  });
  s.addText(
    [
      { text: "[4-byte header]", options: { color: "FF9F0A", breakLine: true } },
      { text: "  version / type / flags / serialization", options: { color: "8E8E93", breakLine: true } },
      { text: "[4-byte event id]  (optional)", options: { color: "FF9F0A", breakLine: true } },
      { text: "[session_id length + bytes]  (optional)", options: { color: "FF9F0A", breakLine: true } },
      { text: "[4-byte payload size + payload]", options: { color: "FF9F0A" } },
    ],
    {
      x: 6.75, y: 2.95, w: 6.0, h: 1.6,
      fontSize: 11, fontFace: "Menlo", margin: 0,
    }
  );

  s.addText("EVENT FLOW", {
    x: 6.6, y: 4.7, w: 6.2, h: 0.3,
    fontSize: 11, fontFace: FONT_H, bold: true, color: ACCENT, charSpacing: 1, margin: 0,
  });
  s.addText("StartConnection → StartSession → TaskRequest → FinishSession → SessionFinished", {
    x: 6.6, y: 5.0, w: 6.2, h: 0.4,
    fontSize: 11, fontFace: "Menlo", color: TEXT, margin: 0,
  });
  s.addText("Audio frames stream back chunked via AudioOnlyServer", {
    x: 6.6, y: 5.4, w: 6.2, h: 0.3,
    fontSize: 11, fontFace: FONT_B, color: MUTED, italic: true, margin: 0,
  });

  s.addText("“Not calling an off-the-shelf pip package — I implemented the protocol layer myself.”", {
    x: 6.6, y: 6.0, w: 6.2, h: 0.6,
    fontSize: 13, fontFace: FONT_B, color: TEXT, italic: true, bold: true, margin: 0,
  });

  addBrand(s);
  addPageNumber(s, 8, TOTAL);
}

// ============ S9 · Bugs ============
{
  const s = pres.addSlide();
  s.background = { color: BG };
  addTitle(s, "Hard-won bugs I tracked down myself", "P10  ·  the most important slide");

  const header = ["#", "Symptom", "Root cause", "Fix / lesson"].map((t) => ({
    text: t,
    options: { bold: true, color: "FFFFFF", fill: { color: BG_DARK }, fontSize: 11, valign: "middle" },
  }));
  const bugs = [
    ["1", "TTS kept returning 401", "Doubao expects Authorization: Bearer;<token> — semicolon, not space", "1-line fix · not every API follows OAuth"],
    ["2", "TTS 400 ‘exceed max len’", "v1 single text payload ≤ 1024 bytes", "_split_text_for_tts splits on sentence boundaries by utf-8 bytes · protocol detail buried in footnote"],
    ["3 ⚠", "BigTTS ‘concurrency exceeded’ forever", "resource_id was an internal numeric id; correct value is the semantic string seed-tts-2.0", "Env fix · don't trust error messages at face value", true],
    ["4", "digest.mp3 came out empty, no error", "language=mixed routed to an English voice synthesizing Chinese → server silently dropped output", "_voice_type maps mixed to Chinese · silent failure is worse than an exception"],
    ["5 ⚠", "Multiple quotes shared the same timestamp", "Old logic returned the segment start — no interpolation", "Rewrote verify_against_segments to interpolate by character position in segment · always look at the data, not just the schema", true],
    ["6", "Worker crashed on retry", "quote_verify re-run hit the (chapter_id, idx) unique constraint", "delete_for_chapters cleans up first + unit test · idempotency is table stakes"],
  ];
  const tableData = [header].concat(
    bugs.map((row, i) => {
      const isWarn = row[4] === true;
      return row.slice(0, 4).map((cell, j) => ({
        text: cell,
        options: {
          fontSize: 11,
          color: isWarn && j === 0 ? WARN : TEXT,
          bold: isWarn && j === 0,
          fill: { color: isWarn ? "FFF4F2" : (i % 2 === 0 ? "FFFFFF" : ACCENT_SOFT) },
          valign: "middle",
        },
      }));
    })
  );
  s.addTable(tableData, {
    x: 0.6, y: 2.0, w: 12.1, colW: [0.7, 2.6, 4.4, 4.4],
    rowH: 0.62,
    fontFace: FONT_B,
    border: { pt: 0.5, color: RULE },
  });

  s.addText(
    "“None of these were the kind of thing an AI could surface up front — they came from reading responses, reading the protocol, reading the DB.”",
    {
      x: 0.6, y: 6.55, w: 12.1, h: 0.4,
      fontSize: 12, fontFace: FONT_B, color: TEXT, italic: true, bold: true, margin: 0,
    }
  );

  addBrand(s);
  addPageNumber(s, 9, TOTAL);
}

// ============ S10 · SDD ============
{
  const s = pres.addSlide();
  s.background = { color: BG };
  addTitle(s, "SDD: write the spec before the code", "P11  ·  SPEC-DRIVEN");

  // Left: spec/ file tree
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.6, y: 2.0, w: 6.0, h: 4.8,
    fill: { color: BG_DARK }, line: { type: "none" },
  });
  s.addText(
    [
      { text: "specs/001-podcast-summary/\n", options: { bold: true, color: "FFFFFF", breakLine: true } },
      { text: "├── spec.md            ", options: { color: "FF9F0A" } },
      { text: "feature spec (stories + acceptance)\n", options: { color: "8E8E93", breakLine: true } },
      { text: "├── plan.md            ", options: { color: "FF9F0A" } },
      { text: "implementation plan + complexity log\n", options: { color: "8E8E93", breakLine: true } },
      { text: "├── research.md        ", options: { color: "FF9F0A" } },
      { text: "vendor trade-off (≥ 2 candidates each)\n", options: { color: "8E8E93", breakLine: true } },
      { text: "├── data-model.md      ", options: { color: "FF9F0A" } },
      { text: "entity relationships\n", options: { color: "8E8E93", breakLine: true } },
      { text: "├── tasks.md           ", options: { color: "FF9F0A" } },
      { text: "dependency-ordered tasks\n", options: { color: "8E8E93", breakLine: true } },
      { text: "├── quickstart.md      ", options: { color: "FF9F0A" } },
      { text: "getting-started guide\n", options: { color: "8E8E93", breakLine: true } },
      { text: "├── ui-brief.md        ", options: { color: "FF9F0A" } },
      { text: "UI design brief\n", options: { color: "8E8E93", breakLine: true } },
      { text: "├── contracts/\n", options: { color: "FFFFFF", breakLine: true } },
      { text: "│   ├── http-api.md          ", options: { color: "FF9F0A" } },
      { text: "REST contract\n", options: { color: "8E8E93", breakLine: true } },
      { text: "│   ├── job-events.md        ", options: { color: "FF9F0A" } },
      { text: "WS event schema\n", options: { color: "8E8E93", breakLine: true } },
      { text: "│   └── episode-output.schema.json\n", options: { color: "FF9F0A", breakLine: true } },
      { text: "└── design/...         ", options: { color: "FF9F0A" } },
      { text: "UI mockups", options: { color: "8E8E93" } },
    ],
    { x: 0.8, y: 2.15, w: 5.7, h: 4.6, fontSize: 11, fontFace: "Menlo", margin: 0 }
  );

  // Top-right: Git log label + task zoom + task list sidebar
  s.addText("Git log: 78 tasks", {
    x: 7.0, y: 1.95, w: 3.5, h: 0.4,
    fontSize: 14, fontFace: FONT_H, bold: true, color: TEXT, margin: 0,
  });

  // image6 (552×198) — task cluster zoom — wide-short
  const tzW = 4.0, tzH = tzW * (198 / 552);
  s.addImage({ path: IMG.taskZoom, x: 7.0, y: 2.35, w: tzW, h: tzH });

  // image5 (564×3580) — full task list — tall sidebar
  const tlH = 4.6, tlW = tlH * (564 / 3580); // ≈0.72
  s.addImage({ path: IMG.taskList, x: 12.55, y: 2.1, w: tlW, h: tlH });

  // constitution.md heading
  s.addText("constitution.md  v1.0.0", {
    x: 7.0, y: 3.7, w: 5.4, h: 0.4,
    fontSize: 16, fontFace: FONT_H, bold: true, color: TEXT, margin: 0,
  });
  s.addText("5 non-negotiable principles", {
    x: 7.0, y: 4.1, w: 5.4, h: 0.3,
    fontSize: 11, fontFace: FONT_B, color: MUTED, italic: true, margin: 0,
  });

  const principles = [
    { n: "1", t: "Ship in English", d: "docs / comments / commits" },
    { n: "2", t: "Python 3.11+", d: "unified backend stack" },
    { n: "3", t: "Domain ≥ 80% coverage", d: "NON-NEGOTIABLE" },
    { n: "4", t: "Externalized config", d: "env / .env · no hardcoded secrets" },
    { n: "5", t: "Versioned prompts", d: "prompts/ directory, every prompt versioned" },
  ];
  principles.forEach((p, i) => {
    const y = 4.55 + i * 0.45;
    s.addShape(pres.shapes.OVAL, {
      x: 7.0, y, w: 0.35, h: 0.35,
      fill: { color: ACCENT }, line: { type: "none" },
    });
    s.addText(p.n, {
      x: 7.0, y, w: 0.35, h: 0.35,
      fontSize: 12, fontFace: FONT_H, bold: true, color: "FFFFFF",
      align: "center", valign: "middle", margin: 0,
    });
    const isNN = p.d === "NON-NEGOTIABLE";
    s.addText(
      [
        { text: p.t, options: { bold: true, color: TEXT, fontSize: 12 } },
        { text: "   " + p.d, options: { color: isNN ? WARN : MUTED, fontSize: 10, bold: isNN } },
      ],
      {
        x: 7.5, y: y, w: 4.9, h: 0.35,
        fontFace: FONT_B, margin: 0, valign: "middle",
      }
    );
  });

  addBrand(s);
  addPageNumber(s, 10, TOTAL);
}

// ============ S11 · THANKS ============
{
  const s = pres.addSlide();
  s.background = { color: BG_DARK };

  s.addText("THANKS", {
    x: 1.0, y: 2.8, w: 5, h: 1.3,
    fontSize: 80, fontFace: FONT_H, bold: true, color: ACCENT, margin: 0,
  });
  s.addText("Q & A", {
    x: 7.5, y: 3.4, w: 5, h: 1.0,
    fontSize: 64, fontFace: FONT_H, bold: true, color: "FFFFFF", margin: 0,
  });

  addPageNumber(s, 11, TOTAL);
}

pres.writeFile({ fileName: path.join(__dirname, "GotIt-Podsum-deck-EN.pptx") })
  .then((name) => console.log("Wrote: " + name));
