import React from "react";
import { api } from "../api";

function nowLabel() {
  return new Date().toLocaleString(undefined, {
    month: "short",
    day: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

const T = {
  en: {
    presets: "Presets",
    newRule: "+ New Rule",
    myRules: "My Rules",
    log: "Log",
    chooseConfig: "Choose config...",
    chooseAccount: "Choose account...",
    configure: "Configure Rule",
    adAccount: "Ad Account",
    campaigns: "Campaigns",
    all: "All",
    none: "None",
    nameOptional: "Name (optional)",
    activateOnMeta: "Activate Rule on Meta",
    runs24: "Rule will run 24/7 on Meta's servers",
    type: "Rule Type",
    schedule: "Schedule",
    condition: "Condition",
    pauseActivateAtTime: "Pause or activate at a specific time",
    checkMetrics: "Check metrics and act automatically",
    details: "Details",
    action: "Action",
    hour: "Hour",
    minute: "Minute",
    timeRange: "Time Range",
    checkEvery: "Check Every",
    conditionsTitle: "CONDITIONS (all must be true)",
    addCondition: "Add Condition (AND)",
    accountCampaigns: "Account & Campaigns",
    nameSave: "Name & Save",
    createOnMeta: "Create Rule on Meta",
    clear: "Clear",
    noRules: "No rules yet.",
    noActivity: "No activity yet.",
    selectAll: "Select All",
    pauseSelected: "Pause Selected",
    activateSelected: "Activate Selected",
    deleteSelected: "Delete Selected",
    loading: "Loading...",
    selectConfigFirst: "Select a config first",
    selectAccount: "Select an account",
    noCampaigns: "No campaigns",
  },
  es: {
    presets: "Predeterminadas",
    newRule: "+ Nueva Regla",
    myRules: "Mis Reglas",
    log: "Registro",
    chooseConfig: "Seleccione configuracion...",
    chooseAccount: "Seleccione cuenta...",
    configure: "Configurar Regla",
    adAccount: "Cuenta Publicitaria",
    campaigns: "Campanas",
    all: "Todas",
    none: "Ninguna",
    nameOptional: "Nombre (opcional)",
    activateOnMeta: "Activar Regla en Meta",
    runs24: "La regla correra 24/7 en los servidores de Meta",
    type: "Tipo de Regla",
    schedule: "Horario",
    condition: "Condicion",
    pauseActivateAtTime: "Pausar o activar a una hora especifica",
    checkMetrics: "Verificar metricas y actuar automaticamente",
    details: "Detalles",
    action: "Accion",
    hour: "Hora",
    minute: "Minuto",
    timeRange: "Rango de Tiempo",
    checkEvery: "Revisar Cada",
    conditionsTitle: "CONDICIONES (todas deben cumplirse)",
    addCondition: "Agregar Condicion (Y)",
    accountCampaigns: "Cuenta y Campanas",
    nameSave: "Nombre y Guardar",
    createOnMeta: "Crear Regla en Meta",
    clear: "Limpiar",
    noRules: "No hay reglas aun.",
    noActivity: "Sin actividad aun.",
    selectAll: "Seleccionar Todas",
    pauseSelected: "Pausar Seleccionadas",
    activateSelected: "Activar Seleccionadas",
    deleteSelected: "Eliminar Seleccionadas",
    loading: "Cargando...",
    selectConfigFirst: "Seleccione una configuracion primero",
    selectAccount: "Seleccione una cuenta",
    noCampaigns: "Sin campanas",
  },
};

const METRICS = ["cpc", "cpm", "cpa_checkout", "cpa_purchase", "spend", "purchases", "checkouts", "days_running"];
const OPS = [">", ">=", "<", "<=", "=="];

export default function RulesEnginePage() {
  const [lang, setLang] = React.useState("en");
  const [tab, setTab] = React.useState("presets");
  const [configs, setConfigs] = React.useState([]);
  const [configId, setConfigId] = React.useState("");
  const [presets, setPresets] = React.useState([]);
  const [selectedPresetId, setSelectedPresetId] = React.useState("");
  const [accounts, setAccounts] = React.useState([]);
  const [accountIdPreset, setAccountIdPreset] = React.useState("");
  const [campaignsPreset, setCampaignsPreset] = React.useState([]);
  const [selectedCampaignsPreset, setSelectedCampaignsPreset] = React.useState({});
  const [accountIdCustom, setAccountIdCustom] = React.useState("");
  const [campaignsCustom, setCampaignsCustom] = React.useState([]);
  const [selectedCampaignsCustom, setSelectedCampaignsCustom] = React.useState({});
  const [customNamePreset, setCustomNamePreset] = React.useState("");
  const [customNameCustom, setCustomNameCustom] = React.useState("");
  const [customType, setCustomType] = React.useState("");
  const [customAction, setCustomAction] = React.useState("PAUSE");
  const [customHour, setCustomHour] = React.useState(23);
  const [customMinute, setCustomMinute] = React.useState(0);
  const [timeRange, setTimeRange] = React.useState("last_3d");
  const [checkFreq, setCheckFreq] = React.useState("30min");
  const [conditions, setConditions] = React.useState([{ metric: "cpc", op: ">", val: 20 }]);
  const [rules, setRules] = React.useState([]);
  const [logs, setLogs] = React.useState([]);
  const [selectedRules, setSelectedRules] = React.useState({});
  const [error, setError] = React.useState("");

  const txt = T[lang];
  const selectedPreset = presets.find((p) => p.id === selectedPresetId);
  const presetAccount = accounts.find((a) => a.id === accountIdPreset) || null;
  const customAccount = accounts.find((a) => a.id === accountIdCustom) || null;

  React.useEffect(() => {
    api
      .listConfigs()
      .then((rows) => {
        setConfigs(rows || []);
        if (rows?.[0]?._id) setConfigId(rows[0]._id);
      })
      .catch((e) => setError(String(e.message || e)));
    api
      .listRulesPresets()
      .then((rows) => {
        setPresets(rows || []);
        if (rows?.[0]?.id) setSelectedPresetId(rows[0].id);
      })
      .catch((e) => setError(String(e.message || e)));
  }, []);

  const loadBase = React.useCallback(async () => {
    if (!configId) return;
    try {
      const [accRes, rulesRes, logsRes] = await Promise.all([
        api.listRulesAccounts(configId),
        api.listRules(configId),
        api.listRulesLogs(configId),
      ]);
      setAccounts(accRes.accounts || []);
      setRules(rulesRes.rules || []);
      setLogs(logsRes.logs || []);
      setSelectedRules({});
      setAccountIdPreset("");
      setCampaignsPreset([]);
      setSelectedCampaignsPreset({});
      setAccountIdCustom("");
      setCampaignsCustom([]);
      setSelectedCampaignsCustom({});
    } catch (e) {
      setError(String(e.message || e));
    }
  }, [configId]);

  React.useEffect(() => {
    loadBase();
  }, [loadBase]);

  async function loadCampaigns(accountId, mode) {
    if (!configId || !accountId) return;
    try {
      const res = await api.listRulesCampaigns(configId, accountId);
      if (mode === "preset") {
        setCampaignsPreset(res.campaigns || []);
        setSelectedCampaignsPreset({});
      } else {
        setCampaignsCustom(res.campaigns || []);
        setSelectedCampaignsCustom({});
      }
    } catch (e) {
      setError(String(e.message || e));
    }
  }

  function toggleAll(mode, on) {
    const source = mode === "preset" ? campaignsPreset : campaignsCustom;
    if (!on) {
      if (mode === "preset") setSelectedCampaignsPreset({});
      else setSelectedCampaignsCustom({});
      return;
    }
    const next = {};
    for (const c of source) next[c.id] = true;
    if (mode === "preset") setSelectedCampaignsPreset(next);
    else setSelectedCampaignsCustom(next);
  }

  function selectedIds(mode) {
    const src = mode === "preset" ? selectedCampaignsPreset : selectedCampaignsCustom;
    return Object.keys(src).filter((k) => src[k]);
  }

  async function createPresetRule() {
    if (!configId) return setError(txt.selectConfigFirst);
    if (!presetAccount) return setError(txt.selectAccount);
    const ids = selectedIds("preset");
    if (!ids.length) return;
    await api.createRule(configId, {
      source: "preset",
      presetId: selectedPresetId,
      accountId: presetAccount.id,
      accountName: presetAccount.name,
      campaignIds: ids,
      customName: customNamePreset,
    });
    setCustomNamePreset("");
    await loadBase();
    setTab("active");
  }

  async function createCustomRule() {
    if (!configId) return setError(txt.selectConfigFirst);
    if (!customAccount) return setError(txt.selectAccount);
    const ids = selectedIds("custom");
    if (!ids.length || !customType) return;
    await api.createRule(configId, {
      source: "custom",
      customType,
      customAction: customType === "schedule" ? customAction : undefined,
      customHour,
      customMinute,
      customActionCondition: customType === "condition" ? customAction : undefined,
      timeRange,
      checkFreq,
      conditions: customType === "condition" ? conditions : undefined,
      accountId: customAccount.id,
      accountName: customAccount.name,
      campaignIds: ids,
      customName: customNameCustom,
    });
    setCustomNameCustom("");
    await loadBase();
    setTab("active");
  }

  async function toggleRule(rule) {
    await api.toggleRule(rule._id, !rule.enabled);
    await loadBase();
  }

  async function deleteRule(rule) {
    await api.deleteRule(rule._id);
    await loadBase();
  }

  async function bulkToggle(action) {
    const ids = Object.keys(selectedRules).filter((k) => selectedRules[k]);
    if (!ids.length || !configId) return;
    await api.bulkToggleRules(configId, ids, action);
    await loadBase();
  }

  async function bulkDelete() {
    const ids = Object.keys(selectedRules).filter((k) => selectedRules[k]);
    if (!ids.length || !configId) return;
    await api.bulkDeleteRules(configId, ids);
    await loadBase();
  }

  async function clearLogs() {
    if (!configId) return;
    await api.clearRulesLogs(configId);
    await loadBase();
  }

  function addCondition() {
    setConditions((prev) => [...prev, { metric: "spend", op: ">", val: 0 }]);
  }

  function removeCondition(idx) {
    setConditions((prev) => prev.filter((_, i) => i !== idx));
  }

  function setCondition(idx, key, value) {
    setConditions((prev) => prev.map((c, i) => (i === idx ? { ...c, [key]: value } : c)));
  }

  return (
    <div className="rules-engine">
      <svg style={{ display: "none" }}>
        <symbol id="i-moon" viewBox="0 0 24 24"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" stroke="currentColor" fill="none" /></symbol>
        <symbol id="i-sun" viewBox="0 0 24 24"><circle cx="12" cy="12" r="5" stroke="currentColor" fill="none" /><line x1="12" y1="1" x2="12" y2="3" stroke="currentColor" /><line x1="12" y1="21" x2="12" y2="23" stroke="currentColor" /><line x1="4.22" y1="4.22" x2="5.64" y2="5.64" stroke="currentColor" /><line x1="18.36" y1="18.36" x2="19.78" y2="19.78" stroke="currentColor" /><line x1="1" y1="12" x2="3" y2="12" stroke="currentColor" /><line x1="21" y1="12" x2="23" y2="12" stroke="currentColor" /><line x1="4.22" y1="19.78" x2="5.64" y2="18.36" stroke="currentColor" /><line x1="18.36" y1="5.64" x2="19.78" y2="4.22" stroke="currentColor" /></symbol>
        <symbol id="i-sunrise" viewBox="0 0 24 24"><path d="M17 18a5 5 0 0 0-10 0" stroke="currentColor" fill="none" /><line x1="12" y1="9" x2="12" y2="2" stroke="currentColor" /><line x1="4.22" y1="10.22" x2="5.64" y2="11.64" stroke="currentColor" /><line x1="1" y1="18" x2="3" y2="18" stroke="currentColor" /><line x1="21" y1="18" x2="23" y2="18" stroke="currentColor" /><line x1="18.36" y1="11.64" x2="19.78" y2="10.22" stroke="currentColor" /><line x1="23" y1="22" x2="1" y2="22" stroke="currentColor" /><polyline points="8 6 12 2 16 6" stroke="currentColor" fill="none" /></symbol>
        <symbol id="i-play" viewBox="0 0 24 24"><polygon points="5 3 19 12 5 21 5 3" stroke="currentColor" fill="none" /></symbol>
        <symbol id="i-x-circle" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" stroke="currentColor" fill="none" /><line x1="15" y1="9" x2="9" y2="15" stroke="currentColor" /><line x1="9" y1="9" x2="15" y2="15" stroke="currentColor" /></symbol>
        <symbol id="i-trending-down" viewBox="0 0 24 24"><polyline points="23 18 13.5 8.5 8.5 13.5 1 6" stroke="currentColor" fill="none" /><polyline points="17 18 23 18 23 12" stroke="currentColor" fill="none" /></symbol>
        <symbol id="i-alert" viewBox="0 0 24 24"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" stroke="currentColor" fill="none" /><line x1="12" y1="9" x2="12" y2="13" stroke="currentColor" /><line x1="12" y1="17" x2="12.01" y2="17" stroke="currentColor" /></symbol>
        <symbol id="i-slash" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" stroke="currentColor" fill="none" /><line x1="4.93" y1="4.93" x2="19.07" y2="19.07" stroke="currentColor" /></symbol>
        <symbol id="i-dollar" viewBox="0 0 24 24"><line x1="12" y1="1" x2="12" y2="23" stroke="currentColor" /><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" stroke="currentColor" fill="none" /></symbol>
      </svg>
      <div className="hdr">
        <h1>Rules Engine</h1>
        <div className="hdr-r">
          <span>{nowLabel()}</span>
          <select className="config-pick" value={configId} onChange={(e) => setConfigId(e.target.value)}>
            <option value="">{txt.chooseConfig}</option>
            {configs.map((c) => (
              <option key={c._id} value={c._id}>{c.name}</option>
            ))}
          </select>
          <div className="lang-t">
            <button className={`lang-b ${lang === "en" ? "active" : ""}`} onClick={() => setLang("en")}>EN</button>
            <button className={`lang-b ${lang === "es" ? "active" : ""}`} onClick={() => setLang("es")}>ES</button>
          </div>
        </div>
      </div>

      <div className="ctn">
        {error ? <div className="card" style={{ borderColor: "#7f1d1d", color: "#ef4444" }}>{error}</div> : null}
        <div className="tabs">
          <button className={`tab ${tab === "presets" ? "active" : ""}`} onClick={() => setTab("presets")}>{txt.presets}</button>
          <button className={`tab ${tab === "custom" ? "active" : ""}`} onClick={() => setTab("custom")}>{txt.newRule}</button>
          <button className={`tab ${tab === "active" ? "active" : ""}`} onClick={() => setTab("active")}>{txt.myRules} ({rules.length})</button>
          <button className={`tab ${tab === "logs" ? "active" : ""}`} onClick={() => setTab("logs")}>{txt.log}</button>
        </div>

        {tab === "presets" ? (
          <div className="split">
            <div>
              <div className="g2">
                {presets.map((p) => (
                  <div key={p.id} className={`card ck ${selectedPresetId === p.id ? "sel" : ""}`} onClick={() => setSelectedPresetId(p.id)}>
                    <div className="hi">?
                      <div className="tt">{lang === "es" ? (p.help_es || p.help) : p.help}</div>
                    </div>
                    <div className="pre">
                      <div className="pre-e">
                        <svg className={`ico ico-${p.icon}`} viewBox="0 0 24 24" fill="none">
                          <use href={`#i-${p.icon}`} />
                        </svg>
                      </div>
                      <div className="pre-i">
                        <h3>{lang === "es" ? (p.name_es || p.name) : p.name}</h3>
                        <p>{lang === "es" ? (p.desc_es || p.desc) : p.desc}</p>
                        <div className="badge-row" style={{ marginTop: 6 }}>
                          <span className={`tag ${p.action === "PAUSE" ? "t-p" : "t-a"}`}>{p.action}</span>
                          <span className={`tag ${p.type === "schedule" ? "t-s" : "t-c"}`}>{String(p.type || "").toUpperCase()}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <div className="pnl">
                <div className="pnl-t">{txt.configure}</div>
                <div className="fg" style={{ marginBottom: 12 }}>
                  <label>{txt.adAccount}</label>
                  <select value={accountIdPreset} onChange={(e) => { setAccountIdPreset(e.target.value); loadCampaigns(e.target.value, "preset"); }}>
                    <option value="">{txt.chooseAccount}</option>
                    {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
                  </select>
                </div>

                <div className="fg" style={{ marginBottom: 8 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <label style={{ margin: 0 }}>{txt.campaigns}</label>
                    <div>
                      <button type="button" className="btn btn-s btn-g" onClick={() => toggleAll("preset", true)}>{txt.all}</button>
                      <button type="button" className="btn btn-s btn-g" onClick={() => toggleAll("preset", false)}>{txt.none}</button>
                    </div>
                  </div>
                  <div className="card" style={{ padding: 0, marginTop: 4 }}>
                    <div className="cl">
                      {!accountIdPreset ? <div className="empty" style={{ padding: 24 }}><p>{txt.selectAccount}</p></div> : null}
                      {accountIdPreset && !campaignsPreset.length ? <div className="empty" style={{ padding: 24 }}><p>{txt.noCampaigns}</p></div> : null}
                      {campaignsPreset.map((c) => (
                        <div className="ci" key={c.id}>
                          <input type="checkbox" checked={!!selectedCampaignsPreset[c.id]} onChange={(e) => setSelectedCampaignsPreset((prev) => ({ ...prev, [c.id]: e.target.checked }))} />
                          <div>
                            <div className="cn">{c.name}</div>
                            <div className="cid">{c.id}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="fg" style={{ marginBottom: 16 }}>
                  <label>{txt.nameOptional}</label>
                  <input type="text" value={customNamePreset} onChange={(e) => setCustomNamePreset(e.target.value)} />
                </div>
                <button type="button" className="btn btn-p" onClick={createPresetRule}>{txt.activateOnMeta}</button>
                <div style={{ textAlign: "center", marginTop: 8, fontSize: 11, color: "#6b7280" }}>{txt.runs24}</div>
              </div>
            </div>
          </div>
        ) : null}

        {tab === "custom" ? (
          <div>
            <div className="pnl" style={{ marginBottom: 12 }}>
              <div className="pnl-t"><span className="step">1</span> {txt.type}</div>
              <div className="g2">
                <div className={`card ck ${customType === "schedule" ? "sel" : ""}`} onClick={() => setCustomType("schedule")} style={{ textAlign: "center" }}>
                  <strong style={{ fontSize: 14, color: "#f3f4f6" }}>{txt.schedule}</strong>
                  <p style={{ fontSize: 12, color: "#6b7280" }}>{txt.pauseActivateAtTime}</p>
                </div>
                <div className={`card ck ${customType === "condition" ? "sel" : ""}`} onClick={() => setCustomType("condition")} style={{ textAlign: "center" }}>
                  <strong style={{ fontSize: 14, color: "#f3f4f6" }}>{txt.condition}</strong>
                  <p style={{ fontSize: 12, color: "#6b7280" }}>{txt.checkMetrics}</p>
                </div>
              </div>
            </div>

            <div className="pnl" style={{ marginBottom: 12, display: customType ? "block" : "none" }}>
              <div className="pnl-t"><span className="step">2</span> {txt.details}</div>

              {customType === "schedule" ? (
                <div className="fr">
                  <div className="fg"><label>{txt.action}</label><select value={customAction} onChange={(e) => setCustomAction(e.target.value)}><option value="PAUSE">Pause</option><option value="ACTIVATE">Activate</option></select></div>
                  <div className="fg"><label>{txt.hour}</label><input type="number" min="0" max="23" value={customHour} onChange={(e) => setCustomHour(Number(e.target.value || 0))} /></div>
                  <div className="fg"><label>{txt.minute}</label><input type="number" min="0" max="59" value={customMinute} onChange={(e) => setCustomMinute(Number(e.target.value || 0))} /></div>
                </div>
              ) : null}

              {customType === "condition" ? (
                <>
                  <div className="fr" style={{ marginBottom: 16 }}>
                    <div className="fg"><label>{txt.timeRange}</label><select value={timeRange} onChange={(e) => setTimeRange(e.target.value)}><option value="today">Today</option><option value="last_3d">Last 3 Days</option><option value="last_7d">Last 7 Days</option><option value="lifetime">Lifetime</option></select></div>
                    <div className="fg"><label>{txt.checkEvery}</label><select value={checkFreq} onChange={(e) => setCheckFreq(e.target.value)}><option value="30min">30 min</option><option value="1h">1 hora</option><option value="4h">4 horas</option><option value="6h">6 horas</option><option value="12h">12 horas</option><option value="24h">24 horas</option></select></div>
                    <div className="fg"><label>{txt.action}</label><select value={customAction} onChange={(e) => setCustomAction(e.target.value)}><option value="PAUSE">Pause Adsets</option><option value="ACTIVATE">Activate Adsets</option></select></div>
                  </div>

                  <div className="pnl-t">{txt.conditionsTitle}</div>
                  {conditions.map((c, idx) => (
                    <React.Fragment key={idx}>
                      {idx > 0 ? <div className="and-label">AND</div> : null}
                      <div className="cond-row">
                        <div className="fg">
                          <label>Metric</label>
                          <select value={c.metric} onChange={(e) => setCondition(idx, "metric", e.target.value)}>
                            {METRICS.map((m) => <option key={m} value={m}>{m}</option>)}
                          </select>
                        </div>
                        <div className="fg">
                          <label>Operator</label>
                          <select value={c.op} onChange={(e) => setCondition(idx, "op", e.target.value)}>
                            {OPS.map((op) => <option key={op} value={op}>{op}</option>)}
                          </select>
                        </div>
                        <div className="fg">
                          <label>Value</label>
                          <input type="number" step="0.01" value={c.val} onChange={(e) => setCondition(idx, "val", Number(e.target.value || 0))} />
                        </div>
                        <button type="button" className="cond-rm" onClick={() => removeCondition(idx)}>x</button>
                      </div>
                    </React.Fragment>
                  ))}
                  <button type="button" className="add-cond" onClick={addCondition}>+ {txt.addCondition}</button>
                </>
              ) : null}
            </div>

            <div className="pnl" style={{ marginBottom: 12, display: customType ? "block" : "none" }}>
              <div className="pnl-t"><span className="step">3</span> {txt.accountCampaigns}</div>
              <div className="fg" style={{ marginBottom: 8 }}>
                <select value={accountIdCustom} onChange={(e) => { setAccountIdCustom(e.target.value); loadCampaigns(e.target.value, "custom"); }}>
                  <option value="">{txt.chooseAccount}</option>
                  {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
                </select>
              </div>
              <div className="card" style={{ padding: 0 }}>
                <div className="cl">
                  {!accountIdCustom ? <div className="empty" style={{ padding: 24 }}><p>{txt.selectAccount}</p></div> : null}
                  {accountIdCustom && !campaignsCustom.length ? <div className="empty" style={{ padding: 24 }}><p>{txt.noCampaigns}</p></div> : null}
                  {campaignsCustom.map((c) => (
                    <div className="ci" key={c.id}>
                      <input type="checkbox" checked={!!selectedCampaignsCustom[c.id]} onChange={(e) => setSelectedCampaignsCustom((prev) => ({ ...prev, [c.id]: e.target.checked }))} />
                      <div>
                        <div className="cn">{c.name}</div>
                        <div className="cid">{c.id}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="pnl" style={{ display: customType ? "block" : "none" }}>
              <div className="pnl-t"><span className="step">4</span> {txt.nameSave}</div>
              <div className="fg" style={{ marginBottom: 12 }}>
                <input type="text" value={customNameCustom} onChange={(e) => setCustomNameCustom(e.target.value)} placeholder="Rule name..." />
              </div>
              <button type="button" className="btn btn-p" onClick={createCustomRule}>{txt.createOnMeta}</button>
            </div>
          </div>
        ) : null}

        {tab === "active" ? (
          <div>
            {rules.length ? (
              <>
                <div className="bulk-bar">
                  <label>
                    <input
                      type="checkbox"
                      checked={rules.length > 0 && rules.every((r) => !!selectedRules[r._id])}
                      onChange={(e) => {
                        if (!e.target.checked) return setSelectedRules({});
                        setSelectedRules(Object.fromEntries(rules.map((r) => [r._id, true])));
                      }}
                    /> {txt.selectAll}
                  </label>
                  <div style={{ display: "flex", gap: 6 }}>
                    <button type="button" className="btn btn-s btn-d" onClick={() => bulkToggle("pause")}>{txt.pauseSelected}</button>
                    <button type="button" className="btn btn-s btn-ok" onClick={() => bulkToggle("activate")}>{txt.activateSelected}</button>
                    <button type="button" className="btn btn-s btn-d" onClick={bulkDelete}>{txt.deleteSelected}</button>
                  </div>
                </div>
                {rules.map((r) => (
                  <div className="card" key={r._id}>
                    <div className="rr">
                      <div className="rl">
                        <input type="checkbox" checked={!!selectedRules[r._id]} onChange={(e) => setSelectedRules((prev) => ({ ...prev, [r._id]: e.target.checked }))} />
                        <div className={`dot ${r.enabled ? "dot-on" : "dot-off"}`} />
                        <div>
                          <strong style={{ color: "#f3f4f6", fontSize: 14 }}>{r.name}</strong>
                          <span className="badge-row inline">
                            <span className={`tag ${r.action === "PAUSE" ? "t-p" : "t-a"}`}>{r.action}</span>
                            {r.type === "schedule" ? <span className="tag t-s">{`${String(r.hour ?? 0).padStart(2, "0")}:${String(r.min ?? 0).padStart(2, "0")}`}</span> : null}
                            {r.is_custom ? <span className="tag t-cu">CUSTOM</span> : null}
                          </span>
                          {r.meta_rule_id ? <span className="meta-b">META ✓</span> : null}
                        </div>
                      </div>
                      <div className="ra">
                        <button type="button" className={`btn btn-s ${r.enabled ? "btn-d" : "btn-ok"}`} onClick={() => toggleRule(r)}>{r.enabled ? "Pause" : "Start"}</button>
                        <button type="button" className="btn btn-s btn-d" onClick={() => deleteRule(r)}>x</button>
                      </div>
                    </div>
                    <div className="rm">{r.account_name} · {(r.campaign_ids || []).length} campaigns · {r.type}{r.check_freq ? ` · every ${r.check_freq}` : ""}</div>
                    {Array.isArray(r.conditions) && r.conditions.length ? (
                      <div className="conds-display">
                        {r.conditions.map((c, idx) => (
                          <React.Fragment key={`${c.metric}-${idx}`}>
                            {c.metric} {c.op} {c.val}
                            {idx < r.conditions.length - 1 ? <span style={{ color: "#3b82f6" }}> AND </span> : null}
                          </React.Fragment>
                        ))}
                      </div>
                    ) : null}
                    <div className="rc" style={{ marginTop: 4 }}>
                      {Object.entries(r.campaign_names || {}).map(([cid, cname]) => <span key={cid}>{cname}</span>)}
                    </div>
                  </div>
                ))}
              </>
            ) : (
              <div className="empty"><p style={{ fontSize: 28 }}>📃</p><p>{txt.noRules}</p></div>
            )}
          </div>
        ) : null}

        {tab === "logs" ? (
          <div>
            {logs.length ? (
              <>
                <div style={{ marginBottom: 12 }}>
                  <button type="button" className="btn btn-s btn-d" onClick={clearLogs}>{txt.clear}</button>
                </div>
                <div className="card" style={{ padding: 0 }}>
                  {logs.map((l, idx) => (
                    <div key={`${l.timestamp}-${idx}`} className={`lr ${l.ok ? "l-ok" : "l-err"}`}>
                      <div>
                          {l.ok ? "✅" : "❌"} <strong>{l.rule}</strong> {"->"} {l.action} · {l.account}
                        {l.detail && l.detail !== "OK" ? (
                          <div style={{ fontSize: 11, marginTop: 2, color: l.ok ? "#fbbf24" : "#ef4444" }}>{l.detail}</div>
                        ) : null}
                      </div>
                      <span className="lt">{l.timestamp}</span>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="empty"><p style={{ fontSize: 28 }}>📄</p><p>{txt.noActivity}</p></div>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}
