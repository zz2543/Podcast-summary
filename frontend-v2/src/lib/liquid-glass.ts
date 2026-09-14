/**
 * Liquid glass via SVG displacement maps.
 *
 * Technique adapted from Shu Ding's liquid-glass (MIT):
 * https://github.com/shuding/liquid-glass
 *
 * A per-pixel "fragment shader" runs in JS and writes a displacement map into a
 * canvas (dx in R, dy in G). The canvas is fed to an SVG <feImage> that drives
 * an <feDisplacementMap>, and the whole filter is referenced from the element's
 * `backdrop-filter`. The result is real refraction at the bezel instead of a
 * flat blur.
 *
 * Filters are cached and ref-counted by geometry, so N cards of the same size
 * share one map.
 */

const SVG_NS = "http://www.w3.org/2000/svg";
const XLINK_NS = "http://www.w3.org/1999/xlink";

/** Max pixels in a displacement map before we drop resolution. */
const MAX_MAP_PIXELS = 240_000;
/** Geometry is snapped to this grid so resizes reuse cached filters. */
const SIZE_QUANTUM = 4;

export interface GlassGeometry {
  /** Element width in CSS px. */
  width: number;
  /** Element height in CSS px. */
  height: number;
  /** Corner radius in CSS px. */
  radius: number;
  /** Width of the refracting edge band in CSS px. */
  bezel: number;
  /** How far the bezel pulls the backdrop inward, as a fraction of `bezel`. */
  strength: number;
}

/* ------------------------------------------------------------------ math -- */

function smoothStep(a: number, b: number, t: number): number {
  const x = Math.max(0, Math.min(1, (t - a) / (b - a)));
  return x * x * (3 - 2 * x);
}

/** Signed distance to a rounded rect centred on the origin. Negative inside. */
function roundedRectSDF(
  x: number,
  y: number,
  halfWidth: number,
  halfHeight: number,
  radius: number
): number {
  const qx = Math.abs(x) - halfWidth + radius;
  const qy = Math.abs(y) - halfHeight + radius;
  return (
    Math.min(Math.max(qx, qy), 0) +
    Math.hypot(Math.max(qx, 0), Math.max(qy, 0)) -
    radius
  );
}

/** Outward unit normal of the SDF, by central difference. */
function sdfNormal(
  x: number,
  y: number,
  halfWidth: number,
  halfHeight: number,
  radius: number
): [number, number] {
  const e = 0.5;
  const gx =
    roundedRectSDF(x + e, y, halfWidth, halfHeight, radius) -
    roundedRectSDF(x - e, y, halfWidth, halfHeight, radius);
  const gy =
    roundedRectSDF(x, y + e, halfWidth, halfHeight, radius) -
    roundedRectSDF(x, y - e, halfWidth, halfHeight, radius);
  const len = Math.hypot(gx, gy);
  if (len < 1e-6) return [0, 0];
  return [gx / len, gy / len];
}

/* ------------------------------------------------------------ capability -- */

let supportCache: boolean | null = null;

/**
 * `backdrop-filter: url(#id)` only actually resolves SVG filters on Chromium.
 * WebKit and Gecko accept the declaration but render nothing, so feature
 * queries are useless here and we gate on the engine instead. Everywhere else
 * falls back to the plain blur already carried by the CSS classes.
 */
export function supportsLiquidGlass(): boolean {
  if (supportCache !== null) return supportCache;
  if (typeof window === "undefined" || typeof document === "undefined") {
    return false;
  }

  const ua = navigator.userAgent;
  // iOS wrappers (CriOS/FxiOS/EdgiOS) are WebKit despite the brand in the UA.
  const isChromium =
    /Chrome|Chromium|Edg\/|OPR\//.test(ua) && !/CriOS|FxiOS|EdgiOS|OPiOS/.test(ua);
  const hasBackdrop =
    CSS.supports("backdrop-filter", "blur(1px)") ||
    CSS.supports("-webkit-backdrop-filter", "blur(1px)");
  const reducedTransparency = window.matchMedia?.(
    "(prefers-reduced-transparency: reduce)"
  ).matches;

  supportCache = isChromium && hasBackdrop && !reducedTransparency;
  return supportCache;
}

/* ---------------------------------------------------------------- filters -- */

interface FilterEntry {
  id: string;
  refs: number;
  node: SVGFilterElement;
}

let spriteRoot: SVGSVGElement | null = null;
const cache = new Map<string, FilterEntry>();
let seq = 0;

function getSpriteRoot(): SVGSVGElement {
  if (spriteRoot?.isConnected) return spriteRoot;
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("width", "0");
  svg.setAttribute("height", "0");
  svg.style.cssText =
    "position:fixed;top:0;left:0;width:0;height:0;overflow:hidden;pointer-events:none;";
  svg.appendChild(document.createElementNS(SVG_NS, "defs"));
  document.body.appendChild(svg);
  spriteRoot = svg;
  return svg;
}

function quantize(value: number): number {
  return Math.max(SIZE_QUANTUM, Math.round(value / SIZE_QUANTUM) * SIZE_QUANTUM);
}

export function normalizeGeometry(geometry: GlassGeometry): GlassGeometry {
  const width = quantize(geometry.width);
  const height = quantize(geometry.height);
  return {
    width,
    height,
    radius: Math.round(Math.min(geometry.radius, width / 2, height / 2)),
    bezel: Math.round(
      Math.max(2, Math.min(geometry.bezel, width / 2, height / 2))
    ),
    strength: Math.round(geometry.strength * 100) / 100
  };
}

/**
 * Renders the displacement map. Returns `null` when the geometry produces no
 * displacement at all (nothing to filter, so the caller keeps the plain blur).
 */
