const pptxgen = require("pptxgenjs");

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.3 x 7.5
pres.author = "group 1";
pres.title = "GotIt / Podsum";

const SLIDE_W = 13.3;
const SLIDE_H = 7.5;

// Apple-inspired palette
const BG = "FFFFFF";
const BG_DARK = "1D1D1F";
const TEXT = "1D1D1F";
const MUTED = "6E6E73";
const ACCENT = "0071E3";
const ACCENT_SOFT = "F5F5F7";
const RULE = "D2D2D7";
const WARN = "FF3B30";

const FONT_H = "PingFang SC";
const FONT_B = "PingFang SC";

// ---- helpers ----
function addPageNumber(slide, n, total, dark = false) {
  slide.addText(`${n} / ${total}`, {
    x: SLIDE_W - 1.2, y: SLIDE_H - 0.45, w: 1.0, h: 0.3,
    fontSize: 10, fontFace: FONT_B, color: dark ? MUTED : MUTED,
    align: "right",
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
  // divider
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0.6, y: eyebrow ? 1.65 : 1.4, w: 0.6, h: 0.04,
    fill: { color: ACCENT }, line: { type: "none" },
  });
}

// Image placeholder: dashed rectangle with caption
function addPlaceholder(slide, x, y, w, h, caption) {
  slide.addShape(pres.shapes.RECTANGLE, {
    x, y, w, h,
    fill: { color: ACCENT_SOFT },
    line: { color: RULE, width: 1.5, dashType: "dash" },
  });
  slide.addText(
    [
      { text: "🖼  图片 / 视频占位\n", options: { fontSize: 14, color: MUTED, bold: true, breakLine: true } },
      { text: caption || "在此处粘贴截图或视频", options: { fontSize: 11, color: MUTED } },
    ],
    {
      x, y, w, h, align: "center", valign: "middle",
      fontFace: FONT_B, margin: 0,
    }
  );
}

// ============ P1 · 封面 ============
{
  const s = pres.addSlide();
  s.background = { color: BG_DARK };

  // Big GotIt
  s.addText("GotIt", {
    x: 0.8, y: 2.0, w: 8, h: 1.6,
    fontSize: 96, fontFace: FONT_H, bold: true, color: "FFFFFF", margin: 0,
  });
  s.addText("本地端到端播客摘要工具", {
    x: 0.8, y: 3.6, w: 9, h: 0.6,
    fontSize: 22, fontFace: FONT_H, color: "FFFFFF", margin: 0,
  });
  s.addText("把一小时播客压成几分钟“听得懂”的浓缩", {
    x: 0.8, y: 4.2, w: 10, h: 0.5,
    fontSize: 16, fontFace: FONT_B, color: "8E8E93", margin: 0,
  });

  // accent bar
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.8, y: 5.2, w: 0.8, h: 0.06,
    fill: { color: ACCENT }, line: { type: "none" },
  });
  s.addText("group 1   ·   2026.05", {
    x: 0.8, y: 5.35, w: 6, h: 0.4,
    fontSize: 13, fontFace: FONT_B, color: "8E8E93", charSpacing: 2, margin: 0,
  });

  // right-side small placeholder
  addPlaceholder(s, 8.6, 1.6, 4.0, 4.3, "封面图 / v2 首页截图");

  addBrand(s, true);
  addPageNumber(s, 1, 13, true);
}

