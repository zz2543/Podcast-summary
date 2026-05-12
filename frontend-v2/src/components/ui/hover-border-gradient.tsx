import { motion } from "framer-motion";
import { useState, type ReactNode } from "react";
import { cn } from "@/lib/cn";

export function HoverBorderGradient({
  children,
  className,
  onClick,
  disabled = false
}: {
  children: ReactNode;
  className?: string;
  onClick?: () => void;
  disabled?: boolean;
}) {
  const [hover, setHover] = useState(false);

  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      className={cn(
        "group relative inline-flex items-center justify-center overflow-hidden rounded-full p-[1.5px] transition-opacity",
        disabled && "opacity-40",
        className
      )}
    >
      <motion.span
        aria-hidden
        animate={{
          background: hover
            ? "conic-gradient(from 0deg at 50% 50%, #1D1D1F, #86868B, #D2D2D7, #86868B, #1D1D1F)"
            : "linear-gradient(0deg, #1D1D1F, #1D1D1F)"
        }}
        transition={{ duration: 0.6, ease: "easeInOut", repeat: hover ? Infinity : 0 }}
        className="absolute inset-0 rounded-full"
      />
      <span className="relative z-10 flex items-center justify-center rounded-full bg-text px-5 py-2 text-sm font-medium text-white">
        {children}
      </span>
    </button>
  );
}
