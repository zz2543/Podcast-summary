import { motion } from "framer-motion";
import { Play } from "lucide-react";
import type { Chapter } from "@/api/client";
import { TracingBeam } from "@/components/ui/tracing-beam";
import { formatTimestamp } from "@/lib/time";

export function ChaptersTimeline({
  chapters,
  onQuoteClick
}: {
  chapters: Chapter[];
  onQuoteClick?: (ms: number) => void;
}) {
  if (chapters.length === 0) return null;
  return (
    <section className="space-y-3">
      <h2 className="font-display text-sm font-medium uppercase tracking-wider text-text-subtle">
        Chapters · {chapters.length}
      </h2>
      <TracingBeam>
        <div className="space-y-6 pl-2 md:pl-0">
          {chapters.map((chapter, i) => (
            <motion.article
              key={chapter.idx}
              initial={{ opacity: 0, y: 6 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.35, delay: i * 0.04 }}
              className="rounded-2xl bg-surface p-5 shadow-card"
            >
              <header className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
                <h3 className="font-display text-base font-semibold tracking-tight text-text">
                  {chapter.idx + 1}. {chapter.title}
                </h3>
                <span className="font-mono text-xs text-text-muted">
                  {formatTimestamp(chapter.start_ms)} – {formatTimestamp(chapter.end_ms)}
                </span>
              </header>
              {chapter.key_points.length > 0 && (
                <ul className="space-y-1.5 text-sm leading-relaxed text-text">
                  {chapter.key_points.map((kp, j) => (
                    <li key={j} className="flex gap-2">
                      <span className="mt-1.5 h-1 w-1 flex-shrink-0 rounded-full bg-text-subtle" />
                      <span>{kp}</span>
                    </li>
                  ))}
                </ul>
              )}
              {chapter.quotes.length > 0 && (
                <div className="mt-3 flex flex-col gap-2">
                  {chapter.quotes.map((q, j) => (
                    <button
                      key={j}
                      type="button"
                      onClick={() => onQuoteClick?.(q.start_ms)}
                      className="group/quote flex items-start gap-3 rounded-xl bg-surface-elev px-3 py-2.5 text-left text-sm text-text transition-all hover:bg-white hover:shadow-card"
                    >
                      <span className="mt-0.5 inline-flex h-6 flex-shrink-0 items-center gap-1.5 rounded-full bg-white px-2 font-mono text-[11px] text-text-muted shadow-sm transition-colors group-hover/quote:bg-text group-hover/quote:text-white">
                        <Play className="h-2.5 w-2.5 fill-current" strokeWidth={0} />
                        {formatTimestamp(q.start_ms)}
                      </span>
                      <span className="flex-1 whitespace-pre-wrap leading-relaxed text-text">
                        {q.text}
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </motion.article>
          ))}
        </div>
      </TracingBeam>
    </section>
  );
}
