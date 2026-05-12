import { cn } from "@/lib/cn";
import type { EpisodeStatus } from "@/api/client";

const STATUS_COLOR: Record<EpisodeStatus, string> = {
  pending: "bg-text-subtle",
  processing: "bg-status-warn",
  done: "bg-status-ok",
  partial: "bg-status-warn",
  failed: "bg-status-err"
};

const STATUS_LABEL: Record<EpisodeStatus, string> = {
  pending: "Queued",
  processing: "Processing",
  done: "Done",
  partial: "Partial",
  failed: "Failed"
};

export function StatusDot({
  status,
  showLabel = true,
  className
}: {
  status: EpisodeStatus;
  showLabel?: boolean;
  className?: string;
}) {
  return (
    <span className={cn("inline-flex items-center gap-1.5", className)}>
      <span
        className={cn(
          "inline-block h-2 w-2 rounded-full",
          STATUS_COLOR[status],
          status === "processing" && "animate-pulse"
        )}
      />
      {showLabel && (
        <span className="text-xs font-medium text-text-muted">{STATUS_LABEL[status]}</span>
      )}
    </span>
  );
}