// ============ P2 · 想解决的问题 ============
{
  const s = pres.addSlide();
  s.background = { color: BG };
  addTitle(s, "想解决的问题", "P2  ·  MOTIVATION");

  // left: bullets
  const items = [
    "1 集播客 = 40 – 90 分钟",
    "想知道讲了啥 / 是否值得听 / 哪段值得回头",
    "人脑听 30 秒摘要 ≪ 听完 1 小时",
    "现有工具：太重（Otter）、不带章节（YT 自动字幕）、不浓缩（转录稿）",
  ];
  s.addText(
    items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1 } })),
    { x: 0.6, y: 2.0, w: 6.5, h: 2.5, fontSize: 16, fontFace: FONT_B, color: TEXT, paraSpaceAfter: 8 }
  );

  // tagline card
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.6, y: 4.8, w: 6.5, h: 1.8,
    fill: { color: ACCENT_SOFT }, line: { type: "none" },
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.6, y: 4.8, w: 0.08, h: 1.8,
    fill: { color: ACCENT }, line: { type: "none" },
  });
  s.addText("一句话定位", {
    x: 0.85, y: 4.9, w: 6, h: 0.3,
    fontSize: 11, fontFace: FONT_H, color: ACCENT, bold: true, charSpacing: 2, margin: 0,
  });
  s.addText(
    "给一个链接，10 分钟后你拿到 hook、三幕、章节、引用、命名实体，外加一段 30 秒可听的 TTS 浓缩。",
    {
      x: 0.85, y: 5.2, w: 6.1, h: 1.3,
      fontSize: 15, fontFace: FONT_B, color: TEXT, italic: true, margin: 0,
    }
  );

  // right placeholder
  addPlaceholder(s, 7.6, 2.0, 5.1, 4.6, "左：1 小时音频波形  ／  右：摘要卡片 + 30s digest");

  addBrand(s);
  addPageNumber(s, 2, 13);
}

// ============ P3 · Demo 导览 ============
{
  const s = pres.addSlide();
  s.background = { color: BG };
  addTitle(s, "Demo 导览", "P3  ·  LIVE DEMO");

  const steps = [
    { n: "01", t: "粘贴链接", d: "YouTube / Bilibili / mp3" },
    { n: "02", t: "看实时进度", d: "WebSocket 推送 · 下载 → ASR → 摘要 → 章节 → TTS" },
    { n: "03", t: "打开详情页", d: "hook · 三幕 · 章节时间轴 · 点引用跳原音频" },
    { n: "04", t: "音频概览", d: "豆包大模型 TTS 朗读摘要" },
    { n: "05", t: "一键导出", d: ".md / .json / .mp3" },
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
      x: 1.7, y: y + 0.05, w: 4, h: 0.4,
      fontSize: 18, fontFace: FONT_H, bold: true, color: TEXT, margin: 0,
    });
    s.addText(step.d, {
      x: 1.7, y: y + 0.42, w: 6, h: 0.35,
      fontSize: 12, fontFace: FONT_B, color: MUTED, margin: 0,
    });
  });

  addPlaceholder(s, 8.3, 2.2, 4.4, 4.3, "现场 demo screencast（兜底视频）");

  addBrand(s);
  addPageNumber(s, 3, 13);
}

// ============ P4 · 真实界面 ============
{
  const s = pres.addSlide();
  s.background = { color: BG };
  addTitle(s, "真实界面：列表页 + 详情页", "P4  ·  UI");

  // left: list page
  s.addText("列表页", {
    x: 0.6, y: 2.0, w: 6, h: 0.4,
    fontSize: 16, fontFace: FONT_H, bold: true, color: TEXT, margin: 0,
  });
  const listItems = [
    "🟢🟡🔴 Apple 风克制状态点",
    "实时任务条 · 搜索 · 5 状态过滤",
    "提交弹窗三 Tab：本地 / URL / YT-BB",
    "“+ GotIt” AI 炫彩渐变主按钮",
  ];
  s.addText(
    listItems.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < listItems.length - 1 } })),
    { x: 0.6, y: 2.5, w: 5.8, h: 1.6, fontSize: 13, fontFace: FONT_B, color: TEXT, paraSpaceAfter: 4 }
  );
  addPlaceholder(s, 0.6, 4.3, 5.9, 2.5, "列表页截图");

  // right: detail page
  s.addText("详情页（花时间最多的一页）", {
    x: 6.8, y: 2.0, w: 6, h: 0.4,
    fontSize: 16, fontFace: FONT_H, bold: true, color: TEXT, margin: 0,
  });
  const detailItems = [
    [{ text: "Hook 大字引用", options: { bold: true } }, { text: " — 30 字内一句话定位" }],
    [{ text: "Sticky 原音频播放器", options: { bold: true } }, { text: " — 滚动不消失，永远在顶" }],
    [{ text: "章节引用可点击", options: { bold: true } }, { text: " — 时间戳插值，点一下立即 seek + 自动播放" }],
    [{ text: "AI Digest 播放器", options: { bold: true } }, { text: " — 流动彩虹按钮，区别于原音频" }],
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
    x: 6.8, y: 2.5, w: 5.9, h: 1.6, fontSize: 13, fontFace: FONT_B, color: TEXT, paraSpaceAfter: 4,
  });
  addPlaceholder(s, 6.8, 4.3, 5.9, 2.5, "详情页 GIF：hook → 三幕 → 章节 → 跳播放");

  addBrand(s);
  addPageNumber(s, 4, 13);
}

