import React, { useEffect, useMemo, useState } from "react";
import { api } from "../api";

const emptyProduct = () => ({
  id: "",
  tag: "dirty",
  videoLabel: "",
  retailerId: "",
  title: "",
  description: "",
  availability: "in stock",
  price: "10.00 USD",
  link: "",
  imageLink: "",
  videoUrl: "",
  brand: "Brand",
});

const icons = {
  home: "⌂",
  setup: "⚙",
  catalog: "▣",
  campaign: "↗",
  planning: "☷",
  template: "◇",
  media: "□",
  carnadas: "◈",
  copies: "Aa",
  trick: "◒",
  plus: "+",
  table: "▦",
  layers: "▤",
  trash: "×",
};

function Icon({ name }) {
  return <span className="fb-icon" aria-hidden="true">{icons[name] || "•"}</span>;
}

function toProductRow(row) {
  return {
    id: row._id || "",
    tag: row.tag || "dirty",
    videoLabel: row.video_label || "",
    retailerId: row.retailer_id || "",
    title: row.title || "",
    description: row.description || "",
    availability: row.availability || "in stock",
    price: row.price || "10.00 USD",
    link: row.link || "",
    imageLink: row.image_link || "",
    videoUrl: row.video_url || "",
    brand: row.brand || "Brand",
  };
}

export default function FbCatalogModule() {
  const [page, setPage] = useState("home");
  const [theme, setTheme] = useState(() => localStorage.getItem("fbCatalogTheme") || "dark");
  const [lang, setLang] = useState(() => localStorage.getItem("fbCatalogLang") || "es");
  const [configs, setConfigs] = useState([]);
  const [configId, setConfigId] = useState("");
  const [summary, setSummary] = useState(null);
  const [catalogs, setCatalogs] = useState([]);
  const [selectedCatalogId, setSelectedCatalogId] = useState("");
  const [products, setProducts] = useState([]);
  const [setsPayload, setSetsPayload] = useState({ sets: [], products: [] });
  const [allSets, setAllSets] = useState([]);
  const [locales, setLocales] = useState([]);
  const [setupOptions, setSetupOptions] = useState(null);
  const [media, setMedia] = useState([]);
  const [carnadas, setCarnadas] = useState([]);
  const [copies, setCopies] = useState([]);
  const [campaigns, setCampaigns] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [plans, setPlans] = useState([]);
  const [trick, setTrick] = useState({ pending: [], done: [] });
  const [alert, setAlert] = useState(null);

  const activeConfig = useMemo(() => configs.find((cfg) => cfg._id === configId), [configs, configId]);
  const selectedCatalog = useMemo(() => catalogs.find((cat) => cat._id === selectedCatalogId), [catalogs, selectedCatalogId]);

  useEffect(() => {
    loadConfigRows();
    api.fbLocales().then(setLocales).catch(() => null);
  }, []);

  async function loadConfigRows(nextActiveId = "") {
    try {
      const rows = await api.listConfigs();
      setConfigs(rows);
      if (nextActiveId) setConfigId(nextActiveId);
      else if (!configId && rows[0]) setConfigId(rows[0]._id);
    } catch (e) {
      setAlert({ type: "error", message: String(e.message || e) });
    }
  }

  useEffect(() => {
    localStorage.setItem("fbCatalogTheme", theme);
  }, [theme]);

  useEffect(() => {
    localStorage.setItem("fbCatalogLang", lang);
  }, [lang]);

  useEffect(() => {
    loadOverview();
  }, [configId]);

  useEffect(() => {
    if (page === "products" && selectedCatalogId) loadProducts(selectedCatalogId);
    if (page === "sets" && selectedCatalogId) loadSets(selectedCatalogId);
    if ((page === "setup" || page === "catalog-new") && configId) loadSetupOptions();
    if (page === "media") loadMedia();
    if (page === "carnadas") loadCarnadas();
    if (page === "copies") {
      loadCarnadas();
      loadCopies();
    }
    if (page.startsWith("campaigns")) {
      if (configId) loadSetupOptions();
      loadMedia();
      loadCarnadas();
      loadCopies();
      loadCampaigns();
      loadAllSets();
      loadTemplates();
      loadPlans();
    }
    if (page === "templates") loadTemplates();
    if (page === "planning") {
      if (configId) loadSetupOptions();
      loadMedia();
      loadCopies();
      loadAllSets();
      loadPlans();
    }
    if (page === "trick") loadTrick();
  }, [page, selectedCatalogId]);

  useEffect(() => {
    if ((page === "setup" || page === "catalog-new") && configId) loadSetupOptions();
    if (page === "media") loadMedia();
    if (page === "carnadas") loadCarnadas();
    if (page === "copies") {
      loadCarnadas();
      loadCopies();
    }
    if (page.startsWith("campaigns")) {
      if (configId) loadSetupOptions();
      loadCampaigns();
      loadAllSets();
      loadTemplates();
      loadPlans();
    }
    if (page === "templates") loadTemplates();
    if (page === "planning") {
      if (configId) loadSetupOptions();
      loadMedia();
      loadCopies();
      loadAllSets();
      loadPlans();
    }
    if (page === "trick") loadTrick();
  }, [configId]);

  async function loadOverview() {
    try {
      const [nextSummary, nextCatalogs] = await Promise.all([
        api.fbSummary(configId),
        api.fbListCatalogs(configId),
      ]);
      setSummary(nextSummary);
      setCatalogs(nextCatalogs);
      if (!selectedCatalogId && nextCatalogs[0]) setSelectedCatalogId(nextCatalogs[0]._id);
    } catch (e) {
      setAlert({ type: "error", message: String(e.message || e) });
    }
  }

  async function loadProducts(catalogId) {
    try {
      const data = await api.fbListProducts(catalogId);
      setProducts((data.products || []).map(toProductRow));
    } catch (e) {
      setAlert({ type: "error", message: String(e.message || e) });
    }
  }

  async function loadSets(catalogId) {
    try {
      const data = await api.fbListSets(catalogId);
      setSetsPayload(data);
    } catch (e) {
      setAlert({ type: "error", message: String(e.message || e) });
    }
  }

  async function loadAllSets() {
    try {
      setAllSets(await api.fbListAllSets(configId));
    } catch (e) {
      setAlert({ type: "error", message: String(e.message || e) });
    }
  }

  async function loadSetupOptions(adAccountId = "", businessId = "") {
    if (!configId) return;
    try {
      const data = await api.fbSetupOptions(configId, adAccountId, businessId);
      setSetupOptions(data);
      setAlert(null);
    } catch (e) {
      setAlert({ type: "error", message: String(e.message || e) });
    }
  }

  async function loadMedia() {
    try {
      setMedia(await api.fbListMedia(configId));
    } catch (e) {
      setAlert({ type: "error", message: String(e.message || e) });
    }
  }

  async function loadCarnadas() {
    try {
      setCarnadas(await api.fbListCarnadas(configId));
    } catch (e) {
      setAlert({ type: "error", message: String(e.message || e) });
    }
  }

  async function loadCopies() {
    try {
      setCopies(await api.fbListCopies(configId));
    } catch (e) {
      setAlert({ type: "error", message: String(e.message || e) });
    }
  }

  async function loadCampaigns() {
    try {
      setCampaigns(await api.fbListCampaigns(configId));
    } catch (e) {
      setAlert({ type: "error", message: String(e.message || e) });
    }
  }

  async function loadTemplates() {
    try {
      setTemplates(await api.fbListTemplates(configId));
    } catch (e) {
      setAlert({ type: "error", message: String(e.message || e) });
    }
  }

  async function loadPlans() {
    try {
      setPlans(await api.fbListPlanning(configId));
    } catch (e) {
      setAlert({ type: "error", message: String(e.message || e) });
    }
  }

  async function loadTrick() {
    try {
      setTrick(await api.fbTrickStatus(configId));
    } catch (e) {
      setAlert({ type: "error", message: String(e.message || e) });
    }
  }

  function nav(target, catalogId = selectedCatalogId) {
    if (catalogId) setSelectedCatalogId(catalogId);
    setPage(target);
  }

  return (
    <div className={`fb-shell ${theme === "light" ? "fb-light" : ""}`}>
      <aside className="fb-sidebar">
        <div className="fb-brand" onClick={() => nav("home")}>
          <div className="fb-brand-title"><Icon name="home" /> FB Catalog</div>
          <div className="fb-subtitle">Dashboard de Campanas</div>
        </div>
        <nav className="fb-nav">
          <NavItem page={page} id="home" label="Inicio" icon="home" onClick={nav} />
          <NavItem page={page} id="setup" label="Configuracion" icon="setup" onClick={nav} />
          <NavItem page={page} id="catalogs" label="Catalogos" icon="catalog" onClick={nav} />
          <NavItem page={page} id="campaigns" label="Campanas" icon="campaign" onClick={nav} />
          <NavItem page={page} id="planning" label="Planificacion" icon="planning" onClick={nav} />
          <NavItem page={page} id="templates" label="Plantillas" icon="template" onClick={nav} />
          <NavItem page={page} id="media" label="Creativos" icon="media" onClick={nav} />
          <NavItem page={page} id="carnadas" label="Carnadas" icon="carnadas" onClick={nav} />
          <NavItem page={page} id="copies" label="Copy Multi-Idioma" icon="copies" onClick={nav} />
          <NavItem page={page} id="trick" label="Truco automatico" icon="trick" onClick={nav} />
        </nav>
        <div className="fb-sidebar-foot">
          <span>v2.2</span>
          <div className="fb-foot-actions">
            <button className="fb-icon-btn" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>{theme === "dark" ? "moon" : "sun"}</button>
            <button className="fb-icon-btn" onClick={() => setLang(lang === "es" ? "en" : "es")}>{lang.toUpperCase()}</button>
          </div>
        </div>
      </aside>

      <main className="fb-main">
        <div className="fb-content">
          <div className="fb-topline">
            <div>{alert && <span className={`fb-alert ${alert.type}`}>{alert.message}</span>}</div>
            <label className="fb-config-picker">
              Config
              <select value={configId} onChange={(e) => setConfigId(e.target.value)}>
                {configs.map((cfg) => <option key={cfg._id} value={cfg._id}>{cfg.name}</option>)}
              </select>
            </label>
          </div>
          {page === "home" && <HomePage summary={summary} tokenSet={Boolean(activeConfig?.tokenConfigured)} onGo={nav} />}
          {page === "catalogs" && <CatalogsPage catalogs={catalogs} reload={loadOverview} onGo={nav} setAlert={setAlert} />}
          {page === "catalog-new" && <CatalogCreatePage configId={configId} activeConfig={activeConfig} setupOptions={setupOptions} reload={loadOverview} onGo={nav} setAlert={setAlert} />}
          {page === "products" && <ProductsPage catalog={selectedCatalog} products={products} setProducts={setProducts} reload={() => loadProducts(selectedCatalogId)} onGo={nav} setAlert={setAlert} />}
          {page === "sets" && <SetsPage catalog={selectedCatalog} data={setsPayload} reload={() => loadSets(selectedCatalogId)} setAlert={setAlert} configId={configId} />}
          {page === "setup" && <SetupPage configId={configId} activeConfig={activeConfig} configs={configs} setConfigId={setConfigId} reloadConfigs={loadConfigRows} options={setupOptions} reload={loadSetupOptions} setAlert={setAlert} />}
          {page === "media" && <MediaPage configId={configId} setupOptions={setupOptions} media={media} reload={loadMedia} setAlert={setAlert} />}
          {page === "carnadas" && <CarnadasPage configId={configId} locales={locales} carnadas={carnadas} reload={loadCarnadas} setAlert={setAlert} />}
          {page === "copies" && <CopiesPage configId={configId} locales={locales} carnadas={carnadas} copies={copies} reload={loadCopies} setAlert={setAlert} />}
          {page === "campaigns" && <CampaignsListPage campaigns={campaigns} reload={loadCampaigns} onGo={nav} setAlert={setAlert} />}
          {page === "campaigns-new-type" && <CampaignTypePage onGo={nav} />}
          {page === "campaigns-new-catalog" && <CampaignCatalogPage configId={configId} setupOptions={setupOptions} sets={allSets} templates={templates} plans={plans} reloadTemplates={loadTemplates} reloadPlans={loadPlans} reloadCampaigns={loadCampaigns} onGo={nav} setAlert={setAlert} />}
          {page === "campaigns-new-normal" && <CampaignsBuilderPage initialType="normal" configId={configId} setupOptions={setupOptions} media={media} copies={copies} campaigns={campaigns} templates={templates} plans={plans} reload={loadCampaigns} reloadTemplates={loadTemplates} reloadPlans={loadPlans} onGo={nav} setAlert={setAlert} />}
          {page === "campaigns-new-language" && <CampaignsBuilderPage initialType="language" configId={configId} setupOptions={setupOptions} media={media} copies={copies} campaigns={campaigns} templates={templates} plans={plans} reload={loadCampaigns} reloadTemplates={loadTemplates} reloadPlans={loadPlans} onGo={nav} setAlert={setAlert} />}
          {page === "templates" && <TemplatesPage configId={configId} templates={templates} reload={loadTemplates} setAlert={setAlert} />}
          {page === "planning" && <PlanningPage configId={configId} plans={plans} reload={loadPlans} setupOptions={setupOptions} media={media} copies={copies} sets={allSets} setAlert={setAlert} />}
          {page === "trick" && <TrickPage configId={configId} trick={trick} reload={loadTrick} setAlert={setAlert} />}
          {!['home', 'catalogs', 'catalog-new', 'products', 'sets', 'setup', 'media', 'carnadas', 'copies', 'campaigns', 'campaigns-new-type', 'campaigns-new-catalog', 'campaigns-new-normal', 'campaigns-new-language', 'templates', 'planning', 'trick'].includes(page) && <ComingSoon page={page} />}
        </div>
      </main>
    </div>
  );
}

