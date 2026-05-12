import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export function BentoGrid({
  children,
  className
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4",
        className
      )}
    >
      {children}
    </div>
  );
}

export function BentoCell({
  children,
  className,
  span,
  onClick
}: {
  children: ReactNode;
  className?: string;
  span?: "wide" | "tall" | "full";
  onClick?: () => void;
}) {
  const spanCls =
    span === "wide" ? "sm:col-span-2" : span === "tall" ? "row-span-2" : span === "full" ? "col-span-full" : "";
  return (
    <div
      onClick={onClick}
      className={cn(
        "group relative overflow-hidden rounded-2xl bg-surface shadow-card transition-all duration-300",
        onClick && "cursor-pointer hover:-translate-y-0.5 hover:shadow-card-hover",
        spanCls,
        className
      )}
    >
      {children}
    </div>
  );
}
