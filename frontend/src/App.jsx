import React, { useMemo, useState } from "react";
import ConfigurationPage from "./pages/ConfigurationPage";
import CampaignsPage from "./pages/CampaignsPage";

export default function App() {
  const [tab, setTab] = useState("campaigns");

  const title = useMemo(() => {
    if (tab === "configs") return "Configuración";
    return "Campañas";
  }, [tab]);

  return (
    <div className="app">
      <header className="topbar">
        <h1>Meta Clonación</h1>
        <div className="tabs">
          <button className={tab === "campaigns" ? "active" : ""} onClick={() => setTab("campaigns")}>Campañas</button>
          <button className={tab === "configs" ? "active" : ""} onClick={() => setTab("configs")}>Configuración</button>
        </div>
      </header>
      <main className="content">
        <h2>{title}</h2>
        {tab === "configs" ? <ConfigurationPage /> : <CampaignsPage />}
      </main>
    </div>
  );
}
