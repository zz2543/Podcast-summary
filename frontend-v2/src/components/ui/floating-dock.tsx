import { motion, useMotionValue, useSpring, useTransform } from "framer-motion";
import { useRef, type ReactNode } from "react";
import { cn } from "@/lib/cn";
import { useLiquidGlass } from "@/components/ui/liquid-glass";

export interface DockItem {
  id: string;
  icon: ReactNode;
  label: string;
  onClick?: () => void;
  disabled?: boolean;
  variant?: "default" | "danger";
}

export function FloatingDock({
  items,
  className
}: {
  items: DockItem[];
  className?: string;
}) {
  const mouseX = useMotionValue(Infinity);
  const dockRef = useLiquidGlass<HTMLDivElement>({
    bezel: 22,
    strength: 0.85,
    blur: 13
  });

  return (
    <motion.div
      ref={dockRef}
      onMouseMove={(e) => mouseX.set(e.pageX)}
      onMouseLeave={() => mouseX.set(Infinity)}
      style={{
        background: "rgba(255,255,255,0.38)",
        backdropFilter: "blur(13px) saturate(2) brightness(1.06) contrast(1.1)",
        WebkitBackdropFilter: "blur(13px) saturate(2) brightness(1.06) contrast(1.1)",
        border: "1px solid rgba(255,255,255,0.65)",
        boxShadow:
          "0 1px 0 rgba(255,255,255,0.95) inset, 0 -1px 0 rgba(255,255,255,0.45) inset, 0 12px 40px rgba(0,0,0,0.14), 0 2px 8px rgba(0,0,0,0.06)"
      }}
      className={cn(
        "fixed bottom-6 left-1/2 z-40 flex -translate-x-1/2 items-end gap-2 rounded-2xl px-3 py-2",
        className
      )}
    >
      {items.map((item) => (
        <DockButton key={item.id} mouseX={mouseX} item={item} />
      ))}
    </motion.div>
  );
}

function DockButton({
  mouseX,
  item
}: {
  mouseX: ReturnType<typeof useMotionValue<number>>;
  item: DockItem;
}) {
  const ref = useRef<HTMLButtonElement>(null);
  const distance = useTransform(mouseX, (v) => {
    const rect = ref.current?.getBoundingClientRect() ?? { x: 0, width: 0 };
    return v - rect.x - rect.width / 2;
  });
  const size = useSpring(useTransform(distance, [-80, 0, 80], [40, 56, 40]), {
    stiffness: 220,
    damping: 18
  });

  return (
    <motion.button
      ref={ref}
      type="button"
      onClick={item.onClick}
      disabled={item.disabled}
      style={{
        width: size,
        height: size,
        background: "rgba(255,255,255,0.22)",
        backdropFilter: "blur(6px) saturate(1.9) brightness(1.05)",
        WebkitBackdropFilter: "blur(6px) saturate(1.9) brightness(1.05)",
        border: "1px solid rgba(255,255,255,0.55)",
        boxShadow: "0 1px 0 rgba(255,255,255,0.85) inset"
      }}
      className={cn(
        "group relative flex items-center justify-center rounded-xl text-text transition-colors",
        "[&_svg]:stroke-[2] [&_svg]:text-text",
        "hover:bg-white/80 disabled:opacity-40 disabled:cursor-not-allowed",
        item.variant === "danger" && "hover:text-status-err [&:hover_svg]:text-status-err"
      )}
      title={item.label}
    >
      {item.icon}
      <span className="pointer-events-none absolute -top-9 whitespace-nowrap rounded-md bg-text px-2 py-1 text-xs font-medium text-white opacity-0 transition-opacity group-hover:opacity-100">
        {item.label}
      </span>
    </motion.button>
  );
}
