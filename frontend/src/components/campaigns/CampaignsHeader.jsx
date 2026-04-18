import React from "react";

export default function CampaignsHeader({
  accountFilter,
  accounts,
  onChangeAccountFilter,
  expandAllAccounts,
  onToggleExpandAll,
  configId,
  configs,
  onChangeConfig,
  onRunExplorer,
}) {
  return (
    <>
      <div className="section-head">
        <h4>Seleccion BM y campañas</h4>
        <div className="section-actions">
          <div className="filter-group">
            <span className="field-label">Filtro cuenta</span>
            <select className="account-filter" value={accountFilter} onChange={(e) => onChangeAccountFilter(e.target.value)}>
              <option value="all">Todas las cuentas</option>
              {accounts.map((acc) => (
                <option key={acc.account_id} value={acc.account_id}>{acc.account_name}</option>
              ))}
            </select>
          </div>
          <label className="switch-wrap" title="Abrir o cerrar todos los bloques">
            <span className="switch-label">{expandAllAccounts ? "OPEN" : "CLOSE"}</span>
            <input
              type="checkbox"
              className="switch-input"
              checked={expandAllAccounts}
              onChange={(e) => onToggleExpandAll(e.target.checked)}
            />
            <span className="switch-slider" />
          </label>
        </div>
      </div>

      <div className="loader-bar">
        <div className="loader-group">
          <span className="field-label">Configuracion BM</span>
          <select value={configId} onChange={(e) => onChangeConfig(e.target.value)}>
            <option value="">Seleccione configuracion</option>
            {configs.map((c) => (
              <option key={c._id} value={c._id}>{c.name}</option>
            ))}
          </select>
        </div>
        <button className="btn btn-primary load-btn" onClick={onRunExplorer}>Cargar campañas</button>
      </div>
    </>
  );
}