function NavItem({ page, id, label, icon, onClick, disabled }) {
  const active = page === id || (id === "campaigns" && page.startsWith("campaigns")) || (id === "catalogs" && ["catalog-new", "products", "sets"].includes(page));
  return (
    <button className={`fb-nav-item nav-${id} ${active ? "active" : ""}`} onClick={() => !disabled && onClick(id)} disabled={disabled}>
      <Icon name={icon} /> <span>{label}</span>{disabled && <small>fase 2</small>}
    </button>
  );
}

function HomePage({ summary, tokenSet, onGo }) {
  return (
    <>
      <div className="fb-title-block">
        <h1><Icon name="home" /> Inicio</h1>
        <p>Panel de control para campanas de catalogo.</p>
      </div>
      {!tokenSet && <div className="fb-warning"><strong>Token de Facebook no configurado.</strong><span>Selecciona o crea una configuracion con token en el modulo principal.</span></div>}
      <div className="fb-stat-grid">
        <Stat label="Catalogos" value={summary?.catalogs || 0} />
        <Stat label="Productos" value={summary?.products || 0} />
        <Stat label="Sets" value={summary?.sets || 0} />
        <Stat label="Campanas" value={summary?.campaigns || 0} />
        <Stat label="Plantillas" value={summary?.templates || 0} />
      </div>
      <div className="fb-two-col">
        <section className="fb-card">
          <h2><Icon name="trick" /> Estado del Truco</h2>
          <div className={summary?.pendingTrick ? "fb-big warn" : "fb-big ok"}>{summary?.pendingTrick || 0}</div>
          <p>campanas esperando aprobacion para apagar blancos</p>
        </section>
        <section className="fb-card">
          <h2><Icon name="campaign" /> Acciones rapidas</h2>
          <div className="fb-stack">
            <button className="fb-btn primary" onClick={() => onGo("catalog-new")}><Icon name="plus" /> Nuevo catalogo</button>
            <button className="fb-btn" onClick={() => onGo("catalogs")}><Icon name="table" /> Editar productos tipo sheet</button>
            <button className="fb-btn ok" onClick={() => onGo("campaigns-new-type")}><Icon name="campaign" /> Nueva campana</button>
          </div>
          <p className="fb-muted">Fase 1: catalogos, productos, sets y feed CSV.</p>
        </section>
      </div>
    </>
  );
}

function Stat({ label, value }) {
  return <div className="fb-stat"><span>{label}</span><strong>{value}</strong></div>;
}