// ============ P5 · 两套前端 ============
{
  const s = pres.addSlide();
  s.background = { color: BG };
  addTitle(s, "两套前端 · 视觉实验", "P5  ·  DUAL FRONTEND");

  const rows = [
    ["维度", "v1  frontend/", "v2  frontend-v2/"],
    ["端口", "5173", "5174"],
    ["样式", "纯 CSS + 渐变", "Tailwind + Apple Liquid Glass"],
    ["动效", "—", "framer-motion + Aceternity"],
    ["风格", "功能优先", "内容优先 + 克制配色"],
    ["定位", "当前主力", "A/B 视觉测试"],
  ];

  const tableData = rows.map((row, i) =>
    row.map((cell, j) => ({
      text: cell,
      options: {
        bold: i === 0,
        color: i === 0 ? "FFFFFF" : TEXT,
        fill: { color: i === 0 ? BG_DARK : (i % 2 === 0 ? ACCENT_SOFT : "FFFFFF") },
        fontSize: i === 0 ? 12 : 13,
        align: j === 0 ? "left" : "left",
        valign: "middle",
      },
    }))
  );

  s.addTable(tableData, {
    x: 0.6, y: 2.1, w: 7.4, colW: [1.6, 2.9, 2.9],
    rowH: 0.5,
    fontFace: FONT_B,
    border: { pt: 0.5, color: RULE },
  });

  // note card
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.6, y: 5.6, w: 7.4, h: 1.2,
    fill: { color: ACCENT_SOFT }, line: { type: "none" },
  });
  s.addText(
    [
      { text: "共享后端 · 同一 API client · 同一 WS 协议\n", options: { bold: true, breakLine: true, color: TEXT, fontSize: 14 } },
      { text: "make run-both  同时启 — 真实视觉决策对比，不是炫技", options: { color: MUTED, fontSize: 12 } },
    ],
    { x: 0.85, y: 5.65, w: 7.1, h: 1.1, fontFace: FONT_B, margin: 0, valign: "middle" }
  );

  addPlaceholder(s, 8.4, 2.1, 4.3, 4.7, "同一 episode：v1 vs v2 截图对比");

  addBrand(s);
  addPageNumber(s, 5, 13);
}

// ============ P6 · 系统架构 ============
{
  const s = pres.addSlide();
  s.background = { color: BG };
  addTitle(s, "系统架构", "P6  ·  ARCHITECTURE");

  // Frontend block
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

  // Frontend layer
  block(0.6, 2.0, 11.0, 1.4, "FRONTEND", [
    "v1  React 19 + 纯 CSS  · :5173        v2  React 19 + Tailwind + framer-motion + Aceternity  · :5174",
  ], "FFFFFF");

  // arrow between frontend and backend
  s.addText("↓   HTTP /api    ·    WS /api/ws/jobs   ↓", {
    x: 0.6, y: 3.45, w: 11.0, h: 0.3,
    fontSize: 11, fontFace: "Menlo", color: MUTED, italic: true, align: "center", margin: 0,
  });

  // Backend
  block(0.6, 3.85, 11.0, 1.9, "FASTAPI  ·  uvicorn :8000", [
    "Pipeline runner（asyncio）",
    "•  8 stages · tenacity 重试 · stage_progress → SQLite",
    "•  event bus → WebSocket 广播",
  ], ACCENT_SOFT);

  // External services
  block(0.6, 5.85, 11.0, 1.0, "外部服务（详见 P8 技术栈）", [
    "yt-dlp / ffmpeg    ·    Doubao ASR / TTS    ·    DeepSeek LLM",
  ], "FFFFFF");

  addBrand(s);
  addPageNumber(s, 6, 13);
}

