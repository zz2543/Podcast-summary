import { MutableRefObject, useState } from "react";

import { Quote } from "../api/client";

export function QuoteChip({
  quote,
  audioRef
}: {
  quote: Quote;
  audioRef: MutableRefObject<HTMLAudioElement | null>;
}) {
  const [flashing, setFlashing] = useState(false);

  const seek = () => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.currentTime = quote.start_ms / 1000;
    void audio.play().catch(() => undefined);
    setFlashing(true);
    window.setTimeout(() => setFlashing(false), 1_000);
  };

  return (
    <button className={`quote-chip ${flashing ? "quote-chip--flash" : ""}`} type="button" onClick={seek}>
      <span>{formatTimestamp(quote.start_ms)}</span>
      <q>{quote.text}</q>
    </button>
  );
}

function formatTimestamp(value: number): string {
  const totalSeconds = Math.max(0, Math.floor(value / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes.toString().padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`;
}
