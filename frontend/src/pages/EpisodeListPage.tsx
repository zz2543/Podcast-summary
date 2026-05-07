import { ChangeEvent, DragEvent, FormEvent, ReactNode, useEffect, useMemo, useRef, useState } from "react";

import {
  ApiError,
  CreateEpisodeInput,
  EpisodeDetail,
  EpisodeStatus,
  EpisodeSummary,
  Job,
  SourceType,
  createEpisode,
  createEpisodeBatch,
  deleteEpisode,
  getEpisode,
  listEpisodes,
  retryEpisode,
  useJobs
} from "../api/client";
import { AppHeader } from "../components/AppHeader";

type SubmitMode = "local_file" | "direct_url" | "youtube";
type FilterStatus = "all" | EpisodeStatus;

const STATUS_LABELS: Record<EpisodeStatus, string> = {
  pending: "Queued",
  processing: "Processing",
  done: "Completed",
  partial: "Partial",
  failed: "Failed"
};

const STAGE_LABELS: Record<string, string> = {
  fetching: "Fetch",
  transcribing: "Transcribe",
  summarizing: "Summarize",
  tts: "TTS",
  queued: "Queued"
};

const MAX_FILE_BYTES = 1_073_741_824;
const SUPPORTED_AUDIO_EXTENSIONS = [".mp3", ".m4a", ".wav"];

