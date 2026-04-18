import React from "react";

export default function BudgetOptimizerPanel({
  configs,
  reduceBm1ConfigId,
  reduceBm2ConfigId,
  reduceExecute,
  reduceMinSpend,
  reduceTargetBudget,
  onSetReduceBm1ConfigId,
  onSetReduceBm2ConfigId,
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
          <span className="field-label">Config BM1 (token)</span>
          <select value={reduceBm1ConfigId} onChange={(e) => onSetReduceBm1ConfigId(e.target.value)}>
            <option value="">No usar</option>
            {configs.map((c) => (
              <option key={c._id} value={c._id}>{c.name}</option>
            ))}
          </select>
        </div>

        <div className="budget-field">
          <span className="field-label">Config BM2 (token)</span>
          <select value={reduceBm2ConfigId} onChange={(e) => onSetReduceBm2ConfigId(e.target.value)}>
            <option value="">No usar</option>
            {configs.map((c) => (
              <option key={c._id} value={c._id}>{c.name}</option>
            ))}
          </select>
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

        <button className="btn btn-primary budget-run" onClick={onRunReduceBudgets}>Ejecutar optimizer</button>
      </div>
    </section>
  );
}
