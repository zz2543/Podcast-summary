import type { Usefulness, UsefulnessBand } from "../api/client";

export const BAND_LABELS: Record<UsefulnessBand, string> = {
  must_listen: "Must listen",
  worth_listening: "Worth listening",
  skimmable: "Skimmable",
  skippable: "Skippable"
};

/**
 * FR-027 usefulness badge. `usefulness === null` renders the muted "Not rated"
 * state — a missing score is never shown as 0, which is a real score.
 * Colour is never the only signal: number and label always ship together.
 */
export function ScoreBadge({ usefulness }: { usefulness: Usefulness | null }) {
  if (!usefulness) {
    return (
      <span className="score-badge score-badge--unrated" title="Not rated yet">
        Not rated
      </span>
    );
  }
  return (
    <span
      className={`score-badge score-badge--${usefulness.band}`}
      title={usefulness.rationale}
    >
      <strong>{usefulness.score}</strong>
      <span>{BAND_LABELS[usefulness.band]}</span>
    </span>
  );
}
