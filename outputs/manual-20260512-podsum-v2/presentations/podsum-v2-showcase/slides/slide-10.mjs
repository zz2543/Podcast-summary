import { C, bg, footer, glass, iridescentButton, kicker, mockAudioBars, pill, text, title } from "./common.mjs";

export async function slide10(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Positioning");
  title(slide, ctx, "这不是普通 AI 播客总结器，而是面向真实学习场景的播客知识工作流工具。", 68, 92, 760, 134, 36);
  text(
    slide,
    ctx,
    "它打通了音频输入、AI 理解、结构化复盘、可信引用、音频摘要和 Markdown 知识沉淀，让播客内容真正变成可以复用的学习资产。",
    70,
    250,
    700,
    70,
    { size: 17, color: C.muted }
  );
  pill(slide, ctx, "Usable website", 70, 356, 128);
  pill(slide, ctx, "Cognitive structure", 212, 356, 154);
  pill(slide, ctx, "Engineering proof", 380, 356, 146);
  pill(slide, ctx, "Knowledge workflow", 540, 356, 158);

  glass(slide, ctx, 842, 118, 314, 420, { fill: "#101014", stroke: "#22222A" });
  text(slide, ctx, "Final message", 872, 154, 160, 16, { size: 11, bold: true, color: "#8D8D96" });
  text(
    slide,
    ctx,
    "从“听完一集播客”到“得到可验证、可复盘、可沉淀的知识材料”。",
    872,
    202,
    240,
    142,
    { size: 25, bold: true, display: true, color: "#FFFFFF" }
  );
  mockAudioBars(slide, ctx, 878, 386);
  iridescentButton(slide, ctx, "Generate digest", 872, 470, 166);
  text(slide, ctx, "Markdown → Obsidian", 872, 514, 176, 16, { size: 12, color: "#D9D9E2", bold: true });
  footer(slide, ctx);
  return slide;
}
