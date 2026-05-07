import { useEffect, useRef, useState } from "react";

export type SourceType = "local_file" | "direct_url" | "youtube";
export type EpisodeStatus = "pending" | "processing" | "done" | "partial" | "failed";
export type JobState =
  | "queued"
  | "fetching"
  | "transcribing"
  | "summarizing"
  | "tts"
  | "done"
  | "partial"
  | "failed";
export type StageStatus = "pending" | "present" | "missing" | "failed_after_retries";

export interface StageStatusMap {
  hook: StageStatus;
  three_act: StageStatus;
  chapters: StageStatus;
  entities: StageStatus;
  tts: StageStatus;
}

export interface EpisodeSummary {
  id: string;
  title: string | null;
  podcast_name: string | null;
  source_type: SourceType;
  duration_seconds: number | null;
  language: "zh" | "en" | "mixed" | null;
  status: EpisodeStatus;
  stage_status: StageStatusMap;
  created_at: string;
  updated_at: string;
}

export interface ThreeAct {
  background: string;
  core_argument: string;
  conclusion: string;
}

export interface Quote {
  text: string;
  start_ms: number;
}

export interface Chapter {
  idx: number;
  title: string;
  start_ms: number;
  end_ms: number;
  key_points: string[];
  quotes: Quote[];
}

export interface EntitySummary {
  name: string;
  kind: "person" | "book" | "product";
  count: number;
  sample_timestamps_ms?: number[];
}

export interface EpisodeDetail extends EpisodeSummary {
  source_ref: string;
  guests: string[] | null;
  prompt_versions: {
    one_liner: string;
    three_act: string;
    chapter_outline: string;
    entity_extraction: string;
  };
  hook: string | null;
  three_act: ThreeAct | null;
  chapters: Chapter[];
  entities: EntitySummary[];
  artifact_paths?: {
    markdown?: string | null;
    json?: string | null;
    tts?: string | null;
  };
}

export interface Job {
  id: string;
  episode_id: string;
  state: JobState;
  stage_progress: Record<string, unknown>;
  attempt: number;
  error: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>;
  };
}

export class ApiError extends Error {
  status: number;
  code: string;
  details: Record<string, unknown>;

  constructor(status: number, body: ApiErrorBody) {
    super(body.error.message);
    this.name = "ApiError";
    this.status = status;
    this.code = body.error.code;
    this.details = body.error.details;
  }
}

export type CreateEpisodeInput =
  | { source_type: "local_file"; file: File }
  | { source_type: "direct_url" | "youtube"; source_ref: string };

export interface CreateEpisodeResponse {
  episode: EpisodeSummary;
  job: Job;
}

export type DigestResponse = Job | { tts_path: string; status: "present" };

export interface EpisodeListResponse {
  items: EpisodeSummary[];
  next_cursor: string | null;
}

export type JobEvent =
  | { type: "hello"; server_version: string; now: string }
  | { type: "snapshot"; jobs: Job[] }
  | { type: "job_update"; job: Job; episode_status: EpisodeStatus }
  | {
      type: "stage_status_update";
      episode_id: string;
      stage: keyof StageStatusMap;
      status: StageStatus;
    }
  | { type: "error"; code: string; message: string };

export interface UseJobsState {
  jobs: Job[];
  episodeStatuses: Record<string, EpisodeStatus>;
  connected: boolean;
  lastError: string | null;
}

export async function createEpisode(input: CreateEpisodeInput): Promise<CreateEpisodeResponse> {
  if (input.source_type === "local_file") {
    const form = new FormData();
    form.append("source_type", input.source_type);
    form.append("file", input.file);
    return apiFetch<CreateEpisodeResponse>("/api/episodes", {
      method: "POST",
      body: form
    });
  }

  return apiFetch<CreateEpisodeResponse>("/api/episodes", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(input)
  });
}

