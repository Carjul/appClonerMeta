import React from "react";

export default function JobsPanel({
  jobs,
  selectedJobs,
  allJobsSelected,
  onToggleAllJobs,
  onToggleJobSelection,
  onRemoveSelectedJobs,
  onOpenLogs,
  onCancelJob,
  selectedJobId,
  jobLogs,
}) {
  return (
    <section className="panel">
      <div className="jobs-head">
        <h3>Jobs</h3>
        {Object.keys(selectedJobs).some((k) => selectedJobs[k]) ? (
          <button className="btn btn-danger" onClick={onRemoveSelectedJobs}>Eliminar</button>
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
        <pre>{jobLogs.map((l) => `[${l.timestamp}] ${l.level}: ${l.message}`).join("\n")}</pre>
      </div>
    </section>
  );
}
