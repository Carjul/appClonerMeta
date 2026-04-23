import React from "react";

function money(v) {
  const n = Number(v || 0);
  return `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function pct(v) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return "-";
  const n = Number(v);
  return `${n > 0 ? "+" : ""}${n.toFixed(1)}%`;
}

function hookPct(v) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return "-";
  return `${Number(v).toFixed(1)}%`;
}

function intVal(v) {
  const n = Number(v || 0);
  if (!Number.isFinite(n)) return 0;
  return Math.round(n);
}

function cpa(v) {
  const n = Number(v || 0);
  if (!Number.isFinite(n) || n <= 0) return "-";
  return money(n);
}

function verdictClass(verdict) {
  const v = String(verdict || "").toLowerCase();
  if (v === "winner") return "verdict-winner";
  if (v === "potential winner") return "verdict-potential";
  if (v === "watch list") return "verdict-watch";
  if (v === "monitor") return "verdict-monitor";
  if (v === "review") return "verdict-review";
  if (v === "new (<48h)") return "verdict-new";
  if (v === "insufficient data") return "verdict-insufficient";
  if (v === "high cpc") return "verdict-high-cpc";
  if (v === "kill") return "verdict-kill";
  return "verdict-default";
}

const verdictOrder = {
  Winner: 0,
  "Potential Winner": 1,
  "Watch List": 2,
  Monitor: 3,
  Review: 4,
  "New (<48h)": 5,
  "Insufficient Data": 6,
  "High CPC": 7,
  Kill: 8,
};

export default function AccountCampaignsBlock({
  account,
  expandAllAccounts,
  selectedCampaigns,
  selectedAccountId,
  onToggleAccountCampaigns,
  onToggleCampaign,
  onCopyCampaignId,
}) {
  const campaigns = [...(account.campaigns || [])].sort((a, b) => {
    const av = (a.metrics && a.metrics.verdict) || "";
    const bv = (b.metrics && b.metrics.verdict) || "";
    const ao = verdictOrder[av] ?? 99;
    const bo = verdictOrder[bv] ?? 99;
    if (ao !== bo) return ao - bo;
    const as = Number((a.metrics && a.metrics.spend_lifetime) || 0);
    const bs = Number((b.metrics && b.metrics.spend_lifetime) || 0);
    return bs - as;
  });

  return (
    <details className="account-block" open={expandAllAccounts}>
      <summary>
        {account.account_name} ({account.account_id}) - {campaigns.length} campañas
      </summary>
      <div className="campaign-table-wrap">
        <table className="campaign-table">
          <thead>
            <tr>
              <th>
                <input
                  type="checkbox"
                  checked={campaigns.length > 0 && campaigns.every((c) => !!selectedCampaigns[c.id])}
                  onChange={(e) => onToggleAccountCampaigns(account.account_id, campaigns, e.target.checked)}
                />
              </th>
              <th>Campaign ID</th>
              <th>Campaign Name</th>
              <th>Status</th>
              <th>Days Live</th>
              <th>Daily Budget</th>
              <th>Spend Today</th>
              <th>Purchases Today</th>
              <th>Checkouts Today</th>
              <th>CPA Checkout Today</th>
              <th>Spend Lifetime</th>
              <th>Purchases LT</th>
              <th>Cost / Purchase</th>
              <th>Checkouts LT</th>
              <th>CPA Checkout LT</th>
              <th>Hook Rate</th>
              <th>CPC</th>
              <th>CPM</th>
              <th>ROI</th>
              <th>Verdict</th>
            </tr>
          </thead>
          <tbody>
            {campaigns.map((c) => {
              const m = c.metrics || {};
              const checked = !!selectedCampaigns[c.id];
              const disabled = !checked && !!selectedAccountId && selectedAccountId !== account.account_id;
              const status = (c.effective_status || c.status || "").toUpperCase();
              return (
                <tr key={c.id} className={disabled ? "row-disabled" : "row-selectable"} onClick={() => !disabled && onToggleCampaign(account.account_id, c.id, !checked)}>
                  <td>
                    <input
                      type="checkbox"
                      checked={checked}
                      disabled={disabled}
                      onClick={(e) => e.stopPropagation()}
                      onChange={(e) => onToggleCampaign(account.account_id, c.id, e.target.checked)}
                    />
                  </td>
                  <td>
                    <button className="id-link" type="button" onClick={(e) => { e.stopPropagation(); onCopyCampaignId(c.id); }} title="Copiar ID">
                      {c.id}
                    </button>
                  </td>
                  <td className="campaign-name-cell" title={c.name || ""}>{c.name}</td>
                  <td>{status === "ACTIVE" ? "Active" : status || "-"}</td>
                  <td>{m.days_live ?? "-"}</td>
                  <td>{m.campaign_daily_budget !== null && m.campaign_daily_budget !== undefined ? money(m.campaign_daily_budget) : (c.daily_budget !== null && c.daily_budget !== undefined ? money(c.daily_budget) : "-")}</td>
                  <td>{money(m.spend_today)}</td>
                  <td>{intVal(m.purchases_today)}</td>
                  <td>{intVal(m.checkouts_today)}</td>
                  <td>{cpa(m.cpa_checkout_today)}</td>
                  <td>{money(m.spend_lifetime)}</td>
                  <td>{intVal(m.purchases_lifetime)}</td>
                  <td>{cpa(m.cost_per_purchase)}</td>
                  <td>{intVal(m.checkouts_lifetime)}</td>
                  <td>{cpa(m.cpa_checkout_lifetime)}</td>
                  <td>{hookPct(m.hook_rate)}</td>
                  <td>{money(m.cpc)}</td>
                  <td>{money(m.cpm)}</td>
                  <td>{pct(m.roi)}</td>
                  <td>
                    <span className={`verdict-chip ${verdictClass(m.verdict)}`}>{m.verdict || "-"}</span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </details>
  );
}
