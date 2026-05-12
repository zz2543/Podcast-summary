import { motion, useScroll, useSpring, useTransform } from "framer-motion";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { cn } from "@/lib/cn";

export function TracingBeam({
  children,
  className
}: {
  children: ReactNode;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end end"] });
  const [height, setHeight] = useState(0);

  useEffect(() => {
    if (ref.current) setHeight(ref.current.offsetHeight);
  }, []);

  const y1 = useSpring(useTransform(scrollYProgress, [0, 0.8], [50, height]), {
    stiffness: 500,
    damping: 90
  });
  const y2 = useSpring(useTransform(scrollYProgress, [0, 1], [50, height - 200]), {
    stiffness: 500,
    damping: 90
  });

  return (
    <motion.div ref={ref} className={cn("relative w-full", className)}>
      <div className="absolute -left-2 top-3 hidden md:block">
        <motion.div
          transition={{ duration: 0.2 }}
          animate={{ boxShadow: scrollYProgress.get() > 0 ? "none" : "0 0 0 4px white" }}
          className="ml-1.5 flex h-3 w-3 items-center justify-center rounded-full border border-border bg-white"
        >
          <motion.div
            transition={{ duration: 0.2 }}
            className="h-1.5 w-1.5 rounded-full bg-text-subtle"
          />
        </motion.div>
        <svg viewBox={`0 0 20 ${height}`} width="20" height={height} className="ml-2 block" aria-hidden>
          <motion.path
            d={`M 1 0 V ${height}`}
            fill="none"
            stroke="#E5E5E7"
            strokeOpacity="0.7"
            transition={{ duration: 10 }}
          />
          <motion.path
            d={`M 1 0 V ${height}`}
            fill="none"
            stroke="#86868B"
            strokeWidth="1.25"
            strokeLinecap="round"
            style={{
              pathLength: useTransform([y1, y2] as any, ([a, b]: number[]) => (b - a) / Math.max(height, 1))
            }}
            transition={{ duration: 10 }}
          />
        </svg>
      </div>
      <div className="md:ml-6">{children}</div>
    </motion.div>
  );
}