export function listEpisodes(params: {
  limit?: number;
  cursor?: string;
  status?: EpisodeStatus;
} = {}): Promise<EpisodeListResponse> {
  const search = new URLSearchParams();
  if (params.limit) search.set("limit", String(params.limit));
  if (params.cursor) search.set("cursor", params.cursor);
  if (params.status) search.set("status", params.status);
  const suffix = search.toString() ? `?${search.toString()}` : "";
  return apiFetch<EpisodeListResponse>(`/api/episodes${suffix}`);
}

export function getEpisode(id: string): Promise<EpisodeDetail> {
  return apiFetch<EpisodeDetail>(`/api/episodes/${encodeURIComponent(id)}`);
}

export async function deleteEpisode(id: string): Promise<void> {
  await apiFetch<void>(`/api/episodes/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export function retryEpisode(id: string): Promise<Job> {
  return apiFetch<Job>(`/api/episodes/${encodeURIComponent(id)}/retry`, { method: "POST" });
}

export function requestDigest(id: string): Promise<DigestResponse> {
  return apiFetch<DigestResponse>(`/api/episodes/${encodeURIComponent(id)}/digest`, {
    method: "POST"
  });
}

export function getJob(id: string): Promise<Job> {
  return apiFetch<Job>(`/api/jobs/${encodeURIComponent(id)}`);
}

export function episodeFileUrl(
  id: string,
  kind: "markdown" | "json" | "audio" | "digest"
): string {
  return `/api/episodes/${encodeURIComponent(id)}/files/${kind}`;
}

export function useJobs(): UseJobsState {
  const [jobsById, setJobsById] = useState<Record<string, Job>>({});
  const [episodeStatuses, setEpisodeStatuses] = useState<Record<string, EpisodeStatus>>({});
  const [connected, setConnected] = useState(false);
  const [lastError, setLastError] = useState<string | null>(null);
  const reconnectDelay = useRef(250);

  useEffect(() => {
    let stopped = false;
    let socket: WebSocket | null = null;
    let timer: number | undefined;

    const scheduleReconnect = () => {
      if (stopped) return;
      const delay = reconnectDelay.current;
      reconnectDelay.current = Math.min(delay * 2, 4_000);
      timer = window.setTimeout(connect, delay);
    };

    const connect = () => {
      socket = new WebSocket(wsEndpoint("/api/ws/jobs"));
      socket.onopen = () => {
        reconnectDelay.current = 250;
        setConnected(true);
        setLastError(null);
      };
      socket.onmessage = (event) => {
        handleJobEvent(JSON.parse(event.data) as JobEvent, setJobsById, setEpisodeStatuses, setLastError);
      };
      socket.onerror = () => setLastError("WebSocket connection error");
      socket.onclose = () => {
        setConnected(false);
        scheduleReconnect();
      };
    };

    connect();
    return () => {
      stopped = true;
      if (timer !== undefined) window.clearTimeout(timer);
      socket?.close();
    };
  }, []);

  return {
    jobs: Object.values(jobsById),
    episodeStatuses,
    connected,
    lastError
  };
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    let body: ApiErrorBody = {
      error: { code: "internal", message: response.statusText, details: {} }
    };
    try {
      body = (await response.json()) as ApiErrorBody;
    } catch {
      // Keep the status text fallback.
    }
    throw new ApiError(response.status, body);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function handleJobEvent(
  event: JobEvent,
  setJobsById: (updater: (previous: Record<string, Job>) => Record<string, Job>) => void,
  setEpisodeStatuses: (
    updater: (previous: Record<string, EpisodeStatus>) => Record<string, EpisodeStatus>
  ) => void,
  setLastError: (message: string | null) => void
) {
  if (event.type === "snapshot") {
    setJobsById(() => Object.fromEntries(event.jobs.map((job) => [job.id, job])));
    return;
  }
  if (event.type === "job_update") {
    setJobsById((previous) => ({ ...previous, [event.job.id]: event.job }));
    setEpisodeStatuses((previous) => ({
      ...previous,
      [event.job.episode_id]: event.episode_status
    }));
    return;
  }
  if (event.type === "error") {
    setLastError(event.message);
  }
}

function wsEndpoint(path: string): string {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}${path}`;
}
