import { C, bg, footer, glass, icon, kicker, page, rect, text, title } from "./common.mjs";

export async function slide08(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Engineering Workload");
  page(slide, ctx, 7);
  title(slide, ctx, "产品体验背后是完整工程系统：状态机、持久化、并发、校验和导出。", 68, 86, 900, 86, 32);

  glass(slide, ctx, 86, 214, 340, 332);
  text(slide, ctx, "Frontend v2", 116, 246, 160, 22, { size: 19, bold: true, display: true });
  text(slide, ctx, "React + Tailwind + Framer Motion", 116, 282, 230, 18, { size: 12, color: C.muted });
  const front = ["Library", "Hook hero", "Chapter timeline", "Floating dock"];
  for (let i = 0; i < front.length; i += 1) {
    rect(slide, ctx, 116, 326 + i * 40, 12, 12, C.info, { geometry: "ellipse", stroke: "#00000000" });
    text(slide, ctx, front[i], 144, 322 + i * 40, 190, 16, { size: 13 });
  }

  glass(slide, ctx, 470, 214, 340, 332, { fill: C.elev });
  text(slide, ctx, "FastAPI Pipeline", 500, 246, 190, 22, { size: 19, bold: true, display: true });
  text(slide, ctx, "queued → fetching → transcribing → summarizing → done", 500, 282, 250, 36, { size: 12, color: C.muted });
  const states = ["Checkpoint resume", "Retry budget", "Optional-stage degrade", "WebSocket progress"];
  for (let i = 0; i < states.length; i += 1) {
    rect(slide, ctx, 500, 326 + i * 40, 12, 12, C.purple, { geometry: "ellipse", stroke: "#00000000" });
    text(slide, ctx, states[i], 528, 322 + i * 40, 220, 16, { size: 13 });
  }

  glass(slide, ctx, 854, 214, 340, 332);
  text(slide, ctx, "Data & Artifacts", 884, 246, 190, 22, { size: 19, bold: true, display: true });
  text(slide, ctx, "SQLite + data/<episode_id>/", 884, 282, 230, 18, { size: 12, color: C.muted });
  const data = ["transcript segments", "chapters / quotes / entities", "Markdown / JSON", "TTS digest"];
  for (let i = 0; i < data.length; i += 1) {
    rect(slide, ctx, 884, 326 + i * 40, 12, 12, C.mint, { geometry: "ellipse", stroke: "#00000000" });
    text(slide, ctx, data[i], 912, 322 + i * 40, 220, 16, { size: 13 });
  }

  await icon(slide, ctx, "ArrowRight", 434, 364, 24, C.subtle);
  await icon(slide, ctx, "ArrowRight", 818, 364, 24, C.subtle);
  text(slide, ctx, "这页用于突出工作量：不是只接 API，而是做了可恢复、可验证、可扩展的系统。", 98, 590, 900, 24, { size: 15, color: C.muted });
  footer(slide, ctx);
  return slide;
}
