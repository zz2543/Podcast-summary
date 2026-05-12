import { AnimatePresence, motion } from "framer-motion";
import { useState, type ReactNode } from "react";
import { cn } from "@/lib/cn";

export function Tooltip({
  label,
  children,
  className
}: {
  label: string;
  children: ReactNode;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  return (
    <span
      className={cn("relative inline-flex", className)}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      {children}
      <AnimatePresence>
        {open ? (
          <motion.span
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 2 }}
            transition={{ duration: 0.12 }}
            className="pointer-events-none absolute -top-9 left-1/2 z-50 -translate-x-1/2 whitespace-nowrap rounded-md bg-text px-2 py-1 text-xs font-medium text-white shadow-card"
          >
            {label}
          </motion.span>
        ) : null}
      </AnimatePresence>
    </span>
  );
}
