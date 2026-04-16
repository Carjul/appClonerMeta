import React, { useEffect, useMemo, useState } from "react";
import { api } from "../api";

const LS_ACCOUNTS_KEY = "meta_campaigns_accounts";
const LS_CONFIG_KEY = "meta_campaigns_config_id";
const LS_SELECTED_KEY = "meta_campaigns_selected";
const LS_SELECTED_ACCOUNT_KEY = "meta_campaigns_selected_account";
const LS_BULK_KEY = "meta_campaigns_bulk_id";

export default function CampaignsPage() {
  const [configs, setConfigs] = useState([]);
  const [configId, setConfigId] = useState(() => localStorage.getItem(LS_CONFIG_KEY) || "");
  const [explorerJobId, setExplorerJobId] = useState("");
  const [accounts, setAccounts] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(LS_ACCOUNTS_KEY) || "[]");
    } catch {
      return [];
    }
  });
  const [selectedCampaigns, setSelectedCampaigns] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(LS_SELECTED_KEY) || "{}");
    } catch {
      return {};
    }
  });
  const [jobs, setJobs] = useState([]);
  const [jobLogs, setJobLogs] = useState([]);
  const [selectedJobId, setSelectedJobId] = useState("");
  const [bulkCampaignId, setBulkCampaignId] = useState(() => localStorage.getItem(LS_BULK_KEY) || "");
  const [selectedAccountId, setSelectedAccountId] = useState(() => localStorage.getItem(LS_SELECTED_ACCOUNT_KEY) || "");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  useEffect(() => {
    localStorage.setItem(LS_CONFIG_KEY, configId || "");
  }, [configId]);

  useEffect(() => {
    localStorage.setItem(LS_ACCOUNTS_KEY, JSON.stringify(accounts || []));
  }, [accounts]);

  useEffect(() => {
    localStorage.setItem(LS_SELECTED_KEY, JSON.stringify(selectedCampaigns || {}));
  }, [selectedCampaigns]);

  useEffect(() => {
    localStorage.setItem(LS_SELECTED_ACCOUNT_KEY, selectedAccountId || "");
  }, [selectedAccountId]);

  useEffect(() => {
    localStorage.setItem(LS_BULK_KEY, bulkCampaignId || "");
  }, [bulkCampaignId]);

  useEffect(() => {
    const timer = setTimeout(() => setInfo(""), 2200);
    return () => clearTimeout(timer);
  }, [info]);

  useEffect(() => {
    function onKeyDown(e) {
      const target = e.target;
      const tag = (target && target.tagName ? target.tagName : "").toLowerCase();
      const isTyping = tag === "input" || tag === "textarea" || (target && target.isContentEditable);
      if (isTyping) return;
      if (e.key && e.key.toLowerCase() === "r") {
        localStorage.removeItem(LS_ACCOUNTS_KEY);
        localStorage.removeItem(LS_CONFIG_KEY);
        localStorage.removeItem(LS_SELECTED_KEY);
        localStorage.removeItem(LS_SELECTED_ACCOUNT_KEY);
        localStorage.removeItem(LS_BULK_KEY);
        setAccounts([]);
        setSelectedCampaigns({});
        setSelectedAccountId("");
        setBulkCampaignId("");
        setConfigId("");
        setInfo("LocalStorage limpiado.");
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  async function loadConfigs() {
    const rows = await api.listConfigs();
    setConfigs(rows);
    if (!configId && rows[0]) setConfigId(rows[0]._id);
  }

  async function loadJobs() {
    const rows = await api.listJobs();
    setJobs(rows);
  }

  useEffect(() => {
    loadConfigs().catch((e) => setError(String(e.message || e)));
    loadJobs().catch((e) => setError(String(e.message || e)));
    const id = setInterval(() => {
      loadJobs().catch(() => null);
      if (selectedJobId) api.getJobLogs(selectedJobId).then(setJobLogs).catch(() => null);
    }, 2500);
    return () => clearInterval(id);
  }, [selectedJobId]);

  async function runExplorer() {
    if (!configId) return;
    setError("");
    setAccounts([]);
    setSelectedCampaigns({});
    setSelectedAccountId("");
    const res = await api.runExplorer(configId);
    setExplorerJobId(res.jobId);
  }

  useEffect(() => {
    if (!explorerJobId) return;
    let stop = false;
    const timer = setInterval(async () => {
      if (stop) return;
      const r = await api.getExplorerResult(explorerJobId);
      if (r.status === "completed") {
        setAccounts((r.result && r.result.accounts) || []);
        clearInterval(timer);
      }
      if (r.status === "failed" || r.status === "cancelled") {
        clearInterval(timer);
      }
    }, 2000);
    return () => {
      stop = true;
      clearInterval(timer);
    };
  }, [explorerJobId]);

  function toggleCampaign(accountId, campaignId, checked) {
    setError("");

    if (checked) {
      if (selectedAccountId && selectedAccountId !== accountId) {
        setError("Solo puedes seleccionar campañas de una misma cuenta anunciante.");
        return;
      }
      setSelectedAccountId(accountId);
      setSelectedCampaigns((prev) => ({ ...prev, [campaignId]: true }));
      return;
    }

    setSelectedCampaigns((prev) => {
      const next = { ...prev, [campaignId]: false };
      const remaining = Object.entries(next).filter(([, v]) => v).map(([k]) => k);
      if (remaining.length === 0) {
        setSelectedAccountId("");
      }
      return next;
    });
  }

  const selectedIds = useMemo(() => Object.keys(selectedCampaigns).filter((k) => selectedCampaigns[k]), [selectedCampaigns]);

  async function runBulk() {
    if (!configId || !bulkCampaignId) return;
    setError("");
    await api.runBulk(configId, bulkCampaignId);
    await loadJobs();
  }

  async function runSingle() {
    if (!configId || selectedIds.length === 0) return;
    setError("");
    await api.runSingle(configId, selectedIds);
    await loadJobs();
  }

  async function cancel(jobId) {
    await api.cancelJob(jobId);
    await loadJobs();
  }

  async function removeJob(jobId) {
    await api.deleteJob(jobId);
    if (selectedJobId === jobId) {
      setSelectedJobId("");
      setJobLogs([]);
    }
    await loadJobs();
  }

  async function openLogs(jobId) {
    setSelectedJobId(jobId);
    const logs = await api.getJobLogs(jobId);
    setJobLogs(logs);
  }

  async function copyCampaignId(campaignId) {
    try {
      await navigator.clipboard.writeText(campaignId);
      setInfo(`ID copiado: ${campaignId}`);
    } catch {
      setError("No se pudo copiar el ID al portapapeles.");
    }
  }

  return (
    <div className="panel-grid single-col">
      <section className="panel">
        <h3>Seleccion BM y campañas</h3>
        {error ? <p className="error">{error}</p> : null}
        {info ? <p className="info">{info}</p> : null}
        <div className="inline-actions">
          <select value={configId} onChange={(e) => setConfigId(e.target.value)}>
            <option value="">Seleccione configuracion</option>
            {configs.map((c) => <option key={c._id} value={c._id}>{c.name}</option>)}
          </select>
          <button className="btn btn-primary" onClick={runExplorer}>Cargar cuentas/campañas</button>
        </div>

        {accounts.map((acc) => (
          <details key={acc.account_id} className="account-block" open>
            <summary>
              {acc.account_name} ({acc.account_id}) - {(acc.campaigns || []).length} campañas
            </summary>
            <table>
              <thead>
                <tr>
                  <th></th>
                  <th>Campaña ID</th>
                  <th>Nombre</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {(acc.campaigns || []).map((c) => {
                  const checked = !!selectedCampaigns[c.id];
                  const disabled = !checked && !!selectedAccountId && selectedAccountId !== acc.account_id;
                  return (
                    <tr key={c.id}>
                      <td>
                        <input
                          type="checkbox"
                          checked={checked}
                          disabled={disabled}
                          onChange={(e) => toggleCampaign(acc.account_id, c.id, e.target.checked)}
                        />
                      </td>
                      <td>
                        <button className="id-link" type="button" onClick={() => copyCampaignId(c.id)} title="Copiar ID">
                          {c.id}
                        </button>
                      </td>
                      <td>{c.name}</td>
                      <td>{c.status}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </details>
        ))}

        <div className="clone-controls">
          <h4>Acciones de clonacion</h4>
        </div>
        <div className="action-cards">
          <div className="mini-card clone-card">
            <h4>Bulk clone</h4>
            <input placeholder="Campaign ID origen" value={bulkCampaignId} onChange={(e) => setBulkCampaignId(e.target.value)} />
            <button className="btn btn-success" onClick={runBulk}>Ejecutar bulk</button>
          </div>
          <div className="mini-card clone-card">
            <h4>Single clone</h4>
            <p>Seleccionadas: {selectedIds.length}</p>
            <button className="btn btn-primary" onClick={runSingle} disabled={selectedIds.length === 0}>Ejecutar single</button>
          </div>
        </div>
      </section>

      <section className="panel">
        <h3>Jobs</h3>
        <div className="jobs-table-wrap">
          <table className="jobs-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Tipo</th>
                <th>Status</th>
                <th>Progreso</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((j) => (
                <tr key={j._id}>
                  <td>{j._id.slice(-8)}</td>
                  <td>{j.type}</td>
                  <td>{j.status}</td>
                  <td>{j.progress ? `${j.progress.percent}% - ${j.progress.message}` : "-"}</td>
                  <td className="row-actions">
                    <button className="btn btn-primary" onClick={() => openLogs(j._id)}>Ver estado</button>
                    {(j.status === "queued" || j.status === "running") ? <button className="btn btn-danger" onClick={() => cancel(j._id)}>Cancelar</button> : null}
                    <button className="btn btn-danger ghost" onClick={() => removeJob(j._id)}>Eliminar</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="logs-box">
          <h4>Logs job {selectedJobId ? selectedJobId.slice(-8) : "-"}</h4>
          <pre>{jobLogs.map((l) => `[${l.timestamp}] ${l.level}: ${l.message}`).join("\n")}</pre>
        </div>
      </section>
    </div>
  );
}
