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
  runSingle: (configId, campaignIds) => req("/api/clone/single", { method: "POST", body: JSON.stringify({ configId, campaignIds }) }),
  deleteCampaigns: (configId, campaignIds, batch = 10) => req("/api/delete/campaigns", { method: "POST", body: JSON.stringify({ configId, campaignIds, batch }) }),

  listJobs: () => req("/api/jobs"),
  getJob: (jobId) => req(`/api/jobs/${jobId}`),
  getJobLogs: (jobId) => req(`/api/jobs/${jobId}/logs`),
  cancelJob: (jobId) => req(`/api/jobs/${jobId}/cancel`, { method: "POST" }),
  deleteJob: (jobId) => req(`/api/jobs/${jobId}`, { method: "DELETE" }),
};
