import { C, bg, footer, glass, icon, kicker, page, rect, text, title } from "./common.mjs";

export async function slide05(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Feature Breakdown");
  page(slide, ctx, 4);
  title(slide, ctx, "功能拆分按用户路径组织，而不是按技术名词堆叠。", 68, 86, 820, 82, 34);

  const rows = [
    ["输入层", "本地音频、音频 URL、YouTube、批量提交。", "Local / URL / YouTube", "Upload"],
    ["AI 处理层", "ASR 转写、LLM 总结、TTS 音频摘要。", "ASR / LLM / TTS", "Cpu"],
    ["认知结构层", "快速浏览、章节复盘、可信引用。", "Browse → Review → Verify", "Layers"],
    ["交互体验层", "V2 动效、Live 状态、章节展开、quote 跳转。", "Motion / Status / Seek", "MousePointerClick"],
    ["知识沉淀层", "Markdown、JSON、音频 digest，进入个人知识库。", "MD / JSON / Obsidian", "BookMarked"],
  ];
  for (let i = 0; i < rows.length; i += 1) {
    const y = 210 + i * 78;
    glass(slide, ctx, 84, y, 1090, 58, { fill: i % 2 ? C.surface : C.elev });
    await icon(slide, ctx, rows[i][3], 112, y + 17, 20, i === 3 ? C.purple : C.info);
    text(slide, ctx, rows[i][0], 152, y + 15, 140, 18, { size: 16, bold: true, display: true });
    text(slide, ctx, rows[i][1], 312, y + 15, 420, 18, { size: 13.5, color: C.muted });
    rect(slide, ctx, 800, y + 16, 1, 26, C.border, { geometry: "rect" });
    text(slide, ctx, rows[i][2], 834, y + 15, 270, 18, { size: 12, bold: true, color: C.text, align: "right" });
  }
  text(
    slide,
    ctx,
    "汇报时可以沿着这五层讲：先证明可用，再证明好用，最后证明能进入长期学习流程。",
    86,
    610,
    760,
    28,
    { size: 15, color: C.muted }
  );
  footer(slide, ctx);
  return slide;
}