function CatalogsPage({ catalogs, reload, onGo, setAlert }) {
  async function remove(id) {
    if (!confirm("Borrar este catalogo y todos sus productos?")) return;
    await api.fbDeleteCatalog(id);
    await reload();
  }

  return (
    <>
      <div className="fb-page-head">
        <h1 className="title-cat"><Icon name="catalog" /> Catalogos</h1>
        <button className="fb-btn primary" onClick={() => onGo("catalog-new")}><Icon name="plus" /> Nuevo catalogo</button>
      </div>
      {!catalogs.length ? <div className="fb-empty">No tienes catalogos aun. Crea uno para empezar.</div> : (
        <div className="fb-table-card">
          <table className="fb-table">
            <thead><tr><th>Nombre</th><th>FB Catalog ID</th><th>Feed URL publica</th><th>Acciones</th></tr></thead>
            <tbody>{catalogs.map((cat) => (
              <tr key={cat._id}>
                <td><strong>{cat.name}</strong></td>
                <td className="fb-muted small">{cat.fb_catalog_id}</td>
                <td><code>{cat.feedUrl}</code></td>
                <td className="fb-actions-cell">
                  <button onClick={() => onGo("products", cat._id)}><Icon name="table" /> Productos</button>
                  <button onClick={() => onGo("sets", cat._id)}><Icon name="layers" /> Sets</button>
                  <button className="danger" onClick={() => remove(cat._id)}><Icon name="trash" /> Borrar</button>
                </td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}
    </>
  );
}

function CatalogCreatePage({ configId, activeConfig, setupOptions, reload, onGo, setAlert }) {
  const [form, setForm] = useState({ name: "", businessId: "", pixelId: "", syncToMeta: false });

  useEffect(() => {
    setForm((prev) => ({ ...prev, businessId: activeConfig?.bm_id || "" }));
  }, [activeConfig?._id]);

  async function create(e) {
    e.preventDefault();
    try {
      const created = await api.fbCreateCatalog({ ...form, configId });
      setForm({ name: "", businessId: activeConfig?.bm_id || "", pixelId: "", syncToMeta: false });
      const warnings = (created?.warnings || []).map((item) => `${item.step}: ${typeof item.detail === "string" ? item.detail : item.detail?.message || JSON.stringify(item.detail)}`).join(" | ");
      setAlert({ type: warnings ? "warning" : "success", message: warnings ? `Catalogo creado con advertencias: ${warnings}` : "Catalogo creado." });
      await reload();
      onGo("catalogs");
    } catch (err) {
      setAlert({ type: "error", message: String(err.message || err) });
    }
  }

  return (
    <>
      <div className="fb-title-block"><h1 className="title-cat"><Icon name="catalog" /> Nuevo Catalogo</h1></div>
      <section className="fb-card fb-form-card narrow">
        <form className="fb-stacked-form" onSubmit={create}>
          <label>Nombre del catalogo<input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="CAT-THM72-2026-05" /></label>
          <label>Business Manager ID<input required value={form.businessId} onChange={(e) => setForm({ ...form, businessId: e.target.value })} placeholder="631835841698356" /></label>
          <label>Pixel ID<input value={form.pixelId || setupOptions?.config?.default_pixel_id || ""} onChange={(e) => setForm({ ...form, pixelId: e.target.value })} placeholder="Opcional" /></label>
          <label className="fb-checkbox-card"><input type="checkbox" checked={form.syncToMeta} onChange={(e) => setForm({ ...form, syncToMeta: e.target.checked })} /><span><strong>Sincronizar a Meta inmediatamente</strong><small>Crea el catalogo y feed en Commerce Manager via API.</small></span></label>
          <div className="fb-actions-cell"><button className="fb-btn primary"><Icon name="plus" /> Crear catalogo</button><button type="button" className="fb-btn" onClick={() => onGo("catalogs")}>Cancelar</button></div>
        </form>
      </section>
    </>
  );
}

function ProductsPage({ catalog, products, setProducts, reload, onGo, setAlert }) {
  if (!catalog) return <div className="fb-empty">Selecciona un catalogo primero.</div>;

  function update(index, field, value) {
    setProducts(products.map((row, i) => (i === index ? { ...row, [field]: value } : row)));
  }

  async function save(e) {
    e.preventDefault();
    try {
      await api.fbSaveProducts(catalog._id, products);
      setAlert({ type: "success", message: "Productos guardados." });
      await reload();
    } catch (err) {
      setAlert({ type: "error", message: String(err.message || err) });
    }
  }

  async function remove(row) {
    if (!row.id) {
      setProducts(products.filter((x) => x !== row));
      return;
    }
    if (!confirm("Borrar este producto?")) return;
    await api.fbDeleteProduct(catalog._id, row.id);
    await reload();
  }

  return (
    <>
      <div className="fb-breadcrumb"><button onClick={() => onGo("catalogs")}>Catalogos</button> / {catalog.name}</div>
      <div className="fb-page-head compact">
        <h1><Icon name="table" /> Productos del catalogo</h1>
        <button className="fb-btn" onClick={() => onGo("sets", catalog._id)}><Icon name="layers" /> Sets</button>
      </div>
      <p className="fb-muted">Catalogo: <code>{catalog.name}</code> - Feed CSV: <code>/feed/{catalog.feed_slug}.csv</code></p>
      <form onSubmit={save} className="fb-sheet-card">
        <div className="fb-sheet-wrap">
          <table className="fb-sheet">
            <thead><tr><th>Etiqueta</th><th>Etiqueta de Video</th><th>ID Producto</th><th>Titulo</th><th>Descripcion</th><th>Disponibilidad</th><th>Precio</th><th>Link</th><th>URL Imagen</th><th>URL Video</th><th>Marca</th><th></th></tr></thead>
            <tbody>{products.map((row, index) => (
              <tr key={row.id || `new-${index}`}>
                <td><select className={row.tag === "clean" ? "tag-clean" : "tag-dirty"} value={row.tag} onChange={(e) => update(index, "tag", e.target.value)}><option value="dirty">Sucio</option><option value="clean">Limpio</option></select></td>
                <td><input className="mono small" value={row.videoLabel} onChange={(e) => update(index, "videoLabel", e.target.value)} placeholder="05_L01_V1" /></td>
                <td><input className="mono tiny" required value={row.retailerId} onChange={(e) => update(index, "retailerId", e.target.value)} /></td>
                <td><input required value={row.title} onChange={(e) => update(index, "title", e.target.value)} /></td>
                <td><textarea rows="2" value={row.description} onChange={(e) => update(index, "description", e.target.value)} /></td>
                <td><select value={row.availability} onChange={(e) => update(index, "availability", e.target.value)}><option value="in stock">in stock</option><option value="out of stock">out of stock</option></select></td>
                <td><input className="tiny" value={row.price} onChange={(e) => update(index, "price", e.target.value)} /></td>
                <td><input required value={row.link} onChange={(e) => update(index, "link", e.target.value)} /></td>
                <td><input required value={row.imageLink} onChange={(e) => update(index, "imageLink", e.target.value)} /></td>
                <td><input value={row.videoUrl} onChange={(e) => update(index, "videoUrl", e.target.value)} /></td>
                <td><input className="tiny" value={row.brand} onChange={(e) => update(index, "brand", e.target.value)} /></td>
                <td><button type="button" className="danger text" onClick={() => remove(row)}>×</button></td>
              </tr>
            ))}</tbody>
          </table>
        </div>
        <div className="fb-sheet-actions">
          <button type="button" className="fb-btn" onClick={() => setProducts([...products, emptyProduct()])}><Icon name="plus" /> Agregar fila</button>
          <button className="fb-btn primary">Guardar todo</button>
        </div>
      </form>
    </>
  );
}

function SetsPage({ catalog, data, reload, setAlert, configId }) {
  const [name, setName] = useState("");
  const [selected, setSelected] = useState({});
  const [syncToMeta, setSyncToMeta] = useState(false);
  if (!catalog) return <div className="fb-empty">Selecciona un catalogo primero.</div>;

  async function create(e) {
    e.preventDefault();
    const productIds = Object.entries(selected).filter(([, checked]) => checked).map(([id]) => id);
    try {
      await api.fbCreateSet(catalog._id, { name, productIds, syncToMeta, configId });
      setName("");
      setSelected({});
      setSyncToMeta(false);
      setAlert({ type: "success", message: "Set creado." });
      await reload();
    } catch (err) {
      setAlert({ type: "error", message: String(err.message || err) });
    }
  }

  async function remove(setId) {
    if (!confirm("Borrar este set?")) return;
    await api.fbDeleteSet(catalog._id, setId);
    await reload();
  }

  function applyPreset(preset) {
    const products = data.products || [];
    const cleans = products.filter((p) => p.tag === "clean");
    const dirties = products.filter((p) => p.tag !== "clean");
    const next = {};
    const pick = (rows) => rows.forEach((p) => { next[p._id] = true; });
    if (preset === "clean1+dirty1") { pick(cleans.slice(0, 1)); pick(dirties.slice(0, 1)); }
    if (preset === "clean2+dirty1") { pick(cleans.slice(0, 2)); pick(dirties.slice(0, 1)); }
    if (preset === "clean4+dirty2") { pick(cleans.slice(0, 4)); pick(dirties.slice(0, 2)); }
    if (preset === "all_dirty") pick(dirties);
    if (preset === "all_clean") pick(cleans);
    if (preset === "all") pick(products);
    setSelected(next);
  }

  return (
    <>
      <div className="fb-page-head compact"><h1><Icon name="layers" /> Sets - {catalog.name}</h1></div>
      <section className="fb-card">
        <h2>Nuevo set</h2>
        <form onSubmit={create} className="fb-set-builder">
          <label>Nombre opcional<input value={name} onChange={(e) => setName(e.target.value)} placeholder="Auto si lo dejas vacio" /></label>
          <label className="fb-check"><input type="checkbox" checked={syncToMeta} onChange={(e) => setSyncToMeta(e.target.checked)} /> Sincronizar a Meta</label>
          <div className="fb-preset-box"><strong><Icon name="campaign" /> Plantillas rapidas:</strong><button type="button" onClick={() => applyPreset("clean1+dirty1")}>1 sucio + 1 limpio</button><button type="button" onClick={() => applyPreset("clean2+dirty1")}>1 sucio + 2 limpios</button><button type="button" onClick={() => applyPreset("clean4+dirty2")}>2 sucios + 4 limpios</button><button type="button" onClick={() => applyPreset("all_dirty")}>Solo sucios</button><button type="button" onClick={() => applyPreset("all_clean")}>Solo limpios</button><button type="button" onClick={() => applyPreset("all")}>Todos</button></div>
          <div className="fb-product-pick">
            {(data.products || []).map((product) => <label key={product._id}><input type="checkbox" checked={Boolean(selected[product._id])} onChange={(e) => setSelected({ ...selected, [product._id]: e.target.checked })} /> <span className={`tag-pill ${product.tag === "clean" ? "tag-clean" : "tag-dirty"}`}>{product.tag === "clean" ? "Limpio" : "Sucio"}</span> {product.video_label || product.retailer_id} - {product.title}</label>)}
          </div>
          <button className="fb-btn primary">Crear set</button>
        </form>
      </section>
      <div className="fb-table-card">
        <table className="fb-table">
          <thead><tr><th>Nombre</th><th>Productos</th><th>Sincronizado a Meta</th><th>Acciones</th></tr></thead>
          <tbody>{(data.sets || []).map((set) => <tr key={set._id}><td><strong>{set.name}</strong></td><td>{(set.retailer_ids || []).join(", ")}</td><td>{set.fb_set_id || "no"}</td><td><button className="danger" onClick={() => remove(set._id)}>Borrar</button></td></tr>)}</tbody>
        </table>
      </div>
    </>
  );
}

function SetupPage({ configId, activeConfig, configs, setConfigId, reloadConfigs, options, reload, setAlert }) {
  const cfg = options?.config || {};
  const activeRow = configs.find((item) => item._id === configId) || {};
  const tokenConfigured = cfg.tokenConfigured ?? activeRow.tokenConfigured;
  const emptyConnection = { name: "", bmId: "", accessToken: "", activateNow: true };
  const [connection, setConnection] = useState(emptyConnection);
  const [form, setForm] = useState({
    businessId: "",
    adAccountId: "",
    pageId: "",
    pixelId: "",
    telegramBotToken: "",
    telegramChatId: "",
    slackWebhookUrl: "",
    notifyOnApproval: true,
    notifyOnConversion: true,
  });

  useEffect(() => {
    setForm({
      businessId: cfg.default_business_id || cfg.bm_id || "",
      adAccountId: cfg.default_ad_account_id || "",
      pageId: cfg.default_page_id || "",
      pixelId: cfg.default_pixel_id || "",
      telegramBotToken: cfg.telegram_bot_token || "",
      telegramChatId: cfg.telegram_chat_id || "",
      slackWebhookUrl: cfg.slack_webhook_url || "",
      notifyOnApproval: cfg.notify_on_approval !== false,
      notifyOnConversion: cfg.notify_on_conversion !== false,
    });
  }, [cfg._id, cfg.default_ad_account_id]);

  useEffect(() => {
    if (configId && (!options || options.config?._id !== configId)) {
      reload("", activeConfig?.bm_id || "");
    }
  }, [configId]);

  async function save(e) {
    e.preventDefault();
    try {
      await api.fbSaveSetup(configId, form);
      setAlert({ type: "success", message: "Configuracion FB Catalog guardada." });
      await reload(form.adAccountId);
    } catch (err) {
      setAlert({ type: "error", message: String(err.message || err) });
    }
  }

  function change(name, value) {
    const next = { ...form, [name]: value };
    if (name === "businessId") {
      const accountsForBm = (options?.accounts || []).filter((item) => (item.business || {}).id === value);
      if (value && !accountsForBm.some((item) => item.id === next.adAccountId)) {
        next.adAccountId = "";
        next.pixelId = "";
      }
    }
    setForm(next);
    if (name === "businessId") reload("", value);
    if (name === "adAccountId") reload(value, next.businessId);
  }

  async function testNotification() {
    try {
      const res = await api.fbTestSetupNotification(configId);
      const ok = [res.telegram ? "Telegram" : "", res.slack ? "Slack" : ""].filter(Boolean).join(", ");
      setAlert({ type: ok ? "success" : "error", message: ok ? `Prueba enviada: ${ok}` : "No se pudo enviar a Telegram/Slack (revisa tokens)." });
    } catch (err) {
      setAlert({ type: "error", message: String(err.message || err) });
    }
  }

  async function saveConnection(e) {
    e.preventDefault();
    try {
      const created = await api.createConfig({ name: connection.name, bmId: connection.bmId, accessToken: connection.accessToken });
      try {
        await api.testConfig(created._id);
      } catch (testErr) {
        setAlert({ type: "error", message: `Conexion guardada, pero el token no valido: ${String(testErr.message || testErr)}` });
      }
      setConnection(emptyConnection);
      if (connection.activateNow) await reloadConfigs(created._id);
      else await reloadConfigs();
      setAlert((prev) => prev?.type === "error" ? prev : { type: "success", message: "Conexion guardada y token probado." });
    } catch (err) {
      setAlert({ type: "error", message: String(err.message || err) });
    }
  }

  async function testConnection(id) {
    try {
      await api.testConfig(id);
      await reloadConfigs();
      setAlert({ type: "success", message: "Token valido." });
    } catch (err) {
      setAlert({ type: "error", message: String(err.message || err) });
    }
  }

  async function deleteConnection(id) {
    if (!confirm("Borrar esta conexion?")) return;
    await api.deleteConfig(id);
    await reloadConfigs();
  }

  const explorerAccounts = (activeConfig?.explorer_accounts || []).map((item) => ({
    id: item.account_id?.startsWith("act_") ? item.account_id : `act_${item.account_id}`,
    name: item.account_name || item.name || item.account_id,
    account_id: (item.account_id || "").replace("act_", ""),
    currency: item.currency || "",
    business: item.business || (activeConfig?.bm_id ? { id: activeConfig.bm_id, name: activeConfig.name || "BM guardado" } : {}),
  }));
  const allAccounts = (options?.accounts?.length ? options.accounts : explorerAccounts) || [];
  const filteredAccounts = allAccounts;
  const matchingAccounts = form.businessId ? allAccounts.filter((item) => (item.business || {}).id === form.businessId) : allAccounts;
  const selectedAccount = allAccounts.find((item) => item.id === form.adAccountId);
  const pages = options?.pages || [];
  const pixels = options?.pixels || [];

  return (
    <>
      <div className="fb-title-block"><h1><Icon name="setup" /> Configuracion</h1><p>{`Defaults del modulo usando la conexion activa (${cfg.name || "sin nombre"}).`}</p></div>
      {!options && <div className="fb-warning"><strong>Cargando datos de Meta...</strong><span>Si esto no desaparece, revisa que el backend este corriendo en <code>http://localhost:8000</code>.</span></div>}
      {options && !tokenConfigured && <div className="fb-warning"><strong>Token no configurado.</strong><span>Agrega el token en Conexiones Meta para cargar cuentas, paginas y pixeles.</span></div>}
      <section className="fb-card fb-form-card">
        <div className="fb-page-head compact"><h2><Icon name="setup" /> Conexiones Meta</h2>{cfg.name && <span className="fb-pill ok">Activa: {cfg.name}</span>}</div>
        <p className="fb-muted">Guarda multiples tokens, prueba si sirven y deja una conexion activa para trabajar en toda la pagina.</p>
        <form onSubmit={saveConnection} className="fb-connection-form">
          <label>Nombre de la conexion<input required value={connection.name} onChange={(e) => setConnection({ ...connection, name: e.target.value })} placeholder="BM USA Principal" /></label>
          <label>Business Manager inicial<input value={connection.bmId} onChange={(e) => setConnection({ ...connection, bmId: e.target.value })} placeholder="Opcional" /></label>
          <label className="wide">Token de Meta<textarea required rows="3" className="mono" value={connection.accessToken} onChange={(e) => setConnection({ ...connection, accessToken: e.target.value })} placeholder="EAAB... con scopes ads_management, business_management, catalog_management" /></label>
          <label className="fb-check"><input type="checkbox" checked={connection.activateNow} onChange={(e) => setConnection({ ...connection, activateNow: e.target.checked })} /> Activar al guardar</label>
          <button className="fb-btn primary"><Icon name="plus" /> Guardar y probar conexion</button>
        </form>
        {!!configs.length && <div className="fb-table-card inner"><table className="fb-table"><thead><tr><th>Nombre</th><th>BM</th><th>Token</th><th>Estado</th><th>Acciones</th></tr></thead><tbody>{configs.map((item) => <tr key={item._id}><td><strong>{item.name}</strong>{item._id === configId && <div className="small fb-ok-text">Activa</div>}</td><td className="small">{item.bm_id || "Sin BM"}</td><td className="small">{item.tokenConfigured ? "Configurado" : "Sin token"}</td><td className="small">{item.is_valid === false ? <span className="fb-pill err">Sin validar</span> : <span className="fb-pill ok">Valido</span>}<div className="fb-muted">{item.last_tested_at || ""}</div>{item.last_error && <div className="fb-error-text">{item.last_error}</div>}</td><td className="fb-actions-cell"><button onClick={() => testConnection(item._id)}>Probar</button>{item._id !== configId && <button className="primary" onClick={() => setConfigId(item._id)}>Activar</button>}<button className="danger" onClick={() => deleteConnection(item._id)}>Borrar</button></td></tr>)}</tbody></table></div>}
      </section>
      <div className="fb-stat-grid compact">
        <Stat label="BMs" value={(options?.businesses || []).length} />
        <Stat label="Cuentas" value={filteredAccounts.length} />
        <Stat label="Paginas" value={pages.length} />
        <Stat label="Pixeles" value={pixels.length} />
        <Stat label="Token" value={tokenConfigured ? "OK" : "NO"} />
      </div>
      <form onSubmit={save} className="fb-card fb-setup-grid">
        <label>Business Manager<select value={form.businessId} onChange={(e) => change("businessId", e.target.value)}><option value="">Todos los BM / ninguno</option>{(options?.businesses || []).map((item) => <option key={item.id} value={item.id}>{item.name || "BM"} - {item.id}</option>)}</select><small>ID seleccionado: {form.businessId || "ninguno"}{form.businessId && matchingAccounts.length === 0 ? " | Este BM no devolvio cuentas directas; mostrando cuentas accesibles por token." : ""}</small></label>
        <label>Cuenta publicitaria<select value={form.adAccountId} onChange={(e) => change("adAccountId", e.target.value)}><option value="">Selecciona cuenta</option>{filteredAccounts.map((item) => <option key={item.id} value={item.id}>{item.name} - {item.id} ({item.currency}) | BM: {(item.business || {}).name || "sin BM"} {(item.business || {}).id || ""}</option>)}</select><small>{selectedAccount?.business?.name ? `BM real de la cuenta: ${selectedAccount.business.name} (${selectedAccount.business.id})` : "Selecciona una cuenta para cargar pixeles"}</small></label>
        <label>Pagina de Facebook<select value={form.pageId} onChange={(e) => change("pageId", e.target.value)}><option value="">Selecciona pagina</option>{pages.map((item) => <option key={item.id} value={item.id}>{item.name} - {item.id}</option>)}</select><small>ID seleccionado: {form.pageId || "ninguno"}</small></label>
        <label>Pixel<select value={form.pixelId} onChange={(e) => change("pixelId", e.target.value)}><option value="">Selecciona pixel</option>{pixels.map((item) => <option key={item.id} value={item.id}>{item.name} - {item.id}</option>)}</select><small>{form.adAccountId ? `Pixeles de ${form.adAccountId}` : "Selecciona cuenta para cargar pixeles"}</small></label>
        <label>Telegram bot token<input value={form.telegramBotToken} onChange={(e) => change("telegramBotToken", e.target.value)} placeholder="Opcional" /></label>
        <label>Telegram chat ID<input value={form.telegramChatId} onChange={(e) => change("telegramChatId", e.target.value)} placeholder="Opcional" /></label>
        <label>Slack webhook<input value={form.slackWebhookUrl} onChange={(e) => change("slackWebhookUrl", e.target.value)} placeholder="Opcional" /></label>
        <label className="fb-check"><input type="checkbox" checked={form.notifyOnApproval} onChange={(e) => change("notifyOnApproval", e.target.checked)} /> Notificar approvals</label>
        <label className="fb-check"><input type="checkbox" checked={form.notifyOnConversion} onChange={(e) => change("notifyOnConversion", e.target.checked)} /> Notificar conversiones</label>
        <button className="fb-btn primary">Guardar defaults</button>
        <button type="button" className="fb-btn" onClick={testNotification}>Enviar prueba Telegram/Slack</button>
      </form>
    </>
  );
}

function MediaPage({ configId, setupOptions, media, reload, setAlert }) {
  const empty = { id: "", name: "", type: "image", publicUrl: "", notes: "", isDefault: false };
  const [form, setForm] = useState(empty);
  const [uploading, setUploading] = useState("");
  const [selectedIds, setSelectedIds] = useState([]);
  const defaultAccount = setupOptions?.config?.default_ad_account_id || "";

  function edit(item) {
    setForm({ id: item._id, name: item.name || "", type: item.type || "image", publicUrl: item.public_url || "", notes: item.notes || "", isDefault: Boolean(item.is_default) });
  }

  async function save(e) {
    e.preventDefault();
    const payload = { configId, name: form.name, type: form.type, publicUrl: form.publicUrl, notes: form.notes, isDefault: form.isDefault };
    try {
      if (form.id) await api.fbUpdateMedia(form.id, payload);
      else await api.fbCreateMedia(payload);
      setForm(empty);
      setAlert({ type: "success", message: "Creativo guardado." });
      await reload();
    } catch (err) {
      setAlert({ type: "error", message: String(err.message || err) });
    }
  }

  async function upload(item) {
    setUploading(item._id);
    try {
      await api.fbUploadMedia(item._id, { configId, adAccountId: defaultAccount });
      setAlert({ type: "success", message: "Creativo subido a Meta." });
      await reload();
    } catch (err) {
      setAlert({ type: "error", message: String(err.message || err) });
    } finally {
      setUploading("");
    }
  }

  async function remove(id) {
    if (!confirm("Borrar creativo?")) return;
    await api.fbDeleteMedia(id);
    await reload();
  }

  async function bulkRemove() {
    if (!selectedIds.length || !confirm("Borrar los seleccionados?")) return;
    await api.fbBulkDeleteMedia(selectedIds);
    setSelectedIds([]);
    await reload();
  }

  function toggleSelected(id) {
    setSelectedIds((prev) => prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]);
  }

  return (
    <>
      <div className="fb-page-head"><h1><Icon name="media" /> Creativos</h1></div>
      <section className="fb-card fb-form-card">
        <h2><Icon name="plus" /> {form.id ? "Editar creativo" : "Agregar creativo"}</h2>
        <form onSubmit={save} className="fb-media-form">
          <label>Nombre<input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="BizOp US #1" /></label>
          <label>Tipo<select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}><option value="image">Imagen</option><option value="video">Video</option></select></label>
          <label>URL del creativo<input required className="mono" value={form.publicUrl} onChange={(e) => setForm({ ...form, publicUrl: e.target.value })} placeholder="https://cdn.example.com/creativo.jpg" /></label>
          <label className="fb-check"><input type="checkbox" checked={form.isDefault} onChange={(e) => setForm({ ...form, isDefault: e.target.checked })} /> Carnada limpia</label>
          <label className="wide">Notas<input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="Opcional" /></label>
          <button className="fb-btn primary">Guardar</button>
          {form.id && <button type="button" className="fb-btn" onClick={() => setForm(empty)}>Cancelar</button>}
        </form>
      </section>
      {!!media.length && <div className="fb-bulkbar"><button className="danger" disabled={!selectedIds.length} onClick={bulkRemove}>Borrar seleccionados</button><span>{selectedIds.length} seleccionados</span></div>}
      <div className="fb-table-card">
        <table className="fb-table">
          <thead><tr><th><input type="checkbox" checked={!!media.length && selectedIds.length === media.length} onChange={(e) => setSelectedIds(e.target.checked ? media.map((item) => item._id) : [])} /></th><th>Nombre</th><th>Tipo</th><th>Rol</th><th>URL</th><th>En Meta</th><th>Acciones</th></tr></thead>
          <tbody>{media.map((item) => <tr key={item._id}><td><input type="checkbox" checked={selectedIds.includes(item._id)} onChange={() => toggleSelected(item._id)} /></td><td><strong>{item.name}</strong></td><td><span className="fb-pill">{item.type}</span></td><td>{item.is_default ? <span className="fb-pill ok">Carnada</span> : <span className="fb-pill err">Real</span>}</td><td className="small"><a href={item.public_url} target="_blank" rel="noreferrer">{item.public_url}</a></td><td>{item.uploaded_to_meta ? <span className="fb-ok-text">{item.meta_id}</span> : <span className="fb-muted">pendiente</span>}</td><td className="fb-actions-cell"><button onClick={() => edit(item)}>Editar</button>{!item.uploaded_to_meta && <button disabled={uploading === item._id} onClick={() => upload(item)}>{uploading === item._id ? "Subiendo..." : "Subir a Meta"}</button>}<button className="danger" onClick={() => remove(item._id)}>Borrar</button></td></tr>)}</tbody>
        </table>
      </div>
    </>
  );
}

function CarnadasPage({ configId, locales, carnadas, reload, setAlert }) {
  const empty = { id: "", localeId: 6, body: "", title: "", description: "", url: "", notes: "" };
  const [form, setForm] = useState(empty);
  const [selectedIds, setSelectedIds] = useState([]);

  function edit(item) {
    setForm({ id: item._id, localeId: item.locale_id || 6, body: item.body || "", title: item.title || "", description: item.description || "", url: item.url || "", notes: item.notes || "" });
  }

  async function save(e) {
    e.preventDefault();
    const payload = { configId, localeId: Number(form.localeId), body: form.body, title: form.title, description: form.description, url: form.url, notes: form.notes };
    try {
      if (form.id) await api.fbUpdateCarnada(form.id, payload);
      else await api.fbCreateCarnada(payload);
      setForm(empty);
      setAlert({ type: "success", message: "Carnada guardada." });
      await reload();
    } catch (err) {
      setAlert({ type: "error", message: String(err.message || err) });
    }
  }

  async function remove(id) {
    if (!confirm("Borrar carnada?")) return;
    await api.fbDeleteCarnada(id);
    await reload();
  }

  async function bulkRemove() {
    if (!selectedIds.length || !confirm("Borrar los seleccionados?")) return;
    await api.fbBulkDeleteCarnadas(selectedIds);
    setSelectedIds([]);
    await reload();
  }

  function toggleSelected(id) {
    setSelectedIds((prev) => prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]);
  }

  return (
    <>
      <div className="fb-page-head"><h1><Icon name="carnadas" /> Carnadas</h1></div>
      <section className="fb-card fb-form-card">
        <h2>{form.id ? "Editar carnada" : "Nueva carnada"}</h2>
        <form onSubmit={save} className="fb-carnada-form">
          <label>Idioma<select value={form.localeId} onChange={(e) => setForm({ ...form, localeId: Number(e.target.value) })}>{locales.map((locale) => <option key={locale.id} value={locale.id}>{locale.name}</option>)}</select></label>
          <label>Body<textarea required rows="2" value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} /></label>
          <label>Titulo<input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></label>
          <label>Descripcion<input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></label>
          <label>URL<input required value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} /></label>
          <label>Notas<input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></label>
          <button className="fb-btn primary">Guardar</button>
          {form.id && <button type="button" className="fb-btn" onClick={() => setForm(empty)}>Cancelar</button>}
        </form>
      </section>
      {!!carnadas.length && <div className="fb-bulkbar"><button className="danger" disabled={!selectedIds.length} onClick={bulkRemove}>Borrar seleccionados</button><span>{selectedIds.length} seleccionados</span></div>}
      <div className="fb-table-card"><table className="fb-table"><thead><tr><th><input type="checkbox" checked={!!carnadas.length && selectedIds.length === carnadas.length} onChange={(e) => setSelectedIds(e.target.checked ? carnadas.map((item) => item._id) : [])} /></th><th>Idioma</th><th>Title</th><th>Body</th><th>URL</th><th>Acciones</th></tr></thead><tbody>{carnadas.map((item) => <tr key={item._id}><td><input type="checkbox" checked={selectedIds.includes(item._id)} onChange={() => toggleSelected(item._id)} /></td><td>{item.language_name}</td><td>{item.title}</td><td className="small fb-muted">{item.body}</td><td className="small" style={{ maxWidth: 280, overflowWrap: "anywhere" }}><a href={item.url} target="_blank" rel="noreferrer" style={{ color: "#60a5fa", textDecoration: "underline" }}>{item.url}</a></td><td className="fb-actions-cell"><button onClick={() => edit(item)}>Editar</button><button className="danger" onClick={() => remove(item._id)}>Borrar</button></td></tr>)}</tbody></table></div>
    </>
  );
}

