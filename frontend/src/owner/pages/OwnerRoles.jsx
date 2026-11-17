// src/pages/OwnerRoles.jsx  (route: /owner/roles)
import { useCallback, useEffect, useMemo, useState } from "react";
import OwnerLayout from "../components/OwnerLayout";
import { errorText } from "../../api/axiosClient";
import { roleApi } from "../../api/staffApi";
import { moduleIcon } from "../../constants/modules";

const EMPTY = { name: "", modules: [] };

export default function OwnerRoles() {
  const [roles, setRoles] = useState([]);
  const [catalog, setCatalog] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [businessLabel, setBusinessLabel] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState(null);

  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [formError, setFormError] = useState("");
  const [saving, setSaving] = useState(false);

  const labels = useMemo(() => Object.fromEntries(catalog.map((m) => [m.key, m.label])), [catalog]);
  const commonMods = useMemo(() => catalog.filter((m) => m.group === "common"), [catalog]);
  const businessMods = useMemo(() => catalog.filter((m) => m.group !== "common"), [catalog]);

  const load = useCallback(async () => {
    try {
      const [r, m] = await Promise.all([roleApi.list(), roleApi.modules()]);
      setRoles(r.data);
      const payload = m.data;
      setCatalog(Array.isArray(payload) ? payload : payload.modules || []);
      setTemplates(Array.isArray(payload) ? [] : payload.templates || []);
      setBusinessLabel(Array.isArray(payload) ? "" : payload.business_label || "");
    } catch (e) {
      setError(errorText(e));
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  const openNew = () => { setForm(EMPTY); setFormError(""); setEditing("new"); };
  const openEdit = (r) => {
    const allowed = new Set(catalog.map((m) => m.key));
    setForm({ name: r.name, modules: r.modules.filter((k) => allowed.has(k)) });
    setFormError("");
    setEditing(r);
  };
  const close = () => setEditing(null);

  const applyTemplate = (t) => setForm({ name: t.name, modules: [...t.modules] });

  const toggleModule = (key) =>
    setForm((f) => ({
      ...f,
      modules: f.modules.includes(key) ? f.modules.filter((m) => m !== key) : [...f.modules, key],
    }));

  const save = async (e) => {
    e.preventDefault();
    setFormError("");
    setSaving(true);
    try {
      if (editing === "new") {
        const { data } = await roleApi.create(form);
        setRoles((list) => [...list, data].sort((a, b) => a.name.localeCompare(b.name)));
      } else {
        const { data } = await roleApi.update(editing.id, form);
        setRoles((list) => list.map((r) => (r.id === data.id ? data : r)));
      }
      close();
    } catch (err) {
      setFormError(errorText(err));
    } finally {
      setSaving(false);
    }
  };

  const toggleActive = async (r) => {
    setBusyId(r.id);
    setError("");
    try {
      const { data } = await roleApi.update(r.id, { is_active: !r.is_active });
      setRoles((list) => list.map((x) => (x.id === r.id ? data : x)));
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusyId(null);
    }
  };

  const remove = async (r) => {
    if (!window.confirm(`Delete role "${r.name}"?`)) return;
    setBusyId(r.id);
    setError("");
    try {
      await roleApi.remove(r.id);
      setRoles((list) => list.filter((x) => x.id !== r.id));
    } catch (e) {
      setError(errorText(e)); // e.g. "Staff is assigned to this role..."
    } finally {
      setBusyId(null);
    }
  };

  const renderMod = (m) => (
    <label key={m.key} className={`ow-mod ${form.modules.includes(m.key) ? "on" : ""}`}>
      <input type="checkbox" checked={form.modules.includes(m.key)} onChange={() => toggleModule(m.key)} />
      <span>{moduleIcon(m.key)}</span>
      {m.label}
    </label>
  );

  return (
    <OwnerLayout
      title="Roles & access"
      subtitle={
        businessLabel
          ? `Create your own roles and choose which ${businessLabel} features each role can see.`
          : "Create roles for your team and choose what each role sees on its dashboard."
      }
      action={<button className="ad-btn ad-btn-primary" onClick={openNew}>+ New role</button>}
    >
      {error && <div className="ad-alert" role="alert">{error}</div>}

      {loading && <div className="ow-staff-grid">{[1, 2, 3].map((n) => <div className="ad-skeleton" style={{ height: 190 }} key={n} />)}</div>}

      {!loading && roles.length === 0 && (
        <div className="ad-empty">
          <span>🛡️</span>
          <h3>No roles yet</h3>
          <p>Create a role with any name you like, then pick what they can access.</p>
          <button className="ad-btn ad-btn-primary" style={{ marginTop: 18 }} onClick={openNew}>+ New role</button>
        </div>
      )}

      <div className="ow-staff-grid">
        {roles.map((r) => {
          const visible = r.modules.filter((m) => labels[m]);
          return (
            <article className={`ow-staff-card ${r.is_active ? "" : "off"}`} key={r.id}>
              <div className="ow-staff-top">
                <div className="ow-staff-name">
                  <h3>{r.name}</h3>
                  <small>{r.staff_count} staff</small>
                </div>
                <span className={`ow-status ${r.is_active ? "on" : ""}`}>{r.is_active ? "Active" : "Disabled"}</span>
              </div>

              <div className="ow-chips">
                {visible.length === 0 && <span className="ow-muted">No access selected</span>}
                {visible.map((m) => (
                  <span className="ow-chip" key={m}>{moduleIcon(m)} {labels[m]}</span>
                ))}
              </div>

              <div className="ow-actions-row">
                <button className="ad-btn ad-btn-primary" onClick={() => openEdit(r)}>Edit access</button>
                <button className="ad-btn ad-btn-ghost" disabled={busyId === r.id} onClick={() => toggleActive(r)}>
                  {r.is_active ? "Disable" : "Enable"}
                </button>
                <button className="ad-btn ad-btn-danger" disabled={busyId === r.id} onClick={() => remove(r)}>Delete</button>
              </div>
            </article>
          );
        })}
      </div>

      {editing && (
        <div className="ow-modal-bg" onClick={close}>
          <div className="ow-modal wide" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
            <button className="ow-close" onClick={close} aria-label="Close">✕</button>
            <form onSubmit={save} className="ow-scroll">
              <h2>{editing === "new" ? "New role" : `Edit ${editing.name}`}</h2>
              <p className="ow-muted">Staff with this role will only see the items you tick below on their dashboard.</p>
              {formError && <div className="ad-alert" role="alert">{formError}</div>}

              {editing === "new" && templates.length > 0 && (
                <>
                  <span className="ow-label">Quick start (optional)</span>
                  <div className="ow-chips" style={{ marginBottom: 14 }}>
                    {templates.map((t) => (
                      <button type="button" key={t.name} className="ow-chip" onClick={() => applyTemplate(t)}>
                        + {t.name}
                      </button>
                    ))}
                  </div>
                </>
              )}

              <div className="ow-field">
                <label htmlFor="role_name">Role name</label>
                <input
                  id="role_name"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="Type any name, e.g. Kitchen Staff, Night Cashier"
                  required
                />
              </div>

              {commonMods.length > 0 && (
                <>
                  <span className="ow-label">Common features</span>
                  <div className="ow-mods">{commonMods.map(renderMod)}</div>
                </>
              )}

              {businessMods.length > 0 && (
                <>
                  <span className="ow-label">{businessLabel ? `${businessLabel} features` : "Business features"}</span>
                  <div className="ow-mods">{businessMods.map(renderMod)}</div>
                </>
              )}

              <div className="ow-modal-actions">
                <button className="ad-btn ad-btn-primary" disabled={saving}>{saving ? "Saving..." : "Save role"}</button>
                <button type="button" className="ad-btn ad-btn-ghost" onClick={close}>Cancel</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </OwnerLayout>
  );
}