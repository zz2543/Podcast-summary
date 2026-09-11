import { cn } from "@/lib/cn";
import type { Usefulness, UsefulnessBand } from "@/api/client";

export const BAND_LABELS: Record<UsefulnessBand, string> = {
  must_listen: "必听",
  worth_listening: "值得听",
  skimmable: "可跳读",
  skippable: "可跳过"
};

/**
 * Colour is never the only signal: the number and the label always ship
 * together, so the badge still reads without colour perception.
 */
export const BAND_FILLS: Record<UsefulnessBand, string> = {
  must_listen: "bg-status-ok",
  worth_listening: "bg-status-info",
  skimmable: "bg-status-warn",
  skippable: "bg-text-subtle"
};

export const BAND_TONES: Record<UsefulnessBand, string> = {
  must_listen: "bg-status-ok/10 text-status-ok",
  worth_listening: "bg-status-info/10 text-status-info",
  skimmable: "bg-status-warn/10 text-status-warn",
  skippable: "bg-surface-elev text-text-subtle"
};

/**
 * FR-027 有用性评分徽章。`usefulness` 为 null 时显示「未评分」——
 * 绝不把未评分渲染成 0，0 是一个真实且有意义的分数。
 */
export function ScoreBadge({
  usefulness,
  className
}: {
  usefulness: Usefulness | null;
  className?: string;
}) {
  if (!usefulness) {
    return (
      <span
        className={cn(
          "inline-flex flex-col items-center rounded-xl bg-surface-elev px-2.5 py-1 text-text-subtle",
          className
        )}
      >
        <span className="text-xs font-medium leading-tight">未评分</span>
      </span>
    );
  }

  return (
    <span
      title={usefulness.rationale}
      className={cn(
        "inline-flex flex-col items-center rounded-xl px-2.5 py-1 leading-tight",
        BAND_TONES[usefulness.band],
        className
      )}
    >
      <span className="font-display text-base font-semibold tabular-nums">
        {usefulness.score}
      </span>
      <span className="text-[10px] font-medium">{BAND_LABELS[usefulness.band]}</span>
    </span>
  );
}