function CopiesPage({ configId, locales, carnadas, copies, reload, setAlert }) {
  const empty = { id: "", name: "", targetLocaleId: 6, realBody: "", realTitle: "", realDesc: "", realUrl: "", carnadaIds: [] };
  const [form, setForm] = useState(empty);

  function edit(item) {
    setForm({ id: item._id, name: item.name || "", targetLocaleId: item.target_locale_id || 6, realBody: item.real_body || "", realTitle: item.real_title || "", realDesc: item.real_desc || "", realUrl: item.real_url || "", carnadaIds: item.carnada_ids || [] });
  }

  function toggleCarnada(id) {
    setForm((prev) => ({ ...prev, carnadaIds: prev.carnadaIds.includes(id) ? prev.carnadaIds.filter((item) => item !== id) : [...prev.carnadaIds, id] }));
  }

  async function save(e) {
    e.preventDefault();
    const payload = { configId, name: form.name, targetLocaleId: Number(form.targetLocaleId), realBody: form.realBody, realTitle: form.realTitle, realDesc: form.realDesc, realUrl: form.realUrl, carnadaIds: form.carnadaIds };
    try {
      if (form.id) await api.fbUpdateCopy(form.id, payload);
      else await api.fbCreateCopy(payload);
      setForm(empty);
      setAlert({ type: "success", message: "Copy bundle guardado." });
      await reload();
    } catch (err) {
      setAlert({ type: "error", message: String(err.message || err) });
    }
  }

  async function remove(id) {
    if (!confirm("Borrar paquete de copy?")) return;
    await api.fbDeleteCopy(id);
    await reload();
  }

  const carnadaNames = new Map(carnadas.map((item) => [item._id, item.language_name || item.locale_code]));

  return (
    <>
      <div className="fb-page-head"><h1><Icon name="copies" /> Copy Multi-Idioma</h1></div>
      <section className="fb-card fb-form-card">
        <h2>{form.id ? "Editar paquete" : "Nuevo paquete"}</h2>
        <form onSubmit={save} className="fb-copy-form">
          <label>Nombre<input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
          <label>Idioma real<select value={form.targetLocaleId} onChange={(e) => setForm({ ...form, targetLocaleId: Number(e.target.value) })}>{locales.map((locale) => <option key={locale.id} value={locale.id}>{locale.name}</option>)}</select></label>
          <label>Body real<textarea rows="2" value={form.realBody} onChange={(e) => setForm({ ...form, realBody: e.target.value })} /></label>
          <label>Title real<input value={form.realTitle} onChange={(e) => setForm({ ...form, realTitle: e.target.value })} /></label>
          <label>Description real<input value={form.realDesc} onChange={(e) => setForm({ ...form, realDesc: e.target.value })} /></label>
          <label>URL real<input value={form.realUrl} onChange={(e) => setForm({ ...form, realUrl: e.target.value })} /></label>
          <div className="fb-product-pick wide">{carnadas.map((item) => <label key={item._id}><input type="checkbox" checked={form.carnadaIds.includes(item._id)} onChange={() => toggleCarnada(item._id)} /> {item.language_name}: {item.title}</label>)}</div>
          <button className="fb-btn primary">Guardar paquete</button>
          {form.id && <button type="button" className="fb-btn" onClick={() => setForm(empty)}>Cancelar</button>}
        </form>
      </section>
      <div className="fb-table-card"><table className="fb-table"><thead><tr><th>Nombre</th><th>Real</th><th>Carnadas</th><th>URL</th><th>Acciones</th></tr></thead><tbody>{copies.map((item) => <tr key={item._id}><td><strong>{item.name}</strong></td><td>{item.target_locale_code}</td><td>{(item.carnada_ids || []).map((id) => carnadaNames.get(id) || id).join(", ")}</td><td className="small">{item.real_url}</td><td className="fb-actions-cell"><button onClick={() => edit(item)}>Editar</button><button className="danger" onClick={() => remove(item._id)}>Borrar</button></td></tr>)}</tbody></table></div>
    </>
  );
}

