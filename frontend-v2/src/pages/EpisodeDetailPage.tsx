import { ArrowLeft, Sparkles } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ApiError,
  deleteEpisode,
  episodeFileUrl,
  getEpisode,
  requestDigest,
  retryEpisode,
  type EpisodeDetail
} from "@/api/client";
import { useJobStream } from "@/ws/useJobStream";
import { HookHero } from "@/components/HookHero";
import { ThreeActPanel } from "@/components/ThreeActPanel";
import { ChaptersTimeline } from "@/components/ChaptersTimeline";
import { EntityCloud } from "@/components/EntityCloud";
import { EpisodeDock } from "@/components/EpisodeDock";
import { AudioPlayer } from "@/components/AudioPlayer";
import { IridescentButton } from "@/components/ui/iridescent-button";
import type { AudioControls } from "@/components/AudioPlayer";
import { useRef } from "react";

export default function EpisodeDetailPage() {
  const { episodeId } = useParams();
  const navigate = useNavigate();
  const [episode, setEpisode] = useState<EpisodeDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const { jobsById, episodeStatuses } = useJobStream();
  const originalAudioRef = useRef<AudioControls>(null);
  const audioSectionRef = useRef<HTMLElement>(null);

  const load = useCallback(async () => {
    if (!episodeId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getEpisode(episodeId);
      setEpisode(data);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load episode");
    } finally {
      setLoading(false);
    }
  }, [episodeId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!episode) return;
    const status = episodeStatuses[episode.id];
    if (status && status !== episode.status) {
      load();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [Object.values(jobsById).map((j) => j.state).join("|")]);

  const handleRetry = async () => {
    if (!episode) return;
    setBusy(true);
    setToast(null);
    try {
      await retryEpisode(episode.id);
      setToast("Retry queued");
    } catch (e) {
      setToast(e instanceof ApiError ? e.message : "Retry failed");
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async () => {
    if (!episode) return;
    if (!confirm(`Delete "${episode.title || "this episode"}"?`)) return;
    setBusy(true);
    try {
      await deleteEpisode(episode.id);
      navigate("/");
    } catch (e) {
      setToast(e instanceof ApiError ? e.message : "Delete failed");
      setBusy(false);
    }
  };

  const handleDigest = async () => {
    if (!episode) return;
    setBusy(true);
    setToast(null);
    try {
      const response = await requestDigest(episode.id);
      setToast("status" in response ? "Audio digest ready" : "Audio digest queued");
    } catch (e) {
      setToast(e instanceof ApiError ? e.message : "Digest failed");
    } finally {
      setBusy(false);
    }
  };

  if (loading && !episode) {
    return <div className="text-sm text-text-muted">Loading…</div>;
  }
  if (error || !episode) {
    return (
      <div className="space-y-3">
        <div className="text-sm text-status-err">{error ?? "Episode not found"}</div>
        <Link to="/" className="text-sm text-text-muted underline">
          Back to library
        </Link>
      </div>
    );
  }

  const digestReady = episode.stage_status.tts === "present";
  const digestFailed = episode.stage_status.tts === "failed_after_retries";

  return (
    <div className="space-y-10 pb-32">
      <Link
        to="/"
        className="inline-flex items-center gap-1.5 text-sm text-text-muted hover:text-text"
      >
        <ArrowLeft className="h-4 w-4" strokeWidth={1.6} />
        Library
      </Link>

      <HookHero episode={episode} />

      <section className="flex flex-wrap items-center gap-3">
        <IridescentButton onClick={handleDigest} disabled={busy}>
          <Sparkles className="mr-1.5 h-4 w-4" strokeWidth={1.8} />
          {digestReady
            ? "Regenerate audio digest"
            : digestFailed
            ? "Retry audio digest"
            : "Generate audio digest"}
        </IridescentButton>
        {digestReady && episode.artifact_paths?.tts && (
          <AudioPlayer src={episodeFileUrl(episode.id, "digest")} variant="ai" />
        )}
      </section>

      <section
        ref={audioSectionRef}
        className="sticky top-[60px] z-20 -mx-4 px-4 py-2 sm:-mx-6 sm:px-6"
      >
        <div
          className="rounded-2xl"
          style={{
            background: "rgba(255,255,255,0.55)",
            backdropFilter: "blur(24px) saturate(200%)",
            WebkitBackdropFilter: "blur(24px) saturate(200%)",
            border: "1px solid rgba(255,255,255,0.55)",
            boxShadow:
              "0 1px 0 rgba(255,255,255,0.8) inset, 0 8px 28px rgba(0,0,0,0.08)"
          }}
        >
          <div className="flex items-center justify-between px-4 pt-2.5">
            <span className="font-display text-xs font-medium uppercase tracking-wider text-text-subtle">
              Original audio
            </span>
          </div>
          <div className="p-2">
            <AudioPlayer
              src={episodeFileUrl(episode.id, "audio")}
              ref={originalAudioRef}
              transparent
            />
          </div>
        </div>
      </section>

      <ThreeActPanel three_act={episode.three_act} />

      <ChaptersTimeline
        chapters={episode.chapters}
        onQuoteClick={(ms) => {
          originalAudioRef.current?.seekTo(ms / 1000);
          originalAudioRef.current?.play();
          audioSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
        }}
      />

      <EntityCloud entities={episode.entities} />

      {toast && (
        <div className="fixed bottom-24 left-1/2 z-40 -translate-x-1/2 rounded-full bg-text px-4 py-2 text-sm font-medium text-white shadow-card">
          {toast}
        </div>
      )}

      <EpisodeDock
        episode={episode}
        onRetry={handleRetry}
        onDelete={handleDelete}
        busy={busy}
      />
    </div>
  );
}
