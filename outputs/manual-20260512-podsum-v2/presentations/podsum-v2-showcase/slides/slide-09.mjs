import { C, bg, footer, kicker, metric, page, text, title } from "./common.mjs";

export async function slide09(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Verification");
  page(slide, ctx, 8);
  title(slide, ctx, "完成度不是口头描述，而是有自动化验证和生产模式运行支撑。", 68, 86, 860, 82, 34);

  metric(slide, ctx, "63", "Backend tests passed：覆盖 domain、pipeline、API、并发和 digest。", 86, 226, 330, C.info);
  metric(slide, ctx, "87.98%", "Domain coverage：高于 constitution 规定的 80% coverage gate。", 476, 226, 330, C.ok);
  metric(slide, ctx, "206", "Range endpoint verified：支持音频局部加载和 quote 跳转体验。", 866, 226, 330, C.purple);
  metric(slide, ctx, "PASS", "Quote verifier fixture：PASS 1 / FAIL 0，引用可被离线复查。", 86, 410, 330, C.mint);
  metric(slide, ctx, "≤ 2", "MAX_CONCURRENCY=2 时 transcribing job 从未超过配置上限。", 476, 410, 330, C.warn);
  metric(slide, ctx, "Serve", "make build && make serve 验证 FastAPI 可独立服务生产 SPA。", 866, 410, 330, C.text);

  text(slide, ctx, "适合展示时的结论：系统不只是能演示，而是能构建、能测试、能服务、能复查。", 92, 610, 850, 24, { size: 15, color: C.muted });
  footer(slide, ctx);
  return slide;
}
