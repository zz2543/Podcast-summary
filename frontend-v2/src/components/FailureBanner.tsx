import { useState } from "react";
import { AlertCircle, AlertTriangle, RotateCw } from "lucide-react";
import { cn } from "@/lib/cn";
import type { JobFailure } from "@/api/client";

/** 与 macOS 端 FailureNotice.swift 同一套文案：阶段名翻成人话，常见原因给一句建议。 */
const STAGE_LABELS: Record<string, string> = {
  fetch: "抓取音频",
  transcribe: "转写",
  summarize_hook: "生成一句话摘要",
  summarize_three_act: "生成三幕摘要",
  usefulness_score: "评分",
  chapter_outline: "划分章节",
  quote_verify: "核对引文",
  entity_extract: "抽取提及",
  export: "导出文件"
};

export function stageLabel(stage: string | null): string {
  return stage ? STAGE_LABELS[stage] ?? stage : "处理";
}

function hint(error: string): string | null {
  const e = error.toLowerCase();
  const has = (...needles: string[]) => needles.some((n) => e.includes(n));
  // 状态码只认独立的数字，免得撞上报错里的路径、时长或 ID
  const code = (...codes: string[]) => codes.some((c) => new RegExp(`\\b${c}\\b`).test(e));
  if (has("insufficient balance") || code("402")) return "模型服务余额不足。充值后点「重新处理」。";
  if (has("unauthorized", "forbidden", "is required", "invalid api key") || code("401", "403"))
    return "服务凭证无效或缺失，检查 .env 里对应的密钥。";
  if (has("too many requests", "rate limit") || code("429")) return "请求太频繁被限流了，过几分钟再重新处理。";
  if (
    has("connection reset", "connection aborted", "remote end closed", "timed out", "timeout",
        "writeerror", "readerror", "errno 54", "errno 60", "ssl", "eof occurred")
  )
    return "网络连接中途断了，通常是临时的，重新处理一般就能过。";
  if (has("file exists")) return "上一次处理留下的文件挡住了这一次，重新处理即可。";
  if (has("unsupported", "invalid audio", "audio convert failed"))
    return "音频格式识别不了，换个来源链接或本地文件再试。";
  return null;
}

/**
 * 两种语气：没有可读摘要时醒目（这就是这一集的全部状况）；
 * 摘要还在、只是最近一次重新处理没成时是轻提示（下面的内容仍然可信）。
 */
export function FailureBanner({
  failure,
  hasSummary,
  busy,
  onRetry
}: {
  failure: JobFailure;
  hasSummary: boolean;
  busy?: boolean;
  onRetry: () => void;
}) {
  const [showRaw, setShowRaw] = useState(false);
  const advice = hint(failure.error);
  const step = stageLabel(failure.stage);
  const Icon = hasSummary ? AlertCircle : AlertTriangle;

  return (
    <div
      className={cn(
        "flex gap-3 rounded-2xl border p-5",
        hasSummary ? "border-status-warn/30 bg-status-warn/5" : "border-status-err/30 bg-status-err/5"
      )}
    >
      <Icon
        className={cn("mt-0.5 h-5 w-5 shrink-0", hasSummary ? "text-status-warn" : "text-status-err")}
        strokeWidth={1.8}
      />
      <div className="min-w-0 space-y-2">
        <p className="font-medium text-text">
          {hasSummary
            ? `最近一次重新处理卡在「${step}」，下面仍是上一次的结果`
            : `处理卡在「${step}」这一步，还没有生成摘要`}
        </p>
        {advice && <p className="text-sm text-text-muted">{advice}</p>}
        {(showRaw || !advice) && (
          <pre className="whitespace-pre-wrap break-all font-mono text-xs text-text-subtle">
            {failure.error || "（后端没有留下报错信息）"}
          </pre>
        )}
        <div className="flex items-center gap-3 pt-1">
          <button
            type="button"
            onClick={onRetry}
            disabled={busy}
            className="inline-flex items-center gap-1.5 rounded-full bg-surface-elev px-3 py-1 text-xs font-medium text-text hover:shadow-card disabled:opacity-50"
          >
            <RotateCw className="h-3.5 w-3.5" strokeWidth={1.8} />
            重新处理
          </button>
          {advice && (
            <button
              type="button"
              onClick={() => setShowRaw((v) => !v)}
              className="text-xs text-text-muted underline"
            >
              {showRaw ? "收起原始报错" : "查看原始报错"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
