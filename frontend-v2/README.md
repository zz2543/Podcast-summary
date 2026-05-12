# frontend-v2 — Apple-style preview

Parallel React + Vite + Tailwind frontend running alongside the existing `frontend/`.

- Port: **5174** (v1 stays on 5173)
- Backend: same `uvicorn` on `127.0.0.1:8000` via Vite proxy
- Design: pure white/gray monochrome, glass blur, Aceternity-style motion
- Status: experimental — keep both running side by side; pick the winner later

## Start

```bash
# from project root
make install-v2          # one time
make run-both            # backend + v1 + v2
# or
make run-v2              # backend + v2 only
```

Then open:

- v1: http://127.0.0.1:5173
- v2: http://127.0.0.1:5174

Both consume the same backend, so data shows up in both.

## Tech

React 19 · Vite 6 · TypeScript 5 · Tailwind 3 · framer-motion · lucide-react · react-router 7
