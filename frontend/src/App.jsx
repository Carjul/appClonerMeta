import React, { useEffect, useMemo, useState } from "react";
import ConfigurationPage from "./pages/ConfigurationPage";
import CampaignsPage from "./pages/CampaignsPage";
import DailyReportPage from "./pages/DailyReportPage";
import FbCatalogModule from "./pages/FbCatalogModule";
import RulesEnginePage from "./pages/RulesEnginePage";

export default function App() {
  const [tab, setTab] = useState("campaigns");
  const [menuOpen, setMenuOpen] = useState(false);
  const [authUser, setAuthUser] = useState(null);

  useEffect(() => {
    fetch("/api/auth/me", { headers: { Accept: "application/json" } })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => setAuthUser(data?.user || null))
      .catch(() => setAuthUser(null));
  }, []);

  const title = useMemo(() => {
    if (tab === "configs") return "Configuración";
    if (tab === "fbCatalog") return "FB Catalog";
    if (tab === "daily") return "Dashboard";
    if (tab === "rules") return "Rules Engine";
    return "Campañas";
  }, [tab]);

  const navItems = [
    { id: "campaigns", label: "Clonar Campañas", icon: "📣", action: () => setTab("campaigns") },
    { id: "configs", label: "Configuración", icon: "⚙️", action: () => setTab("configs") },
    { id: "fbCatalog", label: "Crear Campañas", icon: "▣", action: () => { location.href = "/dashboard"; } },
    { id: "daily", label: "Dashboard", icon: "📊", action: () => {location.href = "/metricas";} },
    { id: "rules", label: "Rules", icon: "🧠", action: () => setTab("rules") },
  ];

  function selectNav(item) {
    item.action();
    setMenuOpen(false);
  }

  return (
    <div className="app">
      <header className="topbar">
        <h1 className="brand-title">
          <img className="brand-icon" src="/favicon.svg" alt="Meta Clonación" />
          <span>Meta Tool</span>
        </h1>
        <div className="topbar-actions">
          <div className="topbar-user">
            {authUser ? <span className="topbar-user-name">{authUser.name} · {authUser.role}</span> : null}
            <a href="/logout" className="topbar-logout">Salir</a>
          </div>
          <div className="hamburger-nav">
          <button className={`hamburger-btn ${menuOpen ? "active" : ""}`} onClick={() => setMenuOpen((open) => !open)} aria-label="Abrir menú" aria-expanded={menuOpen}>
            <span />
            <span />
            <span />
          </button>
          {menuOpen && <div className="tabs hamburger-menu">
            {navItems.map((item) => (
              <button key={item.id} className={`nav-tab ${tab === item.id ? "active" : ""}`} onClick={() => selectNav(item)}>
                <span className="nav-icon" aria-hidden="true">{item.icon}</span>
                <span>{item.label}</span>
              </button>
            ))}
          </div>}
          </div>
        </div>
      </header>
      <main className="content">
        {tab === "configs" && authUser?.role === "SuperAdmin" ? <ConfigurationPage /> : tab === "fbCatalog" ? <FbCatalogModule /> : tab === "daily" ? <DailyReportPage /> : tab === "rules" ? <RulesEnginePage /> : authUser?.role === "SuperAdmin" ? <ConfigurationPage />:<CampaignsPage />}
      </main>
    </div>
  );
}
