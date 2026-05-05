const API_BASE = (import.meta.env.VITE_API_BASE || window.location.origin).replace(/\/$/, "");

async function req(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  const contentType = res.headers.get("content-type") || "";

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }

  if (!contentType.includes("application/json")) {
    const text = await res.text();
    throw new Error(`Respuesta no JSON desde API (${res.status}). Revisa VITE_API_BASE. Preview: ${text.slice(0, 120)}`);
  }

  return res.json();
}

export const api = {
  listConfigs: () => req("/api/configs"),
  createConfig: (data) => req("/api/configs", { method: "POST", body: JSON.stringify(data) }),
  updateConfig: (id, data) => req(`/api/configs/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteConfig: (id) => req(`/api/configs/${id}`, { method: "DELETE" }),

  runExplorer: (configId) => req("/api/explorer/run", { method: "POST", body: JSON.stringify({ configId }) }),
  getExplorerResult: (jobId) => req(`/api/explorer/${jobId}/result`),
  getExplorerCache: (configId) => req(`/api/explorer/cache/${configId}`),

  runBulk: (configId, campaignId) => req("/api/clone/bulk", { method: "POST", body: JSON.stringify({ configId, campaignId }) }),
  runSingle: (configId, campaignIds, copiesToCreate = 49) => req("/api/clone/single", { method: "POST", body: JSON.stringify({ configId, campaignIds, copiesToCreate }) }),
  deleteCampaigns: (configId, campaignIds, batch = 10) => req("/api/delete/campaigns", { method: "POST", body: JSON.stringify({ configId, campaignIds, batch }) }),
  updateCampaignsStatus: (configId, campaignIds, status, apiVersion = "v21.0") => req("/api/campaigns/status", { method: "POST", body: JSON.stringify({ configId, campaignIds, status, apiVersion }) }),
  runReduceBudgets: (payload) => req("/api/budgets/reduce", { method: "POST", body: JSON.stringify(payload) }),

  runDailyReport: (configId, periods) => req("/api/daily-report/run", { method: "POST", body: JSON.stringify({ configId, periods }) }),
  getDailyReportLatest: (configId) => req(`/api/daily-report/latest/${configId}`),
  getDailyReportHistory: (configId, limit = 20) => req(`/api/daily-report/history/${configId}?limit=${limit}`),

  listRulesPresets: () => req("/api/rules/presets"),
  listRulesAccounts: (configId) => req(`/api/rules/config/${configId}/accounts`),
  listRulesCampaigns: (configId, accountId) => req(`/api/rules/config/${configId}/accounts/${accountId}/campaigns`),
  listRules: (configId) => req(`/api/rules/config/${configId}`),
  createRule: (configId, payload) => req(`/api/rules/config/${configId}`, { method: "POST", body: JSON.stringify(payload) }),
  toggleRule: (ruleId, enabled) => req(`/api/rules/${ruleId}/toggle`, { method: "POST", body: JSON.stringify({ enabled }) }),
  deleteRule: (ruleId) => req(`/api/rules/${ruleId}`, { method: "DELETE" }),
  bulkToggleRules: (configId, ruleIds, action) => req(`/api/rules/config/${configId}/bulk/toggle`, { method: "POST", body: JSON.stringify({ ruleIds, action }) }),
  bulkDeleteRules: (configId, ruleIds) => req(`/api/rules/config/${configId}/bulk/delete`, { method: "POST", body: JSON.stringify({ ruleIds }) }),
  listRulesLogs: (configId, limit = 80) => req(`/api/rules/config/${configId}/logs?limit=${limit}`),
  clearRulesLogs: (configId) => req(`/api/rules/config/${configId}/logs/clear`, { method: "POST" }),

  listJobs: () => req("/api/jobs"),
  getJob: (jobId) => req(`/api/jobs/${jobId}`),
  getJobLogs: (jobId, limit = 5000) => req(`/api/jobs/${jobId}/logs?limit=${limit}`),
  cancelJob: (jobId) => req(`/api/jobs/${jobId}/cancel`, { method: "POST" }),
  rerunJob: (jobId) => req(`/api/jobs/${jobId}/rerun`, { method: "POST" }),
  deleteJob: (jobId) => req(`/api/jobs/${jobId}`, { method: "DELETE" }),
};
