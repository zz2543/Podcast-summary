import { useEffect, useState } from "react";

import { EpisodeDetailPage } from "./pages/EpisodeDetailPage";
import { EpisodeListPage } from "./pages/EpisodeListPage";

export function App() {
  const [path, setPath] = useState(window.location.pathname);

  useEffect(() => {
    const updatePath = () => setPath(window.location.pathname);
    window.addEventListener("popstate", updatePath);
    return () => window.removeEventListener("popstate", updatePath);
  }, []);

  const detailMatch = path.match(/^\/episodes\/([^/]+)$/);
  if (detailMatch) {
    return <EpisodeDetailPage episodeId={decodeURIComponent(detailMatch[1])} />;
  }
  return <EpisodeListPage />;
}
