import { useEffect, useState } from "react";
import { errorText } from "../../../api/axiosClient";
import { profileApi } from "../../../api/profileApi";
import { useAuth } from "../../../context/AuthContext";

const EMPTY_PW = { current_password: "", new_password: "", confirm: "" };

export default function ProfileTab() {
  const { refreshUser } = useAuth();
  const [info, setInfo] = useState(null);
  const [form, setForm] = useState({ first_name: "", last_name: "", phone: "", address: "" });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [ok, setOk] = useState("");
  const [error, setError] = useState("");

  const [pw, setPw] = useState(EMPTY_PW);
  const [pwSaving, setPwSaving] = useState(false);
  const [pwOk, setPwOk] = useState("");
  const [pwError, setPwError] = useState("");

  useEffect(() => {
    profileApi.get()
      .then(({ data }) => {
        setInfo(data);
        setForm({ first_name: data.first_name, last_name: data.last_name, phone: data.phone, address: data.address });
      })
      .catch((e) => setError(errorText(e)))
      .finally(() => setLoading(false));
  }, []);

  const change = (e) => setForm({ ...form, [e.target.name]: e.target.value });

  const save = async (e) => {
    e.preventDefault();
    setSaving(true); setError(""); setOk("");
    try {
      const { data } = await profileApi.update(form);
      setInfo(data);
      setOk("Profile updated.");
      refreshUser?.();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setSaving(false);
    }
  };

  const savePassword = async (e) => {
    e.preventDefault();
    setPwError(""); setPwOk("");
    if (pw.new_password !== pw.confirm) return setPwError("New passwords do not match.");
    setPwSaving(true);
    try {
      await profileApi.changePassword({ current_password: pw.current_password, new_password: pw.new_password });
      setPw(EMPTY_PW);
      setPwOk("Password changed.");
    } catch (err) {
      setPwError(errorText(err));
    } finally {
      setPwSaving(false);
    }
  };

  if (loading) return <div className="ad-skeleton" style={{ height: 320 }} />;

  return (
    <div className="se-stack" style={{ maxWidth: 720 }}>
      <form className="se-card" onSubmit={save}>
        <h3>Your profile</h3>
        <p className="se-sub">Your personal and business contact details.</p>
        {ok && <div className="se-ok" role="status">{ok}</div>}
        {error && <div className="ad-alert" role="alert">{error}</div>}

        <div className="se-two">
          <div className="se-field">
            <label htmlFor="first_name">First name</label>
            <input id="first_name" name="first_name" value={form.first_name} onChange={change} required />
          </div>
          <div className="se-field">
            <label htmlFor="last_name">Last name</label>
            <input id="last_name" name="last_name" value={form.last_name} onChange={change} />
          </div>
          <div className="se-field">
            <label htmlFor="username">Username</label>
            <input id="username" value={info?.username || ""} readOnly />
          </div>
          <div className="se-field">
            <label htmlFor="email">Email</label>
            <input id="email" value={info?.email || ""} readOnly />
          </div>
          <div className="se-field">
            <label htmlFor="phone">Phone</label>
            <input id="phone" name="phone" value={form.phone} onChange={change} placeholder="03XXXXXXXXX" />
          </div>
          <div className="se-field">
            <label htmlFor="business_name">Business</label>
            <input id="business_name" value={`${info?.business_name || ""}`} readOnly />
            <small>Business type: {info?.business_type || "-"}</small>
          </div>
        </div>

        <div className="se-field">
          <label htmlFor="address">Business address</label>
          <input id="address" name="address" value={form.address} onChange={change} />
        </div>

        <div className="se-actions">
          <button className="ad-btn ad-btn-primary" disabled={saving}>{saving ? "Saving..." : "Save changes"}</button>
        </div>
      </form>

      <form className="se-card" onSubmit={savePassword}>
        <h3>Change password</h3>
        <p className="se-sub">Use at least 8 characters.</p>
        {pwOk && <div className="se-ok" role="status">{pwOk}</div>}
        {pwError && <div className="ad-alert" role="alert">{pwError}</div>}

        <div className="se-field">
          <label htmlFor="cp">Current password</label>
          <input id="cp" type="password" autoComplete="current-password" value={pw.current_password}
            onChange={(e) => setPw({ ...pw, current_password: e.target.value })} required />
        </div>
        <div className="se-two">
          <div className="se-field">
            <label htmlFor="np">New password</label>
            <input id="np" type="password" autoComplete="new-password" minLength={8} value={pw.new_password}
              onChange={(e) => setPw({ ...pw, new_password: e.target.value })} required />
          </div>
          <div className="se-field">
            <label htmlFor="cf">Confirm new password</label>
            <input id="cf" type="password" autoComplete="new-password" minLength={8} value={pw.confirm}
              onChange={(e) => setPw({ ...pw, confirm: e.target.value })} required />
          </div>
        </div>
        <div className="se-actions">
          <button className="ad-btn ad-btn-primary" disabled={pwSaving}>{pwSaving ? "Updating..." : "Update password"}</button>
        </div>
      </form>
    </div>
  );
}