// ============ P7 · Pipeline + 8 stages ============
{
  const s = pres.addSlide();
  s.background = { color: BG };
  addTitle(s, "端到端 Pipeline 与 8 个 Stage", "P7  ·  PIPELINE");

  // Flow strip across the top
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

  // tts callout
  s.addText("+ tts（独立子流程，按需触发，不阻塞主流程 — 详见 P9）", {
    x: 0.6, y: 3.15, w: 12.1, h: 0.3,
    fontSize: 11, fontFace: FONT_B, color: MUTED, italic: true, align: "center", margin: 0,
  });

  // Three pillars below
  const pillars = [
    { t: "独立 Retry", d: "tenacity 指数退避 · 单 stage 失败不重跑整条作业" },
    { t: "进度落盘", d: "stage_progress 写入 SQLite · 进程重启可继续" },
    { t: "实时事件", d: "/api/ws/jobs 推送所有前端 · 单独点 Retry" },
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

  // Highlight bug ref
  s.addText("⚠ stage 6 quote_verify 自研：NFKC + 子串匹配 + 段内字符比例插值时间戳 — 详见 P10 bug #5", {
    x: 0.6, y: 5.6, w: 12.1, h: 0.4,
    fontSize: 12, fontFace: FONT_B, color: WARN, italic: true, margin: 0,
  });

  addPlaceholder(s, 0.6, 6.15, 12.1, 0.7, "可选：流程图截图 / Excalidraw 渲染图");

  addBrand(s);
  addPageNumber(s, 7, 13);
}

// ============ P8 · 技术栈 ============
{
  const s = pres.addSlide();
  s.background = { color: BG };
  addTitle(s, "技术栈与选型理由", "P8  ·  STACK");

  const headerRow = ["层", "选型", "选它的理由"].map((t) => ({
    text: t,
    options: { bold: true, color: "FFFFFF", fill: { color: BG_DARK }, fontSize: 12, valign: "middle" },
  }));

  const dataRows = [
    ["后端", "FastAPI + SQLAlchemy 2 + Alembic + Pydantic 2", "类型严格 · async 友好 · 迁移可控"],
    ["任务编排", "asyncio + tenacity", "不引入额外队列，本地工具够用"],
    ["前端 v1", "React 19 + Vite + 纯 CSS", "功能完整 · 最小依赖"],
    ["前端 v2", "React 19 + Tailwind + framer-motion + Aceternity", "视觉对比实验"],
    ["ASR", "豆包大模型 2.0（流式 / 录音文件）", "中文识别质量高 · 字数计费"],
    ["LLM", "DeepSeek（默认）· Qwen · Anthropic", "性价比 + 多供应商抽象（见 P9）"],
    ["TTS", "豆包 v1 标准 · 豆包大模型 2.0（WS）", "双轨可回退"],
    ["下载", "yt-dlp + ffmpeg", "YouTube / Bilibili 通吃"],
    ["测试", "pytest + Vitest · domain ≥ 80%", "见 P12"],
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
    x: 0.6, y: 2.0, w: 12.1, colW: [1.6, 6.0, 4.5],
    rowH: 0.45,
    fontFace: FONT_B,
    border: { pt: 0.5, color: RULE },
  });

  addBrand(s);
  addPageNumber(s, 8, 13);
}

