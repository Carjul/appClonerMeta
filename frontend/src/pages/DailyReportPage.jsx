import React from "react";
import { api } from "../api";

const PERIODS = ["today", "yesterday", "lifetime"];
const DATE_LABELS = {
  today: "Hoy",
  yesterday: "Ayer",
  lifetime: "Mes",
};

function money(v) {
  const n = Number(v || 0);
  return `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function percent(v) {
  const n = Number(v || 0);
  return `${n >= 0 ? "+" : ""}${n.toFixed(1)}%`;
}

function signClass(v) {
  const n = Number(v || 0);
  if (n > 0) return "vg";
  if (n < 0) return "vr";
  return "zero";
}

function normalizeRows(rows = [], bmLabel = "BM") {
  return rows
    .map((r) => {
      const spend = Number(r?.spend || 0);
      const revenue = Number(r?.revenue || 0);
      const purchases = Number(r?.purchases || 0);
      const profit = revenue - spend;
      const cpa = purchases > 0 ? spend / purchases : null;
      const roi = spend > 0 ? ((revenue - spend) / spend) * 100 : null;
      return {
        id: String(r?.id || `${r?.name || "Cuenta"}-${r?.bm || "BM"}`),
        name: String(r?.name || "Cuenta"),
        bm: bmLabel,
        spend,
        revenue,
        purchases,
        profit,
        cpa,
        roi,
      };
    })
    .filter((r) => r.spend > 0)
    .sort((a, b) => b.spend - a.spend);
}

function mergeReports(reportA, reportB, period) {
  const pA = (reportA?.periods || {})[period] || { rows: [] };
  const pB = (reportB?.periods || {})[period] || { rows: [] };
  const rows = [
    ...normalizeRows(pA.rows || [], "BM1"),
    ...normalizeRows(pB.rows || [], "BM2"),
  ].sort((a, b) => b.spend - a.spend);

  const spend = rows.reduce((s, r) => s + r.spend, 0);
  const revenue = rows.reduce((s, r) => s + r.revenue, 0);
  const purchases = rows.reduce((s, r) => s + r.purchases, 0);
  const roi = spend > 0 ? ((revenue - spend) / spend) * 100 : 0;
  const cpa = purchases > 0 ? spend / purchases : null;

  return {
    rows,
    summary: {
      campaigns: rows.length,
      spend,
      revenue,
      purchases,
      roi,
      cpa,
      profit: revenue - spend,
    },
  };
}

export default function DailyReportPage() {
  const [configs, setConfigs] = React.useState([]);
  const [configIds, setConfigIds] = React.useState([]);
  const [period, setPeriod] = React.useState("today");
  const [reportByConfig, setReportByConfig] = React.useState({});
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");
  const [sortCol, setSortCol] = React.useState("spend");
  const [sortAsc, setSortAsc] = React.useState(false);
  const [lightMode, setLightMode] = React.useState(false);

  React.useEffect(() => {
    let alive = true;
    api
      .listConfigs()
      .then((rows) => {
        if (!alive) return;
        const all = rows || [];
        setConfigs(all);
        setConfigIds(all.slice(0, 2).map((c) => c._id));
      })
      .catch((e) => {
        if (!alive) return;
        setError(String(e.message || e));
      });
    return () => {
      alive = false;
    };
  }, []);

  const configA = React.useMemo(() => configs.find((c) => c._id === configIds[0]) || null, [configs, configIds]);
  const configB = React.useMemo(() => configs.find((c) => c._id === configIds[1]) || null, [configs, configIds]);

  const loadLatest = React.useCallback(async () => {
    if (configIds.length === 0) return;
    setLoading(true);
    setError("");
    try {
      const calls = configIds.map(async (id) => {
        const res = await api.getDailyReportLatest(id);
        return [id, res?.report || null];
      });
      const out = await Promise.all(calls);
      setReportByConfig(Object.fromEntries(out));
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }, [configIds]);

  React.useEffect(() => {
    loadLatest();
  }, [loadLatest]);

  const runNow = React.useCallback(async () => {
    if (configIds.length === 0) return;
    setLoading(true);
    setError("");
    try {
      const calls = configIds.map(async (id) => {
        const res = await api.runDailyReport(id, PERIODS);
        return [id, res?.report || null];
      });
      const out = await Promise.all(calls);
      setReportByConfig(Object.fromEntries(out));
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }, [configIds]);

  const merged = React.useMemo(() => {
    return mergeReports(reportByConfig[configIds[0]], reportByConfig[configIds[1]], period);
  }, [reportByConfig, configIds, period]);

  const sortedRows = React.useMemo(() => {
    const rows = [...(merged.rows || [])];
    rows.sort((a, b) => {
      let va = a[sortCol];
      let vb = b[sortCol];
      if (va === null) va = -Infinity;
      if (vb === null) vb = -Infinity;
      if (typeof va === "string") return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
      return sortAsc ? Number(va) - Number(vb) : Number(vb) - Number(va);
    });
    return rows;
  }, [merged.rows, sortCol, sortAsc]);

  function onSort(col) {
    if (sortCol === col) {
      setSortAsc((s) => !s);
      return;
    }
    setSortCol(col);
    setSortAsc(col === "name" || col === "bm");
  }

  function sortArrow(col) {
    if (sortCol !== col) return "";
    return sortAsc ? " ▲" : " ▼";
  }

  const summary = merged.summary || {};

  return (
    <div className={`dashboard-shell ${lightMode ? "dashboard-light" : ""}`}>
      <section className="dashboard-panel">
        <div className="dashboard-header">
          <h4>Meta Ads Dashboard</h4>
          <div className="dashboard-header-right">
            <div className={`dashboard-status ${loading ? "loading" : ""}`}>
              <span className="dot" />
              <span>{loading ? "Actualizando..." : "Listo"}</span>
            </div>
            <button className="refresh-btn" onClick={runNow} disabled={loading} title="Actualizar ahora">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="23 4 23 10 17 10" />
                <polyline points="1 20 1 14 7 14" />
                <path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15" />
              </svg>
            </button>
            <div className="date-f">
              {PERIODS.map((p) => (
                <button key={p} className={`date-b ${period === p ? "active" : ""}`} onClick={() => setPeriod(p)} disabled={loading}>
                  {DATE_LABELS[p]}
                </button>
              ))}
            </div>
            <button className="theme-t" onClick={() => setLightMode((m) => !m)} title="Cambiar modo oscuro/claro" />
          </div>
        </div>

        <div className="dashboard-configs">
          <span className="cfg-chip">BM1: {configA?.name || "-"}</span>
          <span className="cfg-chip cfg-chip-b2">BM2: {configB?.name || "-"}</span>
        </div>

        {error ? <div className="alert error">{error}</div> : null}

        <div className="sgrid">
          <div className="scard">
            <div className="lbl">Ventas</div>
            <div className="val">{Number(summary.purchases || 0).toLocaleString()}</div>
            <div className="sub">compras (pixel)</div>
          </div>
          <div className="scard">
            <div className="lbl">Revenue</div>
            <div className={`val ${signClass(summary.revenue || 0)}`}>{money(summary.revenue || 0)}</div>
            <div className="sub">ingreso total</div>
          </div>
          <div className="scard">
            <div className="lbl">Spend</div>
            <div className="val">{money(summary.spend || 0)}</div>
            <div className="sub">{Number(summary.campaigns || 0)} cuentas con gasto</div>
          </div>
          <div className="scard">
            <div className="lbl">ROI</div>
            <div className={`val ${signClass(summary.roi || 0)}`}>{percent(summary.roi || 0)}</div>
            <div className="sub">(revenue - spend) / spend</div>
          </div>
        </div>

        <div className="tw">
          <div className="th-bar">
            <h2>Desglose por cuenta</h2>
            <span className="cnt">{sortedRows.length} cuentas activas</span>
          </div>
          <div className="jobs-table-wrap">
            <table>
              <thead>
                <tr>
                  <th className={sortCol === "name" ? "sorted" : ""} onClick={() => onSort("name")}>Cuenta<span className="arrow">{sortArrow("name")}</span></th>
                  <th className={`num ${sortCol === "purchases" ? "sorted" : ""}`} onClick={() => onSort("purchases")}>Ventas<span className="arrow">{sortArrow("purchases")}</span></th>
                  <th className={`num ${sortCol === "spend" ? "sorted" : ""}`} onClick={() => onSort("spend")}>Spend<span className="arrow">{sortArrow("spend")}</span></th>
                  <th className={`num ${sortCol === "revenue" ? "sorted" : ""}`} onClick={() => onSort("revenue")}>Revenue<span className="arrow">{sortArrow("revenue")}</span></th>
                  <th className={`num ${sortCol === "profit" ? "sorted" : ""}`} onClick={() => onSort("profit")}>Profit<span className="arrow">{sortArrow("profit")}</span></th>
                  <th className={`num ${sortCol === "cpa" ? "sorted" : ""}`} onClick={() => onSort("cpa")}>CPA<span className="arrow">{sortArrow("cpa")}</span></th>
                  <th className={`num ${sortCol === "roi" ? "sorted" : ""}`} onClick={() => onSort("roi")}>ROI<span className="arrow">{sortArrow("roi")}</span></th>
                </tr>
              </thead>
              <tbody>
                {sortedRows.map((r) => (
                  <tr key={r.id}>
                    <td>
                      <div className="an">
                        <span className={`bm ${r.bm === "BM2" ? "b2" : ""}`}>{r.bm}</span>
                        {r.name}
                      </div>
                    </td>
                    <td className="num">{r.purchases.toLocaleString()}</td>
                    <td className="num">{money(r.spend)}</td>
                    <td className={`num ${signClass(r.revenue)}`}>{money(r.revenue)}</td>
                    <td className={`num ${signClass(r.profit)}`}>{money(r.profit)}</td>
                    <td className="num">{r.cpa !== null ? money(r.cpa) : "-"}</td>
                    <td className={`num ${r.roi === null ? "zero" : signClass(r.roi)}`}>{r.roi !== null ? percent(r.roi) : "-"}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <td>TOTAL</td>
                  <td className="num">{Number(summary.purchases || 0).toLocaleString()}</td>
                  <td className="num">{money(summary.spend || 0)}</td>
                  <td className={`num ${signClass(summary.revenue || 0)}`}>{money(summary.revenue || 0)}</td>
                  <td className={`num ${signClass(summary.profit || 0)}`}>{money(summary.profit || 0)}</td>
                  <td className="num">{summary.cpa != null ? money(summary.cpa) : "-"}</td>
                  <td className={`num ${signClass(summary.roi || 0)}`}>{percent(summary.roi || 0)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      </section>
    </div>
  );
}
