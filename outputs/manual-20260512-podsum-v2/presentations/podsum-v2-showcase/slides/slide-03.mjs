import { C, bg, footer, glass, icon, iridescentButton, kicker, mockAudioBars, page, pill, rect, text, title } from "./common.mjs";

export async function slide03(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "V2 Product Experience");
  page(slide, ctx, 2);
  title(slide, ctx, "前端参考 V2：浅色玻璃质感、bento 卡片和明确的交互状态。", 68, 86, 790, 104, 32);

  glass(slide, ctx, 82, 222, 482, 336);
  text(slide, ctx, "Library", 110, 248, 120, 20, { size: 16, bold: true, display: true });
  pill(slide, ctx, "Live", 492, 246, 48, { fill: "#EAF8EF", color: "#248A48", stroke: "#CFEBD8" });
  glass(slide, ctx, 110, 292, 190, 146, { fill: C.elev });
  text(slide, ctx, "Active job", 132, 314, 110, 14, { size: 10, bold: true, color: C.subtle });
  text(slide, ctx, "Transcribing episode", 132, 340, 132, 18, { size: 13, bold: true });
  rect(slide, ctx, 132, 382, 122, 8, "#E5E5EA");
  rect(slide, ctx, 132, 382, 82, 8, C.info);
  glass(slide, ctx, 322, 292, 190, 146);
  text(slide, ctx, "Bento episode card", 344, 314, 116, 14, { size: 10, bold: true, color: C.subtle });
  text(slide, ctx, "Hook preview + status", 344, 340, 130, 18, { size: 13, bold: true });
  text(slide, ctx, "Done", 344, 382, 62, 16, { size: 11, color: C.ok, bold: true });

  glass(slide, ctx, 634, 222, 472, 336);
  text(slide, ctx, "Detail", 662, 248, 120, 20, { size: 16, bold: true, display: true });
  iridescentButton(slide, ctx, "Generate audio digest", 862, 244, 178);
  glass(slide, ctx, 662, 300, 384, 70, { fill: C.elev });
  text(slide, ctx, "\"A long episode becomes a structured learning asset.\"", 686, 322, 332, 24, { size: 14, bold: true });
  glass(slide, ctx, 662, 396, 178, 108);
  text(slide, ctx, "Three-act panel", 684, 418, 120, 14, { size: 11, bold: true });
  text(slide, ctx, "Background\nCore argument\nConclusion", 684, 444, 130, 44, { size: 10.5, color: C.muted });
  glass(slide, ctx, 862, 396, 184, 108);
  await icon(slide, ctx, "Play", 884, 422, 18, C.info);
  text(slide, ctx, "Quote chip", 912, 423, 88, 14, { size: 11, bold: true });
  mockAudioBars(slide, ctx, 884, 454);

  const notes = [
    ["Motion", "Framer Motion 进入动画让摘要与章节逐步出现。"],
    ["Feedback", "Live 状态、进度条、toast、按钮 disabled 都表达系统状态。"],
    ["Utility", "浮动 dock 提供 Markdown、JSON、音频、重试和删除。"],
  ];
  for (let i = 0; i < notes.length; i += 1) {
    const y = 228 + i * 84;
    text(slide, ctx, notes[i][0], 1124, y, 90, 16, { size: 11, bold: true, color: C.info });
    text(slide, ctx, notes[i][1], 1124, y + 24, 96, 42, { size: 10.2, color: C.muted });
  }
  footer(slide, ctx);
  return slide;
}