// ============ P9 · 多供应商抽象 + BigTTS 协议 ============
{
  const s = pres.addSlide();
  s.background = { color: BG };
  addTitle(s, "多供应商抽象 + 一处刚啃下来的硬骨头", "P9  ·  PROTOCOL");

  // Left: abstraction
  s.addText("抽象层", {
    x: 0.6, y: 2.0, w: 5.5, h: 0.4,
    fontSize: 16, fontFace: FONT_H, bold: true, color: TEXT, margin: 0,
  });
  const absItems = [
    "ASR：doubao / openai_whisper / qwen — 一个 env 切换",
    "LLM：deepseek / qwen / anthropic — 同上",
    "TTS：doubao legacy / bigmodel / qwen — 同上",
    "create_xxx_client() 工厂 + Protocol 接口，调用方零感知",
  ];
  s.addText(
    absItems.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < absItems.length - 1 } })),
    { x: 0.6, y: 2.5, w: 5.7, h: 2.2, fontSize: 13, fontFace: FONT_B, color: TEXT, paraSpaceAfter: 4 }
  );

  // Bottom-left: what I did
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.6, y: 5.0, w: 5.7, h: 1.85,
    fill: { color: ACCENT_SOFT }, line: { type: "none" },
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.6, y: 5.0, w: 0.08, h: 1.85,
    fill: { color: ACCENT }, line: { type: "none" },
  });
  s.addText("我做了什么", {
    x: 0.85, y: 5.1, w: 5.4, h: 0.3,
    fontSize: 11, fontFace: FONT_H, bold: true, color: ACCENT, charSpacing: 1, margin: 0,
  });
  s.addText(
    [
      { text: "把官方 demo 抄进 _doubao_bigtts_protocol.py，X-Api-App-Key → X-Api-App-Id", options: { bullet: true, breakLine: true } },
      { text: "thread + asyncio.run 把 async WS 桥到同步 stage", options: { bullet: true, breakLine: true } },
      { text: "失败时把 server 响应前 500 字直接写进 job error", options: { bullet: true } },
    ],
    { x: 0.85, y: 5.4, w: 5.4, h: 1.4, fontSize: 11, fontFace: FONT_B, color: TEXT, paraSpaceAfter: 2 }
  );

  // Right: protocol
  s.addText("豆包大模型 TTS 2.0 协议", {
    x: 6.6, y: 2.0, w: 6.2, h: 0.4,
    fontSize: 16, fontFace: FONT_H, bold: true, color: TEXT, margin: 0,
  });
  s.addText("没有 HTTP 一次性接口，只有 WebSocket 二进制流：", {
    x: 6.6, y: 2.45, w: 6.2, h: 0.3,
    fontSize: 12, fontFace: FONT_B, color: MUTED, margin: 0,
  });

  // binary frame box
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

  // event flow
  s.addText("事件流", {
    x: 6.6, y: 4.7, w: 6.2, h: 0.3,
    fontSize: 11, fontFace: FONT_H, bold: true, color: ACCENT, charSpacing: 1, margin: 0,
  });
  s.addText("StartConnection → StartSession → TaskRequest → FinishSession → SessionFinished", {
    x: 6.6, y: 5.0, w: 6.2, h: 0.4,
    fontSize: 11, fontFace: "Menlo", color: TEXT, margin: 0,
  });
  s.addText("音频通过 AudioOnlyServer 帧 chunked 推回", {
    x: 6.6, y: 5.4, w: 6.2, h: 0.3,
    fontSize: 11, fontFace: FONT_B, color: MUTED, italic: true, margin: 0,
  });

  s.addText("“不是调一个现成 pip 包 — 是自己实现的协议层”", {
    x: 6.6, y: 6.0, w: 6.2, h: 0.6,
    fontSize: 13, fontFace: FONT_B, color: TEXT, italic: true, bold: true, margin: 0,
  });

  addBrand(s);
  addPageNumber(s, 9, 13);
}

