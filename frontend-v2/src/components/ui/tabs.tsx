import { motion } from "framer-motion";
import { useState, type ReactNode } from "react";
import { cn } from "@/lib/cn";

export interface TabItem {
  id: string;
  label: ReactNode;
  content: ReactNode;
}

export function Tabs({
  items,
  defaultId,
  className,
  onChange
}: {
  items: TabItem[];
  defaultId?: string;
  className?: string;
  onChange?: (id: string) => void;
}) {
  const [active, setActive] = useState(defaultId ?? items[0]?.id);

  return (
    <div className={cn("w-full", className)}>
      <div className="flex items-center gap-1 rounded-full bg-surface-elev p-1">
        {items.map((item) => {
          const isActive = item.id === active;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => {
                setActive(item.id);
                onChange?.(item.id);
              }}
              className={cn(
                "relative flex-1 rounded-full px-4 py-2 text-sm font-medium transition-colors",
                isActive ? "text-text" : "text-text-muted hover:text-text"
              )}
            >
              {isActive && (
                <motion.span
                  layoutId="tab-pill"
                  className="absolute inset-0 rounded-full bg-surface shadow-card"
                  transition={{ type: "spring", stiffness: 380, damping: 32 }}
                />
              )}
              <span className="relative">{item.label}</span>
            </button>
          );
        })}
      </div>
      <div className="mt-6">{items.find((i) => i.id === active)?.content}</div>
    </div>
  );
}
