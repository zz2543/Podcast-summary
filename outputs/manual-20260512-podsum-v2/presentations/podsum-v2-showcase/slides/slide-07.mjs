import { C, bg, footer, glass, icon, kicker, page, rect, text, title } from "./common.mjs";

export async function slide07(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Knowledge Workflow");
  page(slide, ctx, 6);
  title(slide, ctx, "Markdown 导出把播客接入 Obsidian，完成知识效率闭环。", 68, 86, 820, 82, 34);
  text(slide, ctx, "这里不是“可以下载文件”这么简单，而是把音频内容变成可搜索、可引用、可复习、可写作的知识资产。", 70, 178, 850, 40, { size: 15.5, color: C.muted });

  const cards = [
    ["Podcast", "原始音频、URL 或 YouTube 长内容。", "Podcast"],
    ["Structured summary", "hook、三段式摘要、章节、quote、实体。", "FileText"],
    ["Markdown export", "保留标题层级、要点、引用和时间戳。", "FileDown"],
    ["Obsidian vault", "进入笔记库，支持复习、引用和写作。", "Network"],
  ];
  for (let i = 0; i < cards.length; i += 1) {
    const x = 86 + i * 282;
    glass(slide, ctx, x, 294, 226, 190);
    await icon(slide, ctx, cards[i][2], x + 24, 324, 30, [C.info, C.purple, C.mint, C.text][i]);
    text(slide, ctx, cards[i][0], x + 24, 374, 170, 24, { size: 18, bold: true, display: true });
    text(slide, ctx, cards[i][1], x + 24, 414, 170, 44, { size: 12.5, color: C.muted });
    if (i < cards.length - 1) {
      rect(slide, ctx, x + 236, 388, 34, 2, "#BFC5D1", { geometry: "rect" });
      rect(slide, ctx, x + 266, 384, 8, 10, "#BFC5D1", { geometry: "rect" });
    }
  }

  glass(slide, ctx, 148, 548, 984, 56, { fill: C.elev });
  text(slide, ctx, "展示话术", 172, 568, 100, 14, { size: 11, bold: true, color: C.subtle });
  text(slide, ctx, "我们把播客从一次性消费内容，转化成可以长期复用的学习资产。", 292, 566, 650, 18, { size: 15, bold: true });
  footer(slide, ctx);
  return slide;
}
