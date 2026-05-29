// URLs relativas: la SPA llama siempre al mismo servidor que la sirve.
// No depende de VITE_API_BASE ni del puerto — funciona en dev (proxy Vite)
// y en producción (FastAPI sirve todo desde el mismo origen).
async function req(path, options = {}) {
  const res = await fetch(path, {
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
    throw new Error(`${path}: ${text || `HTTP ${res.status}`}`);
  }

  if (!contentType.includes("application/json")) {
    const text = await res.text();
    throw new Error(`Respuesta no JSON desde API (${res.status}). Revisa VITE_API_BASE. Preview: ${text.slice(0, 120)}`);
  }

  return res.json();
}

export const api = {
  listConfigs: () => req("/api/meta-settings"),
  createConfig: (data) => req("/api/meta-settings", { method: "POST", body: JSON.stringify(data) }),
  updateConfig: (id, data) => req(`/api/meta-settings/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteConfig: (id) => req(`/api/meta-settings/${id}`, { method: "DELETE" }),
  testConfig: (id) => req(`/api/meta-settings/${id}/test`, { method: "POST" }),
  listUsers: () => req("/api/users"),
  updateUser: (id, data) => req(`/api/users/${id}`, { method: "PATCH", body: JSON.stringify(data) }),

  runExplorer: (configId) => req("/api/explorer/run", { method: "POST", body: JSON.stringify({ configId }) }),
  getExplorerResult: (jobId) => req(`/api/explorer/${jobId}/result`),
  getExplorerCache: (configId) => req(`/api/explorer/cache/${configId}`),

  runBulk: (payload) => req("/api/clone/bulk", { method: "POST", body: JSON.stringify(payload) }),
  runSingle: (configId, campaignIds, copiesToCreate = 49, adsPerAdset = 1) => req("/api/clone/single", { method: "POST", body: JSON.stringify({ configId, campaignIds, copiesToCreate, adsPerAdset }) }),
  deleteCampaigns: (configId, campaignIds, batch = 10) => req("/api/delete/campaigns", { method: "POST", body: JSON.stringify({ configId, campaignIds, batch }) }),
  updateCampaignsStatus: (configId, campaignIds, status, apiVersion = "v21.0") => req("/api/campaigns/status", { method: "POST", body: JSON.stringify({ configId, campaignIds, status, apiVersion }) }),
  runReduceBudgets: (payload) => req("/api/budgets/reduce", { method: "POST", body: JSON.stringify(payload) }),

  fbSummary: (configId = "") => req(`/api/fb-catalog/summary${configId ? `?configId=${encodeURIComponent(configId)}` : ""}`),
  fbListCatalogs: (configId = "") => req(`/api/fb-catalog/catalogs${configId ? `?configId=${encodeURIComponent(configId)}` : ""}`),
  fbCreateCatalog: (payload) => req("/api/fb-catalog/catalogs", { method: "POST", body: JSON.stringify(payload) }),
  fbDeleteCatalog: (catalogId) => req(`/api/fb-catalog/catalogs/${catalogId}`, { method: "DELETE" }),
  fbListProducts: (catalogId) => req(`/api/fb-catalog/catalogs/${catalogId}/products`),
  fbSaveProducts: (catalogId, rows) => req(`/api/fb-catalog/catalogs/${catalogId}/products/bulk`, { method: "PUT", body: JSON.stringify({ rows }) }),
  fbDeleteProduct: (catalogId, productId) => req(`/api/fb-catalog/catalogs/${catalogId}/products/${productId}`, { method: "DELETE" }),
  fbListSets: (catalogId) => req(`/api/fb-catalog/catalogs/${catalogId}/sets`),
  fbListAllSets: (configId = "") => req(`/api/fb-catalog/sets/all${configId ? `?configId=${encodeURIComponent(configId)}` : ""}`),
  fbCreateSet: (catalogId, payload) => req(`/api/fb-catalog/catalogs/${catalogId}/sets`, { method: "POST", body: JSON.stringify(payload) }),
  fbDeleteSet: (catalogId, setId) => req(`/api/fb-catalog/catalogs/${catalogId}/sets/${setId}`, { method: "DELETE" }),
  fbLocales: () => req("/api/fb-catalog/locales"),
  fbSetupOptions: (configId, adAccountId = "", businessId = "") => req(`/api/fb-catalog/setup/options?configId=${encodeURIComponent(configId)}${adAccountId ? `&adAccountId=${encodeURIComponent(adAccountId)}` : ""}${businessId ? `&businessId=${encodeURIComponent(businessId)}` : ""}`),
  fbSaveSetup: (configId, payload) => req(`/api/fb-catalog/setup/${configId}`, { method: "PUT", body: JSON.stringify(payload) }),
  fbTestSetupNotification: (configId) => req(`/api/fb-catalog/setup/${configId}/test-notification`, { method: "POST" }),
  fbListMedia: (configId = "") => req(`/api/fb-catalog/media${configId ? `?configId=${encodeURIComponent(configId)}` : ""}`),
  fbCreateMedia: (payload) => req("/api/fb-catalog/media", { method: "POST", body: JSON.stringify(payload) }),
  fbUpdateMedia: (mediaId, payload) => req(`/api/fb-catalog/media/${mediaId}`, { method: "PUT", body: JSON.stringify(payload) }),
  fbDeleteMedia: (mediaId) => req(`/api/fb-catalog/media/${mediaId}`, { method: "DELETE" }),
  fbBulkDeleteMedia: (ids) => req("/api/fb-catalog/media/bulk-delete", { method: "POST", body: JSON.stringify({ ids }) }),
  fbUploadMedia: (mediaId, payload) => req(`/api/fb-catalog/media/${mediaId}/upload`, { method: "POST", body: JSON.stringify(payload) }),
  fbListCarnadas: (configId = "") => req(`/api/fb-catalog/carnadas${configId ? `?configId=${encodeURIComponent(configId)}` : ""}`),
  fbCreateCarnada: (payload) => req("/api/fb-catalog/carnadas", { method: "POST", body: JSON.stringify(payload) }),
  fbUpdateCarnada: (id, payload) => req(`/api/fb-catalog/carnadas/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  fbDeleteCarnada: (id) => req(`/api/fb-catalog/carnadas/${id}`, { method: "DELETE" }),
  fbBulkDeleteCarnadas: (ids) => req("/api/fb-catalog/carnadas/bulk-delete", { method: "POST", body: JSON.stringify({ ids }) }),
  fbListCopies: (configId = "") => req(`/api/fb-catalog/copies${configId ? `?configId=${encodeURIComponent(configId)}` : ""}`),
  fbCreateCopy: (payload) => req("/api/fb-catalog/copies", { method: "POST", body: JSON.stringify(payload) }),
  fbUpdateCopy: (id, payload) => req(`/api/fb-catalog/copies/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  fbDeleteCopy: (id) => req(`/api/fb-catalog/copies/${id}`, { method: "DELETE" }),
  fbListCampaigns: (configId = "") => req(`/api/fb-catalog/campaigns${configId ? `?configId=${encodeURIComponent(configId)}` : ""}`),
  fbCreateNormalCampaign: (payload) => req("/api/fb-catalog/campaigns/normal", { method: "POST", body: JSON.stringify(payload) }),
  fbCreateLanguageCampaign: (payload) => req("/api/fb-catalog/campaigns/language", { method: "POST", body: JSON.stringify(payload) }),
  fbCreateCatalogCampaign: (payload) => req("/api/fb-catalog/campaigns/catalog", { method: "POST", body: JSON.stringify(payload) }),
  fbDeleteCampaign: (id) => req(`/api/fb-catalog/campaigns/${id}`, { method: "DELETE" }),
  fbListTemplates: (configId = "") => req(`/api/fb-catalog/templates${configId ? `?configId=${encodeURIComponent(configId)}` : ""}`),
  fbCreateTemplate: (payload) => req("/api/fb-catalog/templates", { method: "POST", body: JSON.stringify(payload) }),
  fbDeleteTemplate: (id) => req(`/api/fb-catalog/templates/${id}`, { method: "DELETE" }),
  fbListPlanning: (configId = "") => req(`/api/fb-catalog/planning${configId ? `?configId=${encodeURIComponent(configId)}` : ""}`),
  fbCreatePlan: (payload) => req("/api/fb-catalog/planning", { method: "POST", body: JSON.stringify(payload) }),
  fbUpdatePlan: (id, payload) => req(`/api/fb-catalog/planning/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  fbDuplicatePlan: (id) => req(`/api/fb-catalog/planning/${id}/duplicate`, { method: "POST" }),
  fbDeletePlan: (id) => req(`/api/fb-catalog/planning/${id}`, { method: "DELETE" }),
  fbBulkDeletePlans: (ids) => req("/api/fb-catalog/planning/bulk-delete", { method: "POST", body: JSON.stringify({ ids }) }),
  fbExecutePlan: (id) => req(`/api/fb-catalog/planning/${id}/execute`, { method: "POST" }),
  fbExecutePending: (configId) => req(`/api/fb-catalog/planning/execute-pending?configId=${encodeURIComponent(configId)}`, { method: "POST" }),
  fbExecuteDuePlans: (configId = "") => req(`/api/fb-catalog/planning/execute-due${configId ? `?configId=${encodeURIComponent(configId)}` : ""}`, { method: "POST" }),
  fbTrickStatus: (configId = "") => req(`/api/fb-catalog/trick${configId ? `?configId=${encodeURIComponent(configId)}` : ""}`),
  fbRunTrick: (configId = "") => req(`/api/fb-catalog/trick/run-now${configId ? `?configId=${encodeURIComponent(configId)}` : ""}`, { method: "POST" }),

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
