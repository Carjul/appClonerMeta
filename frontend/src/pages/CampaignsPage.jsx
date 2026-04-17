import React, { useEffect, useMemo, useState } from "react";
import Swal from "sweetalert2";
import { api } from "../api";

export default function CampaignsPage() {
  const [configs, setConfigs] = useState([]);
  const [configId, setConfigId] = useState("");
  const [explorerJobId, setExplorerJobId] = useState("");
  const [accounts, setAccounts] = useState([]);
  const [selectedCampaigns, setSelectedCampaigns] = useState({});
  const [jobs, setJobs] = useState([]);
  const [jobLogs, setJobLogs] = useState([]);
  const [selectedJobId, setSelectedJobId] = useState("");
  const [bulkCampaignId, setBulkCampaignId] = useState("");
  const [selectedAccountId, setSelectedAccountId] = useState("");
  const [accountFilter, setAccountFilter] = useState("all");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [deleteWatch, setDeleteWatch] = useState({});

  useEffect(() => {
    const timer = setTimeout(() => setInfo(""), 2200);
    return () => clearTimeout(timer);
  }, [info]);

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

  useEffect(() => {
    async function loadCache() {
      if (!configId) {
        setAccounts([]);
        setSelectedCampaigns({});
        setSelectedAccountId("");
        return;
      }
      try {
        const cache = await api.getExplorerCache(configId);
        setAccounts(cache.accounts || []);
        setSelectedCampaigns({});
        setSelectedAccountId("");
        setAccountFilter("all");
        if (cache.cachedAt) {
          setInfo("Campañas cargadas desde cache de base de datos.");
        }
      } catch (e) {
        setError(String(e.message || e));
      }
    }
    loadCache();
  }, [configId]);

  useEffect(() => {
    if (!jobs.length || !Object.keys(deleteWatch).length) return;

    const jobsById = new Map(jobs.map((j) => [j._id, j]));
    let changed = false;
    const nextWatch = { ...deleteWatch };

    for (const [jobId, watch] of Object.entries(nextWatch)) {
      if (watch.applied) continue;
      const job = jobsById.get(jobId);
      if (!job) continue;

      if (job.status === "completed") {
        const idsSet = new Set(watch.campaignIds || []);
        setAccounts((prev) =>
          prev.map((acc) => ({
            ...acc,
            campaigns: (acc.campaigns || []).filter((c) => !idsSet.has(c.id)),
          }))
        );
        setSelectedCampaigns((prev) => {
          const copy = { ...prev };
          for (const id of idsSet) {
            delete copy[id];
          }
          return copy;
        });
        setSelectedAccountId("");
        setInfo("Campañas eliminadas y lista actualizada sin refrescar.");
        nextWatch[jobId] = { ...watch, applied: true };
        changed = true;
      }

      if (job.status === "failed" || job.status === "cancelled") {
        nextWatch[jobId] = { ...watch, applied: true };
        changed = true;
      }
    }

    if (changed) {
      setDeleteWatch(nextWatch);
    }
  }, [jobs, deleteWatch]);

  async function runExplorer() {
    if (!configId) return;
    setError("");
    setAccounts([]);
    setSelectedCampaigns({});
    setSelectedAccountId("");
    const res = await api.runExplorer(configId);
    setExplorerJobId(res.jobId);
    setSelectedJobId(res.jobId);
    setJobLogs([]);
    await loadJobs();
    await openLogs(res.jobId);
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
    const res = await api.runBulk(configId, bulkCampaignId);
    setSelectedJobId(res.jobId);
    setJobLogs([]);
    await loadJobs();
    await openLogs(res.jobId);
  }

  async function runSingle() {
    if (!configId || selectedIds.length === 0) return;
    setError("");
    const res = await api.runSingle(configId, selectedIds);
    setSelectedJobId(res.jobId);
    setJobLogs([]);
    await loadJobs();
    await openLogs(res.jobId);
  }

  async function runDeleteCampaigns() {
    if (!configId || selectedIds.length === 0) return;
    const confirm = await Swal.fire({
      title: "Eliminar campañas",
      text: `Se eliminaran ${selectedIds.length} campañas seleccionadas.`,
      icon: "warning",
      showCancelButton: true,
      confirmButtonText: "Si, eliminar",
      cancelButtonText: "Cancelar",
    });
    if (!confirm.isConfirmed) return;

    setError("");
    const selectedNow = [...selectedIds];
    const res = await api.deleteCampaigns(configId, selectedNow, 10);
    setSelectedJobId(res.jobId);
    setJobLogs([]);
    setDeleteWatch((prev) => ({
      ...prev,
      [res.jobId]: { campaignIds: selectedNow, applied: false },
    }));

    await Swal.fire({
      title: "Proceso iniciado",
      text: "La eliminacion fue enviada. Puedes seguir el estado en Jobs.",
      icon: "success",
      timer: 1600,
      showConfirmButton: false,
    });
    await loadJobs();
    await openLogs(res.jobId);
  }

  async function cancel(jobId) {
    const confirm = await Swal.fire({
      title: "Cancelar job",
      text: "Se intentara detener la ejecucion en curso.",
      icon: "warning",
      showCancelButton: true,
      confirmButtonText: "Cancelar job",
      cancelButtonText: "Cerrar",
    });
    if (!confirm.isConfirmed) return;

    await api.cancelJob(jobId);
    await Swal.fire({
      title: "Cancelacion enviada",
      text: "Revisa el estado en la tabla de jobs.",
      icon: "success",
      timer: 1400,
      showConfirmButton: false,
    });
    await loadJobs();
  }

  async function removeJob(jobId) {
    const confirm = await Swal.fire({
      title: "Eliminar job",
      text: "Se eliminara el job y sus logs.",
      icon: "warning",
      showCancelButton: true,
      confirmButtonText: "Eliminar",
      cancelButtonText: "Cancelar",
    });
    if (!confirm.isConfirmed) return;

    await api.deleteJob(jobId);
    if (selectedJobId === jobId) {
      setSelectedJobId("");
      setJobLogs([]);
    }
    setDeleteWatch((prev) => {
      const copy = { ...prev };
      delete copy[jobId];
      return copy;
    });
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

  const filteredAccounts = useMemo(() => {
    if (accountFilter === "all") return accounts;
    return accounts.filter((acc) => acc.account_id === accountFilter);
  }, [accounts, accountFilter]);

  return (
    <div className="panel-grid single-col">
      <section className="panel">
        <div className="section-head">
          <h3>Seleccion BM y campañas</h3>
          <select className="account-filter" value={accountFilter} onChange={(e) => setAccountFilter(e.target.value)}>
            <option value="all">Todas las cuentas</option>
            {accounts.map((acc) => (
              <option key={acc.account_id} value={acc.account_id}>{acc.account_name}</option>
            ))}
          </select>
        </div>
        {error ? <p className="error">{error}</p> : null}
        {info ? <p className="info">{info}</p> : null}
        <div className="inline-actions">
          <select value={configId} onChange={(e) => setConfigId(e.target.value)}>
            <option value="">Seleccione configuracion</option>
            {configs.map((c) => <option key={c._id} value={c._id}>{c.name}</option>)}
          </select>
          <button className="btn btn-primary" onClick={runExplorer}>Cargar cuentas/campañas</button>
        </div>

        {filteredAccounts.map((acc) => (
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
          <h4>Acciones</h4>
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
          <div className="mini-card clone-card">
            <h4>Delete campañas</h4>
            <p>Seleccionadas: {selectedIds.length}</p>
            <button className="btn btn-danger" onClick={runDeleteCampaigns} disabled={selectedIds.length === 0}>Eliminar seleccionadas</button>
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
