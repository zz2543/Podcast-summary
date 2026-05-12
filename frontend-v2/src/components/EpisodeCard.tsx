import { Link } from "react-router-dom";
import { Headphones } from "lucide-react";
import { BentoCell } from "@/components/ui/bento-grid";
import { GlareCard } from "@/components/ui/glare-card";
import { StatusDot } from "@/components/StatusDot";
import { formatDuration, formatRelative } from "@/lib/time";
import type { EpisodeStatus, EpisodeSummary } from "@/api/client";

export function EpisodeCard({
  episode,
  status
}: {
  episode: EpisodeSummary;
  status: EpisodeStatus;
}) {
  return (
    <BentoCell className="h-full">
      <Link
        to={`/episodes/${encodeURIComponent(episode.id)}`}
        className="block h-full"
      >
        <GlareCard className="h-full rounded-2xl">
          <div className="flex h-full flex-col gap-3 p-5">
            <div className="flex items-start justify-between gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-surface-elev text-text-muted">
                <Headphones className="h-4 w-4" strokeWidth={1.6} />
              </div>
              <StatusDot status={status} />
            </div>
            <div className="flex-1">
              <h3 className="font-display text-base font-semibold leading-snug tracking-tight text-text line-clamp-2">
                {episode.title || "Untitled episode"}
              </h3>
              {episode.podcast_name && (
                <p className="mt-0.5 text-xs text-text-subtle line-clamp-1">
                  {episode.podcast_name}
                </p>
              )}
            </div>
            <div className="flex items-center gap-2 text-xs text-text-muted">
              <span>{formatDuration(episode.duration_seconds)}</span>
              <span className="text-border">·</span>
              <span className="uppercase tracking-wide">
                {episode.language ?? "—"}
              </span>
              <span className="text-border">·</span>
              <span>{formatRelative(episode.updated_at)}</span>
            </div>
          </div>
        </GlareCard>
      </Link>
    </BentoCell>
  );
}