export function EpisodeListPage() {
  const jobsState = useJobs();
  const [episodes, setEpisodes] = useState<EpisodeSummary[]>([]);
  const [detailsById, setDetailsById] = useState<Record<string, EpisodeDetail>>({});
  const [filter, setFilter] = useState<FilterStatus>("all");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<string | null>(null);
  const gridRef = useRef<HTMLDivElement | null>(null);

  const jobsByEpisode = useMemo(() => {
    return Object.fromEntries(jobsState.jobs.map((job) => [job.episode_id, job]));
  }, [jobsState.jobs]);

  const activeCounts = useMemo(() => {
    const processing = jobsState.jobs.filter((job) => isActiveJob(job) && job.state !== "queued").length;
    const queued = jobsState.jobs.filter((job) => job.state === "queued").length;
    return { processing, queued };
  }, [jobsState.jobs]);

  const loadEpisodes = async (status: FilterStatus = filter) => {
    setLoading(true);
    try {
      const response = await listEpisodes(status === "all" ? {} : { status });
      setEpisodes(response.items);
    } catch (error) {
      setToast(errorMessage(error));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadEpisodes(filter);
  }, [filter]);

  useEffect(() => {
    const terminalUpdateSeen = jobsState.jobs.some((job) => ["done", "partial", "failed"].includes(job.state));
    if (terminalUpdateSeen) {
      void loadEpisodes(filter);
    }
  }, [jobsState.jobs]);

  useEffect(() => {
    const loadDetails = async () => {
      const candidates = episodes.filter(
        (episode) =>
          (resolvedStatus(episode, jobsState.episodeStatuses) === "done" ||
            resolvedStatus(episode, jobsState.episodeStatuses) === "partial") &&
          detailsById[episode.id] === undefined
      );
      const entries = await Promise.all(
        candidates.map(async (episode) => {
          try {
            return [episode.id, await getEpisode(episode.id)] as const;
          } catch {
            return null;
          }
        })
      );
      const validEntries = entries.filter((entry): entry is readonly [string, EpisodeDetail] => entry !== null);
      if (validEntries.length > 0) {
        setDetailsById((previous) => ({ ...previous, ...Object.fromEntries(validEntries) }));
      }
    };

    void loadDetails();
  }, [detailsById, episodes, jobsState.episodeStatuses]);

  useEffect(() => {
    if (toast === null) return;
    const timer = window.setTimeout(() => setToast(null), 3_000);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const filteredEpisodes = episodes.filter((episode) => {
    const haystack = [episode.title, episode.podcast_name, detailsById[episode.id]?.hook]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystack.includes(query.trim().toLowerCase());
  });

  const submitInputs = async (inputs: CreateEpisodeInput[]) => {
    for (const input of inputs) {
      if (inputs.length === 1) {
        await createEpisode(input);
      }
    }
    if (inputs.length > 1) {
      await createEpisodeBatch(inputs);
    }
    setToast(inputs.length === 1 ? "Episode added to the queue" : `${inputs.length} episodes added to the queue`);
    await loadEpisodes(filter);
  };

  const onRetry = async (episodeId: string) => {
    try {
      await retryEpisode(episodeId);
      setToast("Episode queued for retry");
      await loadEpisodes(filter);
    } catch (error) {
      setToast(errorMessage(error));
    }
  };

  const onDelete = async (episodeId: string) => {
    try {
      await deleteEpisode(episodeId);
      setEpisodes((previous) => previous.filter((episode) => episode.id !== episodeId));
      setToast("Episode deleted");
    } catch (error) {
      setToast(errorMessage(error));
    }
  };

  const onOpen = (episodeId: string) => {
    window.history.pushState(null, "", `/episodes/${episodeId}`);
    window.dispatchEvent(new PopStateEvent("popstate"));
  };

  const onQueueClick = () => {
    const firstActive = gridRef.current?.querySelector<HTMLElement>("[data-active='true']");
    firstActive?.scrollIntoView({ behavior: "smooth", block: "center" });
    firstActive?.classList.add("episode-row--flash");
    window.setTimeout(() => firstActive?.classList.remove("episode-row--flash"), 900);
  };

  return (
    <div className="app-shell">
      <AppHeader
        connected={jobsState.connected}
        queueCounts={activeCounts}
        reconnecting={jobsState.lastError !== null}
        onQueueClick={onQueueClick}
      />
      <main className="page page--list">
        <SubmitPanel onSubmit={submitInputs} onToast={setToast} />
        <section className="filter-bar" aria-label="Episode filters">
          <div className="filter-pills">
            <FilterButton active={filter === "all"} onClick={() => setFilter("all")}>
              All
            </FilterButton>
            <FilterButton active={filter === "processing"} onClick={() => setFilter("processing")}>
              Processing
            </FilterButton>
            <FilterButton active={filter === "done"} onClick={() => setFilter("done")}>
              Completed
            </FilterButton>
            <FilterButton active={filter === "partial"} onClick={() => setFilter("partial")}>
              Partial
            </FilterButton>
            <FilterButton active={filter === "failed"} onClick={() => setFilter("failed")}>
              Failed
            </FilterButton>
          </div>
          <label className="search-box">
            <span className="sr-only">Search processed episodes</span>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search processed episodes..."
            />
            <span aria-hidden="true">⌕</span>
          </label>
        </section>
        <section className="episode-grid" ref={gridRef} aria-label="Episode list">
          {loading ? (
            <EpisodeSkeleton />
          ) : filteredEpisodes.length === 0 && episodes.length === 0 ? (
            <EmptyState />
          ) : filteredEpisodes.length === 0 ? (
            <div className="empty-card">
              <strong>No matching episodes</strong>
              <span>Adjust the filter or search terms.</span>
            </div>
          ) : (
            filteredEpisodes.map((episode) => {
              const job = jobsByEpisode[episode.id];
              const status = resolvedStatus(episode, jobsState.episodeStatuses);
              return (
                <EpisodeRow
                  key={episode.id}
                  episode={episode}
                  detail={detailsById[episode.id]}
                  job={job}
                  status={status}
                  onOpen={onOpen}
                  onRetry={onRetry}
                  onDelete={onDelete}
                />
              );
            })
          )}
        </section>
      </main>
      {toast ? (
        <button className="toast" type="button" onClick={() => setToast(null)}>
          {toast}
        </button>
      ) : null}
    </div>
  );
}

function SubmitPanel({
  onSubmit,
  onToast
}: {
  onSubmit: (inputs: CreateEpisodeInput[]) => Promise<void>;
  onToast: (message: string) => void;
}) {
  const [mode, setMode] = useState<SubmitMode>("local_file");
  const [files, setFiles] = useState<File[]>([]);
  const [directUrls, setDirectUrls] = useState("");
  const [youtubeUrls, setYoutubeUrls] = useState("");
  const [validation, setValidation] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const pendingCount =
    mode === "local_file"
      ? files.length
      : parseLines(mode === "direct_url" ? directUrls : youtubeUrls).length;

  const onFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const nextFiles = Array.from(event.target.files ?? []);
    addFiles(nextFiles);
    event.target.value = "";
  };

  const addFiles = (nextFiles: File[]) => {
    const error = validateFiles(nextFiles);
    if (error) {
      setValidation(error);
      return;
    }
    setFiles((previous) => [...previous, ...nextFiles]);
    setValidation(null);
  };

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    addFiles(Array.from(event.dataTransfer.files));
  };

  const onSubmitForm = async (event: FormEvent) => {
    event.preventDefault();
    const inputs = buildInputs(mode, files, directUrls, youtubeUrls);
    const error = validateInputs(inputs, mode);
    if (error) {
      setValidation(error);
      return;
    }
    setBusy(true);
    setValidation(null);
    try {
      await onSubmit(inputs);
      setFiles([]);
      setDirectUrls("");
      setYoutubeUrls("");
    } catch (error) {
      onToast(errorMessage(error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="submit-panel" onSubmit={onSubmitForm}>
      <div className="tabs" role="tablist" aria-label="Submission type">
        <TabButton active={mode === "local_file"} onClick={() => setMode("local_file")}>
          <span aria-hidden="true">□</span> Local Files
        </TabButton>
        <TabButton active={mode === "direct_url"} onClick={() => setMode("direct_url")}>
          <span aria-hidden="true">↗</span> Audio Links
        </TabButton>
        <TabButton active={mode === "youtube"} onClick={() => setMode("youtube")}>
          <span aria-hidden="true">▶</span> YouTube
        </TabButton>
      </div>
      <div className="submit-body">
        {mode === "local_file" ? (
          <>
            <div
              className="dropzone"
              onDragOver={(event) => event.preventDefault()}
              onDrop={onDrop}
              role="button"
              tabIndex={0}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") fileInputRef.current?.click();
              }}
            >
              <input
                ref={fileInputRef}
                className="sr-only"
                type="file"
                multiple
                accept=".mp3,.m4a,.wav,audio/mpeg,audio/mp4,audio/wav"
                onChange={onFileChange}
              />
              <span className="upload-cloud" aria-hidden="true">
                ⇧
              </span>
              <strong>Drop audio files here</strong>
              <span>or</span>
              <button className="secondary-button" type="button" onClick={() => fileInputRef.current?.click()}>
                Choose Files
              </button>
              <small>Supports mp3 / m4a / wav, each file up to 1 GB</small>
            </div>
            <FileChipList files={files} onRemove={(index) => setFiles(files.filter((_, itemIndex) => itemIndex !== index))} />
          </>
        ) : (
          <textarea
            className="url-input"
            value={mode === "direct_url" ? directUrls : youtubeUrls}
            onChange={(event) =>
              mode === "direct_url" ? setDirectUrls(event.target.value) : setYoutubeUrls(event.target.value)
            }
            placeholder={
              mode === "direct_url"
                ? "Paste direct audio links, one per line. Supports .mp3 / .m4a / .wav"
                : "Paste YouTube video links, one per line"
            }
          />
        )}
      </div>
      <div className="submit-footer">
        <div>
          <strong>Concurrency: 3</strong>
          <span> running at once, adjustable with MAX_CONCURRENCY in .env</span>
          {validation ? <p className="validation-text">{validation}</p> : null}
        </div>
        <button className="primary-button" type="submit" disabled={busy || pendingCount === 0}>
          {busy ? "Adding..." : "Start Processing"}
        </button>
      </div>
    </form>
  );
}

function EpisodeRow({
  episode,
  detail,
  job,
  status,
  onOpen,
  onRetry,
  onDelete
}: {
  episode: EpisodeSummary;
  detail?: EpisodeDetail;
  job?: Job;
  status: EpisodeStatus;
  onOpen: (episodeId: string) => void;
  onRetry: (episodeId: string) => void;
  onDelete: (episodeId: string) => void;
}) {
  const active = status === "processing" || status === "pending";
  return (
    <article
      className="episode-row"
      data-active={active ? "true" : "false"}
      onClick={() => onOpen(episode.id)}
      role="button"
      tabIndex={0}
      onKeyDown={(event) => {
        if (event.key === "Enter") onOpen(episode.id);
      }}
    >
      <div className={`source-orb source-orb--${episode.source_type}`} aria-hidden="true">
        {sourceIcon(episode.source_type)}
      </div>
      <div className="episode-main">
        <div className="episode-title-row">
          <h2>{episodeTitle(episode)}</h2>
          <StatusBadge status={status} />
        </div>
        <p className="episode-meta">
          {episode.podcast_name ?? sourceLabel(episode.source_type)} · {formatDuration(episode.duration_seconds)} ·{" "}
          {formatDate(episode.created_at)}
        </p>
        {active ? (
          <JobProgressBar job={job} />
        ) : status === "failed" ? (
          <p className="episode-error">Processing failed. Retry from the latest checkpoint.</p>
        ) : (
          <p className="episode-hook">
            {detail?.hook ?? (status === "partial" ? "Partial summary is ready." : "Open details to read the summary.")}
          </p>
        )}
      </div>
      <div className="episode-actions" onClick={(event) => event.stopPropagation()}>
        <button className="icon-button" type="button" aria-label="Open details" onClick={() => onOpen(episode.id)}>
          ▶
        </button>
        {(status === "failed" || status === "partial") && (
          <button className="icon-button" type="button" aria-label="Retry episode" onClick={() => onRetry(episode.id)}>
            ↻
          </button>
        )}
        <button className="icon-button icon-button--danger" type="button" aria-label="Delete episode" onClick={() => onDelete(episode.id)}>
          ⌫
        </button>
      </div>
    </article>
  );
}

function JobProgressBar({ job }: { job?: Job }) {
  const percent = progressPercent(job);
  const stage = job?.state ? (STAGE_LABELS[job.state] ?? job.state) : "Queued";
  return (
    <div className="job-progress" title={`${stage}: ${percent}%`}>
      <div className="progress-label">
        <span>
          {stage} · {percent}%
        </span>
      </div>
      <div className="progress-track">
        <span style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: EpisodeStatus }) {
  return <span className={`status-badge status-badge--${status}`}>{STATUS_LABELS[status]}</span>;
}

function FilterButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button className={`filter-pill ${active ? "filter-pill--active" : ""}`} type="button" onClick={onClick}>
      {children}
    </button>
  );
}

function TabButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button className={`tab-button ${active ? "tab-button--active" : ""}`} type="button" role="tab" aria-selected={active} onClick={onClick}>
      {children}
    </button>
  );
}

function FileChipList({ files, onRemove }: { files: File[]; onRemove: (index: number) => void }) {
  if (files.length === 0) {
    return (
      <div className="file-list file-list--empty">
        <span>No files selected yet.</span>
      </div>
    );
  }
  return (
    <div className="file-list" aria-label="Selected files">
      {files.map((file, index) => (
        <div className="file-chip" key={`${file.name}-${file.size}-${index}`}>
          <span aria-hidden="true">♫</span>
          <strong>{file.name}</strong>
          <small>{formatBytes(file.size)}</small>
          <button type="button" aria-label={`Remove ${file.name}`} onClick={() => onRemove(index)}>
            ×
          </button>
        </div>
      ))}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="empty-state">
      <div className="empty-illustration" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
      <h2>No episodes yet</h2>
      <p>Drop the first podcast into the submission panel and the summary will appear here.</p>
    </div>
  );
}

function EpisodeSkeleton() {
  return (
    <>
      {[0, 1, 2].map((item) => (
        <div className="episode-row episode-row--skeleton" key={item}>
          <div className="skeleton-orb" />
          <div className="skeleton-lines">
            <span />
            <span />
            <span />
          </div>
        </div>
      ))}
    </>
  );
}

