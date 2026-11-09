import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import OwnerLayout from "../components/OwnerLayout";
import { errorText } from "../../api/axiosClient";
import { roleApi, staffApi } from "../../api/staffApi";

const EMPTY = { first_name: "", last_name: "", username: "", phone: "", email: "", password: "", role_id: "" };

function generatePassword() {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789";
  const bytes = crypto.getRandomValues(new Uint32Array(10));
  return Array.from(bytes, (b) => chars[b % chars.length]).join("");
}

export default function OwnerStaff() {
  const [params, setParams] = useSearchParams();
  const [staff, setStaff] = useState([]);
  const [roles, setRoles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [tab, setTab] = useState("all");
  const [busyId, setBusyId] = useState(null);

  const [open, setOpen] = useState(params.get("add") === "1");
  const [form, setForm] = useState(EMPTY);
  const [formError, setFormError] = useState("");
  const [saving, setSaving] = useState(false);
  const [created, setCreated] = useState(null);
  const [copied, setCopied] = useState(false);

  const activeRoles = useMemo(() => roles.filter((r) => r.is_active), [roles]);

  const load = useCallback(async () => {
    try {
      const [s, r] = await Promise.all([staffApi.list(), roleApi.list()]);
      setStaff(s.data);
      setRoles(r.data);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  const openModal = () => {
    setForm({ ...EMPTY, password: generatePassword(), role_id: activeRoles[0]?.id ?? "" });
    setFormError("");
    setCreated(null);
    setOpen(true);
  };
  const closeModal = () => { setOpen(false); setCreated(null); if (params.get("add")) setParams({}); };

  useEffect(() => {
    if (open && !created && !loading) {
      setForm((f) => ({
        ...f,
        password: f.password || generatePassword(),
        role_id: f.role_id || activeRoles[0]?.id || "",
      }));
    }
  }, [open, loading]); // eslint-disable-line

  const change = (e) => setForm({ ...form, [e.target.name]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setFormError("");
    setSaving(true);
    try {
      const { data } = await staffApi.create({ ...form, role_id: Number(form.role_id) });
      setStaff((list) => [data, ...list]);
      setRoles((list) => list.map((r) => (r.id === data.role_id ? { ...r, staff_count: r.staff_count + 1 } : r)));
      setCreated({ name: data.full_name, username: data.username, password: form.password, role: data.role_name });
    } catch (err) {
      setFormError(errorText(err));
    } finally {
      setSaving(false);
    }
  };

  const copy = async () => {
    const text = `Username: ${created.username}\nPassword: ${created.password}`;
    try { await navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000); } catch { /* ignore */ }
  };

  const toggle = async (s) => {
    if (s.is_active && !window.confirm(`Deactivate ${s.full_name}? They will not be able to log in.`)) return;
    setBusyId(s.id);
    setError("");
    try {
      const { data } = await staffApi.update(s.id, { is_active: !s.is_active });
      setStaff((list) => list.map((x) => (x.id === s.id ? data : x)));
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusyId(null);
    }
  };

  const remove = async (s) => {
    if (!window.confirm(`Remove ${s.full_name} permanently? This cannot be undone.`)) return;
    setBusyId(s.id);
    setError("");
    try {
      await staffApi.remove(s.id);
      setStaff((list) => list.filter((x) => x.id !== s.id));
      load(); // role counts refresh
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusyId(null);
    }
  };

  const changeRole = async (s, roleId) => {
    setBusyId(s.id);
    setError("");
    try {
      const { data } = await staffApi.update(s.id, { role_id: Number(roleId) });
      setStaff((list) => list.map((x) => (x.id === s.id ? data : x)));
      load(); // staff_count refresh
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusyId(null);
    }
  };

  const counts = useMemo(() => {
    const c = { all: staff.length };
    staff.forEach((s) => { c[s.role_id] = (c[s.role_id] || 0) + 1; });
    return c;
  }, [staff]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return staff.filter(
      (s) =>
        (tab === "all" || String(s.role_id) === String(tab)) &&
        (!q || [s.full_name, s.username, s.phone, s.email].some((v) => (v || "").toLowerCase().includes(q)))
    );
  }, [staff, tab, query]);

  return (
    <OwnerLayout
      title="Employees"
      subtitle="Add employees and give each one a role."
      action={<button className="ad-btn ad-btn-primary" onClick={openModal}>+ Add employee</button>}
    >
      <div className="ow-toolbar">
        <div className="ow-tabs" role="tablist">
          {[{ id: "all", name: "All" }, ...roles].map((t) => (
            <button key={t.id} role="tab" aria-selected={tab === t.id} className={tab === t.id ? "on" : ""} onClick={() => setTab(t.id)}>
              {t.name} <em>{counts[t.id] ?? 0}</em>
            </button>
          ))}
        </div>
        <input className="ad-search" type="search" placeholder="Search by name, username or phone" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Search employees" />
      </div>

      {error && <div className="ad-alert" role="alert">{error}</div>}

      {loading && <div className="ow-staff-grid">{[1, 2, 3].map((n) => <div className="ad-skeleton" style={{ height: 190 }} key={n} />)}</div>}

      {!loading && staff.length === 0 && (
        <div className="ad-empty">
          <span>👥</span>
          <h3>No employees yet</h3>
          <p>Add your first employee. They log in with the username and password you set.</p>
          <button className="ad-btn ad-btn-primary" style={{ marginTop: 18 }} onClick={openModal}>+ Add employee</button>
        </div>
      )}

      {!loading && staff.length > 0 && filtered.length === 0 && (
        <div className="ad-empty"><span>🔍</span><h3>No matches</h3><p>Try another search or role filter.</p></div>
      )}

      <div className="ow-staff-grid">
        {filtered.map((s) => (
          <article className={`ow-staff-card ${s.is_active ? "" : "off"}`} key={s.id}>
            <div className="ow-staff-top">
              <span className="ow-avatar">{(s.full_name || s.username || "?").charAt(0).toUpperCase()}</span>
              <div className="ow-staff-name">
                <h3>{s.full_name}</h3>
                <small>@{s.username}</small>
              </div>
              <span className={`ow-status ${s.is_active ? "on" : ""}`}>{s.is_active ? "Active" : "Inactive"}</span>
            </div>

            <label className="ow-label" htmlFor={`role-${s.id}`}>Role</label>
            <select
              id={`role-${s.id}`}
              className="ow-select"
              value={s.role_id ?? ""}
              disabled={busyId === s.id}
              onChange={(e) => changeRole(s, e.target.value)}
            >
              {s.role_id == null && <option value="">No role</option>}
              {roles
                .filter((r) => r.is_active || r.id === s.role_id)
                .map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
            </select>

            <dl className="ow-staff-info">
              <div><dt>Phone</dt><dd>{s.phone || "-"}</dd></div>
              <div><dt>Email</dt><dd>{s.email || "-"}</dd></div>
            </dl>

            <div className="ow-actions-row">
              <button
                className={`ad-btn ${s.is_active ? "ad-btn-ghost" : "ad-btn-primary"}`}
                disabled={busyId === s.id}
                onClick={() => toggle(s)}
              >
                {busyId === s.id ? "Please wait..." : s.is_active ? "Deactivate" : "Activate again"}
              </button>
              <button className="ad-btn ad-btn-danger" disabled={busyId === s.id} onClick={() => remove(s)}>
                Remove
              </button>
            </div>
          </article>
        ))}
      </div>

      {/* ---------- ADD EMPLOYEE MODAL ---------- */}
      {open && (
        <div className="ow-modal-bg" onClick={closeModal}>
          <div className="ow-modal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
            <button className="ow-close" onClick={closeModal} aria-label="Close">✕</button>

            {created ? (
              <div className="ow-done">
                <span className="ow-done-icon">✓</span>
                <h2>{created.name} was added as {created.role}</h2>
                <p>Share these login details with them. The password is not shown again.</p>
                <div className="ow-cred">
                  <div><small>Username</small><strong>{created.username}</strong></div>
                  <div><small>Password</small><strong>{created.password}</strong></div>
                </div>
                <div className="ow-modal-actions">
                  <button className="ad-btn ad-btn-primary" onClick={copy}>{copied ? "Copied ✓" : "Copy details"}</button>
                  <button className="ad-btn ad-btn-ghost" onClick={openModal}>Add another</button>
                </div>
              </div>
            ) : (
              <form onSubmit={submit} className="ow-scroll">
                <h2>Add employee</h2>
                <p className="ow-muted">They will log in with the username and password below.</p>
                {formError && <div className="ad-alert" role="alert">{formError}</div>}

                <span className="ow-label">Role</span>
                {activeRoles.length === 0 ? (
                  <div className="ad-alert">
                    You have no active roles yet. <Link to="/owner/roles">Create a role first →</Link>
                  </div>
                ) : (
                  <div className="ow-roles">
                    {activeRoles.map((r) => (
                      <label key={r.id} className={`ow-role-opt ${String(form.role_id) === String(r.id) ? "on" : ""}`}>
                        <input type="radio" name="role_id" value={r.id} checked={String(form.role_id) === String(r.id)} onChange={change} />
                        <strong>{r.name}</strong>
                        <small>{r.modules.length} dashboard items</small>
                      </label>
                    ))}
                  </div>
                )}

                <div className="ow-grid">
                  <div className="ow-field"><label htmlFor="first_name">First name</label><input id="first_name" name="first_name" value={form.first_name} onChange={change} required /></div>
                  <div className="ow-field"><label htmlFor="last_name">Last name</label><input id="last_name" name="last_name" value={form.last_name} onChange={change} /></div>
                  <div className="ow-field"><label htmlFor="username">Username</label><input id="username" name="username" value={form.username} onChange={change} autoComplete="off" required /></div>
                  <div className="ow-field"><label htmlFor="phone">Phone</label><input id="phone" name="phone" value={form.phone} onChange={change} placeholder="03XXXXXXXXX" /></div>
                </div>
                <div className="ow-field"><label htmlFor="email">Email (optional)</label><input id="email" type="email" name="email" value={form.email} onChange={change} /></div>
                <div className="ow-field">
                  <label htmlFor="password">Password</label>
                  <div className="ow-pass">
                    <input id="password" name="password" value={form.password} onChange={change} minLength={8} autoComplete="off" required />
                    <button type="button" className="ad-btn ad-btn-ghost" onClick={() => setForm({ ...form, password: generatePassword() })}>Generate</button>
                  </div>
                </div>

                <div className="ow-modal-actions">
                  <button className="ad-btn ad-btn-primary" disabled={saving || activeRoles.length === 0}>{saving ? "Creating..." : "Create account"}</button>
                  <button type="button" className="ad-btn ad-btn-ghost" onClick={closeModal}>Cancel</button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </OwnerLayout>
  );
}