// ============ P10 · Hard-Won Bugs ============
{
  const s = pres.addSlide();
  s.background = { color: BG };
  addTitle(s, "自己排到的 Hard-Won Bugs", "P10  ·  最重要的一页");

  const header = ["#", "现象", "根因", "修法 / 学到"].map((t) => ({
    text: t,
    options: { bold: true, color: "FFFFFF", fill: { color: BG_DARK }, fontSize: 11, valign: "middle" },
  }));

  const bugs = [
    ["1", "TTS 一直 401", "豆包要求 Authorization: Bearer;<token>（分号不是空格）", "1 行修复 · 不是所有 API 都遵守 OAuth"],
    ["2", "TTS 400 exceed max len", "v1 单次文本 ≤ 1024 字节", "_split_text_for_tts 按 utf-8 切句 · 协议藏在脚注"],
    ["3 ⚠", "BigTTS concurrency exceeded", "resource_id 用了内部数字编号；正确值是 seed-tts-2.0", "改 env · 错误信息不能尽信", true],
    ["4", "digest.mp3 为空且无错误", "language=mixed 被路由到英文音色合中文 → 静默丢弃", "_voice_type 把 mixed 归类到中文 · 静默失败比报错可怕"],
    ["5 ⚠", "多个 quote 时间戳一样", "旧逻辑返回 segment 起点，没插值", "改 verify_against_segments 按字符位置插值 · 数据要看不只是 schema", true],
    ["6", "Retry 时 worker 崩溃", "quote_verify 重跑撞 (chapter_id, idx) unique 约束", "delete_for_chapters 前置清理 + 单测 · 幂等是基本素养"],
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
    "“这 6 个没有一个是 AI 一上来就能告诉你的 — 都是读响应、读协议、读 DB 数据查出来的。”",
    {
      x: 0.6, y: 6.55, w: 12.1, h: 0.4,
      fontSize: 12, fontFace: FONT_B, color: TEXT, italic: true, bold: true, margin: 0,
    }
  );

  addBrand(s);
  addPageNumber(s, 10, 13);
}

// ============ P11 · SDD ============
{
  const s = pres.addSlide();
  s.background = { color: BG };
  addTitle(s, "SDD：先写规范再写代码", "P11  ·  SPEC-DRIVEN");

  // Left: file tree
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.6, y: 2.0, w: 6.2, h: 4.8,
    fill: { color: BG_DARK }, line: { type: "none" },
  });
  s.addText(
    [
      { text: "specs/001-podcast-summary/\n", options: { bold: true, color: "FFFFFF", breakLine: true } },
      { text: "├── spec.md            ", options: { color: "FF9F0A" } },
      { text: "功能规格（用户故事 + Acceptance）\n", options: { color: "8E8E93", breakLine: true } },
      { text: "├── plan.md            ", options: { color: "FF9F0A" } },
      { text: "实施计划 + 复杂度跟踪\n", options: { color: "8E8E93", breakLine: true } },
      { text: "├── research.md        ", options: { color: "FF9F0A" } },
      { text: "选型权衡（≥2 候选）\n", options: { color: "8E8E93", breakLine: true } },
      { text: "├── data-model.md      ", options: { color: "FF9F0A" } },
      { text: "实体关系\n", options: { color: "8E8E93", breakLine: true } },
      { text: "├── tasks.md           ", options: { color: "FF9F0A" } },
      { text: "依赖排序的任务分解\n", options: { color: "8E8E93", breakLine: true } },
      { text: "├── quickstart.md      ", options: { color: "FF9F0A" } },
      { text: "上手指南\n", options: { color: "8E8E93", breakLine: true } },
      { text: "├── ui-brief.md        ", options: { color: "FF9F0A" } },
      { text: "UI 设计简报\n", options: { color: "8E8E93", breakLine: true } },
      { text: "├── contracts/\n", options: { color: "FFFFFF", breakLine: true } },
      { text: "│   ├── http-api.md          ", options: { color: "FF9F0A" } },
      { text: "REST 契约\n", options: { color: "8E8E93", breakLine: true } },
      { text: "│   ├── job-events.md        ", options: { color: "FF9F0A" } },
      { text: "WS 事件 schema\n", options: { color: "8E8E93", breakLine: true } },
      { text: "│   └── episode-output.schema.json\n", options: { color: "FF9F0A", breakLine: true } },
      { text: "└── design/...         ", options: { color: "FF9F0A" } },
      { text: "UI 设计稿", options: { color: "8E8E93" } },
    ],
    { x: 0.85, y: 2.15, w: 5.9, h: 4.6, fontSize: 11, fontFace: "Menlo", margin: 0 }
  );

  // Right: constitution
  s.addText("constitution.md  v1.0.0", {
    x: 7.2, y: 2.0, w: 5.5, h: 0.4,
    fontSize: 16, fontFace: FONT_H, bold: true, color: TEXT, margin: 0,
  });
  s.addText("5 条不可妥协的原则", {
    x: 7.2, y: 2.45, w: 5.5, h: 0.3,
    fontSize: 12, fontFace: FONT_B, color: MUTED, italic: true, margin: 0,
  });

  const principles = [
    { n: "1", t: "英文交付", d: "文档 / 注释 / commit" },
    { n: "2", t: "Python 3.11+", d: "主栈统一" },
    { n: "3", t: "Domain ≥ 80% 覆盖", d: "NON-NEGOTIABLE" },
    { n: "4", t: "配置外置", d: "env / .env，不硬编码 secret" },
    { n: "5", t: "Prompt 集中版本化", d: "prompts/ 目录，带版本号" },
  ];
  principles.forEach((p, i) => {
    const y = 2.95 + i * 0.75;
    s.addShape(pres.shapes.OVAL, {
      x: 7.2, y, w: 0.45, h: 0.45,
      fill: { color: ACCENT }, line: { type: "none" },
    });
    s.addText(p.n, {
      x: 7.2, y, w: 0.45, h: 0.45,
      fontSize: 14, fontFace: FONT_H, bold: true, color: "FFFFFF",
      align: "center", valign: "middle", margin: 0,
    });
    const isNN = p.d === "NON-NEGOTIABLE";
    s.addText(
      [
        { text: p.t, options: { bold: true, color: TEXT, fontSize: 13 } },
        { text: "   " + p.d, options: { color: isNN ? WARN : MUTED, fontSize: 11, bold: isNN } },
      ],
      {
        x: 7.8, y: y + 0.02, w: 4.9, h: 0.45,
        fontFace: FONT_B, margin: 0, valign: "middle",
      }
    );
  });

  addBrand(s);
  addPageNumber(s, 11, 13);
}

