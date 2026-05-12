import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import "./globals.css";
import AppShell from "@/components/AppShell";
import EpisodeListPage from "@/pages/EpisodeListPage";
import EpisodeDetailPage from "@/pages/EpisodeDetailPage";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<EpisodeListPage />} />
          <Route path="/episodes/:episodeId" element={<EpisodeDetailPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);
