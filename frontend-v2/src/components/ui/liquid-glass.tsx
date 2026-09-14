import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  type ElementType,
  type HTMLAttributes
} from "react";
import { cn } from "@/lib/cn";
import {
  DEFAULT_OPTICS,
  acquireFilter,
  backdropFilterValue,
  normalizeGeometry,
  releaseFilter,
  supportsLiquidGlass
} from "@/lib/liquid-glass";

export interface LiquidGlassOptions {
  /** Corner radius in px. Defaults to the element's computed border-radius. */
  radius?: number;
  /** Width of the refracting edge band in px. */
  bezel?: number;
  /** How hard the bezel bends the backdrop, as a fraction of `bezel`. */
  strength?: number;
  blur?: number;
  saturate?: number;
  brightness?: number;
  contrast?: number;
  /** Set false to keep the flat CSS blur (e.g. while a panel is hidden). */
  enabled?: boolean;
}

/**
 * Attaches a generated SVG displacement filter to an element's backdrop-filter,
 * keeping it in sync with the element's size. On engines that cannot resolve
 * SVG filters inside backdrop-filter this is a no-op and the element keeps the
 * blur declared by its CSS class.
 */
export function useLiquidGlass<T extends HTMLElement>(
  options: LiquidGlassOptions = {}
) {
  const ref = useRef<T | null>(null);
  const filterIdRef = useRef<string | null>(null);

  const {
    radius,
    bezel = 18,
    strength = 0.7,
    blur = DEFAULT_OPTICS.blur,
    saturate = DEFAULT_OPTICS.saturate,
    brightness = DEFAULT_OPTICS.brightness,
    contrast = DEFAULT_OPTICS.contrast,
    enabled = true
  } = options;

  useEffect(() => {
    const element = ref.current;
    if (!element || !enabled || !supportsLiquidGlass()) return;

    let frame = 0;
    let appliedKey = "";

    const apply = () => {
      // offsetWidth/Height is the layout box, so scale animations don't thrash.
      const width = element.offsetWidth;
      const height = element.offsetHeight;
      if (width < 8 || height < 8) return;

      const resolvedRadius =
        radius ??
        parseFloat(getComputedStyle(element).borderTopLeftRadius) ??
        0;
      const geometry = normalizeGeometry({
        width,
        height,
        radius: Number.isFinite(resolvedRadius) ? resolvedRadius : 0,
        bezel,
        strength
      });
      const key = Object.values(geometry).join(":");
      if (key === appliedKey) return;
      appliedKey = key;

      const nextId = acquireFilter(geometry);
      releaseFilter(filterIdRef.current);
      filterIdRef.current = nextId;

      const value = backdropFilterValue(nextId, {
        blur,
        saturate,
        brightness,
        contrast
      });
      element.style.setProperty("backdrop-filter", value);
      element.style.setProperty("-webkit-backdrop-filter", value);
    };

    const observer = new ResizeObserver(() => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(apply);
    });
    observer.observe(element);
    apply();

    return () => {
      observer.disconnect();
      cancelAnimationFrame(frame);
      releaseFilter(filterIdRef.current);
      filterIdRef.current = null;
      element.style.removeProperty("backdrop-filter");
      element.style.removeProperty("-webkit-backdrop-filter");
    };
  }, [radius, bezel, strength, blur, saturate, brightness, contrast, enabled]);

  return ref;
}

export interface GlassSurfaceProps
  extends HTMLAttributes<HTMLDivElement>,
    LiquidGlassOptions {
  /** Visual weight of the fallback/base layer. */
  tone?: "default" | "strong" | "dark";
  as?: ElementType;
}

/**
 * A div whose backdrop refracts. `tone` picks the CSS base layer (tint, edge
 * highlights, shadow); the hook adds the displacement on top where supported.
 */
export const GlassSurface = forwardRef<HTMLDivElement, GlassSurfaceProps>(
  function GlassSurface(
    {
      tone = "default",
      className,
      children,
      radius,
      bezel,
      strength,
      blur,
      saturate,
      brightness,
      contrast,
      enabled,
      ...rest
    },
    forwardedRef
  ) {
    const innerRef = useLiquidGlass<HTMLDivElement>({
      radius,
      bezel,
      strength,
      blur,
      saturate,
      brightness,
      contrast,
      enabled
    });
    useImperativeHandle(forwardedRef, () => innerRef.current as HTMLDivElement);

    return (
      <div
        ref={innerRef}
        className={cn(
          tone === "strong" ? "glass-strong" : tone === "dark" ? "glass-dark" : "glass",
          className
        )}
        {...rest}
      >
        {children}
      </div>
    );
  }
);
