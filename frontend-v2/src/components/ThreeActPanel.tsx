import { motion } from "framer-motion";
import type { ThreeAct } from "@/api/client";

const SECTIONS: { key: keyof ThreeAct; label: string }[] = [
  { key: "background", label: "Background" },
  { key: "core_argument", label: "Core argument" },
  { key: "conclusion", label: "Conclusion" }
];

export function ThreeActPanel({ three_act }: { three_act: ThreeAct | null }) {
  if (!three_act) return null;
  return (
    <section className="space-y-3">
      <h2 className="font-display text-sm font-medium uppercase tracking-wider text-text-subtle">
        Three-act summary
      </h2>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        {SECTIONS.map((s, i) => (
          <motion.div
            key={s.key}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: i * 0.05 }}
            className="rounded-2xl glass p-5 shadow-card"
          >
            <div className="mb-2 text-xs font-medium uppercase tracking-wider text-text-subtle">
              {s.label}
            </div>
            <p className="text-sm leading-relaxed text-text">{three_act[s.key]}</p>
          </motion.div>
        ))}
      </div>
    </section>
  );
}
