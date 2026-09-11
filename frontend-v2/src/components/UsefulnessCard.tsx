import { motion } from "framer-motion";
import { cn } from "@/lib/cn";
import { BAND_FILLS, BAND_LABELS, BAND_TONES } from "@/components/ScoreBadge";
import type { EpisodeDetail } from "@/api/client";

/**
 * FR-027 详情页评分卡：hook 说这集讲什么，这张卡说值不值得花时间。
 * 未评分（stage_status.usefulness !== "present"）时降级为占位卡，
 * 不影响页面其余部分。
 */
export function UsefulnessCard({
  episode,
  onRetry
}: {
  episode: EpisodeDetail;
  onRetry?: () => void;
}) {
  const usefulness = episode.usefulness;
  const stage = episode.stage_status.usefulness;

  if (!usefulness) {
    if (stage === "pending" || stage === "present") return null;
    return (
      <div className="rounded-2xl border border-dashed border-border bg-surface p-5 text-sm text-text-muted">
        <p className="font-medium text-text">有用性评分未生成</p>
        <p className="mt-1 text-xs">
          {stage === "failed_after_retries"
            ? "多次重试后仍未拿到评分，其余摘要不受影响。"
            : "这一集还没有评分，其余摘要不受影响。"}
        </p>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="mt-3 rounded-full bg-surface-elev px-3 py-1 text-xs font-medium text-text hover:shadow-card"
          >
            重试此环节
          </button>
        )}
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, delay: 0.12 }}
      className="rounded-2xl bg-surface p-6 shadow-card"
    >
      <div className="flex items-baseline gap-3">
        <span className="font-display text-5xl font-semibold tabular-nums leading-none text-text">
          {usefulness.score}
        </span>
        <span className="text-sm text-text-subtle">/ 100</span>
        <span
          className={cn(
            "ml-auto rounded-full px-3 py-1 text-xs font-medium",
            BAND_TONES[usefulness.band]
          )}
          title="由模型根据转写内容给出的参考评分。"
        >
          {BAND_LABELS[usefulness.band]}
        </span>
      </div>

      {/* Decorative: the score itself is already stated above in text. */}
      <div aria-hidden className="mt-4 h-1.5 w-full overflow-hidden rounded-full bg-surface-elev">
        <div
          className={cn("h-full rounded-full", BAND_FILLS[usefulness.band])}
          style={{ width: `${usefulness.score}%` }}
        />
      </div>

      <p className="mt-4 text-sm leading-relaxed text-text">{usefulness.rationale}</p>

      {episode.prompt_versions.usefulness_score && (
        <p className="mt-3 text-[11px] text-text-subtle">
          Prompt 版本：{episode.prompt_versions.usefulness_score}
        </p>
      )}
    </motion.div>
  );
}
