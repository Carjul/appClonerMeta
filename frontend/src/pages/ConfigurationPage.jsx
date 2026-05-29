import React, { useEffect, useState } from "react";
import Swal from "sweetalert2";
import { api } from "../api";

const initialForm = { name: "", bmId: "", accessToken: "" };

export default function ConfigurationPage() {
  const [configs, setConfigs] = useState([]);
  const [users, setUsers] = useState([]);
  const [form, setForm] = useState(initialForm);
  const [editing, setEditing] = useState(null);
  const [loading, setLoading] = useState(false);
  const [configsLoaded, setConfigsLoaded] = useState(false);
  const [showTokenConfig, setShowTokenConfig] = useState(false);
  const [usersLoading, setUsersLoading] = useState(false);
  const [error, setError] = useState("");
  const [usersError, setUsersError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const rows = await api.listConfigs();
      setConfigs(rows);
      setConfigsLoaded(true);
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }

  async function loadUsers() {
    setUsersLoading(true);
    setUsersError("");
    try {
      const rows = await api.listUsers();
      setUsers(rows);
    } catch (e) {
      setUsersError(String(e.message || e));
    } finally {
      setUsersLoading(false);
    }
  }

  useEffect(() => {
    loadUsers();
  }, []);

  async function openTokenConfig() {
    setShowTokenConfig(true);
    if (!configsLoaded) await load();
  }

  async function onSubmit(e) {
    e.preventDefault();
    setError("");
    try {
      if (editing) {
        await api.updateConfig(editing, form);
      } else {
        await api.createConfig(form);
      }
      setForm(initialForm);
      setEditing(null);
      await load();
    } catch (err) {
      setError(String(err.message || err));
    }
  }

  function onEdit(row) {
    setEditing(row._id);
    setForm({ name: row.name || "", bmId: row.bm_id || "", accessToken: "" });
  }

  async function onUpdateUser(user) {
    setUsersError("");
    try {
      await api.updateUser(user.id, { role: user.role, status: user.status });
      await loadUsers();
      await Swal.fire({ title: "Usuario actualizado", icon: "success", timer: 1200, showConfirmButton: false });
    } catch (err) {
      setUsersError(String(err.message || err));
    }
  }

  function updateUserLocal(id, patch) {
    setUsers((rows) => rows.map((u) => (u.id === id ? { ...u, ...patch } : u)));
  }

  async function onDelete(id) {
    const confirm = await Swal.fire({
      title: "Eliminar configuracion",
      text: "Esta accion eliminara la configuracion guardada.",
      icon: "warning",
      showCancelButton: true,
      confirmButtonText: "Eliminar",
      cancelButtonText: "Cancelar",
    });
    if (!confirm.isConfirmed) return;

    setError("");
    try {
      await api.deleteConfig(id);
      await Swal.fire({
        title: "Eliminado",
        text: "La configuracion fue eliminada.",
        icon: "success",
        timer: 1400,
        showConfirmButton: false,
      });
      await load();
    } catch (err) {
      setError(String(err.message || err));
    }
  }

  return (
    <div className="panel-grid">
      <section className="panel token-config-toggle">
        <div>
          <h3>Tokens Meta</h3>
          <p style={{ color: "#9ca3af", marginTop: 0 }}>Esta sección carga configuraciones/tokens solo cuando la abres manualmente.</p>
        </div>
        {!showTokenConfig ? (
          <button className="btn btn-primary" type="button" onClick={openTokenConfig}>Cargar configuraciones Meta</button>
        ) : null}
      </section>

      {showTokenConfig ? <>
      <section className="panel" style={{ margin:"10px" }}>
        <h3>{editing ? "Editar configuracion" : "Nueva configuracion"}</h3>
        <form onSubmit={onSubmit} className="form-grid">
          <label>Nombre BM</label>
          <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          <label>BM ID</label>
          <input value={form.bmId} onChange={(e) => setForm({ ...form, bmId: e.target.value })} required />
          <label>Access Token</label>
          <textarea
            value={form.accessToken}
            onChange={(e) => setForm({ ...form, accessToken: e.target.value })}
            required={!editing}
            placeholder={editing ? "Dejar vacio para mantener token actual" : "Pegar token"}
            rows={3}
          />
          <div className="actions">
            <button className="btn btn-success" type="submit">{editing ? "Guardar" : "Crear"}</button>
            {editing ? <button className="btn btn-primary" type="button" onClick={() => { setEditing(null); setForm(initialForm); }}>Cancelar</button> : null}
          </div>
        </form>
      </section>
      <section className="panel" style={{ margin:"10px" }}>
        <h3>Configuraciones</h3>
        {loading ? <p>Cargando...</p> : null}
        {error ? <p className="error">{error}</p> : null}
        <div className="config-table-wrap">
          <table className="config-table">
            <thead>
              <tr>
                <th>Nombre</th>
                <th>BM ID</th>
                <th>Token</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {configs.map((c) => (
                <tr key={c._id}>
                  <td>{c.name}</td>
                  <td>{c.bm_id}</td>
                  <td>{c.tokenConfigured ? "Configurado" : "No configurado"}</td>
                  <td className="row-actions">
                    <button className="btn btn-primary" onClick={() => onEdit(c)}>Editar</button>
                    <button className="btn btn-danger" onClick={() => onDelete(c._id)}>Eliminar</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      </> : null}

      <section className="panel users-admin-card">
        <h3>Usuarios</h3>
        <p style={{ color: "#9ca3af", marginTop: 0 }}>Administra estatus y rol. Las contraseñas no se muestran ni se editan aquí.</p>
        {usersLoading ? <p>Cargando usuarios...</p> : null}
        {usersError ? <p className="error">{usersError}</p> : null}
        <div className="config-table-wrap users-table-wrap">
          <table className="config-table users-table">
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Email</th>
                <th>Rol</th>
                <th>Status</th>
                <th>Verificado</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>{u.name || "—"}</td>
                  <td>{u.email || "—"}</td>
                  <td>
                    <select value={u.role || "Cliente"} onChange={(e) => updateUserLocal(u.id, { role: e.target.value })}>
                      <option value="Cliente">Cliente</option>
                      <option value="Admin">Admin</option>
                      <option value="SuperAdmin">SuperAdmin</option>
                    </select>
                  </td>
                  <td>
                    <select value={u.status || "active"} onChange={(e) => updateUserLocal(u.id, { status: e.target.value })}>
                      <option value="active">active</option>
                      <option value="inactive">inactive</option>
                    </select>
                  </td>
                  <td>{u.email_verified_at ? new Date(u.email_verified_at).toLocaleString() : "—"}</td>
                  <td className="row-actions">
                    <button className="btn btn-success" type="button" onClick={() => onUpdateUser(u)}>Guardar</button>
                  </td>
                </tr>
              ))}
              {!users.length && !usersLoading ? (
                <tr><td colSpan="6">Sin usuarios.</td></tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