function buildInputs(mode: SubmitMode, files: File[], directUrls: string, youtubeUrls: string): CreateEpisodeInput[] {
  if (mode === "local_file") {
    return files.map((file) => ({ source_type: "local_file", file }));
  }
  const sourceType = mode === "direct_url" ? "direct_url" : "youtube";
  return parseLines(sourceType === "direct_url" ? directUrls : youtubeUrls).map((source_ref) => ({
    source_type: sourceType,
    source_ref
  }));
}

function validateInputs(inputs: CreateEpisodeInput[], mode: SubmitMode): string | null {
  if (inputs.length === 0) return "Select a file or paste at least one link.";
  if (mode !== "local_file") {
    const invalid = inputs.some((input) => input.source_type !== "local_file" && !isValidUrl(input.source_ref));
    if (invalid) return "One or more links are invalid.";
  }
  return null;
}

function validateFiles(files: File[]): string | null {
  for (const file of files) {
    const lowerName = file.name.toLowerCase();
    if (!SUPPORTED_AUDIO_EXTENSIONS.some((extension) => lowerName.endsWith(extension))) {
      return "Only mp3 / m4a / wav files are supported.";
    }
    if (file.size > MAX_FILE_BYTES) {
      return "A file exceeds the 1 GB limit. Compress it and try again.";
    }
  }
  return null;
}