function CampaignsListPage({ campaigns, reload, onGo, setAlert }) {
  async function remove(id) {
    if (!confirm("Borrar registro local? La campana en Meta queda intacta.")) return;
    try {
      await api.fbDeleteCampaign(id);
      await reload();
    } catch (err) {
      setAlert({ type: "error", message: String(err.message || err) });
    }
  }

  return (
    <>
      <div className="fb-page-head"><h1 className="title-camp"><Icon name="campaign" /> Campanas</h1><button className="fb-btn ok" onClick={() => onGo("campaigns-new-type")}><Icon name="plus" /> Nueva campana</button></div>
      {!campaigns.length ? <div className="fb-empty">Sin campanas aun. Crea una nueva para empezar.</div> : (
        <div className="fb-table-card"><table className="fb-table"><thead><tr><th>Nombre</th><th>Cuenta</th><th>FB IDs</th><th>Truco</th><th>Status</th><th>Acciones</th></tr></thead><tbody>{campaigns.map((item) => <tr key={item._id}><td><strong>{item.name}</strong></td><td className="small">act_{item.ad_account_id}</td><td className="small fb-muted">camp: {item.fb_campaign_id || "-"}<br />ad: {item.fb_ad_id || "-"}</td><td className="small">{item.trick_enabled ? (item.trick_executed ? <span className="fb-pill ok">Ejecutado</span> : <span className="fb-pill warn">Esperando approval</span>) : "-"}</td><td className="small">{item.last_status || "-"}</td><td><button className="danger" onClick={() => remove(item._id)}><Icon name="trash" /> Borrar</button></td></tr>)}</tbody></table></div>
      )}
    </>
  );
}

function CampaignTypePage({ onGo }) {
  return (
    <>
      <div className="fb-title-block"><h1><Icon name="campaign" /> Nueva campana</h1><p>Que tipo de campana quieres montar?</p></div>
      <div className="fb-type-grid">
        <button className="fb-type-card" onClick={() => onGo("campaigns-new-catalog")}>
          <span className="fb-type-icon orange"><Icon name="catalog" /></span><strong>Truco de Catalogo</strong><p>Advantage+ Catalog Ads (DPA). Usa productos in_stock/out_of_stock para esconder el creativo agresivo detras del compliance.</p><small>{"Configurar ->"}</small>
        </button>
        <button className="fb-type-card" onClick={() => onGo("campaigns-new-language")}>
          <span className="fb-type-icon teal"><Icon name="copies" /></span><strong>Truco de Idiomas</strong><p>Asset feed multi-locale. El reviewer ve copy benigno; el usuario target ve el creativo real.</p><small>{"Configurar ->"}</small>
        </button>
        <button className="fb-type-card" onClick={() => onGo("campaigns-new-normal")}>
          <span className="fb-type-icon blue"><Icon name="campaign" /></span><strong>Normal</strong><p>Campana estandar sin truco. CBO/ABO con volumen, cost cap, bid cap o ROAS y N anuncios.</p><small>{"Configurar ->"}</small>
        </button>
      </div>
    </>
  );
}

function CampaignCatalogPage({ configId, setupOptions, sets, templates, plans, reloadTemplates, reloadPlans, reloadCampaigns, onGo, setAlert }) {
  const defaults = setupOptions?.config || {};
  const [form, setForm] = useState({
    name: "",
    cboOrAbo: "CBO",
    objective: "OUTCOME_SALES",
    optimizationGoal: "OFFSITE_CONVERSIONS",
    customEventType: "PURCHASE",
    budgetType: "daily",
    dailyBudgetUsd: "10",
    spendCapUsd: "",
    bidStrategy: "LOWEST_COST_WITHOUT_CAP",
    bidAmountUsd: "",
    roasFloor: "",
    countries: "US",
    ageMin: "40",
    ageMax: "65",
    localeIds: "",
    adsetName: "",
    adName: "",
    startTime: "",
    endTime: "",
    instagramId: "",
    productSetId: "",
    lander: "",
    message: "{{product.description}}",
    headline: "{{product.name}}",
    linkDescription: "",
    ctaType: "LEARN_MORE",
    urlTags: "",
    useVideo: true,
    multiAdvertiserOptout: true,
    trickEnabled: true,
  });

  const syncedSets = (sets || []).filter((item) => item.synced);

  function update(name, value) {
    setForm({ ...form, [name]: value });
  }

  function buildPayload(includeConfigId = true) {
    const payload = {
      name: form.name,
      adAccountId: defaults.default_ad_account_id || "",
      pageId: defaults.default_page_id || "",
      pixelId: defaults.default_pixel_id || "",
      instagramId: form.instagramId,
      cboOrAbo: form.cboOrAbo,
      objective: form.objective,
      optimizationGoal: form.optimizationGoal,
      customEventType: form.customEventType,
      budgetType: form.budgetType,
      dailyBudgetUsd: Number(form.dailyBudgetUsd || 0),
      spendCapUsd: Number(form.spendCapUsd || 0),
      bidStrategy: form.bidStrategy,
      bidAmountUsd: Number(form.bidAmountUsd || 0),
      roasFloor: Number(form.roasFloor || 0),
      countries: form.countries,
      ageMin: Number(form.ageMin || 18),
      ageMax: Number(form.ageMax || 65),
      localeIds: form.localeIds.split(",").map((item) => Number(item.trim())).filter(Boolean),
      adsetName: form.adsetName,
      adName: form.adName,
      startTime: form.startTime,
      endTime: form.endTime,
      productSetId: form.productSetId,
      lander: form.lander,
      message: form.message,
      headline: form.headline,
      linkDescription: form.linkDescription,
      ctaType: form.ctaType,
      urlTags: form.urlTags,
      useVideo: Boolean(form.useVideo),
      multiAdvertiserOptout: Boolean(form.multiAdvertiserOptout),
      trickEnabled: Boolean(form.trickEnabled),
    };
    if (includeConfigId) payload.configId = configId;
    return payload;
  }

  function loadConfig(item) {
    if (!item) return;
    const cfg = item.config || {};
    setForm({ ...form, ...cfg, localeIds: Array.isArray(cfg.localeIds) ? cfg.localeIds.join(",") : (cfg.localeIds || form.localeIds) });
  }

  async function saveAsTemplate() {
    const name = prompt("Nombre de la plantilla", form.name ? `${form.name} plantilla` : "Nueva plantilla");
    if (!name) return;
    try {
      await api.fbCreateTemplate({ configId, name, campaignType: "catalog", config: buildPayload(false) });
      setAlert({ type: "success", message: "Plantilla de catalogo guardada." });
      await reloadTemplates();
    } catch (err) {
      setAlert({ type: "error", message: String(err.message || err) });
    }
  }

  async function saveAsPlan() {
    const name = prompt("Nombre del plan", form.name || "Nuevo plan");
    if (!name) return;
    try {
      await api.fbCreatePlan({ configId, name, campaignType: "catalog", config: buildPayload(false) });
      setAlert({ type: "success", message: "Plan de catalogo guardado." });
      await reloadPlans();
    } catch (err) {
      setAlert({ type: "error", message: String(err.message || err) });
    }
  }

  async function submit(e) {
    e.preventDefault();
    if (!confirm("Crear campana en Meta en PAUSED?")) return;
    try {
      await api.fbCreateCatalogCampaign(buildPayload());
      setAlert({ type: "success", message: "Campana de catalogo creada en Meta." });
      await reloadCampaigns();
      onGo("campaigns");
    } catch (err) {
      setAlert({ type: "error", message: String(err.message || err) });
    }
  }

  return (
    <>
      <div className="fb-title-block"><h1><Icon name="catalog" /> Nueva campana - Truco de Catalogo</h1><p>1 campana a 1 adset a 1 ad de catalogo dinamico (DPA).</p></div>
      <section className="fb-card fb-form-card">
        <div className="fb-page-head compact"><h2><Icon name="campaign" /> Campana</h2><button type="button" className="fb-btn" onClick={() => onGo("campaigns-new-type")}>Cancelar</button></div>
        <div className="fb-builder-tools">
          <label>Cargar plantilla<select defaultValue="" onChange={(e) => { const item = templates.find((tpl) => tpl._id === e.target.value); loadConfig(item); e.target.value = ""; }}><option value="">Selecciona</option>{templates.filter((item) => item.campaign_type === "catalog").map((item) => <option key={item._id} value={item._id}>{item.name}</option>)}</select></label>
          <label>Cargar plan<select defaultValue="" onChange={(e) => { const item = plans.find((plan) => plan._id === e.target.value); loadConfig(item); e.target.value = ""; }}><option value="">Selecciona</option>{plans.map((item) => <option key={item._id} value={item._id}>{item.name}</option>)}</select></label>
          <button type="button" className="fb-btn" onClick={saveAsTemplate}>Guardar como plantilla</button>
          <button type="button" className="fb-btn" onClick={saveAsPlan}>Guardar como plan</button>
        </div>
        <form onSubmit={submit} className="fb-campaign-form">
          <label>Nombre<input required value={form.name} onChange={(e) => update("name", e.target.value)} /></label>
          <label>Set de productos<select required value={form.productSetId} onChange={(e) => update("productSetId", e.target.value)}><option value="">Selecciona set</option>{syncedSets.map((item) => <option key={item._id} value={item._id}>{item.name} ({item.catalog_name})</option>)}</select></label>
          <label>CBO o ABO<select value={form.cboOrAbo} onChange={(e) => update("cboOrAbo", e.target.value)}><option value="CBO">CBO</option><option value="ABO">ABO</option></select></label>
          <label>Budget tipo<select value={form.budgetType} onChange={(e) => update("budgetType", e.target.value)}><option value="daily">Diario</option><option value="lifetime">Total</option></select></label>
          <label>Budget USD<input type="number" step="0.01" value={form.dailyBudgetUsd} onChange={(e) => update("dailyBudgetUsd", e.target.value)} /></label>
          <label>Spend cap USD<input type="number" step="0.01" value={form.spendCapUsd} onChange={(e) => update("spendCapUsd", e.target.value)} /></label>
          <label>Objetivo<select value={form.objective} onChange={(e) => update("objective", e.target.value)}><option>OUTCOME_SALES</option><option>OUTCOME_LEADS</option><option>OUTCOME_TRAFFIC</option><option>OUTCOME_AWARENESS</option><option>OUTCOME_ENGAGEMENT</option></select></label>
          <label>Optimizar<select value={form.optimizationGoal} onChange={(e) => update("optimizationGoal", e.target.value)}><option>OFFSITE_CONVERSIONS</option><option>VALUE</option><option>LANDING_PAGE_VIEWS</option><option>LINK_CLICKS</option><option>IMPRESSIONS</option><option>REACH</option></select></label>
          <label>Evento<select value={form.customEventType} onChange={(e) => update("customEventType", e.target.value)}><option>PURCHASE</option><option>INITIATE_CHECKOUT</option><option>ADD_TO_CART</option><option>LEAD</option><option>COMPLETE_REGISTRATION</option><option>VIEW_CONTENT</option></select></label>
          <label>Bid strategy<select value={form.bidStrategy} onChange={(e) => update("bidStrategy", e.target.value)}><option>LOWEST_COST_WITHOUT_CAP</option><option>COST_CAP</option><option>LOWEST_COST_WITH_MIN_ROAS</option><option>LOWEST_COST_WITH_BID_CAP</option></select></label>
          <label>Bid amount<input type="number" step="0.01" value={form.bidAmountUsd} onChange={(e) => update("bidAmountUsd", e.target.value)} /></label>
          <label>ROAS floor<input type="number" step="0.01" value={form.roasFloor} onChange={(e) => update("roasFloor", e.target.value)} /></label>
          <label>Paises<input value={form.countries} onChange={(e) => update("countries", e.target.value)} /></label>
          <label>Edad min<input type="number" value={form.ageMin} onChange={(e) => update("ageMin", e.target.value)} /></label>
          <label>Edad max<input type="number" value={form.ageMax} onChange={(e) => update("ageMax", e.target.value)} /></label>
          <label>Locales<input value={form.localeIds} onChange={(e) => update("localeIds", e.target.value)} placeholder="6,24" /></label>
          <label>Lander URL<input required value={form.lander} onChange={(e) => update("lander", e.target.value)} /></label>
          <label>Headline<input value={form.headline} onChange={(e) => update("headline", e.target.value)} /></label>
          <label>Mensaje<textarea rows="2" value={form.message} onChange={(e) => update("message", e.target.value)} /></label>
          <label>Descripcion link<input value={form.linkDescription} onChange={(e) => update("linkDescription", e.target.value)} /></label>
          <label>CTA<select value={form.ctaType} onChange={(e) => update("ctaType", e.target.value)}><option>LEARN_MORE</option><option>SHOP_NOW</option><option>SIGN_UP</option><option>SUBSCRIBE</option><option>GET_OFFER</option><option>APPLY_NOW</option><option>DOWNLOAD</option><option>CONTACT_US</option></select></label>
          <label>Adset name<input value={form.adsetName} onChange={(e) => update("adsetName", e.target.value)} /></label>
          <label>Ad name<input value={form.adName} onChange={(e) => update("adName", e.target.value)} /></label>
          <label>Instagram ID<input value={form.instagramId} onChange={(e) => update("instagramId", e.target.value)} /></label>
          <label>Start time<input type="datetime-local" value={form.startTime} onChange={(e) => update("startTime", e.target.value)} /></label>
          <label>End time<input type="datetime-local" value={form.endTime} onChange={(e) => update("endTime", e.target.value)} /></label>
          <label className="wide">URL tags<input value={form.urlTags} onChange={(e) => update("urlTags", e.target.value)} /></label>
          <label className="fb-check"><input type="checkbox" checked={form.useVideo} onChange={(e) => update("useVideo", e.target.checked)} /> Forzar formato video</label>
          <label className="fb-check"><input type="checkbox" checked={form.multiAdvertiserOptout} onChange={(e) => update("multiAdvertiserOptout", e.target.checked)} /> Multi advertiser opt-out</label>
          <label className="fb-check"><input type="checkbox" checked={form.trickEnabled} onChange={(e) => update("trickEnabled", e.target.checked)} /> Activar truco automatico</label>
          <div className="wide fb-actions-cell"><button className="fb-btn primary">Crear campana en Meta (PAUSED)</button><button type="button" className="fb-btn" onClick={() => onGo("campaigns-new-type")}>Cancelar</button></div>
        </form>
      </section>
    </>
  );
}

