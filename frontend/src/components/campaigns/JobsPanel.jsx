import React from "react";

function logClass(level, message) {
  const upper = String(level || "").toUpperCase();
  const text = String(message || "").toUpperCase();
  if (upper.includes("ERROR") || text.includes("ERROR") || text.includes("TRACEBACK")) return "log-line log-error";
  if (upper.includes("WARN") || text.includes("WARN")) return "log-line log-warn";
  if (text.includes("SUCCESS") || text.includes(" OK") || text.includes("COMPLETADO")) return "log-line log-ok";
  return "log-line log-info";
}

function jobTarget(job) {
  const payload = job?.payload || {};
  if (payload.campaignId) return payload.campaignId;
  if (Array.isArray(payload.campaignIds) && payload.campaignIds.length > 0) {
    if (payload.campaignIds.length === 1) return payload.campaignIds[0];
    return `${payload.campaignIds[0]} (+${payload.campaignIds.length - 1})`;
  }
  if (payload.bmId) return `BM ${payload.bmId}`;
  if (payload.tokenConfigIdBm1 || payload.tokenConfigIdBm2) {
    const bm1 = payload.tokenConfigIdBm1 ? `BM1:${String(payload.tokenConfigIdBm1).slice(-6)}` : null;
    const bm2 = payload.tokenConfigIdBm2 ? `BM2:${String(payload.tokenConfigIdBm2).slice(-6)}` : null;
    return [bm1, bm2].filter(Boolean).join(" | ");
  }
  return "-";
}

export default function JobsPanel({
  jobs,
  selectedJobs,
  allJobsSelected,
  onToggleAllJobs,
  onToggleJobSelection,
  onRemoveSelectedJobs,
  onRerunSelectedJobs,
  onOpenLogs,
  onCancelJob,
  selectedJobId,
  jobLogs,
}) {
  return (
    <section className="panel actions-panel">
      <div className="jobs-head">
        <h3>Jobs</h3>
        {Object.keys(selectedJobs).some((k) => selectedJobs[k]) ? (
          <div className="jobs-head-actions">
            <button className="btn btn-primary" onClick={onRerunSelectedJobs}>Reejecutar</button>
            <button className="btn btn-danger" onClick={onRemoveSelectedJobs}>Eliminar</button>
          </div>
        ) : null}
      </div>
      <div className="jobs-table-wrap">
        <table className="jobs-table">
          <thead>
            <tr>
              <th>
                <input type="checkbox" checked={allJobsSelected} onChange={(e) => onToggleAllJobs(e.target.checked)} />
              </th>
              <th>ID</th>
              <th>Tipo</th>
              <th>Campana/BM</th>
              <th>Status</th>
              <th>Progreso</th>
              <th>Acciones</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((j) => (
              <tr key={j._id}>
                <td>
                  <input type="checkbox" checked={!!selectedJobs[j._id]} onChange={(e) => onToggleJobSelection(j._id, e.target.checked)} />
                </td>
                <td>{j._id.slice(-8)}</td>
                <td>{j.type}</td>
                <td title={jobTarget(j)}>{jobTarget(j)}</td>
                <td>{j.status}</td>
                <td>{j.progress ? `${j.progress.percent}% - ${j.progress.message}` : "-"}</td>
                <td className="row-actions">
                  <button className="btn btn-primary" onClick={() => onOpenLogs(j._id)}>Ver estado</button>
                  {(j.status === "queued" || j.status === "running") ? <button className="btn btn-danger" onClick={() => onCancelJob(j._id)}>Cancelar</button> : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="logs-box">
        <h4>Logs job {selectedJobId ? selectedJobId.slice(-8) : "-"}</h4>
        <pre className="logs-stream">
          {jobLogs.map((l, idx) => (
            <div key={`${l.timestamp}-${idx}`} className={logClass(l.level, l.message)}>
              <span className="log-ts">[{l.timestamp}]</span>
              <span className="log-level"> {l.level}: </span>
              <span className="log-msg">{l.message}</span>
            </div>
          ))}
        </pre>
      </div>
    </section>
  );
}
