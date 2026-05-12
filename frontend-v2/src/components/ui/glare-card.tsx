import { useRef, useState, type ReactNode } from "react";
import { cn } from "@/lib/cn";

export function GlareCard({
  children,
  className
}: {
  children: ReactNode;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ x: 50, y: 50, on: false });

  return (
    <div
      ref={ref}
      onMouseMove={(e) => {
        const rect = ref.current?.getBoundingClientRect();
        if (!rect) return;
        const x = ((e.clientX - rect.left) / rect.width) * 100;
        const y = ((e.clientY - rect.top) / rect.height) * 100;
        setPos({ x, y, on: true });
      }}
      onMouseLeave={() => setPos((p) => ({ ...p, on: false }))}
      className={cn("relative overflow-hidden", className)}
    >
      {children}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 transition-opacity duration-300"
        style={{
          opacity: pos.on ? 1 : 0,
          background: `radial-gradient(420px circle at ${pos.x}% ${pos.y}%, rgba(255,255,255,0.55), rgba(255,255,255,0) 60%)`
        }}
      />
    </div>
  );
}
