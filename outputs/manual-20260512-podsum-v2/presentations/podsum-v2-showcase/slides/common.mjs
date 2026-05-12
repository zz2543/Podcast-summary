export const C = {
  bg: "#FBFBFD",
  surface: "#FFFFFF",
  elev: "#F5F5F7",
  border: "#D2D2D7",
  text: "#1D1D1F",
  muted: "#6E6E73",
  subtle: "#86868B",
  ok: "#34C759",
  warn: "#FF9F0A",
  err: "#FF3B30",
  info: "#0A84FF",
  pink: "#FF6B9D",
  purple: "#8B7DFF",
  cyan: "#5FA8FF",
  mint: "#4ED6BB",
  yellow: "#FFC857",
};

export const F = {
  display: "SF Pro Display",
  body: "SF Pro Text",
  mono: "Aptos Mono",
};

export function rect(slide, ctx, x, y, w, h, fill = C.surface, opts = {}) {
  return ctx.addShape(slide, {
    left: x,
    top: y,
    width: w,
    height: h,
    geometry: opts.geometry ?? "roundRect",
    fill,
    line: opts.line ?? ctx.line(opts.stroke ?? "#00000000", opts.strokeWidth ?? 0),
    name: opts.name,
  });
}

export function text(slide, ctx, value, x, y, w, h, opts = {}) {
  return ctx.addText(slide, {
    text: String(value ?? ""),
    left: x,
    top: y,
    width: w,
    height: h,
    fontSize: opts.size ?? 18,
    color: opts.color ?? C.text,
    bold: Boolean(opts.bold),
    typeface: opts.face ?? (opts.display ? F.display : F.body),
    align: opts.align ?? "left",
    valign: opts.valign ?? "top",
    fill: opts.fill ?? "#00000000",
    line: opts.line ?? ctx.line(),
    insets: opts.insets ?? { left: 0, right: 0, top: 0, bottom: 0 },
  });
}

export function line(slide, ctx, x, y, w, color = C.border, weight = 1) {
  return rect(slide, ctx, x, y, w, weight, color, { geometry: "rect" });
}

export function bg(slide, ctx) {
  rect(slide, ctx, 0, 0, ctx.W, ctx.H, C.bg, { geometry: "rect" });
  for (let x = 32; x < ctx.W; x += 64) {
    rect(slide, ctx, x, 64, 1, ctx.H - 128, "#ECECF1", { geometry: "rect" });
  }
  for (let y = 64; y < ctx.H; y += 64) {
    rect(slide, ctx, 64, y, ctx.W - 128, 1, "#ECECF1", { geometry: "rect" });
  }
}

export function glass(slide, ctx, x, y, w, h, opts = {}) {
  rect(slide, ctx, x + 3, y + 8, w, h, "#00000010", { stroke: "#00000000" });
  return rect(slide, ctx, x, y, w, h, opts.fill ?? C.surface, {
    stroke: opts.stroke ?? "#E5E5EA",
    strokeWidth: opts.strokeWidth ?? 1,
  });
}

export function kicker(slide, ctx, value, x = 68, y = 50) {
  text(slide, ctx, value.toUpperCase(), x, y, 420, 18, {
    size: 11,
    bold: true,
    color: C.subtle,
  });
}

export function title(slide, ctx, value, x = 68, y = 82, w = 820, h = 96, size = 34) {
  text(slide, ctx, value, x, y, w, h, {
    size,
    bold: true,
    display: true,
    color: C.text,
  });
}

export function subtitle(slide, ctx, value, x = 68, y = 176, w = 720, h = 54) {
  text(slide, ctx, value, x, y, w, h, {
    size: 16,
    color: C.muted,
  });
}

export function page(slide, ctx, n) {
  text(slide, ctx, String(n).padStart(2, "0"), 1160, 48, 48, 18, {
    size: 12,
    bold: true,
    align: "right",
    color: C.subtle,
  });
}

export function footer(slide, ctx, value = "Podsum v2 · podcast knowledge workflow") {
  line(slide, ctx, 68, 655, 1144, "#E5E5EA", 1);
  text(slide, ctx, value, 68, 670, 760, 20, { size: 10, color: C.subtle });
}

export function pill(slide, ctx, label, x, y, w, opts = {}) {
  rect(slide, ctx, x, y, w, 30, opts.fill ?? C.elev, {
    stroke: opts.stroke ?? "#E5E5EA",
    strokeWidth: 1,
  });
  text(slide, ctx, label, x + 12, y + 8, w - 24, 12, {
    size: 10,
    bold: true,
    color: opts.color ?? C.text,
    align: "center",
  });
}

export function iridescentButton(slide, ctx, label, x, y, w = 190) {
  const colors = [C.pink, "#C66FBC", C.purple, C.cyan, C.mint, C.yellow];
  const band = w / colors.length;
  for (let i = 0; i < colors.length; i += 1) {
    rect(slide, ctx, x + i * band, y, band + 1, 38, colors[i], {
      geometry: i === 0 || i === colors.length - 1 ? "roundRect" : "rect",
      stroke: "#00000000",
    });
  }
  text(slide, ctx, label, x, y + 10, w, 14, {
    size: 11,
    bold: true,
    color: "#FFFFFF",
    align: "center",
  });
}

export async function icon(slide, ctx, name, x, y, size = 22, color = C.text) {
  return ctx.addLucideIcon(slide, {
    icon: name,
    left: x,
    top: y,
    width: size,
    height: size,
    color,
    strokeWidth: 1.7,
  });
}

export function miniWindow(slide, ctx, x, y, w, h) {
  glass(slide, ctx, x, y, w, h);
  rect(slide, ctx, x, y, w, 40, C.elev, { stroke: "#E5E5EA" });
  rect(slide, ctx, x + 18, y + 16, 8, 8, C.err, { geometry: "ellipse" });
  rect(slide, ctx, x + 34, y + 16, 8, 8, C.warn, { geometry: "ellipse" });
  rect(slide, ctx, x + 50, y + 16, 8, 8, C.ok, { geometry: "ellipse" });
}

export function mockAudioBars(slide, ctx, x, y) {
  const heights = [18, 32, 24, 42, 30, 52, 20, 36, 28, 46];
  heights.forEach((h, i) => {
    rect(slide, ctx, x + i * 12, y + 56 - h, 6, h, i % 2 ? C.info : C.text, {
      geometry: "roundRect",
      stroke: "#00000000",
    });
  });
}

export function metric(slide, ctx, value, label, x, y, w = 300, accent = C.info) {
  glass(slide, ctx, x, y, w, 132);
  text(slide, ctx, value, x + 22, y + 20, w - 44, 42, {
    size: 28,
    bold: true,
    display: true,
    color: accent,
  });
  text(slide, ctx, label, x + 22, y + 72, w - 44, 42, { size: 12.5, color: C.muted });
}
