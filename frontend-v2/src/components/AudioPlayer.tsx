import { Pause, Play } from "lucide-react";
import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import { cn } from "@/lib/cn";

const SPEEDS = [0.75, 1, 1.25, 1.5, 2] as const;

export interface AudioControls {
  seekTo: (sec: number) => void;
  play: () => void;
  pause: () => void;
}

export const AudioPlayer = forwardRef<
  AudioControls,
  { src: string; transparent?: boolean; variant?: "default" | "ai" }
>(function AudioPlayer({ src, transparent = false, variant = "default" }, ref) {
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

  useImperativeHandle(
    ref,
    () => ({
      seekTo: (sec: number) => {
        const a = audioRef.current;
        if (!a) return;
        a.currentTime = Math.max(0, sec);
      },
      play: () => {
        audioRef.current?.play().catch(() => undefined);
      },
      pause: () => {
        audioRef.current?.pause();
      }
    }),
    []
  );

  return (
    <div
      className={cn(
        "rounded-2xl p-3",
        transparent ? "bg-transparent" : "bg-surface shadow-card"
      )}
    >
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
          className={cn(
            "relative flex h-9 w-9 items-center justify-center overflow-hidden rounded-full text-white transition-transform hover:scale-105",
            variant === "ai" ? "shadow-card" : "bg-text"
          )}
        >
          {variant === "ai" && (
            <>
              <span aria-hidden className="ai-iridescent absolute inset-0 rounded-full" />
              <span
                aria-hidden
                className="absolute inset-0 rounded-full bg-gradient-to-b from-white/15 via-transparent to-black/10"
              />
            </>
          )}
          <span className="relative z-10 inline-flex items-center justify-center drop-shadow-[0_1px_1px_rgba(0,0,0,0.18)]">
            {playing ? (
              <Pause className="h-4 w-4" strokeWidth={2} />
            ) : (
              <Play className="ml-0.5 h-4 w-4" strokeWidth={2} />
            )}
          </span>
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
          {SPEEDS.map((s) => {
            const active = s === speed;
            return (
              <button
                key={s}
                type="button"
                onClick={() => setSpeed(s)}
                className={cn(
                  "relative overflow-hidden rounded-full px-2 py-1 text-xs font-medium transition-colors",
                  active
                    ? variant === "ai"
                      ? "text-white"
                      : "bg-text text-white"
                    : "text-text-muted hover:text-text"
                )}
              >
                {active && variant === "ai" && (
                  <span
                    aria-hidden
                    className="ai-iridescent absolute inset-0 rounded-full"
                  />
                )}
                <span className="relative z-10">{s}×</span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
});

function formatSec(sec: number): string {
  if (!Number.isFinite(sec)) return "0:00";
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}
