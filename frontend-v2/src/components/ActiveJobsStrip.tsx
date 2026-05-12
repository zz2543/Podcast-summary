import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/cn";
import type { Job } from "@/api/client";

const STAGE_ORDER = ["queued", "fetching", "transcribing", "summarizing", "tts"] as const;
const STAGE_LABEL: Record<string, string> = {
  queued: "Queued",
  fetching: "Downloading",
  transcribing: "Transcribing",
  summarizing: "Summarizing",
  tts: "Synthesizing"
};

export function ActiveJobsStrip({
  jobs,
  titleByEpisode
}: {
  jobs: Job[];
  titleByEpisode: Record<string, string | null>;
}) {
  const active = jobs.filter((j) =>
    ["queued", "fetching", "transcribing", "summarizing", "tts"].includes(j.state)
  );
  if (active.length === 0) return null;

  return (
    <div className="mb-6 overflow-hidden rounded-2xl glass shadow-card">
      <div className="flex items-center gap-2 border-b border-black/5 px-4 py-2">
        <span className="h-2 w-2 animate-pulse rounded-full bg-status-warn" />
        <span className="text-xs font-medium uppercase tracking-wider text-text-muted">
          In progress
        </span>
        <span className="text-xs text-text-subtle">· {active.length}</span>
      </div>
      <div className="flex gap-3 overflow-x-auto scroll-area px-4 py-3">
        <AnimatePresence>
          {active.map((job) => (
            <motion.div
              key={job.id}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 8 }}
              className="flex min-w-[260px] flex-col gap-2 rounded-xl bg-surface px-3 py-2.5 shadow-card"
            >
              <div className="truncate text-sm font-medium text-text">
                {titleByEpisode[job.episode_id] ?? job.episode_id.slice(-8)}
              </div>
              <StageBar state={job.state} />
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}

function StageBar({ state }: { state: Job["state"] }) {
  const currentIdx = STAGE_ORDER.indexOf(state as (typeof STAGE_ORDER)[number]);
  return (
    <div className="flex items-center gap-1.5">
      {STAGE_ORDER.map((s, i) => {
        const reached = currentIdx >= i;
        const isCurrent = currentIdx === i;
        return (
          <div
            key={s}
            className={cn(
              "h-1 flex-1 rounded-full transition-all",
              reached ? "bg-text" : "bg-border",
              isCurrent && "animate-pulse"
            )}
          />
        );
      })}
      <span className="ml-2 min-w-[80px] text-xs text-text-muted">
        {STAGE_LABEL[state] ?? state}
      </span>
    </div>
  );
}
