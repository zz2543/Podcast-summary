import { MutableRefObject } from "react";

import { EntitySummary, StageStatus } from "../api/client";

const GROUPS: Array<{ kind: EntitySummary["kind"]; title: string }> = [
  { kind: "person", title: "People" },
  { kind: "book", title: "Books" },
  { kind: "product", title: "Products" }
];

export function EntityPanel({
  entities,
  status,
  audioRef,
  onRetry
}: {
  entities: EntitySummary[];
  status: StageStatus;
  audioRef: MutableRefObject<HTMLAudioElement | null>;
  onRetry: () => Promise<void>;
}) {
  const seek = (timestamp: number | undefined) => {
    if (timestamp === undefined) return;
    const audio = audioRef.current;
    if (!audio) return;
    audio.currentTime = timestamp / 1000;
    void audio.play().catch(() => undefined);
  };

  return (
    <aside className="entity-panel">
      <h2>Entities</h2>
      {status !== "present" ? (
        <div className="entity-empty">
          <p>Entity recognition has not been generated.</p>
          <button className="text-button" type="button" onClick={() => void onRetry()}>
            Retry this stage
          </button>
        </div>
      ) : (
        <div className="entity-groups">
          {GROUPS.map((group) => {
            const items = entities.filter((entity) => entity.kind === group.kind);
            return (
              <section key={group.kind}>
                <h3>{group.title}</h3>
                {items.length === 0 ? (
                  <span className="entity-muted">None</span>
                ) : (
                  <div className="entity-chip-list">
                    {items.map((entity) => (
                      <button
                        className="entity-chip"
                        type="button"
                        key={`${entity.kind}-${entity.name}`}
                        onClick={() => seek(entity.sample_timestamps_ms?.[0])}
                      >
                        <span>{entity.name}</span>
                        <strong>× {entity.count}</strong>
                      </button>
                    ))}
                  </div>
                )}
              </section>
            );
          })}
        </div>
      )}
    </aside>
  );
}
