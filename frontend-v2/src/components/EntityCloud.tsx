import { motion } from "framer-motion";
import type { EntitySummary } from "@/api/client";
import { cn } from "@/lib/cn";

const KIND_LABEL: Record<EntitySummary["kind"], string> = {
  person: "Person",
  book: "Book",
  product: "Product"
};

export function EntityCloud({ entities }: { entities: EntitySummary[] }) {
  if (entities.length === 0) return null;
  return (
    <section className="space-y-3">
      <h2 className="font-display text-sm font-medium uppercase tracking-wider text-text-subtle">
        Entities · {entities.length}
      </h2>
      <div className="flex flex-wrap gap-2">
        {entities.map((e, i) => (
          <motion.span
            key={`${e.kind}-${e.name}`}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.25, delay: i * 0.02 }}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full bg-surface px-3 py-1.5 text-sm text-text shadow-card"
            )}
          >
            <span className="text-xs font-medium uppercase tracking-wide text-text-subtle">
              {KIND_LABEL[e.kind]}
            </span>
            <span className="text-border">·</span>
            <span>{e.name}</span>
            {e.count > 1 && (
              <span className="rounded-full bg-surface-elev px-1.5 text-xs text-text-muted">
                ×{e.count}
              </span>
            )}
          </motion.span>
        ))}
      </div>
    </section>
  );
}
