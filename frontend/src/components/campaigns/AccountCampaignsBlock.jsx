import React, { useMemo, useState } from "react";

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

const numericSortKeys = new Set([
  "days_live",
  "daily_budget",
  "spend_today",
  "purchases_today",
  "checkouts_today",
  "cpa_checkout_today",
  "spend_lifetime",
  "purchases_lifetime",
  "cost_per_purchase",
  "checkouts_lifetime",
  "cpa_checkout_lifetime",
  "hook_rate",
  "cpc",
  "cpm",
  "roi",
]);

function sortValue(campaign, key) {
  const m = campaign.metrics || {};
  switch (key) {
    case "campaign_id":
      return String(campaign.id || "");
    case "campaign_name":
      return String(campaign.name || "");
    case "status":
      return String(campaign.effective_status || campaign.status || "").toUpperCase();
    case "verdict":
      return String(m.verdict || "");
    case "daily_budget":
      return m.campaign_daily_budget ?? campaign.daily_budget ?? null;
    default:
      return m[key] ?? null;
  }
}

function statusValue(campaign) {
  return String(campaign.effective_status || campaign.status || "").toUpperCase();
}

export default function AccountCampaignsBlock({
  account,
  expandAllAccounts,
  selectedCampaigns,
  selectedAccountId,
  onToggleAccountCampaigns,
  onToggleCampaign,
  onCopyCampaignId,
}) {
  const [sortBy, setSortBy] = useState("");
  const [sortDir, setSortDir] = useState("desc");

  const baseCampaigns = useMemo(
    () =>
      [...(account.campaigns || [])].sort((a, b) => {
        const av = (a.metrics && a.metrics.verdict) || "";
        const bv = (b.metrics && b.metrics.verdict) || "";
        const ao = verdictOrder[av] ?? 99;
        const bo = verdictOrder[bv] ?? 99;
        if (ao !== bo) return ao - bo;
        const as = Number((a.metrics && a.metrics.spend_lifetime) || 0);
        const bs = Number((b.metrics && b.metrics.spend_lifetime) || 0);
        return bs - as;
      }),
    [account.campaigns]
  );

  const campaigns = useMemo(() => {
    if (!sortBy) return baseCampaigns;
    const dirMul = sortDir === "desc" ? -1 : 1;
    return [...baseCampaigns].sort((a, b) => {
      const va = sortValue(a, sortBy);
      const vb = sortValue(b, sortBy);

      if (numericSortKeys.has(sortBy)) {
        const na = Number(va);
        const nb = Number(vb);
        const aMissing = !Number.isFinite(na);
        const bMissing = !Number.isFinite(nb);
        if (aMissing && bMissing) return 0;
        if (aMissing) return 1;
        if (bMissing) return -1;
        const primary = (na - nb) * dirMul;
        if (primary !== 0) return primary;
        const sa = statusValue(a);
        const sb = statusValue(b);
        const statusCmp = sa.localeCompare(sb, undefined, { sensitivity: "base" });
        if (statusCmp !== 0) return statusCmp;
        return String(a.name || "").localeCompare(String(b.name || ""), undefined, { sensitivity: "base" });
      }

      const sa = String(va || "");
      const sb = String(vb || "");
      const primary = sa.localeCompare(sb, undefined, { sensitivity: "base" }) * dirMul;
      if (primary !== 0) return primary;
      const ssa = statusValue(a);
      const ssb = statusValue(b);
      const statusCmp = ssa.localeCompare(ssb, undefined, { sensitivity: "base" });
      if (statusCmp !== 0) return statusCmp;
      return String(a.name || "").localeCompare(String(b.name || ""), undefined, { sensitivity: "base" });
    });
  }, [baseCampaigns, sortBy, sortDir]);

  function onSort(key) {
    if (sortBy === key) {
      setSortDir((prev) => (prev === "desc" ? "asc" : "desc"));
      return;
    }
    setSortBy(key);
    setSortDir(numericSortKeys.has(key) ? "desc" : "asc");
  }

  function sortArrow(key) {
    if (sortBy !== key) return "↕";
    return sortDir === "desc" ? "↓" : "↑";
  }

  function SortHead({ label, sortKey }) {
    const active = sortBy === sortKey;
    return (
      <button
        type="button"
        className={`th-sort-btn ${active ? "active" : ""}`}
        onClick={() => onSort(sortKey)}
        title={`Ordenar por ${label}`}
      >
        <span>{label}</span>
        <span className="th-sort-arrow">{sortArrow(sortKey)}</span>
      </button>
    );
  }

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
                  className="checkbox checkbox-info"
                  checked={campaigns.length > 0 && campaigns.every((c) => !!selectedCampaigns[c.id])}
                  onChange={(e) => onToggleAccountCampaigns(account.account_id, campaigns, e.target.checked)}
                />
              </th>
              <th><SortHead label="Campaign ID" sortKey="campaign_id" /></th>
              <th><SortHead label="Campaign Name" sortKey="campaign_name" /></th>
              <th><SortHead label="Status" sortKey="status" /></th>
              <th><SortHead label="Days Live" sortKey="days_live" /></th>
              <th><SortHead label="Daily Budget" sortKey="daily_budget" /></th>
              <th><SortHead label="Spend Today" sortKey="spend_today" /></th>
              <th><SortHead label="Purchases Today" sortKey="purchases_today" /></th>
              <th><SortHead label="Checkouts Today" sortKey="checkouts_today" /></th>
              <th><SortHead label="CPA Checkout Today" sortKey="cpa_checkout_today" /></th>
              <th><SortHead label="Spend Lifetime" sortKey="spend_lifetime" /></th>
              <th><SortHead label="Purchases LT" sortKey="purchases_lifetime" /></th>
              <th><SortHead label="Cost / Purchase" sortKey="cost_per_purchase" /></th>
              <th><SortHead label="Checkouts LT" sortKey="checkouts_lifetime" /></th>
              <th><SortHead label="CPA Checkout LT" sortKey="cpa_checkout_lifetime" /></th>
              <th><SortHead label="Hook Rate" sortKey="hook_rate" /></th>
              <th><SortHead label="CPC" sortKey="cpc" /></th>
              <th><SortHead label="CPM" sortKey="cpm" /></th>
              <th><SortHead label="ROI" sortKey="roi" /></th>
              <th><SortHead label="Verdict" sortKey="verdict" /></th>
            </tr>
          </thead>
          <tbody>
            {campaigns.map((c) => {
              const m = c.metrics || {};
              const checked = !!selectedCampaigns[c.id];
              const disabled = !checked && !!selectedAccountId && selectedAccountId !== account.account_id;
              const status = (c.effective_status || c.status || "").toUpperCase();
              const rowClass = disabled ? "row-disabled" : checked ? "row-selected" : "row-selectable";
              return (
                <tr key={c.id} className={rowClass} onClick={() => !disabled && onToggleCampaign(account.account_id, c.id, !checked)}>
                  <td>
                    <input
                      type="checkbox"
                      className="checkbox checkbox-info"
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
