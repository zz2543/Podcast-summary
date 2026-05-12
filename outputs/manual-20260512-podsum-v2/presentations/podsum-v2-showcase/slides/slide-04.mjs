import { C, bg, footer, glass, icon, kicker, page, rect, text, title } from "./common.mjs";

export async function slide04(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Core Workflow");
  page(slide, ctx, 3);
  title(slide, ctx, "一条端到端流程：从音频输入到 Obsidian 知识库。", 68, 86, 780, 82, 34);

  const steps = [
    ["Input", "Audio / URL / YouTube", "Upload"],
    ["Acquire", "fetch, validate, normalize", "Download"],
    ["ASR", "timestamped transcript", "AudioWaveform"],
    ["Prompt", "structured summary", "Sparkles"],
    ["Browse", "hook + three-act", "ScanText"],
    ["Review", "chapters + quotes", "ListTree"],
    ["Export", "MD / JSON / digest", "FileDown"],
    ["Knowledge", "Obsidian / notes", "Brain"],
  ];
  for (let i = 0; i < steps.length; i += 1) {
    const row = i < 4 ? 0 : 1;
    const col = i % 4;
    const x = 76 + col * 288;
    const y = 238 + row * 178;
    glass(slide, ctx, x, y, 226, 116, { fill: i === 7 ? "#F0F8FF" : C.surface });
    await icon(slide, ctx, steps[i][2], x + 18, y + 22, 22, i === 7 ? C.info : C.text);
    text(slide, ctx, steps[i][0], x + 54, y + 22, 132, 18, { size: 15, bold: true, display: true });
    text(slide, ctx, steps[i][1], x + 18, y + 62, 182, 32, { size: 11.5, color: C.muted });
    if (col < 3) {
      rect(slide, ctx, x + 232, y + 58, 42, 2, "#BFC5D1", { geometry: "rect" });
      rect(slide, ctx, x + 270, y + 54, 8, 10, "#BFC5D1", { geometry: "rect" });
    }
  }
  rect(slide, ctx, 1138, 354, 2, 58, "#BFC5D1", { geometry: "rect" });
  rect(slide, ctx, 1104, 412, 36, 2, "#BFC5D1", { geometry: "rect" });
  text(
    slide,
    ctx,
    "这条链路让展示重点从“AI 能总结”升级为“网站能完成真实学习任务”。",
    92,
    590,
    820,
    28,
    { size: 16, color: C.muted }
  );
  footer(slide, ctx);
  return slide;
}
