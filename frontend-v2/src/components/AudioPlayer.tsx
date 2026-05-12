import { Pause, Play } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/cn";

const SPEEDS = [0.75, 1, 1.25, 1.5, 2] as const;

export function AudioPlayer({ src }: { src: string }) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<(typeof SPEEDS)[number]>(1);
  const [progress, setProgress] = useState(0);
  const [duration, setDuration] = useState(0);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.playbackRate = speed;
  }, [speed]);

  return (
    <div className="rounded-2xl bg-surface p-3 shadow-card">
      <audio
        ref={audioRef}
        src={src}
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onTimeUpdate={(e) => setProgress(e.currentTarget.currentTime)}
        onLoadedMetadata={(e) => setDuration(e.currentTarget.duration)}
      />
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => {
            const a = audioRef.current;
            if (!a) return;
            if (a.paused) a.play();
            else a.pause();
          }}
          className="flex h-9 w-9 items-center justify-center rounded-full bg-text text-white transition-transform hover:scale-105"
        >
          {playing ? (
            <Pause className="h-4 w-4" strokeWidth={2} />
          ) : (
            <Play className="ml-0.5 h-4 w-4" strokeWidth={2} />
          )}
        </button>
        <div className="flex-1">
          <input
            type="range"
            min={0}
            max={duration || 0}
            step={0.1}
            value={progress}
            onChange={(e) => {
              const a = audioRef.current;
              if (a) a.currentTime = Number(e.target.value);
            }}
            className="w-full accent-text"
          />
          <div className="mt-0.5 flex justify-between font-mono text-xs text-text-muted">
            <span>{formatSec(progress)}</span>
            <span>{formatSec(duration)}</span>
          </div>
        </div>
        <div className="flex items-center gap-0.5 rounded-full bg-surface-elev p-0.5">
          {SPEEDS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setSpeed(s)}
              className={cn(
                "rounded-full px-2 py-1 text-xs font-medium transition-colors",
                s === speed ? "bg-text text-white" : "text-text-muted hover:text-text"
              )}
            >
              {s}×
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function formatSec(sec: number): string {
  if (!Number.isFinite(sec)) return "0:00";
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}
