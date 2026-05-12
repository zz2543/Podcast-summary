import { C, bg, footer, glass, icon, iridescentButton, kicker, miniWindow, mockAudioBars, pill, subtitle, text, title } from "./common.mjs";

export async function slide01(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Podcast Summary System");
  title(slide, ctx, "从播客消费到知识沉淀的完整工作流网站", 68, 92, 610, 150, 40);
  subtitle(
    slide,
    ctx,
    "不是一次性的 AI 总结 demo，而是围绕真实学习场景设计的本地 Web 产品：输入、理解、验证、导出、复用。",
    70,
    254,
    560,
    72
  );
  pill(slide, ctx, "ASR + LLM + TTS", 70, 350, 142);
  pill(slide, ctx, "Quote verification", 222, 350, 158);
  pill(slide, ctx, "Obsidian-ready", 390, 350, 140);

  miniWindow(slide, ctx, 740, 74, 430, 520);
  text(slide, ctx, "Podsum", 766, 84, 70, 16, { size: 12, bold: true, display: true });
  text(slide, ctx, "v2", 842, 88, 20, 10, { size: 7, color: C.subtle });
  pill(slide, ctx, "Live", 1084, 78, 56, { fill: "#EAF8EF", color: "#248A48", stroke: "#CFEBD8" });

  glass(slide, ctx, 768, 142, 350, 86, { fill: C.elev });
  text(slide, ctx, "Hook hero", 790, 162, 120, 16, { size: 10, color: C.subtle, bold: true });
  text(slide, ctx, "How one long interview becomes a reusable learning asset", 790, 184, 292, 24, { size: 14, bold: true });

  glass(slide, ctx, 768, 254, 156, 118);
  text(slide, ctx, "Background", 790, 276, 110, 16, { size: 11, bold: true });
  text(slide, ctx, "Context before detail, so users know what problem the episode answers.", 790, 302, 106, 42, { size: 9.5, color: C.muted });
  glass(slide, ctx, 944, 254, 156, 118);
  text(slide, ctx, "Core argument", 966, 276, 110, 16, { size: 11, bold: true });
  text(slide, ctx, "The central claim is separated from supporting details.", 966, 302, 104, 42, { size: 9.5, color: C.muted });

  glass(slide, ctx, 768, 398, 350, 88);
  await icon(slide, ctx, "Play", 790, 424, 20, C.info);
  text(slide, ctx, "14:32 verified quote", 820, 426, 150, 14, { size: 11, bold: true });
  text(slide, ctx, "Click quote chips to jump back to the original audio evidence.", 790, 452, 260, 18, { size: 9.5, color: C.muted });
  mockAudioBars(slide, ctx, 970, 420);

  iridescentButton(slide, ctx, "Generate audio digest", 768, 516, 178);
  pill(slide, ctx, "Markdown", 962, 520, 86);
  pill(slide, ctx, "JSON", 1056, 520, 58);
  footer(slide, ctx);
  return slide;
}
