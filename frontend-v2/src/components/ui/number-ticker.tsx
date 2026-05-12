import { animate, useMotionValue, useTransform, motion } from "framer-motion";
import { useEffect } from "react";

export function NumberTicker({
  value,
  duration = 0.8,
  className
}: {
  value: number;
  duration?: number;
  className?: string;
}) {
  const mv = useMotionValue(0);
  const rounded = useTransform(mv, (v) => Math.round(v).toString());

  useEffect(() => {
    const controls = animate(mv, value, { duration, ease: [0.22, 1, 0.36, 1] });
    return () => controls.stop();
  }, [value, duration, mv]);

  return <motion.span className={className}>{rounded}</motion.span>;
}
