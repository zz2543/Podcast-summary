import { MutableRefObject, useState } from "react";

import { Chapter } from "../api/client";
import { QuoteChip } from "./QuoteChip";

export function ChapterCard({
  chapter,
  defaultExpanded,
  audioRef
}: {
  chapter: Chapter;
  defaultExpanded: boolean;
  audioRef: MutableRefObject<HTMLAudioElement | null>;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  const seekToChapter = () => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.currentTime = chapter.start_ms / 1000;
    void audio.play().catch(() => undefined);
  };

  return (
    <article className="chapter-card">
      <header>
        <button className="chapter-index-button" type="button" onClick={seekToChapter}>
          ▶ {chapter.idx + 1}
        </button>
        <div>
          <h3>{chapter.title}</h3>
          <span>
            {formatTimestamp(chapter.start_ms)}–{formatTimestamp(chapter.end_ms)}
          </span>
        </div>
        <button className="chapter-collapse-button" type="button" onClick={() => setExpanded(!expanded)}>
          {expanded ? "⌃" : "⌄"}
        </button>
      </header>
      {expanded ? (
        <div className="chapter-card-body">
          <section>
            <h4>Key Points</h4>
            <ul>
              {chapter.key_points.map((point) => (
                <li key={point}>{point}</li>
              ))}
            </ul>
          </section>
          {chapter.quotes.length > 0 ? (
            <section>
              <h4>Quotes</h4>
              <div className="quote-list">
                {chapter.quotes.map((quote) => (
                  <QuoteChip key={`${quote.start_ms}-${quote.text}`} quote={quote} audioRef={audioRef} />
                ))}
              </div>
            </section>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}

function formatTimestamp(value: number): string {
  const totalSeconds = Math.max(0, Math.floor(value / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes.toString().padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`;
}
