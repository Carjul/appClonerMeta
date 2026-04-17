const API_BASE = import.meta.env.VITE_API_BASE || "https://appclonermeta.onrender.com";

async function req(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
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

  runBulk: (configId, campaignId) => req("/api/clone/bulk", { method: "POST", body: JSON.stringify({ configId, campaignId }) }),
  runSingle: (configId, campaignIds) => req("/api/clone/single", { method: "POST", body: JSON.stringify({ configId, campaignIds }) }),

  listJobs: () => req("/api/jobs"),
  getJob: (jobId) => req(`/api/jobs/${jobId}`),
  getJobLogs: (jobId) => req(`/api/jobs/${jobId}/logs`),
  cancelJob: (jobId) => req(`/api/jobs/${jobId}/cancel`, { method: "POST" }),
  deleteJob: (jobId) => req(`/api/jobs/${jobId}`, { method: "DELETE" }),
};
