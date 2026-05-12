import { C, bg, footer, glass, icon, kicker, page, text, title } from "./common.mjs";

export async function slide02(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Problem");
  page(slide, ctx, 1);
  title(slide, ctx, "长播客的痛点不是听不完，而是筛选、复盘、沉淀都很低效。", 68, 88, 840, 112, 34);
  text(
    slide,
    ctx,
    "目标是把 60-90 分钟的音频，转化成可以快速判断、可信复盘、长期复用的学习材料。",
    70,
    204,
    720,
    44,
    { size: 16, color: C.muted }
  );

  const cards = [
    ["快速理解", "先用 hook 与三段式摘要判断这期是否值得深入。", "Scan"],
    ["可信复盘", "通过章节、原文 quote 和时间戳回到证据本身。", "Verify"],
    ["知识沉淀", "导出 Markdown/JSON，进入 Obsidian 等笔记系统。", "Reuse"],
  ];
  for (let i = 0; i < cards.length; i += 1) {
    const x = 92 + i * 365;
    glass(slide, ctx, x, 318, 316, 210);
    await icon(slide, ctx, i === 0 ? "Search" : i === 1 ? "BadgeCheck" : "BookOpen", x + 24, 342, 30, i === 0 ? C.info : i === 1 ? C.ok : C.purple);
    text(slide, ctx, cards[i][0], x + 24, 388, 220, 28, { size: 23, bold: true, display: true });
    text(slide, ctx, cards[i][1], x + 24, 430, 250, 48, { size: 14, color: C.muted });
    text(slide, ctx, cards[i][2], x + 24, 492, 120, 18, { size: 11, bold: true, color: C.subtle });
  }
  footer(slide, ctx);
  return slide;
}