function CampaignsBuilderPage({ initialType = "normal", configId, setupOptions, media, copies, templates, plans, reload, reloadTemplates, reloadPlans, onGo, setAlert }) {
  const [type, setType] = useState(initialType);
  const [form, setForm] = useState({
    name: "",
    dailyBudgetUsd: "5.00",
    cboOrAbo: "ABO",
    countries: "US",
    ageMin: "18",
    ageMax: "65",
    objective: "OUTCOME_SALES",
    optimizationGoal: "OFFSITE_CONVERSIONS",
    customEventType: "PURCHASE",
    bidStrategy: "LOWEST_COST_WITHOUT_CAP",
    bidAmountUsd: "",
    roasFloor: "",
    localeIds: "6",
    urlTags: "",
    adsetName: "",
    instagramId: "",
    trickEnabled: false,
  });
  const [ads, setAds] = useState([{ mediaAssetId: "", defaultMediaId: "", copyBundleId: "", body: "", title: "", description: "", link: "", ctaType: "LEARN_MORE", adName: "" }]);
  const defaults = setupOptions?.config || {};
  const uploadedMedia = media.filter((item) => item.uploaded_to_meta);

  function update(name, value) {
    setForm({ ...form, [name]: value });
  }

  function updateAd(index, name, value) {
    setAds(ads.map((ad, i) => (i === index ? { ...ad, [name]: value } : ad)));
  }

  function buildCampaignPayload(includeConfigId = true) {
    const base = {
      name: form.name,
      adAccountId: defaults.default_ad_account_id || "",
      pageId: defaults.default_page_id || "",
      pixelId: defaults.default_pixel_id || "",
      instagramId: form.instagramId,
      cboOrAbo: form.cboOrAbo,
      dailyBudgetUsd: Number(form.dailyBudgetUsd),
      bidStrategy: form.bidStrategy,
      bidAmountUsd: Number(form.bidAmountUsd || 0),
      roasFloor: Number(form.roasFloor || 0),
      countries: form.countries,
      ageMin: Number(form.ageMin),
      ageMax: Number(form.ageMax),
      localeIds: form.localeIds.split(",").map((item) => Number(item.trim())).filter(Boolean),
      objective: form.objective,
      optimizationGoal: form.optimizationGoal,
      customEventType: form.customEventType,
      urlTags: form.urlTags,
      adsetName: form.adsetName,
      trickEnabled: Boolean(form.trickEnabled),
    };
    if (includeConfigId) base.configId = configId;
    if (type === "normal") {
      return { ...base, ads: ads.map((ad) => ({ mediaAssetId: ad.mediaAssetId, body: ad.body, title: ad.title, description: ad.description, link: ad.link, ctaType: ad.ctaType, adName: ad.adName })).filter((ad) => ad.mediaAssetId && ad.body && ad.title && ad.link) };
    }
    return { ...base, ads: ads.map((ad) => ({ mediaAssetId: ad.mediaAssetId, defaultMediaId: ad.defaultMediaId, copyBundleId: ad.copyBundleId, ctaType: ad.ctaType, adName: ad.adName })).filter((ad) => ad.mediaAssetId && ad.defaultMediaId && ad.copyBundleId) };
  }

  function loadBuilderConfig(item) {
    if (!item) return;
    const cfg = item.config || item.payload || {};
    setType(item.campaign_type || item.campaignType || type);
    setForm({
      name: cfg.name || item.name || "",
      dailyBudgetUsd: String(cfg.dailyBudgetUsd ?? "5.00"),
      cboOrAbo: cfg.cboOrAbo || "ABO",
      countries: cfg.countries || "US",
      ageMin: String(cfg.ageMin ?? "18"),
      ageMax: String(cfg.ageMax ?? "65"),
      objective: cfg.objective || "OUTCOME_SALES",
      optimizationGoal: cfg.optimizationGoal || "OFFSITE_CONVERSIONS",
      customEventType: cfg.customEventType || "PURCHASE",
      bidStrategy: cfg.bidStrategy || "LOWEST_COST_WITHOUT_CAP",
      bidAmountUsd: String(cfg.bidAmountUsd || ""),
      roasFloor: String(cfg.roasFloor || ""),
      localeIds: Array.isArray(cfg.localeIds) ? cfg.localeIds.join(",") : (cfg.localeIds || "6"),
      urlTags: cfg.urlTags || "",
      adsetName: cfg.adsetName || "",
      instagramId: cfg.instagramId || "",
      trickEnabled: Boolean(cfg.trickEnabled),
    });
    setAds((cfg.ads?.length ? cfg.ads : [{ mediaAssetId: "", defaultMediaId: "", copyBundleId: "", body: "", title: "", description: "", link: "", ctaType: "LEARN_MORE", adName: "" }]).map((ad) => ({ ctaType: "LEARN_MORE", mediaAssetId: "", defaultMediaId: "", copyBundleId: "", body: "", title: "", description: "", link: "", adName: "", ...ad })));
  }

  async function saveAsTemplate() {
    const name = prompt("Nombre de la plantilla", form.name ? `${form.name} plantilla` : "Nueva plantilla");
    if (!name) return;
    try {
      await api.fbCreateTemplate({ configId, name, campaignType: type, config: buildCampaignPayload(false) });
      setAlert({ type: "success", message: "Plantilla guardada desde el builder." });
      await reloadTemplates();
    } catch (err) {
      setAlert({ type: "error", message: String(err.message || err) });
    }
  }

  async function saveAsPlan() {
    const name = prompt("Nombre del plan", form.name || "Nuevo plan");
    if (!name) return;
    const scheduledAt = prompt("Fecha/hora programada en formato ISO. Deja vacio para pendiente manual.", "");
    try {
      await api.fbCreatePlan({ configId, name, campaignType: type, config: buildCampaignPayload(false), scheduledAt: scheduledAt || "" });
      setAlert({ type: "success", message: "Plan guardado desde el builder." });
      await reloadPlans();
    } catch (err) {
      setAlert({ type: "error", message: String(err.message || err) });
    }
  }

  async function submit(e) {
    e.preventDefault();
    if (!confirm("Crear campana en Meta en PAUSED?")) return;
    try {
      if (type === "normal") {
        await api.fbCreateNormalCampaign(buildCampaignPayload());
      } else {
        await api.fbCreateLanguageCampaign(buildCampaignPayload());
      }
      setAlert({ type: "success", message: "Campana creada en Meta." });
      await reload();
    } catch (err) {
      setAlert({ type: "error", message: String(err.message || err) });
    }
  }

  return (
    <>
      <div className="fb-title-block"><h1><Icon name={type === "language" ? "copies" : "campaign"} /> {type === "language" ? "Nueva campana con truco de idiomas" : "Nueva campana Normal"}</h1><p>{type === "language" ? "Estructura: 1 campana a 1 ad set a N anuncios. Todos los anuncios comparten el mismo idioma target del adset." : "Sin truco. Estructura: 1 campana a 1 ad set a N anuncios. Cada anuncio lleva 1 creativo + texto libre."}</p></div>
      <section className="fb-card fb-form-card">
        <div className="fb-page-head compact"><h2><Icon name="campaign" /> Campana</h2><button type="button" className="fb-btn" onClick={() => onGo("campaigns-new-type")}>Cancelar</button></div>
        <div className="fb-builder-tools">
          <label>Cargar plantilla<select defaultValue="" onChange={(e) => { const item = templates.find((tpl) => tpl._id === e.target.value); loadBuilderConfig(item); e.target.value = ""; }}><option value="">Selecciona</option>{templates.map((item) => <option key={item._id} value={item._id}>{item.name} ({item.campaign_type})</option>)}</select></label>
          <label>Cargar plan<select defaultValue="" onChange={(e) => { const item = plans.find((plan) => plan._id === e.target.value); loadBuilderConfig(item); e.target.value = ""; }}><option value="">Selecciona</option>{plans.map((item) => <option key={item._id} value={item._id}>{item.name} ({item.status})</option>)}</select></label>
          <button type="button" className="fb-btn" onClick={saveAsTemplate}>Guardar como plantilla</button>
          <button type="button" className="fb-btn" onClick={saveAsPlan}>Guardar como plan</button>
        </div>
        <form onSubmit={submit} className="fb-campaign-form">
          <label>Nombre<input required value={form.name} onChange={(e) => update("name", e.target.value)} /></label>
          <label>CBO o ABO<select value={form.cboOrAbo} onChange={(e) => update("cboOrAbo", e.target.value)}><option value="ABO">ABO</option><option value="CBO">CBO</option></select></label>
          <label>Budget diario USD<input type="number" step="0.01" value={form.dailyBudgetUsd} onChange={(e) => update("dailyBudgetUsd", e.target.value)} /></label>
          <label>Paises<input value={form.countries} onChange={(e) => update("countries", e.target.value)} /></label>
          <label>Edad min<input type="number" value={form.ageMin} onChange={(e) => update("ageMin", e.target.value)} /></label>
          <label>Edad max<input type="number" value={form.ageMax} onChange={(e) => update("ageMax", e.target.value)} /></label>
          <label>Locales<input value={form.localeIds} onChange={(e) => update("localeIds", e.target.value)} placeholder="6,24" /></label>
          <label>Objetivo<select value={form.objective} onChange={(e) => update("objective", e.target.value)}><option>OUTCOME_SALES</option><option>OUTCOME_LEADS</option><option>OUTCOME_TRAFFIC</option><option>OUTCOME_AWARENESS</option><option>OUTCOME_ENGAGEMENT</option></select></label>
          <label>Optimizar<select value={form.optimizationGoal} onChange={(e) => update("optimizationGoal", e.target.value)}><option>OFFSITE_CONVERSIONS</option><option>LANDING_PAGE_VIEWS</option><option>LINK_CLICKS</option><option>IMPRESSIONS</option><option>REACH</option></select></label>
          <label>Evento<select value={form.customEventType} onChange={(e) => update("customEventType", e.target.value)}><option>PURCHASE</option><option>INITIATE_CHECKOUT</option><option>ADD_TO_CART</option><option>LEAD</option><option>COMPLETE_REGISTRATION</option><option>VIEW_CONTENT</option></select></label>
          <label>Bid strategy<select value={form.bidStrategy} onChange={(e) => update("bidStrategy", e.target.value)}><option>LOWEST_COST_WITHOUT_CAP</option><option>COST_CAP</option><option>LOWEST_COST_WITH_MIN_ROAS</option><option>LOWEST_COST_WITH_BID_CAP</option></select></label>
          <label>Bid amount<input type="number" step="0.01" value={form.bidAmountUsd} onChange={(e) => update("bidAmountUsd", e.target.value)} /></label>
          <label>ROAS floor<input type="number" step="0.01" value={form.roasFloor} onChange={(e) => update("roasFloor", e.target.value)} /></label>
          <label className="wide">URL tags<input value={form.urlTags} onChange={(e) => update("urlTags", e.target.value)} /></label>
          {type === "language" && <label className="wide fb-check"><input type="checkbox" checked={form.trickEnabled} onChange={(e) => update("trickEnabled", e.target.checked)} /> Activar truco automatico para revisar el primer ad hasta que este ACTIVE</label>}

          <div className="wide fb-ad-slots">
            <div className="fb-page-head compact"><h2>Anuncios</h2><button type="button" className="fb-btn" onClick={() => setAds([...ads, { mediaAssetId: "", defaultMediaId: "", copyBundleId: "", body: "", title: "", description: "", link: "", ctaType: "LEARN_MORE", adName: "" }])}>Agregar slot</button></div>
            {ads.map((ad, index) => <div className="fb-ad-slot" key={index}>
              <strong><span className="fb-ad-num">{index + 1}</span> Anuncio</strong>
              <label>Nombre ad<input value={ad.adName} onChange={(e) => updateAd(index, "adName", e.target.value)} /></label>
              <label>{type === "language" ? "Creativo REAL (sucio)" : "Creativo"}<select value={ad.mediaAssetId} onChange={(e) => updateAd(index, "mediaAssetId", e.target.value)}><option value="">Selecciona</option>{uploadedMedia.map((item) => <option key={item._id} value={item._id}>{item.is_default ? "Carnada" : "Real"} - {item.name} ({item.type})</option>)}</select></label>
              {type === "language" && <label>Creativo DEFAULT (carnada limpia)<select value={ad.defaultMediaId} onChange={(e) => updateAd(index, "defaultMediaId", e.target.value)}><option value="">Selecciona</option>{uploadedMedia.map((item) => <option key={item._id} value={item._id}>{item.is_default ? "Carnada" : "Real"} - {item.name} ({item.type})</option>)}</select></label>}
              {type === "language" && <label>Copy bundle<select value={ad.copyBundleId} onChange={(e) => updateAd(index, "copyBundleId", e.target.value)}><option value="">Selecciona</option>{copies.map((item) => <option key={item._id} value={item._id}>{item.name}</option>)}</select></label>}
              {type === "normal" && <label>Body<textarea rows="2" value={ad.body} onChange={(e) => updateAd(index, "body", e.target.value)} /></label>}
              {type === "normal" && <label>Title<input value={ad.title} onChange={(e) => updateAd(index, "title", e.target.value)} /></label>}
              {type === "normal" && <label>Description<input value={ad.description} onChange={(e) => updateAd(index, "description", e.target.value)} /></label>}
              {type === "normal" && <label>Link<input value={ad.link} onChange={(e) => updateAd(index, "link", e.target.value)} /></label>}
              <label>CTA<select value={ad.ctaType} onChange={(e) => updateAd(index, "ctaType", e.target.value)}><option>LEARN_MORE</option><option>SHOP_NOW</option><option>SIGN_UP</option><option>SUBSCRIBE</option><option>GET_OFFER</option><option>APPLY_NOW</option><option>DOWNLOAD</option><option>CONTACT_US</option></select></label>
              {ads.length > 1 && <button type="button" className="danger" onClick={() => setAds(ads.filter((_, i) => i !== index))}>Quitar</button>}
            </div>)}
          </div>
          <div className="wide fb-actions-cell"><button className="fb-btn primary">Crear campana en Meta (PAUSED)</button><button type="button" className="fb-btn" onClick={() => onGo("campaigns-new-type")}>Cancelar</button></div>
        </form>
      </section>
    </>
  );
}

