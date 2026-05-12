import { AnimatePresence, motion } from "framer-motion";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { cn } from "@/lib/cn";

type ModalContextValue = {
  open: boolean;
  setOpen: (open: boolean) => void;
};

const ModalContext = createContext<ModalContextValue | null>(null);

export function Modal({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return <ModalContext.Provider value={{ open, setOpen }}>{children}</ModalContext.Provider>;
}

function useModal() {
  const ctx = useContext(ModalContext);
  if (!ctx) throw new Error("Modal subcomponents must be used inside <Modal>");
  return ctx;
}

export function ModalTrigger({
  children,
  className
}: {
  children: ReactNode;
  className?: string;
}) {
  const { setOpen } = useModal();
  return (
    <button type="button" onClick={() => setOpen(true)} className={className}>
      {children}
    </button>
  );
}

export function ModalBody({
  children,
  className
}: {
  children: ReactNode;
  className?: string;
}) {
  const { open, setOpen } = useModal();

  useEffect(() => {
    if (!open) return;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    if (open) window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, setOpen]);

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18 }}
          className="fixed inset-0 z-50 flex items-center justify-center px-4"
          style={{
            backgroundColor: "rgba(0,0,0,0.32)",
            backdropFilter: "blur(8px)",
            WebkitBackdropFilter: "blur(8px)"
          }}
          onClick={() => setOpen(false)}
        >
          <motion.div
            initial={{ scale: 0.95, opacity: 0, y: 8 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.97, opacity: 0, y: 4 }}
            transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
            onClick={(e) => e.stopPropagation()}
            className={cn(
              "relative w-full max-w-2xl rounded-3xl bg-surface shadow-glass",
              className
            )}
          >
            {children}
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

export function ModalContent({
  children,
  className
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={cn("p-6", className)}>{children}</div>;
}

export function ModalFooter({
  children,
  className
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex items-center justify-end gap-3 border-t border-black/5 px-6 py-4", className)}>
      {children}
    </div>
  );
}

export function useModalControls() {
  return useModal();
}