// ============ P12 · 测试 ============
{
  const s = pres.addSlide();
  s.background = { color: BG };
  addTitle(s, "测试 + 质量门", "P12  ·  TESTING");

  // Left: stats
  const stats = [
    { n: "12", l: "unit test 文件", d: "解析 · 分段 · quote 校验 · 提示装配" },
    { n: "8", l: "integration 文件", d: "流水线 stage · 客户端 mock · 端到端" },
    { n: "80%", l: "覆盖率硬门", d: "domain 模块 line + branch · CI 阻塞" },
  ];
  stats.forEach((st, i) => {
    const y = 2.0 + i * 1.5;
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0.6, y, w: 5.8, h: 1.3,
      fill: { color: ACCENT_SOFT }, line: { type: "none" },
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0.6, y, w: 0.08, h: 1.3,
      fill: { color: ACCENT }, line: { type: "none" },
    });
    s.addText(st.n, {
      x: 0.85, y: y + 0.15, w: 1.7, h: 1.0,
      fontSize: 48, fontFace: FONT_H, bold: true, color: ACCENT,
      valign: "middle", margin: 0,
    });
    s.addText(st.l, {
      x: 2.55, y: y + 0.2, w: 3.7, h: 0.45,
      fontSize: 16, fontFace: FONT_H, bold: true, color: TEXT, margin: 0,
    });
    s.addText(st.d, {
      x: 2.55, y: y + 0.7, w: 3.7, h: 0.5,
      fontSize: 11, fontFace: FONT_B, color: MUTED, margin: 0,
    });
  });

  // Right: pyproject snippet + notes
  s.addShape(pres.shapes.RECTANGLE, {
    x: 6.7, y: 2.0, w: 6.0, h: 1.5,
    fill: { color: BG_DARK }, line: { type: "none" },
  });
  s.addText(
    [
      { text: "backend/pyproject.toml\n", options: { color: "8E8E93", breakLine: true } },
      { text: "  --cov=backend/src/podsum/domain\n", options: { color: "FFFFFF", breakLine: true } },
      { text: "  --cov-fail-under=80   ", options: { color: "FFFFFF" } },
      { text: "← CI 硬门", options: { color: "FF9F0A", bold: true } },
    ],
    { x: 6.85, y: 2.15, w: 5.8, h: 1.3, fontSize: 12, fontFace: "Menlo", margin: 0 }
  );

  s.addText("亮点", {
    x: 6.7, y: 3.7, w: 6.0, h: 0.3,
    fontSize: 13, fontFace: FONT_H, bold: true, color: ACCENT, charSpacing: 1, margin: 0,
  });
  s.addText(
    [
      { text: "domain 纯函数化 — 测试不启 DB、不 mock 外部 API", options: { bullet: true, breakLine: true } },
      { text: "P10 #5 修复同步加 test_quote_inside_long_merged_segment_is_interpolated", options: { bullet: true, breakLine: true } },
      { text: "frontend 用 Vitest + jsdom", options: { bullet: true } },
    ],
    { x: 6.7, y: 4.05, w: 6.0, h: 2.0, fontSize: 12, fontFace: FONT_B, color: TEXT, paraSpaceAfter: 4 }
  );

  s.addShape(pres.shapes.RECTANGLE, {
    x: 6.7, y: 6.0, w: 6.0, h: 0.85,
    fill: { color: ACCENT_SOFT }, line: { type: "none" },
  });
  s.addText("“修一个 bug 必带一个测试 — 不是 KPI，是给自己留护栏。”", {
    x: 6.85, y: 6.05, w: 5.8, h: 0.8,
    fontSize: 12, fontFace: FONT_B, color: TEXT, italic: true, bold: true, valign: "middle", margin: 0,
  });

  addBrand(s);
  addPageNumber(s, 12, 13);
}

