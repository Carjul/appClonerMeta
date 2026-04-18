import React, { useEffect, useState } from "react";
import Swal from "sweetalert2";
import { api } from "../api";

const initialForm = { name: "", bmId: "", accessToken: "" };

export default function ConfigurationPage() {
  const [configs, setConfigs] = useState([]);
  const [form, setForm] = useState(initialForm);
  const [editing, setEditing] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const rows = await api.listConfigs();
      setConfigs(rows);
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

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
    </div>
  );
}
