import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export function IridescentButton({
  children,
  onClick,
  disabled = false,
  size = "md",
  className
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  size?: "sm" | "md";
  className?: string;
}) {
  const padding = size === "sm" ? "px-4 py-2 text-sm" : "px-5 py-2.5 text-sm";
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={cn(
        "group relative inline-flex items-center justify-center overflow-hidden rounded-full",
        "shadow-card transition-transform hover:-translate-y-px hover:shadow-card-hover",
        "disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0",
        className
      )}
    >
      <span
        aria-hidden
        className="ai-iridescent absolute inset-0 rounded-full"
      />
      <span
        aria-hidden
        className="absolute inset-0 rounded-full bg-gradient-to-b from-white/15 via-transparent to-black/10"
      />
      <span
        className={cn(
          "relative z-10 flex items-center justify-center font-medium text-white drop-shadow-[0_1px_1px_rgba(0,0,0,0.18)]",
          padding
        )}
      >
        {children}
      </span>
    </button>
  );
}
