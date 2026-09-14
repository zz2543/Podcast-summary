import { Link, Outlet } from "react-router-dom";
import { useLiquidGlass } from "@/components/ui/liquid-glass";

export default function AppShell() {
  const headerRef = useLiquidGlass<HTMLElement>({
    radius: 0,
    bezel: 14,
    strength: 0.55,
    blur: 10
  });

  return (
    <div className="relative min-h-screen">
      <BackgroundGrid />
      <header ref={headerRef} className="sticky top-0 z-30 glass">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-6">
          <Link
            to="/"
            className="font-display text-lg font-semibold tracking-tight text-text"
          >
            GotIt
          </Link>
        </div>
      </header>
      <main className="relative z-10 mx-auto max-w-6xl px-4 py-8 sm:px-6">
        <Outlet />
      </main>
    </div>
  );
}

function BackgroundGrid() {
  return (
    <>
      {/*
       * Refraction needs something to bend. A near-white page gives the bezel
       * nothing to work with, so a very faint colour wash sits under the grid.
       */}
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 z-0"
        style={{
          backgroundImage:
            "radial-gradient(60% 50% at 12% 0%, rgba(120,160,255,0.16), transparent 70%)," +
            "radial-gradient(50% 45% at 92% 12%, rgba(255,150,190,0.14), transparent 70%)," +
            "radial-gradient(55% 50% at 55% 100%, rgba(120,215,200,0.12), transparent 70%)"
        }}
      />
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 z-0 opacity-[0.35]"
        style={{
          backgroundImage:
            "radial-gradient(circle at 1px 1px, rgba(0,0,0,0.06) 1px, transparent 0)",
          backgroundSize: "32px 32px",
          maskImage:
            "radial-gradient(ellipse 80% 60% at 50% 0%, black 30%, transparent 100%)"
        }}
      />
    </>
  );
}