function parseLines(value: string): string[] {
  return value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

function isValidUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

function resolvedStatus(episode: EpisodeSummary, episodeStatuses: Record<string, EpisodeStatus>): EpisodeStatus {
  return episodeStatuses[episode.id] ?? episode.status;
}

function episodeTitle(episode: EpisodeSummary): string {
  if (episode.title) return episode.title;
  return `Untitled episode · ${sourceLabel(episode.source_type)}`;
}

function sourceLabel(sourceType: SourceType): string {
  if (sourceType === "local_file") return "Local file";
  if (sourceType === "direct_url") return "Audio link";
  return "YouTube";
}

function sourceIcon(sourceType: SourceType): string {
  if (sourceType === "direct_url") return "↗";
  if (sourceType === "youtube") return "▶";
  return "♫";
}

function formatDuration(durationSeconds: number | null): string {
  if (durationSeconds === null) return "Duration pending";
  const minutes = Math.floor(durationSeconds / 60);
  const seconds = Math.floor(durationSeconds % 60);
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function formatBytes(value: number): string {
  if (value < 1_000_000) return `${Math.round(value / 1_000)} KB`;
  return `${(value / 1_000_000).toFixed(1)} MB`;
}

function progressPercent(job?: Job): number {
  if (!job) return 0;
  if (job.state === "done") return 100;
  if (job.state === "failed") return 100;
  if (job.state === "queued") return 5;
  const numericValues = Object.values(job.stage_progress).filter((value): value is number => typeof value === "number");
  if (numericValues.length > 0) {
    const bounded = Math.max(0, Math.min(100, Math.round(Math.max(...numericValues))));
    return bounded;
  }
  const stateBase: Partial<Record<Job["state"], number>> = {
    fetching: 15,
    transcribing: 45,
    summarizing: 72,
    tts: 88,
    partial: 100
  };
  return stateBase[job.state] ?? 10;
}

function isActiveJob(job: Job): boolean {
  return !["done", "partial", "failed"].includes(job.state);
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "payload_too_large") return "The file exceeds the 1 GB / 6 hour limit.";
    if (error.code === "unsupported_media") return "Unsupported file or link type.";
    if (error.code === "conflict") return "This episode is already processing or already exists.";
    if (error.code === "not_found") return "The episode no longer exists.";
    return error.message;
  }
  if (error instanceof Error) return error.message;
  return "Something went wrong. Refresh and try again.";
}
