import { Link, Outlet } from "react-router-dom";

export default function AppShell() {
  return (
    <div className="relative min-h-screen">
      <BackgroundGrid />
      <header className="sticky top-0 z-30 glass">
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
  );
}