function TemplatesPage({ configId, templates, reload, setAlert }) {
  const [form, setForm] = useState({ name: "", campaignType: "normal", configText: "{}" });

  async function save(e) {
    e.preventDefault();
    try {
      await api.fbCreateTemplate({ configId, name: form.name, campaignType: form.campaignType, config: JSON.parse(form.configText || "{}") });
      setForm({ name: "", campaignType: "normal", configText: "{}" });
      setAlert({ type: "success", message: "Plantilla guardada." });
      await reload();
    } catch (err) {
      setAlert({ type: "error", message: String(err.message || err) });
    }
  }

  async function remove(id) {
    if (!confirm("Borrar plantilla?")) return;
    await api.fbDeleteTemplate(id);
    await reload();
  }

  return (
    <>
      <div className="fb-page-head"><h1><Icon name="template" /> Plantillas</h1></div>
      <section className="fb-card fb-form-card">
        <form onSubmit={save} className="fb-template-form">
          <label>Nombre<input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
          <label>Tipo<select value={form.campaignType} onChange={(e) => setForm({ ...form, campaignType: e.target.value })}><option value="normal">normal</option><option value="language">language</option><option value="catalog">catalog</option></select></label>
          <label className="wide">Config JSON<textarea rows="6" className="mono" value={form.configText} onChange={(e) => setForm({ ...form, configText: e.target.value })} /></label>
          <button className="fb-btn primary">Guardar plantilla</button>
        </form>
      </section>
      <div className="fb-table-card"><table className="fb-table"><thead><tr><th>Nombre</th><th>Tipo</th><th>Creada</th><th>Acciones</th></tr></thead><tbody>{templates.map((item) => <tr key={item._id}><td><strong>{item.name}</strong></td><td>{item.campaign_type}</td><td className="small">{item.created_at}</td><td><button className="danger" onClick={() => remove(item._id)}>Borrar</button></td></tr>)}</tbody></table></div>
    </>
  );
}

