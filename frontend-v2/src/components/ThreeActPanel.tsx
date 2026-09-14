import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { useLiquidGlass } from "@/components/ui/liquid-glass";
import type { ThreeAct } from "@/api/client";

const SECTIONS: { key: keyof ThreeAct; label: string }[] = [
  { key: "background", label: "Background" },
  { key: "core_argument", label: "Core argument" },
  { key: "conclusion", label: "Conclusion" }
];

/** Collapsed height in px — roughly ten lines before the card is cut off. */
const COLLAPSED_MAX = 230;

export function ThreeActPanel({ three_act }: { three_act: ThreeAct | null }) {
  if (!three_act) return null;
  return (
    <section className="space-y-3">
      <h2 className="font-display text-sm font-medium uppercase tracking-wider text-text-subtle">
        Three-act summary
      </h2>
      {/* items-start so expanding one card does not stretch its neighbours. */}
      <div className="grid grid-cols-1 items-start gap-3 md:grid-cols-3">
        {SECTIONS.map((s, i) => (
          <ActCard
            key={s.key}
            label={s.label}
            body={three_act[s.key]}
            index={i}
          />
        ))}
      </div>
    </section>
  );
}

function ActCard({
  label,
  body,
  index
}: {
  label: string;
  body: string;
  index: number;
}) {
  const ref = useLiquidGlass<HTMLDivElement>({ bezel: 20, strength: 0.75 });
  const bodyRef = useRef<HTMLParagraphElement>(null);
  const [expanded, setExpanded] = useState(false);
  const [overflows, setOverflows] = useState(false);

  useEffect(() => {
    const element = bodyRef.current;
    if (!element) return;
    // scrollHeight still reports the full text while the box is clipped.
    const measure = () =>
      setOverflows(element.scrollHeight > COLLAPSED_MAX + 8);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, [body]);

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: index * 0.05 }}
      className="rounded-2xl glass p-5"
    >
      <div className="mb-2 text-xs font-medium uppercase tracking-wider text-text-subtle">
        {label}
      </div>
      <div className="relative">
        <p
          ref={bodyRef}
          className="overflow-hidden text-sm leading-relaxed text-text"
          style={{ maxHeight: expanded ? undefined : COLLAPSED_MAX }}
        >
          {body}
        </p>
        {!expanded && overflows && (
          <div
            aria-hidden
            className="pointer-events-none absolute inset-x-0 bottom-0 h-14"
            style={{
              background:
                "linear-gradient(to bottom, rgba(255,255,255,0), rgba(255,255,255,0.82))"
            }}
          />
        )}
      </div>
      {overflows && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
          className="mt-3 text-xs font-medium text-text-muted transition-colors hover:text-text"
        >
          {expanded ? "收起" : "展开全文"}
        </button>
      )}
    </motion.div>
  );
}
