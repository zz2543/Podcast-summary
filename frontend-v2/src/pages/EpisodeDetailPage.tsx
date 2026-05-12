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
import { HoverBorderGradient } from "@/components/ui/hover-border-gradient";

export default function EpisodeDetailPage() {
  const { episodeId } = useParams();
  const navigate = useNavigate();
  const [episode, setEpisode] = useState<EpisodeDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const { jobsById, episodeStatuses } = useJobStream();

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
        <HoverBorderGradient onClick={handleDigest} disabled={busy}>
          <Sparkles className="mr-1.5 h-4 w-4" strokeWidth={1.6} />
          {digestReady
            ? "Regenerate audio digest"
            : digestFailed
            ? "Retry audio digest"
            : "Generate audio digest"}
        </HoverBorderGradient>
        {digestReady && episode.artifact_paths?.tts && (
          <AudioPlayer src={episodeFileUrl(episode.id, "digest")} />
        )}
      </section>

      <section className="space-y-2">
        <h2 className="font-display text-sm font-medium uppercase tracking-wider text-text-subtle">
          Original audio
        </h2>
        <AudioPlayer src={episodeFileUrl(episode.id, "audio")} />
      </section>

      <ThreeActPanel three_act={episode.three_act} />

      <ChaptersTimeline chapters={episode.chapters} />

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
