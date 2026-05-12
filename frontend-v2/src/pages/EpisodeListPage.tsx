import { Search } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useJobStream } from "@/ws/useJobStream";
import {
  ApiError,
  listEpisodes,
  type EpisodeStatus,
  type EpisodeSummary
} from "@/api/client";
import { SubmitModal } from "@/components/SubmitModal";
import { EpisodeCard } from "@/components/EpisodeCard";
import { ActiveJobsStrip } from "@/components/ActiveJobsStrip";
import { BentoGrid, BentoCell } from "@/components/ui/bento-grid";
import { cn } from "@/lib/cn";

type Filter = "all" | "processing" | "done" | "partial" | "failed";

const FILTERS: { id: Filter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "processing", label: "Running" },
  { id: "done", label: "Done" },
  { id: "partial", label: "Partial" },
  { id: "failed", label: "Failed" }
];

export default function EpisodeListPage() {
  const [episodes, setEpisodes] = useState<EpisodeSummary[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const { jobs, episodeStatuses, connected } = useJobStream();

  const fetchEpisodes = useCallback(
    async (reset = false) => {
      setLoading(true);
      setError(null);
      try {
        const params = filter === "all" ? {} : { status: filter as EpisodeStatus };
        const data = await listEpisodes({
          limit: 24,
          cursor: reset ? undefined : cursor ?? undefined,
          ...params
        });
        setEpisodes((prev) => (reset ? data.items : [...prev, ...data.items]));
        setCursor(data.next_cursor);
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Failed to load");
      } finally {
        setLoading(false);
      }
    },
    [filter, cursor]
  );

  useEffect(() => {
    setEpisodes([]);
    setCursor(null);
    fetchEpisodes(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter]);

  useEffect(() => {
    const terminal = jobs.some((j) => ["done", "partial", "failed"].includes(j.state));
    if (terminal) {
      fetchEpisodes(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobs.map((j) => `${j.id}:${j.state}`).join("|")]);

  const titleByEpisode = useMemo(
    () => Object.fromEntries(episodes.map((e) => [e.id, e.title])),
    [episodes]
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return episodes;
    return episodes.filter((e) =>
      [e.title, e.podcast_name].filter(Boolean).some((v) => v!.toLowerCase().includes(q))
    );
  }, [episodes, query]);

  return (
    <div className="space-y-6">
      <Toolbar
        connected={connected}
        query={query}
        onQuery={setQuery}
        filter={filter}
        onFilter={setFilter}
        onSubmitted={() => fetchEpisodes(true)}
      />

      <ActiveJobsStrip jobs={jobs} titleByEpisode={titleByEpisode} />

      {error && (
        <div className="rounded-xl bg-status-err/10 px-4 py-3 text-sm text-status-err">
          {error}
        </div>
      )}

      {filtered.length === 0 && !loading ? (
        <EmptyState />
      ) : (
        <BentoGrid>
          {filtered.map((e) => (
            <EpisodeCard
              key={e.id}
              episode={e}
              status={episodeStatuses[e.id] ?? e.status}
            />
          ))}
          {loading && (
            <BentoCell className="h-44 animate-pulse bg-surface-elev">
              <span />
            </BentoCell>
          )}
        </BentoGrid>
      )}

      {cursor && !loading && (
        <div className="flex justify-center pt-2">
          <button
            type="button"
            onClick={() => fetchEpisodes(false)}
            className="rounded-full bg-surface px-5 py-2 text-sm font-medium text-text shadow-card hover:shadow-card-hover"
          >
            Load more
          </button>
        </div>
      )}
    </div>
  );
}

function Toolbar({
  connected,
  query,
  onQuery,
  filter,
  onFilter,
  onSubmitted
}: {
  connected: boolean;
  query: string;
  onQuery: (q: string) => void;
  filter: Filter;
  onFilter: (f: Filter) => void;
  onSubmitted: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <div className="relative min-w-[220px] flex-1">
        <Search
          className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-subtle"
          strokeWidth={1.6}
        />
        <input
          value={query}
          onChange={(e) => onQuery(e.target.value)}
          placeholder="Search episodes…"
          className="w-full rounded-full border border-border bg-surface py-2 pl-9 pr-3 text-sm outline-none transition-colors focus:border-text/40 focus:bg-white"
        />
      </div>
      <div className="flex items-center gap-1 rounded-full bg-surface-elev p-1">
        {FILTERS.map((f) => (
          <button
            key={f.id}
            type="button"
            onClick={() => onFilter(f.id)}
            className={cn(
              "rounded-full px-3 py-1 text-xs font-medium transition-colors",
              filter === f.id ? "bg-surface text-text shadow-card" : "text-text-muted hover:text-text"
            )}
          >
            {f.label}
          </button>
        ))}
      </div>
      <span
        className={cn(
          "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium",
          connected ? "bg-status-ok/10 text-status-ok" : "bg-surface-elev text-text-subtle"
        )}
      >
        <span
          className={cn(
            "h-1.5 w-1.5 rounded-full",
            connected ? "bg-status-ok" : "bg-text-subtle"
          )}
        />
        {connected ? "Live" : "Offline"}
      </span>
      <SubmitModal onSubmitted={onSubmitted} />
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl bg-surface px-6 py-20 text-center shadow-card">
      <div className="font-display text-xl font-semibold text-text">
        No episodes yet
      </div>
      <p className="mt-2 max-w-md text-sm text-text-muted">
        Drop an audio file, paste a URL, or add a YouTube link to start your library.
      </p>
    </div>
  );
}