// ============ P13 · 收尾 ============
{
  const s = pres.addSlide();
  s.background = { color: BG_DARK };

  s.addText("THANKS", {
    x: 0.8, y: 0.7, w: 8, h: 0.5,
    fontSize: 12, fontFace: FONT_H, color: ACCENT, bold: true, charSpacing: 3, margin: 0,
  });

  s.addText("AI 是工具，不是答案。", {
    x: 0.8, y: 1.4, w: 12, h: 1.0,
    fontSize: 44, fontFace: FONT_H, bold: true, color: "FFFFFF", margin: 0,
  });
  s.addText("这套东西是查出来的、设计出来的、写出来的。", {
    x: 0.8, y: 2.4, w: 12, h: 0.7,
    fontSize: 22, fontFace: FONT_H, color: "8E8E93", margin: 0,
  });

  // Three signals
  const signals = [
    { t: "完整 + 实用", d: "下载 · ASR · 摘要 · 章节 · 引用 · 实体 · TTS · 导出 — 每天在用" },
    { t: "技术力", d: "8 stage pipeline · BigTTS 二进制协议 · 多供应商抽象 · WS 实时事件 · 双前端" },
    { t: "人投入大", d: "6 个 hard-won bug · 12 份 spec 文档 · domain 80% 覆盖硬门" },
  ];
  signals.forEach((sig, i) => {
    const y = 3.8 + i * 0.85;
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0.8, y, w: 0.08, h: 0.6,
      fill: { color: ACCENT }, line: { type: "none" },
    });
    s.addText(sig.t, {
      x: 1.05, y: y - 0.05, w: 3.5, h: 0.45,
      fontSize: 18, fontFace: FONT_H, bold: true, color: "FFFFFF", margin: 0,
    });
    s.addText(sig.d, {
      x: 4.55, y: y, w: 8.2, h: 0.55,
      fontSize: 13, fontFace: FONT_B, color: "8E8E93", margin: 0, valign: "middle",
    });
  });

  s.addText("Q & A", {
    x: 0.8, y: 6.7, w: 12, h: 0.5,
    fontSize: 16, fontFace: FONT_H, color: "FFFFFF", bold: true, charSpacing: 4, margin: 0,
  });

  addPageNumber(s, 13, 13, true);
}

pres.writeFile({ fileName: "/Users/zhangzuhao/code-project/Podcast-summary/presentation/GotIt-Podsum-deck.pptx" })
  .then((name) => console.log("Wrote: " + name));
