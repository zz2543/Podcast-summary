import { motion } from "framer-motion";
import type { EpisodeDetail } from "@/api/client";
import { StatusDot } from "@/components/StatusDot";
import { formatDuration } from "@/lib/time";

export function HookHero({ episode }: { episode: EpisodeDetail }) {
  return (
    <section className="space-y-5">
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="flex flex-wrap items-center gap-3 text-sm text-text-muted"
      >
        {episode.podcast_name && (
          <span className="font-medium text-text">{episode.podcast_name}</span>
        )}
        <span className="text-border">·</span>
        <span>{formatDuration(episode.duration_seconds)}</span>
        <span className="text-border">·</span>
        <span className="uppercase tracking-wide">{episode.language ?? "—"}</span>
        <span className="text-border">·</span>
        <StatusDot status={episode.status} />
      </motion.div>

      <motion.h1
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45, delay: 0.05 }}
        className="font-display text-3xl font-semibold leading-tight tracking-tight text-text sm:text-4xl"
      >
        {episode.title || "Untitled episode"}
      </motion.h1>

      {episode.hook && (
        <motion.blockquote
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="rounded-2xl bg-surface-elev p-6 text-lg font-medium leading-relaxed text-text sm:text-xl"
        >
          <span className="mr-2 text-text-subtle">"</span>
          {episode.hook}
          <span className="ml-1 text-text-subtle">"</span>
        </motion.blockquote>
      )}
    </section>
  );
}
