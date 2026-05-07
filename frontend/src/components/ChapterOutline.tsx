import { MutableRefObject } from "react";

import { Chapter } from "../api/client";
import { ChapterCard } from "./ChapterCard";

export function ChapterOutline({
  chapters,
  audioRef
}: {
  chapters: Chapter[];
  audioRef: MutableRefObject<HTMLAudioElement | null>;
}) {
  if (chapters.length === 0) {
    return (
      <section className="chapter-stub">
        <header>
          <h2>Chapter Outline</h2>
          <span>Empty</span>
        </header>
        <p>No chapters were generated for this episode.</p>
      </section>
    );
  }

  return (
    <section className="chapter-outline">
      <header className="section-heading">
        <h2>Chapter Outline</h2>
        <span>{chapters.length} chapters</span>
      </header>
      <div className="chapter-list">
        {chapters.map((chapter, index) => (
          <ChapterCard
            key={`${chapter.idx}-${chapter.title}`}
            chapter={chapter}
            defaultExpanded={index < 3}
            audioRef={audioRef}
          />
        ))}
      </div>
    </section>
  );
}
