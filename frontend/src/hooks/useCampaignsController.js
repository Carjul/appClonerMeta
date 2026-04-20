import { useEffect, useMemo, useState } from "react";
import Swal from "sweetalert2";
import { api } from "../api";

export default function useCampaignsController() {
  const [configs, setConfigs] = useState([]);
  const [configId, setConfigId] = useState("");
  const [explorerJobId, setExplorerJobId] = useState("");
  const [accounts, setAccounts] = useState([]);
  const [selectedCampaigns, setSelectedCampaigns] = useState({});
  const [selectedJobs, setSelectedJobs] = useState({});
  const [jobs, setJobs] = useState([]);
  const [jobLogs, setJobLogs] = useState([]);
  const [selectedJobId, setSelectedJobId] = useState("");
  const [bulkCampaignId, setBulkCampaignId] = useState("");
  const [selectedAccountId, setSelectedAccountId] = useState("");
  const [targetStatus, setTargetStatus] = useState("PAUSED");
  const [accountFilter, setAccountFilter] = useState("all");
  const [expandAllAccounts, setExpandAllAccounts] = useState(false);
  const [alert, setAlert] = useState(null);
  const [deleteWatch, setDeleteWatch] = useState({});
  const [statusWatch, setStatusWatch] = useState({});
  const [reduceBm1ConfigId, setReduceBm1ConfigId] = useState("");
  const [reduceBm2ConfigId, setReduceBm2ConfigId] = useState("");
  const [reduceExecute, setReduceExecute] = useState(false);
  const [reduceMinSpend, setReduceMinSpend] = useState("5.0");
  const [reduceTargetBudget, setReduceTargetBudget] = useState("1.00");

  useEffect(() => {
    if (!alert) return undefined;
    const timer = setTimeout(() => setAlert(null), 2400);
    return () => clearTimeout(timer);
  }, [alert]);

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
    loadConfigs().catch((e) => setAlert({ type: "error", message: String(e.message || e) }));
    loadJobs().catch((e) => setAlert({ type: "error", message: String(e.message || e) }));
    const id = setInterval(() => {
      loadJobs().catch(() => null);
      if (selectedJobId) api.getJobLogs(selectedJobId, 20000).then(setJobLogs).catch(() => null);
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
        setExpandAllAccounts(false);
        if (cache.cachedAt) {
          setAlert({ type: "success", message: "Campañas cargadas desde cache de base de datos." });
        }
      } catch (e) {
        setAlert({ type: "error", message: String(e.message || e) });
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
          for (const id of idsSet) delete copy[id];
          return copy;
        });
        setSelectedAccountId("");
        setAlert({ type: "success", message: "Campañas eliminadas y lista actualizada sin refrescar." });
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
      setSelectedJobs((prev) => {
        const copy = { ...prev };
        for (const [jobId, watch] of Object.entries(nextWatch)) {
          if (watch.applied) delete copy[jobId];
        }
        return copy;
      });
    }
  }, [jobs, deleteWatch]);

  useEffect(() => {
    if (!jobs.length || !Object.keys(statusWatch).length) return;

    const jobsById = new Map(jobs.map((j) => [j._id, j]));
    let changed = false;
    const nextWatch = { ...statusWatch };

    for (const [jobId, watch] of Object.entries(nextWatch)) {
      if (watch.applied) continue;
      const job = jobsById.get(jobId);
      if (!job) continue;

      if (job.status === "completed") {
        const idsSet = new Set(watch.campaignIds || []);
        const newStatus = watch.status;
        setAccounts((prev) =>
          prev.map((acc) => ({
            ...acc,
            campaigns: (acc.campaigns || []).map((c) => (idsSet.has(c.id) ? { ...c, status: newStatus } : c)),
          }))
        );
        setAlert({ type: "success", message: `Status actualizado a ${newStatus} sin refrescar.` });
        nextWatch[jobId] = { ...watch, applied: true };
        changed = true;
      }

      if (job.status === "failed" || job.status === "cancelled") {
        nextWatch[jobId] = { ...watch, applied: true };
        changed = true;
      }
    }

    if (changed) {
      setStatusWatch(nextWatch);
    }
  }, [jobs, statusWatch]);

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
    setAlert(null);

    if (checked) {
      if (selectedAccountId && selectedAccountId !== accountId) {
        setAlert({ type: "error", message: "Solo puedes seleccionar campañas de una misma cuenta anunciante." });
        return;
      }
      setSelectedAccountId(accountId);
      setSelectedCampaigns((prev) => ({ ...prev, [campaignId]: true }));
      return;
    }

    setSelectedCampaigns((prev) => {
      const next = { ...prev, [campaignId]: false };
      const remaining = Object.entries(next).filter(([, v]) => v).map(([k]) => k);
      if (remaining.length === 0) setSelectedAccountId("");
      return next;
    });
  }

  function onChangeAccountFilter(value) {
    setAccountFilter(value);
    if (selectedIds.length > 0) {
      setSelectedCampaigns({});
      setSelectedAccountId("");
      setAlert({ type: "info", message: "Selecciones limpiadas al cambiar el filtro de cuentas." });
    }
  }

  function toggleAccountCampaigns(accountId, campaigns, checked) {
    const ids = (campaigns || []).map((c) => c.id);
    if (checked) {
      if (selectedAccountId && selectedAccountId !== accountId) {
        setAlert({ type: "error", message: "Solo puedes seleccionar campañas de una misma cuenta anunciante." });
        return;
      }
      setSelectedAccountId(accountId);
      setSelectedCampaigns((prev) => {
        const next = { ...prev };
        for (const id of ids) next[id] = true;
        return next;
      });
      return;
    }
    setSelectedCampaigns((prev) => {
      const next = { ...prev };
      for (const id of ids) delete next[id];
      const hasAny = Object.keys(next).some((k) => next[k]);
      if (!hasAny) setSelectedAccountId("");
      return next;
    });
  }

  function toggleJobSelection(jobId, checked) {
    setSelectedJobs((prev) => {
      const next = { ...prev };
      if (checked) next[jobId] = true;
      else delete next[jobId];
      return next;
    });
  }

  function toggleAllJobs(checked) {
    if (!checked) {
      setSelectedJobs({});
      return;
    }
    const next = {};
    for (const j of jobs) next[j._id] = true;
    setSelectedJobs(next);
  }

  async function openLogs(jobId) {
    setSelectedJobId(jobId);
    const logs = await api.getJobLogs(jobId, 20000);
    setJobLogs(logs);
  }

  async function runExplorer() {
    if (!configId) return;
    setAlert(null);
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

  async function runBulk() {
    if (!configId || !bulkCampaignId) return;
    const confirm = await Swal.fire({
      title: "Confirmar bulk clone",
      text: `Se duplicara la campana ${bulkCampaignId}. Este proceso puede tardar varios minutos.`,
      icon: "warning",
      showCancelButton: true,
      confirmButtonText: "Si, duplicar",
      cancelButtonText: "Cancelar",
    });
    if (!confirm.isConfirmed) return;

    setAlert(null);
    const res = await api.runBulk(configId, bulkCampaignId);
    setSelectedJobId(res.jobId);
    setJobLogs([]);

    await Swal.fire({
      title: "Proceso iniciado",
      text: "Bulk clone en ejecucion. Revisa el progreso en Jobs.",
      icon: "success",
      timer: 1600,
      showConfirmButton: false,
    });

    await loadJobs();
    await openLogs(res.jobId);
  }

  async function runReduceBudgets() {
    const bm1 = reduceBm1ConfigId || null;
    const bm2 = reduceBm2ConfigId || null;
    if (!bm1 && !bm2) {
      setAlert({ type: "error", message: "Selecciona al menos una configuracion para token BM1 o BM2." });
      return;
    }

    const targetBudget = Number(reduceTargetBudget);
    const minSpend = Number(reduceMinSpend);
    if (!Number.isFinite(targetBudget) || targetBudget <= 0 || !Number.isFinite(minSpend) || minSpend < 0) {
      setAlert({ type: "error", message: "Valores invalidos en target budget o min spend." });
      return;
    }

    const confirm = await Swal.fire({
      title: reduceExecute ? "Ejecutar optimizer" : "Dry run optimizer",
      text: reduceExecute
        ? "Se aplicaran cambios reales de budget en Meta Ads."
        : "Se ejecutara en modo simulacion (sin cambios).",
      icon: reduceExecute ? "warning" : "info",
      showCancelButton: true,
      confirmButtonText: reduceExecute ? "Ejecutar" : "Iniciar dry run",
      cancelButtonText: "Cancelar",
    });
    if (!confirm.isConfirmed) return;

    const res = await api.runReduceBudgets({
      tokenConfigIdBm1: bm1,
      tokenConfigIdBm2: bm2,
      execute: reduceExecute,
      minSpend,
      targetBudget,
    });

    setSelectedJobId(res.jobId);
    setJobLogs([]);
    await loadJobs();
    await openLogs(res.jobId);

    setAlert({
      type: "success",
      message: reduceExecute ? "Optimizer en ejecucion (EXECUTE)." : "Optimizer en ejecucion (DRY RUN).",
    });
  }

  async function runSingle() {
    if (!configId || selectedIds.length === 0) return;
    const confirm = await Swal.fire({
      title: "Confirmar single clone",
      text: `Se duplicaran ${selectedIds.length} campanas seleccionadas.`,
      icon: "warning",
      showCancelButton: true,
      confirmButtonText: "Si, duplicar",
      cancelButtonText: "Cancelar",
    });
    if (!confirm.isConfirmed) return;

    setAlert(null);
    const res = await api.runSingle(configId, selectedIds);
    setSelectedJobId(res.jobId);
    setJobLogs([]);

    await Swal.fire({
      title: "Proceso iniciado",
      text: "Single clone en ejecucion. Revisa el progreso en Jobs.",
      icon: "success",
      timer: 1600,
      showConfirmButton: false,
    });

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

    setAlert(null);
    const selectedNow = [...selectedIds];
    const res = await api.deleteCampaigns(configId, selectedNow, 10);
    setSelectedJobId(res.jobId);
    setJobLogs([]);
    setDeleteWatch((prev) => ({ ...prev, [res.jobId]: { campaignIds: selectedNow, applied: false } }));

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

  async function runCampaignStatus() {
    if (!configId || selectedIds.length === 0) return;
    const confirm = await Swal.fire({
      title: "Cambiar status de campañas",
      text: `Se cambiara a ${targetStatus} en ${selectedIds.length} campañas seleccionadas.`,
      icon: "question",
      showCancelButton: true,
      confirmButtonText: "Aplicar",
      cancelButtonText: "Cancelar",
    });
    if (!confirm.isConfirmed) return;

    setAlert(null);
    const selectedNow = [...selectedIds];
    const res = await api.updateCampaignsStatus(configId, selectedNow, targetStatus, "v21.0");
    setSelectedJobId(res.jobId);
    setJobLogs([]);
    setStatusWatch((prev) => ({ ...prev, [res.jobId]: { campaignIds: selectedNow, status: targetStatus, applied: false } }));

    await Swal.fire({
      title: "Proceso iniciado",
      text: "Cambio de status enviado. Revisa los logs en Jobs.",
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

  async function removeSelectedJobs() {
    const ids = Object.keys(selectedJobs).filter((k) => selectedJobs[k]);
    if (ids.length === 0) {
      setAlert({ type: "info", message: "No hay jobs seleccionados." });
      return;
    }
    const confirm = await Swal.fire({
      title: "Eliminar jobs",
      text: `Se eliminaran ${ids.length} jobs y sus logs.`,
      icon: "warning",
      showCancelButton: true,
      confirmButtonText: "Eliminar",
      cancelButtonText: "Cancelar",
    });
    if (!confirm.isConfirmed) return;

    for (const jobId of ids) {
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
      setStatusWatch((prev) => {
        const copy = { ...prev };
        delete copy[jobId];
        return copy;
      });
    }
    setSelectedJobs({});
    await loadJobs();
    setAlert({ type: "success", message: "Jobs seleccionados eliminados." });
  }

  async function rerunSelectedJobs() {
    const ids = Object.keys(selectedJobs).filter((k) => selectedJobs[k]);
    if (ids.length === 0) {
      setAlert({ type: "info", message: "No hay jobs seleccionados." });
      return;
    }

    const confirm = await Swal.fire({
      title: "Reejecutar jobs",
      text: `Se reejecutaran ${ids.length} jobs con la misma configuracion/comando.`,
      icon: "question",
      showCancelButton: true,
      confirmButtonText: "Reejecutar",
      cancelButtonText: "Cancelar",
    });
    if (!confirm.isConfirmed) return;

    let firstNewJobId = null;
    for (const jobId of ids) {
      try {
        const res = await api.rerunJob(jobId);
        if (!firstNewJobId && res?.jobId) firstNewJobId = res.jobId;
      } catch (e) {
        setAlert({ type: "error", message: `No se pudo reejecutar ${jobId.slice(-8)}: ${String(e.message || e)}` });
      }
    }

    await loadJobs();
    if (firstNewJobId) {
      setSelectedJobId(firstNewJobId);
      setJobLogs([]);
      await openLogs(firstNewJobId);
    }
    setAlert({ type: "success", message: "Reejecucion enviada." });
  }

  async function copyCampaignId(campaignId) {
    try {
      await navigator.clipboard.writeText(campaignId);
      setAlert({ type: "success", message: `ID copiado: ${campaignId}` });
    } catch {
      setAlert({ type: "error", message: "No se pudo copiar el ID al portapapeles." });
    }
  }

  const selectedIds = useMemo(() => Object.keys(selectedCampaigns).filter((k) => selectedCampaigns[k]), [selectedCampaigns]);
  const filteredAccounts = useMemo(() => (accountFilter === "all" ? accounts : accounts.filter((acc) => acc.account_id === accountFilter)), [accounts, accountFilter]);
  const allJobsSelected = useMemo(() => jobs.length > 0 && jobs.every((j) => !!selectedJobs[j._id]), [jobs, selectedJobs]);

  return {
    alert,
    configs,
    configId,
    accountFilter,
    accounts,
    filteredAccounts,
    expandAllAccounts,
    selectedCampaigns,
    selectedAccountId,
    selectedIds,
    bulkCampaignId,
    targetStatus,
    reduceBm1ConfigId,
    reduceBm2ConfigId,
    reduceExecute,
    reduceMinSpend,
    reduceTargetBudget,
    jobs,
    selectedJobs,
    allJobsSelected,
    selectedJobId,
    jobLogs,

    setConfigId,
    setExpandAllAccounts,
    setBulkCampaignId,
    setTargetStatus,
    setReduceBm1ConfigId,
    setReduceBm2ConfigId,
    setReduceExecute,
    setReduceMinSpend,
    setReduceTargetBudget,
    onChangeAccountFilter,
    toggleCampaign,
    toggleAccountCampaigns,
    toggleJobSelection,
    toggleAllJobs,
    runExplorer,
    runBulk,
    runSingle,
    runDeleteCampaigns,
    runCampaignStatus,
    runReduceBudgets,
    removeSelectedJobs,
    rerunSelectedJobs,
    openLogs,
    cancel,
    copyCampaignId,
  };
}
