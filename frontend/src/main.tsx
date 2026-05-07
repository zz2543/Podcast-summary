import React from "react";
import ReactDOM from "react-dom/client";

import { EpisodeListPage } from "./pages/EpisodeListPage";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <EpisodeListPage />
  </React.StrictMode>
);
