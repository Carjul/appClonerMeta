import React, { useMemo, useState } from "react";
import ConfigurationPage from "./pages/ConfigurationPage";
import CampaignsPage from "./pages/CampaignsPage";
import DailyReportPage from "./pages/DailyReportPage";
import RulesEnginePage from "./pages/RulesEnginePage";

export default function App() {
  const [tab, setTab] = useState("campaigns");

  const title = useMemo(() => {
    if (tab === "configs") return "Configuración";
    if (tab === "daily") return "Dashboard";
    if (tab === "rules") return "Rules Engine";
    return "Campañas";
  }, [tab]);

  return (
    <div className="app">
      <header className="topbar">
        <h1 className="brand-title">
          <img className="brand-icon" src="/favicon.svg" alt="Meta Clonación" />
          <span>Meta Tool</span>
        </h1>
        <div className="tabs">
          <button className={`nav-tab ${tab === "campaigns" ? "active" : ""}`} onClick={() => setTab("campaigns")}>
            <span className="nav-icon" aria-hidden="true">📣</span>
            <span>Campañas</span>
          </button>
          <button className={`nav-tab ${tab === "configs" ? "active" : ""}`} onClick={() => setTab("configs")}>
            <span className="nav-icon" aria-hidden="true">⚙️</span>
            <span>Configuración</span>
          </button>
          <button className={`nav-tab ${tab === "daily" ? "active" : ""}`} onClick={() => setTab("daily")}>
            <span className="nav-icon" aria-hidden="true">📊</span>
            <span>Dashboard</span>
          </button>
          <button className={`nav-tab ${tab === "rules" ? "active" : ""}`} onClick={() => setTab("rules")}>
            <span className="nav-icon" aria-hidden="true">🧠</span>
            <span>Rules</span>
          </button>
        </div>
      </header>
      <main className="content">
{/*         <h2>{title}</h2> */}
        {tab === "configs" ? <ConfigurationPage /> : tab === "daily" ? <DailyReportPage /> : tab === "rules" ? <RulesEnginePage /> : <CampaignsPage />}
      </main>
    </div>
  );
}
