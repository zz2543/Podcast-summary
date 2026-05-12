export const C = {
  black: "#020407",
  panel: "#07090D",
  panel2: "#0D1117",
  white: "#F7FAFF",
  muted: "#B8C0CC",
  subtle: "#727B88",
  line: "#DCE7F840",
  blue: "#2D8FCF",
  cyan: "#55C7E8",
  mint: "#54D8B6",
  pink: "#FCA1D3",
  amber: "#F8B55B",
};

export const F = {
  title: "Inter",
  body: "Inter",
  mono: "Aptos Mono",
};

function svgDataUrl(svg) {
  return `data:image/svg+xml;base64,${Buffer.from(svg, "utf8").toString("base64")}`;
}

export async function bg(slide, ctx, variant = 0) {
  const palettes = [
    [
      ["#2D8FCF", 860, 144, 420, 260, 0.72],
      ["#54D8B6", 210, 506, 360, 180, 0.42],
      ["#FCA1D3", 1084, 540, 300, 160, 0.42],
    ],
    [
      ["#2D8FCF", 220, 180, 430, 260, 0.62],
      ["#54D8B6", 1020, 488, 410, 190, 0.38],
      ["#F8B55B", 650, 560, 300, 130, 0.34],
    ],
    [
      ["#55C7E8", 980, 130, 520, 310, 0.58],
      ["#FCA1D3", 760, 560, 320, 180, 0.34],
      ["#54D8B6", 184, 590, 380, 150, 0.3],
    ],
    [
      ["#2D8FCF", 260, 110, 480, 280, 0.48],
      ["#F8B55B", 1040, 575, 360, 180, 0.32],
      ["#FCA1D3", 930, 170, 320, 160, 0.25],
    ],
  ][variant % 4];
  const ellipses = palettes
    .map(
      ([fill, cx, cy, rx, ry, opacity]) =>
        `<ellipse cx="${cx}" cy="${cy}" rx="${rx}" ry="${ry}" fill="${fill}" opacity="${opacity}" filter="url(#blur)"/>`
    )
    .join("");
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <defs>
    <filter id="blur" x="-40%" y="-60%" width="180%" height="220%"><feGaussianBlur stdDeviation="54"/></filter>
    <radialGradient id="shade" cx="50%" cy="42%" r="80%"><stop offset="0%" stop-color="#111827" stop-opacity="0.05"/><stop offset="100%" stop-color="#020407" stop-opacity="0.72"/></radialGradient>
  </defs>
  <rect width="1280" height="720" fill="#020407"/>
  ${ellipses}
  <rect width="1280" height="720" fill="url(#shade)"/>
  <rect width="1280" height="720" fill="#000000" opacity="0.10"/>
</svg>`;
  await ctx.addImage(slide, {
    dataUrl: svgDataUrl(svg),
    left: 0,
    top: 0,
    width: ctx.W,
    height: ctx.H,
    fit: "cover",
    alt: "abstract blue glow background",
  });
}

export function rect(slide, ctx, x, y, w, h, fill = "#00000000", opts = {}) {
  return ctx.addShape(slide, {
    left: x,
    top: y,
    width: w,
    height: h,
    geometry: opts.geometry ?? "roundRect",
    fill,
    line: opts.line ?? ctx.line(opts.stroke ?? C.line, opts.strokeWidth ?? 1),
  });
}

export function text(slide, ctx, value, x, y, w, h, opts = {}) {
  return ctx.addText(slide, {
    text: String(value ?? ""),
    left: x,
    top: y,
    width: w,
    height: h,
    fontSize: opts.size ?? 18,
    color: opts.color ?? C.white,
    bold: Boolean(opts.bold),
    typeface: opts.face ?? (opts.title ? F.title : F.body),
    align: opts.align ?? "left",
    valign: opts.valign ?? "top",
    fill: "#00000000",
    line: ctx.line(),
    insets: opts.insets ?? { left: 0, right: 0, top: 0, bottom: 0 },
  });
}

export function header(slide, ctx, label, n, total = 9) {
  text(slide, ctx, "Podsum", 64, 36, 68, 20, { size: 12, bold: true });
  rect(slide, ctx, 150, 39, 34, 14, "#FFFFFF", { stroke: "#FFFFFF", strokeWidth: 0 });
  text(slide, ctx, "v2", 156, 41, 22, 8, { size: 7, bold: true, color: "#06080C", align: "center" });
  text(slide, ctx, label, 540, 36, 200, 16, { size: 10, bold: true, color: C.muted, align: "center" });
  text(slide, ctx, `2026`, 1158, 36, 60, 16, { size: 10, bold: true, color: C.muted, align: "right" });
  text(slide, ctx, `${n}/${total}`, 610, 54, 60, 34, { size: 26, bold: true, align: "center" });
}

export function title(slide, ctx, value, x, y, w, h, size = 54) {
  text(slide, ctx, value, x, y, w, h, {
    size,
    bold: true,
    title: true,
    color: C.white,
  });
}

export function body(slide, ctx, value, x, y, w, h, size = 17) {
  text(slide, ctx, value, x, y, w, h, { size, color: "#E4E9F0" });
}

export function small(slide, ctx, value, x, y, w, h, size = 12) {
  text(slide, ctx, value, x, y, w, h, { size, color: C.muted });
}

export async function icon(slide, ctx, name, x, y, size = 24, color = C.white) {
  return ctx.addLucideIcon(slide, {
    icon: name,
    left: x,
    top: y,
    width: size,
    height: size,
    color,
    strokeWidth: 1.8,
  });
}

export function pill(slide, ctx, label, x, y, w, opts = {}) {
  rect(slide, ctx, x, y, w, 28, opts.fill ?? "#FFFFFF", {
    stroke: opts.stroke ?? "#FFFFFF",
    strokeWidth: 0,
  });
  text(slide, ctx, label, x + 9, y + 8, w - 18, 10, {
    size: 8.5,
    bold: true,
    color: opts.color ?? "#05070B",
    align: "center",
  });
}

export function outlineCard(slide, ctx, x, y, w, h, opts = {}) {
  rect(slide, ctx, x, y, w, h, opts.fill ?? "#00000056", {
    stroke: opts.stroke ?? "#FFFFFF99",
    strokeWidth: opts.strokeWidth ?? 1.25,
  });
}

export function underline(slide, ctx, x, y, w, color = "#FFFFFFB0") {
  rect(slide, ctx, x, y, w, 1.4, color, { geometry: "rect", stroke: "#00000000" });
}

export function metricCard(slide, ctx, value, label, x, y, w, h = 160, accent = C.blue) {
  outlineCard(slide, ctx, x, y, w, h);
  text(slide, ctx, value, x + 22, y + 22, w - 44, 46, { size: 38, bold: true, color: accent, title: true });
  text(slide, ctx, label, x + 22, y + 84, w - 44, 48, { size: 13, color: "#E6ECF5" });
}

export function audioBars(slide, ctx, x, y, color = C.blue) {
  const heights = [18, 36, 28, 52, 22, 44, 34, 56, 26, 48];
  heights.forEach((h, i) => {
    rect(slide, ctx, x + i * 16, y + 60 - h, 8, h, i % 3 === 0 ? "#FFFFFF" : color, {
      geometry: "roundRect",
      stroke: "#00000000",
    });
  });
}

export function arrowCircle(slide, ctx, x, y, size = 62) {
  rect(slide, ctx, x, y, size, size, "#FFFFFF", { geometry: "ellipse", stroke: "#FFFFFF", strokeWidth: 0 });
  text(slide, ctx, "↗", x + size * 0.22, y + size * 0.1, size * 0.6, size * 0.6, {
    size: size * 0.48,
    bold: true,
    color: C.blue,
    align: "center",
  });
}

export const CN = {
  label: "播客知识工作流",
  s1Title: "把长播客变成可复用的知识材料",
  s1Body:
    "我们做的不是简单 AI 总结器，而是一个完整网站：音频输入、转写、结构化复盘、可信引用、音频摘要和 Markdown 知识沉淀。",
  s2Title: "长播客的问题不是听不完，而是难筛选、难复盘、难沉淀。",
  s2Body:
    "目标是把 60 到 90 分钟的音频，转化成可以快速浏览、深入复盘、长期沉淀的学习材料。",
  s2Cards: [
    ["快速理解", "用 hook 和结构化摘要先判断是否值得深入。"],
    ["可信复盘", "章节、quote 和时间戳让用户回到原文证据。"],
    ["知识沉淀", "Markdown/JSON 导出进入 Obsidian 等笔记系统。"],
  ],
  s3Title: "产品不是静态结果页，而是有状态反馈和动效的网站。",
  s3Body:
    "上传、处理、摘要出现、章节切换、quote 跳转和音频摘要生成都有清晰反馈，让用户知道系统正在做什么。",
  s3Items: ["上传后的任务卡片变化", "ASR/LLM 处理进度推进", "摘要与章节逐步出现", "quote 点击后跳转原音频", "音频摘要按钮状态变化"],
  s4Title: "核心流程把 Prompt 与 Obsidian 融进同一条认知效率链路。",
  s4Steps: [
    ["Podcast / YouTube / Audio URL", "原始输入"],
    ["音频获取与格式处理", "进入 pipeline"],
    ["ASR 转写", "带时间戳 transcript"],
    ["Prompt 结构化总结", "按认知层级生成"],
    ["快速浏览摘要", "Background / Core / Agreement / Conclusion"],
    ["分章节深度复盘", "章节要点 / quote / 时间戳 / 实体"],
    ["导出与再利用", "Markdown / JSON / TTS digest"],
    ["个人知识库", "Obsidian / Notion / 笔记系统"],
  ],
  s5Title: "功能拆分成五层，既突出产品可用性，也突出工作量",
  s5Rows: [
    ["输入层", "本地音频、音频链接、YouTube、批量提交"],
    ["AI 处理层", "ASR 转写、LLM 总结、TTS 音频摘要"],
    ["认知结构层", "Background / Core Argument / Agreement / Conclusion + 分章节总结"],
    ["交互体验层", "动效、进度反馈、章节展开、quote 点击跳转"],
    ["知识沉淀层", "Markdown / JSON 导出，接入 Obsidian 等笔记软件"],
  ],
  s5Quote:
    "快速浏览回答“这期值不值得看”；分章节总结回答“重点在哪里”；quote 和时间戳回答“原文是不是这样说”。",
  s6Title: "工程亮点说明这些体验背后的真实工作量。",
  s6Items: [
    ["Pipeline 状态机", "完整 job 阶段与重试、恢复、降级语义。"],
    ["SQLite 持久化", "episode、job、transcript、chapter、quote、entity、artifact。"],
    ["并发队列", "批量任务按 MAX_CONCURRENCY 控制并行处理。"],
    ["Quote 校验", "必须逐字命中 transcript 才能展示，减少幻觉。"],
    ["Prompt 版本化", "提示词集中在 prompts/，按 role/version 读取。"],
    ["多格式导出", "Markdown、JSON、原音频、TTS digest 都可下载。"],
  ],
  s7Title: "踩坑与取舍体现项目不是表面 demo，而是经过工程收敛。",
  s7Items: [
    ["SQLite 并发写锁", "改成阶段 checkpoint 后立即 commit，避免长事务阻塞。"],
    ["Quote 双层防御", "写入时校验，JSON 导出时再次过滤 verified quote。"],
    ["Optional stage 降级", "TTS/entity 失败不拖垮整个 episode。"],
    ["V1 范围控制", "不做 diarization/auth/local model，保证主链路可交付。"],
  ],
  s8Title: "完成度用测试、校验和生产模式验证支撑。",
  s8Metrics: [
    ["63", "Backend tests passed"],
    ["87.98%", "Domain coverage"],
    ["PASS", "Quote verifier: PASS 1 / FAIL 0"],
    ["206", "Range endpoint verified"],
    ["≤ 2", "MAX_CONCURRENCY=2 生效"],
    ["Serve", "make build && make serve 通过"],
  ],
  closeTitle: "不是普通 AI 播客总结器，而是面向真实学习场景的播客知识工作流工具。",
  closeQuote: "从“听完一集播客”到“得到可验证、可复盘、可沉淀的知识材料”。",
};

export const EN = {
  label: "Podcast Knowledge Workflow",
  s1Title: "Turning long podcasts into reusable knowledge assets",
  s1Body:
    "This is not a simple AI summarizer. It is a usable web product for audio intake, transcription, structured review, verified quotes, audio digest, and Markdown knowledge capture.",
  s2Title: "The problem is not just listening time; it is triage, review, and retention.",
  s2Body:
    "The goal is to turn a 60-90 minute episode into material users can scan quickly, review deeply, and keep in their knowledge system.",
  s2Cards: [
    ["Fast understanding", "A hook and structured summary help users decide whether to go deeper."],
    ["Trustworthy review", "Chapters, quotes, and timestamps bring users back to source evidence."],
    ["Knowledge capture", "Markdown/JSON exports move the episode into Obsidian or similar tools."],
  ],
  s3Title: "The product is not a static result page; it is an interactive website with motion and state.",
  s3Body:
    "Upload, processing, summary reveal, chapter switching, quote seeking, and audio digest generation all provide clear feedback.",
  s3Items: ["Task card changes after upload", "ASR/LLM progress feedback", "Summary and chapters reveal", "Quote click seeks original audio", "Audio digest button state"],
  s4Title: "The core workflow integrates prompt design and Obsidian into one cognition pipeline.",
  s4Steps: [
    ["Podcast / YouTube / Audio URL", "raw input"],
    ["Audio acquisition", "pipeline entry"],
    ["ASR transcription", "timestamped transcript"],
    ["Prompted structure", "cognition-first output"],
    ["Quick browse", "Background / Core / Agreement / Conclusion"],
    ["Chapter review", "key points / quotes / timestamps / entities"],
    ["Export and reuse", "Markdown / JSON / TTS digest"],
    ["Knowledge base", "Obsidian / Notion / notes"],
  ],
  s5Title: "The feature set is organized into five user-facing layers.",
  s5Rows: [
    ["Input layer", "local audio, direct URL, YouTube, batch submission"],
    ["AI processing", "ASR transcription, LLM summary, TTS audio digest"],
    ["Cognitive structure", "Background / Core Argument / Agreement / Conclusion + chapter review"],
    ["Interaction layer", "motion, progress feedback, chapter expansion, quote seeking"],
    ["Knowledge layer", "Markdown / JSON export into Obsidian-style note workflows"],
  ],
  s5Quote:
    "Quick browsing answers “is this worth my time”; chapter review answers “where are the key ideas”; quotes answer “did the source really say this.”",
  s6Title: "Engineering highlights show the work behind the experience.",
  s6Items: [
    ["Pipeline state machine", "Job stages with retry, resume, and degradation semantics."],
    ["SQLite persistence", "episode, job, transcript, chapter, quote, entity, artifact."],
    ["Concurrency queue", "Batch tasks obey MAX_CONCURRENCY."],
    ["Quote verification", "Quotes must match the transcript verbatim before display."],
    ["Prompt versioning", "Prompts live in prompts/ and are loaded by role/version."],
    ["Multi-format export", "Markdown, JSON, original audio, and TTS digest are downloadable."],
  ],
  s7Title: "Tradeoffs and fixes show engineering reality, not a surface demo.",
  s7Items: [
    ["SQLite write lock", "Fixed by committing immediately after each checkpoint."],
    ["Double quote defense", "Verify on write and filter verified quotes again during JSON export."],
    ["Optional-stage degrade", "TTS/entity failures do not break the whole episode."],
    ["V1 scope control", "No diarization/auth/local model so the core workflow can ship."],
  ],
  s8Title: "Completion is backed by tests, verification, and production serving.",
  s8Metrics: [
    ["63", "Backend tests passed"],
    ["87.98%", "Domain coverage"],
    ["PASS", "Quote verifier: PASS 1 / FAIL 0"],
    ["206", "Range endpoint verified"],
    ["≤ 2", "MAX_CONCURRENCY=2 respected"],
    ["Serve", "make build && make serve passed"],
  ],
  closeTitle: "Not just an AI podcast summarizer, but a real learning workflow tool.",
  closeQuote: "From listening once to producing verifiable, reviewable, reusable knowledge.",
};

export function content(lang) {
  return lang === "en" ? EN : CN;
}

export async function slide1(presentation, ctx, lang = "cn") {
  const d = content(lang);
  const slide = presentation.slides.add();
  await bg(slide, ctx, 0);
  header(slide, ctx, d.label, 1);
  title(slide, ctx, d.s1Title, 74, 196, 760, 132, lang === "en" ? 52 : 52);
  body(slide, ctx, d.s1Body, 78, 354, 610, 80, lang === "en" ? 16 : 17);
  pill(slide, ctx, "ASR + LLM + TTS", 78, 470, 128);
  pill(slide, ctx, "Verified quotes", 222, 470, 124);
  pill(slide, ctx, "Markdown → Obsidian", 362, 470, 162);
  arrowCircle(slide, ctx, 834, 282, 76);
  outlineCard(slide, ctx, 874, 380, 268, 118);
  text(slide, ctx, "Structured\nPodcast\nWorkflow", 904, 410, 196, 64, { size: 24, bold: true, title: true });
  audioBars(slide, ctx, 906, 534, C.blue);
  return slide;
}

export async function slide2(presentation, ctx, lang = "cn") {
  const d = content(lang);
  const slide = presentation.slides.add();
  await bg(slide, ctx, 1);
  header(slide, ctx, d.label, 2);
  title(slide, ctx, d.s2Title, 74, 122, 900, 104, lang === "en" ? 42 : 42);
  body(slide, ctx, d.s2Body, 78, 238, 720, 48, 16);
  const icons = ["Search", "BadgeCheck", "BookOpen"];
  for (let i = 0; i < d.s2Cards.length; i += 1) {
    const x = 74 + i * 382;
    outlineCard(slide, ctx, x, 342, 310, 210);
    await icon(slide, ctx, icons[i], x + 28, 372, 34, i === 0 ? C.cyan : i === 1 ? C.mint : C.pink);
    text(slide, ctx, d.s2Cards[i][0], x + 28, 426, 238, 30, { size: lang === "en" ? 21 : 24, bold: true, title: true });
    small(slide, ctx, d.s2Cards[i][1], x + 28, 474, 238, 48, 14);
  }
  return slide;
}

export async function slide3(presentation, ctx, lang = "cn") {
  const d = content(lang);
  const slide = presentation.slides.add();
  await bg(slide, ctx, 2);
  header(slide, ctx, d.label, 3);
  title(slide, ctx, d.s3Title, 74, 100, 850, 112, lang === "en" ? 35 : 42);
  body(slide, ctx, d.s3Body, 78, lang === "en" ? 240 : 220, 680, 48, 16);
  outlineCard(slide, ctx, 78, 326, 508, 230);
  text(slide, ctx, "Motion storyboard", 108, 356, 220, 22, { size: 22, bold: true, title: true });
  const stages = ["Upload", "ASR", "Summary", "Quote", "Digest"];
  for (let i = 0; i < stages.length; i += 1) {
    const x = 114 + i * 84;
    rect(slide, ctx, x, 422, 48, 48, i % 2 ? "#FFFFFF18" : "#2D8FCF90", { geometry: "ellipse", stroke: "#FFFFFF70" });
    text(slide, ctx, String(i + 1), x, 438, 48, 14, { size: 12, bold: true, align: "center" });
    small(slide, ctx, stages[i], x - 8, 488, 64, 14, 9.5);
  }
  outlineCard(slide, ctx, 660, 296, 440, 292);
  for (let i = 0; i < d.s3Items.length; i += 1) {
    const y = 326 + i * 48;
    rect(slide, ctx, 694, y + 4, 10, 10, i % 2 ? C.mint : C.cyan, { geometry: "ellipse", stroke: "#00000000" });
    text(slide, ctx, d.s3Items[i], 724, y, 320, 22, { size: lang === "en" ? 14 : 15, bold: true });
  }
  return slide;
}

export async function slide4(presentation, ctx, lang = "cn") {
  const d = content(lang);
  const slide = presentation.slides.add();
  await bg(slide, ctx, 3);
  header(slide, ctx, d.label, 4);
  title(slide, ctx, d.s4Title, 74, 96, 880, 92, lang === "en" ? 39 : 40);
  const xs = [86, 360, 634, 908];
  for (let i = 0; i < d.s4Steps.length; i += 1) {
    const row = i < 4 ? 0 : 1;
    const col = i % 4;
    const x = xs[col];
    const y = 252 + row * 178;
    outlineCard(slide, ctx, x, y, 218, 106);
    text(slide, ctx, d.s4Steps[i][0], x + 18, y + 22, 178, 28, { size: lang === "en" ? 13.5 : 14.5, bold: true });
    small(slide, ctx, d.s4Steps[i][1], x + 18, y + 62, 176, 24, 10.5);
    if (col < 3) {
      underline(slide, ctx, x + 224, y + 54, 42, "#FFFFFF80");
    }
  }
  underline(slide, ctx, 1018, 374, 1.2, "#FFFFFF80");
  return slide;
}

export async function slide5(presentation, ctx, lang = "cn") {
  const d = content(lang);
  const slide = presentation.slides.add();
  await bg(slide, ctx, 0);
  header(slide, ctx, d.label, 5);
  title(slide, ctx, d.s5Title, 74, 90, 940, 82, lang === "en" ? 40 : 40);
  for (let i = 0; i < d.s5Rows.length; i += 1) {
    const y = 218 + i * 68;
    outlineCard(slide, ctx, 86, y, 1048, 48, { fill: i % 2 ? "#00000038" : "#FFFFFF12" });
    text(slide, ctx, d.s5Rows[i][0], 118, y + 14, 180, 16, { size: 15, bold: true });
    small(slide, ctx, d.s5Rows[i][1], 342, y + 14, 630, 16, lang === "en" ? 11.5 : 12.5);
  }
  text(slide, ctx, d.s5Quote, 132, 582, 948, 42, { size: lang === "en" ? 16 : 17, bold: true, align: "center" });
  return slide;
}

export async function slide6(presentation, ctx, lang = "cn") {
  const d = content(lang);
  const slide = presentation.slides.add();
  await bg(slide, ctx, 1);
  header(slide, ctx, d.label, 6);
  title(slide, ctx, d.s6Title, 74, 86, 880, 78, lang === "en" ? 42 : 42);
  for (let i = 0; i < d.s6Items.length; i += 1) {
    const col = i % 3;
    const row = Math.floor(i / 3);
    const x = 76 + col * 378;
    const y = 230 + row * 188;
    outlineCard(slide, ctx, x, y, 318, 126);
    text(slide, ctx, d.s6Items[i][0], x + 24, y + 26, 236, 22, { size: lang === "en" ? 17 : 19, bold: true, title: true });
    small(slide, ctx, d.s6Items[i][1], x + 24, y + 66, 246, 38, 12.5);
  }
  return slide;
}

export async function slide7(presentation, ctx, lang = "cn") {
  const d = content(lang);
  const slide = presentation.slides.add();
  await bg(slide, ctx, 2);
  header(slide, ctx, d.label, 7);
  title(slide, ctx, d.s7Title, 74, 90, 920, 88, lang === "en" ? 40 : 40);
  rect(slide, ctx, 636, 220, 2, 372, "#FFFFFFA8", { geometry: "rect", stroke: "#00000000" });
  for (let i = 0; i < d.s7Items.length; i += 1) {
    const y = 242 + i * 86;
    rect(slide, ctx, 626, y + 8, 22, 22, "#FFFFFF", { geometry: "ellipse", stroke: "#FFFFFF", strokeWidth: 0 });
    underline(slide, ctx, 650, y + 19, 92, "#FFFFFFA8");
    text(slide, ctx, d.s7Items[i][0], 766, y, 320, 24, { size: lang === "en" ? 20 : 22, bold: true, title: true });
    small(slide, ctx, d.s7Items[i][1], 766, y + 34, 350, 30, lang === "en" ? 12 : 13);
  }
  text(slide, ctx, lang === "en" ? "Tradeoffs" : "取舍", 92, 396, 250, 52, { size: 48, bold: true, title: true });
  small(slide, ctx, lang === "en" ? "Real engineering work means fixing failures and controlling scope." : "真实工程工作意味着修复失败，并控制边界。", 96, 468, 330, 44, 15);
  return slide;
}

export async function slide8(presentation, ctx, lang = "cn") {
  const d = content(lang);
  const slide = presentation.slides.add();
  await bg(slide, ctx, 3);
  header(slide, ctx, d.label, 8);
  title(slide, ctx, d.s8Title, 74, 112, 890, 86, lang === "en" ? 38 : 38);
  for (let i = 0; i < d.s8Metrics.length; i += 1) {
    const col = i % 3;
    const row = Math.floor(i / 3);
    const x = 84 + col * 374;
    const y = 228 + row * 176;
    metricCard(slide, ctx, d.s8Metrics[i][0], d.s8Metrics[i][1], x, y, 300, 128, [C.blue, C.mint, C.pink, C.cyan, C.amber, C.white][i]);
  }
  return slide;
}

export async function slide9(presentation, ctx, lang = "cn") {
  const d = content(lang);
  const slide = presentation.slides.add();
  await bg(slide, ctx, 0);
  header(slide, ctx, d.label, 9, 9);
  title(slide, ctx, d.closeTitle, 74, 142, 720, 138, lang === "en" ? 44 : 46);
  body(slide, ctx, d.s1Body, 78, 330, 610, 64, 16);
  outlineCard(slide, ctx, 790, 214, 350, 320);
  text(slide, ctx, "Final message", 826, 252, 150, 16, { size: 11, color: C.muted, bold: true });
  text(slide, ctx, d.closeQuote, 826, 312, 282, 132, { size: lang === "en" ? 21 : 25, bold: true, title: true });
  audioBars(slide, ctx, 832, 474, C.blue);
  return slide;
}