function renderDisplacementMap(
  geometry: GlassGeometry
): { href: string; scale: number } | null {
  const { width, height, radius, bezel, strength } = geometry;

  let dpi = 1;
  while (width * height * dpi * dpi > MAX_MAP_PIXELS && dpi > 0.25) {
    dpi /= 2;
  }
  const cols = Math.max(1, Math.round(width * dpi));
  const rows = Math.max(1, Math.round(height * dpi));

  const halfWidth = width / 2;
  const halfHeight = height / 2;
  const raw = new Float32Array(cols * rows * 2);
  let maxAbs = 0;

  for (let row = 0; row < rows; row++) {
    const y = ((row + 0.5) / rows - 0.5) * height;
    for (let col = 0; col < cols; col++) {
      const x = ((col + 0.5) / cols - 0.5) * width;
      const distance = roundedRectSDF(x, y, halfWidth, halfHeight, radius);

      let dx = 0;
      let dy = 0;
      const depth = -distance;
      if (depth > 0 && depth < bezel) {
        // 1 right at the edge, easing to 0 once we are `bezel` px inside.
        const t = 1 - smoothStep(0, bezel, depth);
        const amount = strength * bezel * t * t;
        const [nx, ny] = sdfNormal(x, y, halfWidth, halfHeight, radius);
        // Sample inward along the normal: the bezel drags the backdrop outward.
        dx = -nx * amount;
        dy = -ny * amount;
      }

      const i = (row * cols + col) * 2;
      raw[i] = dx;
      raw[i + 1] = dy;
      maxAbs = Math.max(maxAbs, Math.abs(dx), Math.abs(dy));
    }
  }

  if (maxAbs < 0.01) return null;

  // feDisplacementMap computes offset = scale * (channel - 0.5), channel in
  // [0,1]. Encoding with a half-range of maxAbs means scale = 2 * maxAbs.
  const scale = 2 * maxAbs;
  const pixels = new Uint8ClampedArray(cols * rows * 4);
  for (let i = 0, p = 0; p < raw.length; i += 4, p += 2) {
    pixels[i] = (raw[p] / scale + 0.5) * 255;
    pixels[i + 1] = (raw[p + 1] / scale + 0.5) * 255;
    pixels[i + 2] = 0;
    pixels[i + 3] = 255;
  }

  const canvas = document.createElement("canvas");
  canvas.width = cols;
  canvas.height = rows;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.putImageData(new ImageData(pixels, cols, rows), 0, 0);

  return { href: canvas.toDataURL(), scale };
}

/**
 * Returns the id of a filter matching `geometry`, creating it if needed.
 * Every successful call must be paired with `releaseFilter`.
 */
export function acquireFilter(geometry: GlassGeometry): string | null {
  if (!supportsLiquidGlass()) return null;

  const normalized = normalizeGeometry(geometry);
  const key = [
    normalized.width,
    normalized.height,
    normalized.radius,
    normalized.bezel,
    normalized.strength
  ].join(":");

  const hit = cache.get(key);
  if (hit) {
    hit.refs += 1;
    return hit.id;
  }

  const map = renderDisplacementMap(normalized);
  if (!map) return null;

  const id = `liquid-glass-${(seq += 1)}`;
  const filter = document.createElementNS(SVG_NS, "filter");
  filter.setAttribute("id", id);
  filter.setAttribute("filterUnits", "userSpaceOnUse");
  filter.setAttribute("colorInterpolationFilters", "sRGB");
  filter.setAttribute("x", "0");
  filter.setAttribute("y", "0");
  filter.setAttribute("width", String(normalized.width));
  filter.setAttribute("height", String(normalized.height));

  const feImage = document.createElementNS(SVG_NS, "feImage");
  feImage.setAttribute("result", `${id}_map`);
  feImage.setAttribute("width", String(normalized.width));
  feImage.setAttribute("height", String(normalized.height));
  feImage.setAttribute("preserveAspectRatio", "none");
  feImage.setAttribute("href", map.href);
  feImage.setAttributeNS(XLINK_NS, "xlink:href", map.href);

  const feDisplacementMap = document.createElementNS(SVG_NS, "feDisplacementMap");
  feDisplacementMap.setAttribute("in", "SourceGraphic");
  feDisplacementMap.setAttribute("in2", `${id}_map`);
  feDisplacementMap.setAttribute("xChannelSelector", "R");
  feDisplacementMap.setAttribute("yChannelSelector", "G");
  feDisplacementMap.setAttribute("scale", String(map.scale));

  filter.appendChild(feImage);
  filter.appendChild(feDisplacementMap);
  getSpriteRoot().firstChild!.appendChild(filter);

  cache.set(key, { id, refs: 1, node: filter });
  return id;
}

export function releaseFilter(id: string | null): void {
  if (!id) return;
  for (const [key, entry] of cache) {
    if (entry.id !== id) continue;
    entry.refs -= 1;
    if (entry.refs <= 0) {
      entry.node.remove();
      cache.delete(key);
    }
    return;
  }
}

/* ------------------------------------------------------------------ css --- */

export interface GlassOptics {
  blur: number;
  saturate: number;
  brightness: number;
  contrast: number;
}

export const DEFAULT_OPTICS: GlassOptics = {
  blur: 8,
  saturate: 1.8,
  brightness: 1.04,
  contrast: 1.08
};

export function backdropFilterValue(
  filterId: string | null,
  optics: GlassOptics
): string {
  const parts = [
    `blur(${optics.blur}px)`,
    `saturate(${optics.saturate})`,
    `brightness(${optics.brightness})`,
    `contrast(${optics.contrast})`
  ];
  if (filterId) parts.unshift(`url(#${filterId})`);
  return parts.join(" ");
}
