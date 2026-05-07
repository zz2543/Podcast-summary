import { MutableRefObject, useEffect, useMemo, useRef, useState } from "react";

import {
  ApiError,
  EpisodeDetail,
  Job,
  StageStatus,
  deleteEpisode,
  episodeFileUrl,
  getEpisode,
  retryEpisode,
  useJobs
} from "../api/client";
import { AppHeader } from "../components/AppHeader";

const STAGE_COPY: Record<string, string> = {
  hook: "one-line hook",
  three_act: "three-act summary",
  chapters: "chapter outline",
  entities: "entity extraction",
  tts: "audio digest"
};

export function EpisodeDetailPage({ episodeId }: { episodeId: string }) {
  const jobsState = useJobs();
  const [episode, setEpisode] = useState<EpisodeDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const activeCounts = useMemo(() => {
    const processing = jobsState.jobs.filter((job) => isActiveJob(job) && job.state !== "queued").length;
    const queued = jobsState.jobs.filter((job) => job.state === "queued").length;
    return { processing, queued };
  }, [jobsState.jobs]);

  const currentJob = jobsState.jobs.find((job) => job.episode_id === episodeId);

  const loadEpisode = async () => {
    setLoading(true);
    try {
      setEpisode(await getEpisode(episodeId));
      setError(null);
    } catch (loadError) {
      setError(errorMessage(loadError));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadEpisode();
    // loadEpisode intentionally closes over episodeId only for this route instance.
    // eslint-disable-next-line @typescript-eslint/no-floating-promises
  }, [episodeId]);

  useEffect(() => {
    const terminalUpdateSeen = jobsState.jobs.some(
      (job) => job.episode_id === episodeId && ["done", "partial", "failed"].includes(job.state)
    );
    if (terminalUpdateSeen) {
      void loadEpisode();
    }
    // eslint-disable-next-line @typescript-eslint/no-floating-promises
  }, [jobsState.jobs, episodeId]);

  useEffect(() => {
    if (toast === null) return;
    const timer = window.setTimeout(() => setToast(null), 3_000);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const onRetry = async () => {
    try {
      await retryEpisode(episodeId);
      setToast("Episode queued for retry");
      await loadEpisode();
    } catch (retryError) {
      setToast(errorMessage(retryError));
    }
  };

  const onDelete = async () => {
    if (!window.confirm("Delete this episode and all generated files? This cannot be undone.")) return;
    try {
      await deleteEpisode(episodeId);
      setToast("Episode deleted");
      window.history.pushState(null, "", "/");
      window.dispatchEvent(new PopStateEvent("popstate"));
    } catch (deleteError) {
      setToast(errorMessage(deleteError));
    }
  };

  return (
    <div className="app-shell detail-shell">
      <AppHeader
        connected={jobsState.connected}
        reconnecting={jobsState.lastError !== null}
        queueCounts={activeCounts}
        showBackLink
      />
      <main className="page page--detail">
        {loading ? <DetailSkeleton /> : null}
        {!loading && error ? <DetailError message={error} /> : null}
        {!loading && episode ? (
          <>
            <MetaHeader episode={episode} job={currentJob} />
            <HookCard episode={episode} onRetry={onRetry} />
            <section className="detail-content-grid">
              <div className="detail-main-column">
                <ThreeActSection episode={episode} onRetry={onRetry} />
                <ChapterStub status={episode.stage_status.chapters} onRetry={onRetry} />
              </div>
              <EntityStub status={episode.stage_status.entities} onRetry={onRetry} />
            </section>
            <ArtifactBar episode={episode} onRetry={onRetry} onDelete={onDelete} />
          </>
        ) : null}
      </main>
      {episode ? <StickyAudioBar episodeId={episode.id} audioRef={audioRef} /> : null}
      {toast ? (
        <button className="toast" type="button" onClick={() => setToast(null)}>
          {toast}
        </button>
      ) : null}
    </div>
  );
}

function MetaHeader({ episode, job }: { episode: EpisodeDetail; job?: Job }) {
  return (
    <section className="meta-header">
      <div className="cover-tile" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
      <div className="meta-main">
        <div className="meta-title-line">
          <h1>{episode.title ?? "Untitled episode"}</h1>
          <StatusPill label={statusLabel(job?.state ?? episode.status)} />
        </div>
        <p>
          {episode.podcast_name ?? "Podcast"} · {guestText(episode.guests)} · {formatDuration(episode.duration_seconds)} ·{" "}
          {sourceText(episode.source_ref)}
        </p>
      </div>
      <span className="language-tag">{languageLabel(episode.language)}</span>
    </section>
  );
}

function HookCard({ episode, onRetry }: { episode: EpisodeDetail; onRetry: () => Promise<void> }) {
  if (episode.stage_status.hook !== "present" || !episode.hook) {
    return <MissingStagePlaceholder stage="hook" status={episode.stage_status.hook} onRetry={onRetry} />;
  }
  return (
    <section className="hook-card">
      <span>One-Line Hook</span>
      <p>{episode.hook}</p>
      <small>Prompt version: {episode.prompt_versions.one_liner}</small>
    </section>
  );
}

function ThreeActSection({ episode, onRetry }: { episode: EpisodeDetail; onRetry: () => Promise<void> }) {
  if (episode.stage_status.three_act !== "present" || !episode.three_act) {
    return <MissingStagePlaceholder stage="three_act" status={episode.stage_status.three_act} onRetry={onRetry} />;
  }
  return (
    <section className="three-act-section">
      <SummaryCard index="I" title="Background" text={episode.three_act.background} />
      <SummaryCard index="II" title="Core Argument" text={episode.three_act.core_argument} />
      <SummaryCard index="III" title="Conclusion" text={episode.three_act.conclusion} />
    </section>
  );
}

function SummaryCard({ index, title, text }: { index: string; title: string; text: string }) {
  return (
    <article className="summary-card">
      <div>
        <span>{index}</span>
        <h2>{title}</h2>
      </div>
      <p>{text}</p>
    </article>
  );
}

function ChapterStub({ status, onRetry }: { status: StageStatus; onRetry: () => Promise<void> }) {
  if (status !== "present") {
    return <MissingStagePlaceholder stage="chapters" status={status} onRetry={onRetry} />;
  }
  return (
    <section className="chapter-stub">
      <header>
        <h2>Chapter Outline</h2>
        <span>US2</span>
      </header>
      <p>Chapter cards, quote timestamps, and jump-to-audio controls are reserved for the deep-dive stage.</p>
    </section>
  );
}

function EntityStub({ status, onRetry }: { status: StageStatus; onRetry: () => Promise<void> }) {
  return (
    <aside className="entity-panel">
      <h2>Key Information</h2>
      <dl>
        <div>
          <dt>Chapters</dt>
          <dd>{status === "present" ? "Ready" : "Not generated yet"}</dd>
        </div>
        <div>
          <dt>Entities</dt>
          <dd>US2 panel stub</dd>
        </div>
      </dl>
      {status !== "present" ? (
        <button className="text-button" type="button" onClick={() => void onRetry()}>
          Retry this stage
        </button>
      ) : null}
    </aside>
  );
}

function ArtifactBar({
  episode,
  onRetry,
  onDelete
}: {
  episode: EpisodeDetail;
  onRetry: () => Promise<void>;
  onDelete: () => Promise<void>;
}) {
  return (
    <section className="artifact-bar" aria-label="Episode files and actions">
      <a className="secondary-button artifact-button" href={episodeFileUrl(episode.id, "markdown")} download>
        ↓ Download Markdown
      </a>
      <a className="secondary-button artifact-button" href={episodeFileUrl(episode.id, "json")} download>
        ↓ Download JSON
      </a>
      <a className="secondary-button artifact-button" href={episodeFileUrl(episode.id, "audio")} download>
        ↓ Download Audio
      </a>
      <button className="secondary-button artifact-button" type="button" onClick={() => void onRetry()} disabled={!["failed", "partial"].includes(episode.status)}>
        ↻ Reprocess
      </button>
      <button className="secondary-button artifact-button artifact-button--danger" type="button" onClick={() => void onDelete()}>
        ⌫ Delete Episode
      </button>
    </section>
  );
}

function StickyAudioBar({
  episodeId,
  audioRef
}: {
  episodeId: string;
  audioRef: MutableRefObject<HTMLAudioElement | null>;
}) {
  const [speed, setSpeed] = useState("1");
  return (
    <div className="sticky-audio-bar">
      <audio ref={audioRef} controls src={episodeFileUrl(episodeId, "audio")} preload="metadata" />
      <label>
        <span className="sr-only">Playback speed</span>
        <select
          value={speed}
          onChange={(event) => {
            setSpeed(event.target.value);
            if (audioRef.current) audioRef.current.playbackRate = Number(event.target.value);
          }}
        >
          <option value="0.75">0.75×</option>
          <option value="1">1.0×</option>
          <option value="1.25">1.25×</option>
          <option value="1.5">1.5×</option>
          <option value="2">2.0×</option>
        </select>
      </label>
      <a className="icon-button" href={episodeFileUrl(episodeId, "audio")} download aria-label="Download original audio">
        ↓
      </a>
    </div>
  );
}

function MissingStagePlaceholder({
  stage,
  status,
  onRetry
}: {
  stage: keyof typeof STAGE_COPY;
  status: StageStatus;
  onRetry: () => Promise<void>;
}) {
  return (
    <section className="missing-stage">
      <strong>{STAGE_COPY[stage]} is not available</strong>
      <span>Status: {status}</span>
      <button className="text-button" type="button" onClick={() => void onRetry()}>
        Retry this stage
      </button>
    </section>
  );
}

function DetailSkeleton() {
  return (
    <div className="detail-skeleton">
      <span />
      <span />
      <span />
    </div>
  );
}

function DetailError({ message }: { message: string }) {
  return (
    <section className="empty-state">
      <h2>Episode not available</h2>
      <p>{message}</p>
      <button
        className="primary-button"
        type="button"
        onClick={() => {
          window.history.pushState(null, "", "/");
          window.dispatchEvent(new PopStateEvent("popstate"));
        }}
      >
        Back to list
      </button>
    </section>
  );
}

function StatusPill({ label }: { label: string }) {
  return <span className="status-badge status-badge--done">{label}</span>;
}

function statusLabel(value: string): string {
  if (value === "done") return "Completed";
  if (value === "partial") return "Partial";
  if (value === "failed") return "Failed";
  if (value === "queued" || value === "pending") return "Queued";
  return "Processing";
}

function guestText(guests: string[] | null): string {
  if (!guests || guests.length === 0) return "Guests pending";
  return `Guests: ${guests.join(", ")}`;
}

function formatDuration(durationSeconds: number | null): string {
  if (durationSeconds === null) return "Duration pending";
  const hours = Math.floor(durationSeconds / 3600);
  const minutes = Math.floor((durationSeconds % 3600) / 60);
  const seconds = Math.floor(durationSeconds % 60);
  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`;
  }
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

function sourceText(sourceRef: string): string {
  try {
    const url = new URL(sourceRef);
    return url.hostname;
  } catch {
    return "Local file";
  }
}

function languageLabel(language: EpisodeDetail["language"]): string {
  if (language === "zh") return "Chinese";
  if (language === "en") return "English";
  if (language === "mixed") return "Mixed";
  return "Language pending";
}

function isActiveJob(job: Job): boolean {
  return !["done", "partial", "failed"].includes(job.state);
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "not_found") return "The episode does not exist or was deleted.";
    if (error.code === "conflict") return "This episode already has an active job.";
    return error.message;
  }
  if (error instanceof Error) return error.message;
  return "Something went wrong. Refresh and try again.";
}
