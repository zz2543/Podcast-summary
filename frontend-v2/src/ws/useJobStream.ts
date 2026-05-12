import { useEffect, useRef, useState } from "react";
import {
  wsEndpoint,
  type EpisodeStatus,
  type Job,
  type JobEvent,
  type StageStatus,
  type StageStatusMap
} from "@/api/client";

export interface StageEvent {
  episode_id: string;
  stage: keyof StageStatusMap;
  status: StageStatus;
  at: number;
}

export interface JobStreamState {
  jobs: Job[];
  jobsById: Record<string, Job>;
  episodeStatuses: Record<string, EpisodeStatus>;
  recentStageEvents: StageEvent[];
  connected: boolean;
  lastError: string | null;
}

export function useJobStream(): JobStreamState {
  const [jobsById, setJobsById] = useState<Record<string, Job>>({});
  const [episodeStatuses, setEpisodeStatuses] = useState<Record<string, EpisodeStatus>>({});
  const [recentStageEvents, setRecentStageEvents] = useState<StageEvent[]>([]);
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
      reconnectDelay.current = Math.min(delay * 2, 4000);
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
        const data = JSON.parse(event.data) as JobEvent;
        if (data.type === "snapshot") {
          setJobsById(() => Object.fromEntries(data.jobs.map((j) => [j.id, j])));
        } else if (data.type === "job_update") {
          setJobsById((prev) => ({ ...prev, [data.job.id]: data.job }));
          setEpisodeStatuses((prev) => ({
            ...prev,
            [data.job.episode_id]: data.episode_status
          }));
        } else if (data.type === "stage_status_update") {
          setRecentStageEvents((prev) =>
            [
              {
                episode_id: data.episode_id,
                stage: data.stage,
                status: data.status,
                at: Date.now()
              },
              ...prev
            ].slice(0, 20)
          );
        } else if (data.type === "error") {
          setLastError(data.message);
        }
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
    jobsById,
    episodeStatuses,
    recentStageEvents,
    connected,
    lastError
  };
}
