import { useEffect, useState } from "react";
import OwnerLayout from "../owner/components/OwnerLayout";
import { privacyApi } from "../api/operationsApi";
import { errorText } from "../api/axiosClient";

const CONSENT_TYPES = [
  ["voice_ai_recording", "Voice AI Recording & Processing"],
  ["whatsapp_notifications", "WhatsApp Notifications"],
  ["data_processing", "Order & Data Processing"],
  ["marketing_upsell", "Marketing & Upsell Offers"],
];

const CHANNELS = [
  ["public_web", "Public Web"],
  ["widget", "Website Widget"],
  ["whatsapp", "WhatsApp"],
  ["dashboard", "Dashboard"],
];

export default function PrivacyComplianceSettings({ embedded = false }) {
  const [policy, setPolicy] = useState({
    chat_retention_days: 90,
    order_pii_retention_days: 365,
    auto_purge_enabled: false,
    last_purge_at: null,
  });
  const [consents, setConsents] = useState([]);
  const [consentForm, setConsentForm] = useState({
    customer_identifier: "",
    consent_type: "voice_ai_recording",
    channel: "dashboard",
    granted: true,
  });
  const [eraseQuery, setEraseQuery] = useState("");
  const [eraseResult, setEraseResult] = useState(null);
  const [purgeResult, setPurgeResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const loadAll = async () => {
    setError("");
    try {
      const [polRes, conRes] = await Promise.allSettled([
        privacyApi.getRetention(),
        privacyApi.listConsents(),
      ]);
      if (polRes.status === "fulfilled") setPolicy(polRes.value.data);
      if (conRes.status === "fulfilled") setConsents(Array.isArray(conRes.value.data) ? conRes.value.data : []);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
  }, []);

  const flashNotice = (msg) => {
    setNotice(msg);
    setTimeout(() => setNotice(""), 4000);
  };

  const handleSavePolicy = async (e) => {
    e.preventDefault();
    setBusy("policy");
    setError("");
    try {
      const { data } = await privacyApi.updateRetention({
        chat_retention_days: Number(policy.chat_retention_days || 90),
        order_pii_retention_days: Number(policy.order_pii_retention_days || 365),
        auto_purge_enabled: Boolean(policy.auto_purge_enabled),
      });
      setPolicy(data);
      flashNotice("Data retention policy saved.");
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy("");
    }
  };

  const handleRunPurge = async () => {
    if (!window.confirm("Run data retention purge now? Expired chat logs will be deleted and expired order PII anonymized (financial totals stay intact).")) {
      return;
    }
    setBusy("purge");
    setError("");
    try {
      const { data } = await privacyApi.runPurge({ dry_run: false });
      setPurgeResult(data);
      setPolicy((prev) => ({ ...prev, last_purge_at: data.last_purge_at || prev.last_purge_at }));
      flashNotice(`Purge complete: ${data.purged_messages} message(s) purged, ${data.anonymized_orders} order(s) anonymized.`);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy("");
    }
  };

  const handleEraseCustomer = async (e) => {
    e.preventDefault();
    if (!eraseQuery.trim()) return;
    if (!window.confirm(`Permanently anonymize all personal data for "${eraseQuery.trim()}" across orders, conversations, and appointments? Financial totals will be preserved.`)) {
      return;
    }
    setBusy("erase");
    setError("");
    try {
      const { data } = await privacyApi.eraseCustomer(eraseQuery.trim());
      setEraseResult(data);
      setEraseQuery("");
      await loadAll();
      flashNotice("Customer PII anonymized cleanly.");
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy("");
    }
  };

  const handleLogConsent = async (e) => {
    e.preventDefault();
    if (!consentForm.customer_identifier.trim()) return;
    setBusy("consent");
    setError("");
    try {
      await privacyApi.recordConsent(consentForm);
      setConsentForm({ customer_identifier: "", consent_type: "voice_ai_recording", channel: "dashboard", granted: true });
      await loadAll();
      flashNotice("Customer consent recorded.");
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy("");
    }
  };

  const content = (
    <div style={{ display: "grid", gap: 18 }}>
      {error && <div className="ad-alert" role="alert">{error}</div>}
      {notice && (
        <div style={{ background: "#fdf4ff", border: "1px solid #f0abfc", color: "#86198f", padding: "10px 14px", borderRadius: 10, fontSize: 13, fontWeight: 600 }}>
          ✅ {notice}
        </div>
      )}

      {loading ? (
        <div style={{ background: "#fff", borderRadius: 14, padding: 24, color: "#64748b" }}>Loading privacy &amp; compliance settings...</div>
      ) : (
        <>
          {/* 1. Data Retention Policy Card */}
          <form onSubmit={handleSavePolicy} style={{ background: "#fff", border: "1px solid #f0abfc", borderRadius: 16, padding: 20, display: "grid", gap: 14 }}>
            <div>
              <h3 style={{ margin: 0, fontSize: 16 }}>🛡️ Data Retention Policy</h3>
              <p style={{ margin: "4px 0 0", fontSize: 12.5, color: "#64748b" }}>
                Automatically purge old AI transcripts and anonymize expired order PII while keeping financial revenue totals intact.
              </p>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: 12 }}>
              <label style={{ display: "grid", gap: 5, fontSize: 12.5, fontWeight: 600 }}>
                Chat Retention (Days)
                <input
                  type="number"
                  min="1"
                  value={policy.chat_retention_days}
                  onChange={(e) => setPolicy({ ...policy, chat_retention_days: e.target.value })}
                  style={{ padding: "9px 12px", borderRadius: 10, border: "1px solid #d1d5db" }}
                />
              </label>

              <label style={{ display: "grid", gap: 5, fontSize: 12.5, fontWeight: 600 }}>
                Order PII Retention (Days)
                <input
                  type="number"
                  min="1"
                  value={policy.order_pii_retention_days}
                  onChange={(e) => setPolicy({ ...policy, order_pii_retention_days: e.target.value })}
                  style={{ padding: "9px 12px", borderRadius: 10, border: "1px solid #d1d5db" }}
                />
              </label>
            </div>

            <label style={{ display: "inline-flex", alignItems: "center", gap: 10, cursor: "pointer", fontSize: 13.5, fontWeight: 600 }}>
              <input
                type="checkbox"
                checked={Boolean(policy.auto_purge_enabled)}
                onChange={(e) => setPolicy({ ...policy, auto_purge_enabled: e.target.checked })}
              />
              Enable Scheduled Auto-Purge (`purge_expired_data`)
            </label>

            {policy.last_purge_at && (
              <div style={{ fontSize: 12, color: "#64748b" }}>
                Last purge executed: <strong>{new Date(policy.last_purge_at).toLocaleString()}</strong>
              </div>
            )}

            {purgeResult && (
              <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 10, padding: "10px 12px", fontSize: 12.5 }}>
                Purged <strong>{purgeResult.purged_messages}</strong> expired chat message(s) and anonymized <strong>{purgeResult.anonymized_orders}</strong> expired order(s).
              </div>
            )}

            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              <button
                type="submit"
                disabled={busy === "policy"}
                style={{
                  padding: "9px 18px",
                  borderRadius: 10,
                  border: "none",
                  background: "#ff77ff",
                  color: "#fff",
                  fontWeight: 700,
                  fontSize: 13,
                  cursor: "pointer",
                  boxShadow: "0 3px 10px rgba(255,119,255,0.35)",
                }}
              >
                {busy === "policy" ? "Saving..." : "Save Policy"}
              </button>
              <button
                type="button"
                disabled={busy === "purge"}
                onClick={handleRunPurge}
                style={{
                  padding: "9px 16px",
                  borderRadius: 10,
                  border: "1px solid #f0abfc",
                  background: "#fdf4ff",
                  color: "#a21caf",
                  fontWeight: 700,
                  fontSize: 13,
                  cursor: "pointer",
                }}
              >
                {busy === "purge" ? "Purging..." : "🧹 Run Purge Now"}
              </button>
            </div>
          </form>

          {/* 2. Customer Right-to-Erasure Card */}
          <form onSubmit={handleEraseCustomer} style={{ background: "#fff", border: "1px solid #fecaca", borderRadius: 16, padding: 20, display: "grid", gap: 12 }}>
            <div>
              <h3 style={{ margin: 0, fontSize: 16, color: "#991b1b" }}>🗑️ Customer Right-to-Erasure (Anonymize PII)</h3>
              <p style={{ margin: "4px 0 0", fontSize: 12.5, color: "#64748b" }}>
                Enter a customer&apos;s phone number or email to immediately anonymize their personal information across orders, appointments, conversations, and consent logs.
              </p>
            </div>

            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              <input
                placeholder="Customer phone (e.g. 03001234567) or email"
                value={eraseQuery}
                onChange={(e) => setEraseQuery(e.target.value)}
                required
                style={{ flex: 1, minWidth: 220, padding: "9px 12px", borderRadius: 10, border: "1px solid #fca5a5" }}
              />
              <button
                type="submit"
                disabled={busy === "erase"}
                style={{
                  padding: "9px 16px",
                  borderRadius: 10,
                  border: "none",
                  background: "#dc2626",
                  color: "#fff",
                  fontWeight: 700,
                  fontSize: 13,
                  cursor: "pointer",
                }}
              >
                {busy === "erase" ? "Anonymizing..." : "Anonymize Customer Data"}
              </button>
            </div>

            {eraseResult && (
              <div style={{ background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 10, padding: "10px 12px", fontSize: 12.5, color: "#991b1b" }}>
                Anonymized: <strong>{eraseResult.anonymized_orders}</strong> order(s), <strong>{eraseResult.anonymized_conversations}</strong> conversation(s), <strong>{eraseResult.purged_messages}</strong> message(s), <strong>{eraseResult.anonymized_appointments}</strong> appointment(s), <strong>{eraseResult.anonymized_lab_bookings}</strong> lab booking(s).
              </div>
            )}
          </form>

          {/* 3. Customer Consent Ledger */}
          <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 16, padding: 20, display: "grid", gap: 14 }}>
            <div>
              <h3 style={{ margin: 0, fontSize: 16 }}>📜 Customer Consent Ledger</h3>
              <p style={{ margin: "4px 0 0", fontSize: 12.5, color: "#64748b" }}>
                Audit trail of customer permissions for voice AI processing, WhatsApp alerts, and marketing offers.
              </p>
            </div>

            <form onSubmit={handleLogConsent} style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 8, alignItems: "center" }}>
              <input
                placeholder="Phone, email or session ID"
                value={consentForm.customer_identifier}
                onChange={(e) => setConsentForm({ ...consentForm, customer_identifier: e.target.value })}
                required
                style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid #d1d5db", fontSize: 13 }}
              />
              <select
                value={consentForm.consent_type}
                onChange={(e) => setConsentForm({ ...consentForm, consent_type: e.target.value })}
                style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid #d1d5db", fontSize: 13 }}
              >
                {CONSENT_TYPES.map(([k, lbl]) => <option key={k} value={k}>{lbl}</option>)}
              </select>
              <select
                value={consentForm.channel}
                onChange={(e) => setConsentForm({ ...consentForm, channel: e.target.value })}
                style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid #d1d5db", fontSize: 13 }}
              >
                {CHANNELS.map(([k, lbl]) => <option key={k} value={k}>{lbl}</option>)}
              </select>
              <select
                value={consentForm.granted ? "yes" : "no"}
                onChange={(e) => setConsentForm({ ...consentForm, granted: e.target.value === "yes" })}
                style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid #d1d5db", fontSize: 13 }}
              >
                <option value="yes">Granted</option>
                <option value="no">Revoked</option>
              </select>
              <button type="submit" disabled={busy === "consent"} className="ad-btn ad-btn-primary">
                + Log Consent
              </button>
            </form>

            {consents.length === 0 ? (
              <p style={{ margin: 0, fontSize: 13, color: "#94a3b8" }}>No consent records logged yet.</p>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid #e2e8f0", color: "#64748b", textAlign: "left" }}>
                      <th style={{ padding: "8px 6px" }}>Customer</th>
                      <th style={{ padding: "8px 6px" }}>Consent Type</th>
                      <th style={{ padding: "8px 6px" }}>Channel</th>
                      <th style={{ padding: "8px 6px" }}>Status</th>
                      <th style={{ padding: "8px 6px" }}>Recorded</th>
                    </tr>
                  </thead>
                  <tbody>
                    {consents.map((c) => (
                      <tr key={c.id} style={{ borderBottom: "1px solid #f1f5f9" }}>
                        <td style={{ padding: "8px 6px", fontWeight: 600 }}>{c.customer_identifier}</td>
                        <td style={{ padding: "8px 6px" }}>{c.consent_type_label}</td>
                        <td style={{ padding: "8px 6px" }}>{c.channel_label}</td>
                        <td style={{ padding: "8px 6px" }}>
                          <span style={{ fontSize: 11, fontWeight: 700, padding: "2px 8px", borderRadius: 999, background: c.granted ? "#ecfdf5" : "#fef2f2", color: c.granted ? "#047857" : "#b91c1c" }}>
                            {c.granted ? "Granted" : "Revoked"}
                          </span>
                        </td>
                        <td style={{ padding: "8px 6px", color: "#64748b", fontSize: 12 }}>{c.recorded_at ? new Date(c.recorded_at).toLocaleString() : ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );

  if (embedded) return content;

  return (
    <OwnerLayout
      title="Privacy & Data Retention"
      subtitle="Configure retention windows, audit customer consents, and execute right-to-erasure anonymization."
    >
      {content}
    </OwnerLayout>
  );
}