function PlanningPage({ configId, plans, reload, setupOptions, media, copies, sets, setAlert }) {
  const [form, setForm] = useState({ id: "", name: "", campaignType: "normal", scheduledAt: "", configText: "{}" });
  const [selectedIds, setSelectedIds] = useState([]);
  const [visualType, setVisualType] = useState("normal");
  const [visual, setVisual] = useState({ name: "", dailyBudgetUsd: "5", countries: "US", ageMin: "18", ageMax: "65", localeIds: "6", lander: "", productSetId: "", message: "{{product.description}}", headline: "{{product.name}}", scheduledAt: "" });
  const [visualAds, setVisualAds] = useState([{ mediaAssetId: "", defaultMediaId: "", copyBundleId: "", body: "", title: "", description: "", link: "", ctaType: "LEARN_MORE" }]);
  const defaults = setupOptions?.config || {};

  function edit(plan) {
    setForm({ id: plan._id, name: plan.name || "", campaignType: plan.campaign_type || "normal", scheduledAt: plan.scheduled_at || "", configText: JSON.stringify(plan.config || {}, null, 2) });
  }

  async function save(e) {
    e.preventDefault();
    try {
      const payload = { configId, name: form.name, campaignType: form.campaignType, scheduledAt: form.scheduledAt, config: JSON.parse(form.configText || "{}") };
      if (form.id) await api.fbUpdatePlan(form.id, payload);
      else await api.fbCreatePlan(payload);
      setForm({ id: "", name: "", campaignType: "normal", scheduledAt: "", configText: "{}" });
      setAlert({ type: "success", message: "Plan guardado." });
      await reload();
    } catch (err) {
      setAlert({ type: "error", message: String(err.message || err) });
    }
  }

  function visualBase() {
    return {
      name: visual.name,
      adAccountId: defaults.default_ad_account_id || "",
      pageId: defaults.default_page_id || "",
      pixelId: defaults.default_pixel_id || "",
      cboOrAbo: "ABO",
      dailyBudgetUsd: Number(visual.dailyBudgetUsd || 0),
      countries: visual.countries,
      ageMin: Number(visual.ageMin || 18),
      ageMax: Number(visual.ageMax || 65),
      localeIds: visual.localeIds.split(",").map((item) => Number(item.trim())).filter(Boolean),
      objective: "OUTCOME_SALES",
      optimizationGoal: "OFFSITE_CONVERSIONS",
      customEventType: "PURCHASE",
      bidStrategy: "LOWEST_COST_WITHOUT_CAP",
      bidAmountUsd: 0,
      roasFloor: 0,
      urlTags: "",
    };
  }

  async function saveVisualPlan(e) {
    e.preventDefault();
    try {
      let config = visualBase();
      if (visualType === "normal") {
        config.ads = visualAds.map((ad) => ({ mediaAssetId: ad.mediaAssetId, body: ad.body, title: ad.title, description: ad.description, link: ad.link, ctaType: ad.ctaType })).filter((ad) => ad.mediaAssetId && ad.body && ad.title && ad.link);
      } else if (visualType === "language") {
        config.ads = visualAds.map((ad) => ({ mediaAssetId: ad.mediaAssetId, defaultMediaId: ad.defaultMediaId, copyBundleId: ad.copyBundleId, ctaType: ad.ctaType })).filter((ad) => ad.mediaAssetId && ad.defaultMediaId && ad.copyBundleId);
      } else {
        config = { ...config, productSetId: visual.productSetId, lander: visual.lander, message: visual.message, headline: visual.headline, linkDescription: "", ctaType: "LEARN_MORE", useVideo: true, multiAdvertiserOptout: true, trickEnabled: true };
      }
      await api.fbCreatePlan({ configId, name: visual.name, campaignType: visualType, scheduledAt: visual.scheduledAt, config });
      setVisual({ name: "", dailyBudgetUsd: "5", countries: "US", ageMin: "18", ageMax: "65", localeIds: "6", lander: "", productSetId: "", message: "{{product.description}}", headline: "{{product.name}}", scheduledAt: "" });
      setVisualAds([{ mediaAssetId: "", defaultMediaId: "", copyBundleId: "", body: "", title: "", description: "", link: "", ctaType: "LEARN_MORE" }]);
      setAlert({ type: "success", message: "Fila visual guardada en cola." });
      await reload();
    } catch (err) {
      setAlert({ type: "error", message: String(err.message || err) });
    }
  }

  function updateVisualAd(index, key, value) {
    setVisualAds(visualAds.map((ad, i) => i === index ? { ...ad, [key]: value } : ad));
  }

  async function execute(id) {
    if (!confirm("Ejecutar esta fila en Meta?")) return;
    try {
      await api.fbExecutePlan(id);
      setAlert({ type: "success", message: "Plan ejecutado." });
    } catch (err) {
      setAlert({ type: "error", message: String(err.message || err) });
    }
    await reload();
  }

  async function executePending() {
    if (!confirm("Ejecutar todas las pendientes/error?")) return;
    await api.fbExecutePending(configId);
    await reload();
  }

  async function executeDue() {
    await api.fbExecuteDuePlans(configId);
    await reload();
  }

  async function remove(id) {
    if (!confirm("Borrar plan?")) return;
    await api.fbDeletePlan(id);
    await reload();
  }

  async function bulkRemove() {
    if (!selectedIds.length || !confirm("Borrar las filas seleccionadas?")) return;
    await api.fbBulkDeletePlans(selectedIds);
    setSelectedIds([]);
    await reload();
  }

  function toggleSelected(id) {
    setSelectedIds((prev) => prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]);
  }

  async function duplicate(id) {
    await api.fbDuplicatePlan(id);
    await reload();
  }

  return (
    <>
      <div className="fb-page-head"><h1><Icon name="planning" /> Planificacion de Campanas</h1><div className="fb-actions-cell"><button className="fb-btn" onClick={executeDue}>Ejecutar vencidos</button><button className="fb-btn primary" onClick={executePending}>Ejecutar pendientes</button></div></div>
      <section className="fb-card fb-form-card">
        <div className="fb-page-head compact"><h2><Icon name="plus" /> Nueva fila visual</h2><div className="fb-campaign-type"><button type="button" className={visualType === "catalog" ? "active" : ""} onClick={() => setVisualType("catalog")}>Catalogo</button><button type="button" className={visualType === "language" ? "active" : ""} onClick={() => setVisualType("language")}>Truco de Idiomas</button><button type="button" className={visualType === "normal" ? "active" : ""} onClick={() => setVisualType("normal")}>Normal</button></div></div>
        <form onSubmit={saveVisualPlan} className="fb-campaign-form">
          <label>Nombre<input required value={visual.name} onChange={(e) => setVisual({ ...visual, name: e.target.value })} /></label>
          <label>Budget diario USD<input type="number" step="0.50" value={visual.dailyBudgetUsd} onChange={(e) => setVisual({ ...visual, dailyBudgetUsd: e.target.value })} /></label>
          <label>Paises<input value={visual.countries} onChange={(e) => setVisual({ ...visual, countries: e.target.value })} /></label>
          <label>Edad min<input type="number" value={visual.ageMin} onChange={(e) => setVisual({ ...visual, ageMin: e.target.value })} /></label>
          <label>Edad max<input type="number" value={visual.ageMax} onChange={(e) => setVisual({ ...visual, ageMax: e.target.value })} /></label>
          <label>Locale IDs<input value={visual.localeIds} onChange={(e) => setVisual({ ...visual, localeIds: e.target.value })} /></label>
          <label>Programar para<input value={visual.scheduledAt} onChange={(e) => setVisual({ ...visual, scheduledAt: e.target.value })} placeholder="2026-05-20T16:30:00-05:00" /></label>
          {visualType === "catalog" && <label>Product Set<select required value={visual.productSetId} onChange={(e) => setVisual({ ...visual, productSetId: e.target.value })}><option value="">Selecciona</option>{(sets || []).filter((s) => s.synced).map((s) => <option key={s._id} value={s._id}>{s.name} ({s.catalog_name})</option>)}</select></label>}
          {visualType === "catalog" && <label>Lander<input required value={visual.lander} onChange={(e) => setVisual({ ...visual, lander: e.target.value })} /></label>}
          {visualType === "catalog" && <label>Headline<input value={visual.headline} onChange={(e) => setVisual({ ...visual, headline: e.target.value })} /></label>}
          {visualType === "catalog" && <label className="wide">Mensaje<textarea rows="2" value={visual.message} onChange={(e) => setVisual({ ...visual, message: e.target.value })} /></label>}
          {visualType !== "catalog" && <div className="wide fb-ad-slots"><div className="fb-page-head compact"><h2>Anuncios</h2><button type="button" className="fb-btn" onClick={() => setVisualAds([...visualAds, { mediaAssetId: "", defaultMediaId: "", copyBundleId: "", body: "", title: "", description: "", link: "", ctaType: "LEARN_MORE" }])}>Generar slot</button></div>{visualAds.map((ad, index) => <div className="fb-ad-slot" key={index}><strong><span className="fb-ad-num">{index + 1}</span> Anuncio</strong><label>Creativo<select value={ad.mediaAssetId} onChange={(e) => updateVisualAd(index, "mediaAssetId", e.target.value)}><option value="">Selecciona</option>{media.map((m) => <option key={m._id} value={m._id}>{m.name}</option>)}</select></label>{visualType === "language" && <label>Default<select value={ad.defaultMediaId} onChange={(e) => updateVisualAd(index, "defaultMediaId", e.target.value)}><option value="">Selecciona</option>{media.map((m) => <option key={m._id} value={m._id}>{m.name}</option>)}</select></label>}{visualType === "language" && <label>Copy<select value={ad.copyBundleId} onChange={(e) => updateVisualAd(index, "copyBundleId", e.target.value)}><option value="">Selecciona</option>{copies.map((c) => <option key={c._id} value={c._id}>{c.name}</option>)}</select></label>}{visualType === "normal" && <label>Link<input value={ad.link} onChange={(e) => updateVisualAd(index, "link", e.target.value)} /></label>}{visualType === "normal" && <label>Body<textarea rows="2" value={ad.body} onChange={(e) => updateVisualAd(index, "body", e.target.value)} /></label>}{visualType === "normal" && <label>Title<input value={ad.title} onChange={(e) => updateVisualAd(index, "title", e.target.value)} /></label>}<label>CTA<select value={ad.ctaType} onChange={(e) => updateVisualAd(index, "ctaType", e.target.value)}><option>LEARN_MORE</option><option>SHOP_NOW</option><option>SIGN_UP</option><option>SUBSCRIBE</option><option>GET_OFFER</option><option>APPLY_NOW</option><option>DOWNLOAD</option><option>CONTACT_US</option></select></label>{visualAds.length > 1 && <button type="button" className="danger" onClick={() => setVisualAds(visualAds.filter((_, i) => i !== index))}>Quitar</button>}</div>)}</div>}
          <button className="fb-btn primary">Guardar en cola</button>
        </form>
      </section>
      <section className="fb-card fb-form-card">
        <h2>Editor avanzado JSON</h2>
        <form onSubmit={save} className="fb-template-form">
          <label>Nombre<input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
          <label>Tipo<select value={form.campaignType} onChange={(e) => setForm({ ...form, campaignType: e.target.value })}><option value="normal">normal</option><option value="language">language</option><option value="catalog">catalog</option></select></label>
          <label className="wide">Programar para<input placeholder="2026-05-20T16:30:00-05:00" value={form.scheduledAt} onChange={(e) => setForm({ ...form, scheduledAt: e.target.value })} /></label>
          <label className="wide">Config JSON<textarea rows="8" className="mono" value={form.configText} onChange={(e) => setForm({ ...form, configText: e.target.value })} /></label>
          <button className="fb-btn primary">{form.id ? "Actualizar" : "Guardar fila"}</button>{form.id && <button type="button" className="fb-btn" onClick={() => setForm({ id: "", name: "", campaignType: "normal", scheduledAt: "", configText: "{}" })}>Cancelar</button>}
        </form>
      </section>
      {!!plans.length && <div className="fb-bulkbar"><button className="danger" disabled={!selectedIds.length} onClick={bulkRemove}>Borrar seleccionadas</button><span>{selectedIds.length} seleccionadas · {plans.length} total</span></div>}
      <div className="fb-table-card"><table className="fb-table"><thead><tr><th><input type="checkbox" checked={!!plans.length && selectedIds.length === plans.length} onChange={(e) => setSelectedIds(e.target.checked ? plans.map((item) => item._id) : [])} /></th><th>Estado</th><th>Tipo</th><th>Nombre</th><th>Programada</th><th>Resultado/Error</th><th>Acciones</th></tr></thead><tbody>{plans.map((item) => <tr key={item._id}><td><input type="checkbox" checked={selectedIds.includes(item._id)} onChange={() => toggleSelected(item._id)} /></td><td><span className={`fb-pill ${item.status === "done" ? "ok" : item.status === "error" ? "err" : ""}`}>{item.status}</span></td><td>{item.campaign_type}</td><td><strong>{item.name}</strong></td><td className="small">{item.scheduled_at || "manual"}</td><td className="small">{item.result_ids?.fb_campaign_id || item.error_msg || "-"}</td><td className="fb-actions-cell"><button onClick={() => execute(item._id)}>Ejecutar</button><button onClick={() => edit(item)}>Editar</button><button onClick={() => duplicate(item._id)}>Duplicar</button><button className="danger" onClick={() => remove(item._id)}>Borrar</button></td></tr>)}</tbody></table></div>
    </>
  );
}

function TrickPage({ configId, trick, reload, setAlert }) {
  async function runNow() {
    try {
      await api.fbRunTrick(configId);
      setAlert({ type: "success", message: "Revision del truco ejecutada." });
      await reload();
    } catch (err) {
      setAlert({ type: "error", message: String(err.message || err) });
    }
  }
  return (
    <>
      <div className="fb-page-head"><h1><Icon name="trick" /> Truco automatico</h1><button className="fb-btn primary" onClick={runNow}>Correr ahora</button></div>
      <div className="fb-two-col">
        <section className="fb-card"><h2>Pendientes</h2><div className="fb-big warn">{trick.pending?.length || 0}</div><CampaignMiniList items={trick.pending || []} /></section>
        <section className="fb-card"><h2>Ejecutados</h2><div className="fb-big ok">{trick.done?.length || 0}</div><CampaignMiniList items={trick.done || []} /></section>
      </div>
    </>
  );
}

function CampaignMiniList({ items }) {
  if (!items.length) return <p className="fb-muted">Sin registros.</p>;
  return <div className="fb-mini-list">{items.map((item) => <div key={item._id}><strong>{item.name}</strong><span>{item.last_status || item.fb_campaign_id || "-"}</span></div>)}</div>;
}

function ComingSoon({ page }) {
  return <div className="fb-empty">{page}: se integra en la siguiente fase.</div>;
}
