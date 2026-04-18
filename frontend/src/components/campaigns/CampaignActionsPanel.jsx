import React from "react";

export default function CampaignActionsPanel({
  selectedCount,
  bulkCampaignId,
  onChangeBulkCampaignId,
  onRunBulk,
  onRunSingle,
  targetStatus,
  onChangeTargetStatus,
  onRunStatus,
  onRunDelete,
}) {
  return (
    <section className="panel actions-panel">
      <div className="clone-controls">
        <h4>Acciones</h4>
      </div>
      <div className="action-cards">
        <div className="mini-card clone-card">
          <h4>
            Bulk clone
            <span className="action-badge badge-bulk">BULK</span>
          </h4>
          <input placeholder="Campaign ID origen" value={bulkCampaignId} onChange={(e) => onChangeBulkCampaignId(e.target.value)} />
          <div className="clone-footer">
            <button className="btn btn-success" onClick={onRunBulk}>Ejecutar bulk</button>
          </div>
        </div>

        <div className="mini-card clone-card">
          <h4>
            Single clone
            <span className="action-badge badge-single">SINGLE</span>
          </h4>
          <p>Seleccionadas: {selectedCount}</p>
          <div className="clone-footer">
            <button className="btn btn-primary" onClick={onRunSingle} disabled={selectedCount === 0}>Ejecutar single</button>
          </div>
        </div>

        <div className="mini-card clone-card">
          <h4>
            Status campañas
            <span className="action-badge badge-status">STATUS</span>
          </h4>
          <p>Seleccionadas: {selectedCount}</p>
          <select value={targetStatus} onChange={(e) => onChangeTargetStatus(e.target.value)} disabled={selectedCount === 0}>
            <option value="ACTIVE">ACTIVE</option>
            <option value="PAUSED">PAUSED</option>
          </select>
          <div className="clone-footer">
            <button className="btn btn-primary" onClick={onRunStatus} disabled={selectedCount === 0}>Aplicar status</button>
          </div>
        </div>

        <div className="mini-card clone-card">
          <h4>
            Delete campañas
            <span className="action-badge badge-delete">DELETE</span>
          </h4>
          <p>Seleccionadas: {selectedCount}</p>
          <div className="clone-footer">
            <button className="btn btn-danger" onClick={onRunDelete} disabled={selectedCount === 0}>Eliminar</button>
          </div>
        </div>
      </div>
    </section>
  );
}
