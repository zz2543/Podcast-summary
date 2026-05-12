import { C, bg, footer, glass, kicker, page, rect, text, title } from "./common.mjs";

export async function slide06(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Prompt & Cognition");
  page(slide, ctx, 5);
  title(slide, ctx, "提示词设计服务人的理解流程：先判断价值，再深入复盘，再回到证据。", 68, 86, 880, 98, 32);

  glass(slide, ctx, 78, 228, 500, 320);
  text(slide, ctx, "Quick browse layer", 110, 258, 220, 24, { size: 20, bold: true, display: true });
  const quick = [
    ["Background", "先交代背景，降低理解门槛。"],
    ["Core argument", "提炼节目真正的核心主张。"],
    ["Conclusion", "给出收束判断，帮助决定是否深入。"],
  ];
  for (let i = 0; i < quick.length; i += 1) {
    const y = 320 + i * 66;
    rect(slide, ctx, 112, y, 32, 32, i === 1 ? C.info : C.elev, { geometry: "ellipse", stroke: "#00000000" });
    text(slide, ctx, String(i + 1), 112, y + 8, 32, 12, { size: 11, bold: true, color: i === 1 ? "#FFFFFF" : C.text, align: "center" });
    text(slide, ctx, quick[i][0], 164, y + 2, 180, 16, { size: 14, bold: true });
    text(slide, ctx, quick[i][1], 164, y + 24, 310, 18, { size: 11.5, color: C.muted });
  }

  glass(slide, ctx, 644, 228, 500, 320, { fill: "#101014", stroke: "#25252A" });
  text(slide, ctx, "Deep review layer", 676, 258, 220, 24, { size: 20, bold: true, display: true, color: "#FFFFFF" });
  const deep = [
    ["Chapter outline", "把长音频拆成可浏览的时间段。"],
    ["Key points", "每章保留原始顺序，便于复盘。"],
    ["Verified quotes", "quote 必须逐字命中 transcript。"],
    ["Entity list", "人物、书、产品被集中整理。"],
  ];
  for (let i = 0; i < deep.length; i += 1) {
    const y = 318 + i * 48;
    rect(slide, ctx, 678, y, 14, 14, [C.pink, C.purple, C.mint, C.yellow][i], { geometry: "ellipse", stroke: "#00000000" });
    text(slide, ctx, deep[i][0], 712, y - 2, 150, 16, { size: 13, bold: true, color: "#FFFFFF" });
    text(slide, ctx, deep[i][1], 876, y - 2, 220, 16, { size: 11, color: "#D9D9E2" });
  }
  text(slide, ctx, "快速浏览回答“值不值得看”；章节总结回答“重点在哪里”；quote 回答“原文是不是这样说”。", 124, 586, 960, 28, { size: 16, color: C.muted, align: "center" });
  footer(slide, ctx);
  return slide;
}
