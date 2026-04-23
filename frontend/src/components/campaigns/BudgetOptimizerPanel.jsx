import React from "react";

export default function BudgetOptimizerPanel({
  selectedCount,
  configName,
  reduceExecute,
  reduceMinSpend,
  reduceTargetBudget,
  onSetReduceExecute,
  onSetReduceMinSpend,
  onSetReduceTargetBudget,
  onRunReduceBudgets,
}) {
  return (
    <section className="panel actions-panel">
      <div className="clone-controls">
        <h4>Budget Optimizer</h4>
      </div>

      <div className="budget-grid">
        <div className="budget-field">
          <span className="field-label">Config actual</span>
          <input value={configName || "(sin config seleccionada)"} disabled />
        </div>

        <div className="budget-field">
          <span className="field-label">Target Budget (USD)</span>
          <input type="number" step="0.01" min="0.01" value={reduceTargetBudget} onChange={(e) => onSetReduceTargetBudget(e.target.value)} />
        </div>

        <div className="budget-field">
          <span className="field-label">Min Spend (USD)</span>
          <input type="number" step="0.1" min="0" value={reduceMinSpend} onChange={(e) => onSetReduceMinSpend(e.target.value)} />
        </div>

        <label className="budget-exec">
          <input type="checkbox" checked={reduceExecute} onChange={(e) => onSetReduceExecute(e.target.checked)} />
          <span>{reduceExecute ? "EXECUTE" : "DRY RUN"}</span>
        </label>

        <button className="btn btn-primary budget-run" onClick={onRunReduceBudgets}>
          Ejecutar optimizer ({selectedCount})
        </button>
      </div>
    </section>
  );
}
