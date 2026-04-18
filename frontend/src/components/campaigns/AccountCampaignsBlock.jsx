import React from "react";

export default function AccountCampaignsBlock({
  account,
  expandAllAccounts,
  selectedCampaigns,
  selectedAccountId,
  onToggleAccountCampaigns,
  onToggleCampaign,
  onCopyCampaignId,
}) {
  return (
    <details className="account-block" open={expandAllAccounts}>
      <summary>
        {account.account_name} ({account.account_id}) - {(account.campaigns || []).length} campañas
      </summary>
      <table className="campaign-table">
        <thead>
          <tr>
            <th>
              <input
                type="checkbox"
                checked={(account.campaigns || []).length > 0 && (account.campaigns || []).every((c) => !!selectedCampaigns[c.id])}
                onChange={(e) => onToggleAccountCampaigns(account.account_id, account.campaigns || [], e.target.checked)}
              />
            </th>
            <th>Campaña ID</th>
            <th>Nombre</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {(account.campaigns || []).map((c) => {
            const checked = !!selectedCampaigns[c.id];
            const disabled = !checked && !!selectedAccountId && selectedAccountId !== account.account_id;
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
                <td>{c.name}</td>
                <td>{c.status}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </details>
  );
}
