import { useEffect, useState } from "react";
import OwnerLayout from "../owner/components/OwnerLayout";
import { notificationTemplatesApi } from "../api/operationsApi";
import { errorText } from "../api/axiosClient";

function ToggleSwitch({ checked, disabled, onChange, label }) {
  return (
    <label style={{ display: "inline-flex", alignItems: "center", gap: 7, cursor: disabled ? "not-allowed" : "pointer", fontSize: 12.5, fontWeight: 600, color: "#334155" }}>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={onChange}
        style={{
          position: "relative",
          width: 40,
          height: 22,
          borderRadius: 999,
          border: "none",
          padding: 0,
          cursor: disabled ? "not-allowed" : "pointer",
          background: checked ? "#ff77ff" : "#cbd5e1",
          transition: "background 0.2s ease",
        }}
      >
        <span
          style={{
            position: "absolute",
            top: 2,
            left: checked ? 20 : 2,
            width: 18,
            height: 18,
            borderRadius: "50%",
            background: "#fff",
            boxShadow: "0 1px 3px rgba(0,0,0,0.2)",
            transition: "left 0.2s ease",
          }}
        />
      </button>
      <span>{label}</span>
    </label>
  );
}

function renderSamplePreview(templateStr, companyName) {
  const sample = {
    customer_name: "Ali Raza",
    order_id: "RA-261124-9A4B",
    company_name: companyName || "Your Business",
    total_amount: "Rs. 1,450.00",
    status: "Confirmed",
    appointment_time: "Tomorrow at 11:00 AM",
    rider_name: "Bilal Ahmed",
  };
  return (templateStr || "").replace(/\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g, (_, key) =>
    sample[key] !== undefined ? sample[key] : ""
  );
}

export default function NotificationSettings({ embedded = false }) {
  const [companyName, setCompanyName] = useState("");
  const [placeholders, setPlaceholders] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [expanded, setExpanded] = useState({});
  const [drafts, setDrafts] = useState({});
  const [loading, setLoading] = useState(true);
  const [busyEvent, setBusyEvent] = useState(null);
  const [toast, setToast] = useState("");
  const [error, setError] = useState("");

  const loadTemplates = async () => {
    setError("");
    try {
      const { data } = await notificationTemplatesApi.list();
      setCompanyName(data.company_name || "");
      setPlaceholders(data.placeholders || []);
      const list = data.templates || [];
      setTemplates(list);
      const nextDrafts = {};
      list.forEach((t) => {
        nextDrafts[t.event_type] = {
          subject_template: t.subject_template,
          body_template: t.body_template,
        };
      });
      setDrafts(nextDrafts);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTemplates();
  }, []);

  const flashToast = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(""), 3200);
  };

  const handleToggle = async (tpl, field) => {
    setBusyEvent(tpl.event_type);
    setError("");
    try {
      const { data } = await notificationTemplatesApi.update(tpl.event_type, {
        [field]: !tpl[field],
      });
      setTemplates((prev) => prev.map((t) => (t.event_type === tpl.event_type ? data : t)));
      flashToast(`Updated "${tpl.label}" settings.`);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusyEvent(null);
    }
  };

  const handleSave = async (tpl) => {
    const draft = drafts[tpl.event_type] || {};
    setBusyEvent(tpl.event_type);
    setError("");
    try {
      const { data } = await notificationTemplatesApi.update(tpl.event_type, {
        subject_template: draft.subject_template ?? tpl.subject_template,
        body_template: draft.body_template ?? tpl.body_template,
      });
      setTemplates((prev) => prev.map((t) => (t.event_type === tpl.event_type ? data : t)));
      flashToast(`Saved template for "${tpl.label}".`);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusyEvent(null);
    }
  };

  const handleReset = async (tpl) => {
    setBusyEvent(tpl.event_type);
    setError("");
    try {
      const { data } = await notificationTemplatesApi.reset(tpl.event_type);
      setTemplates((prev) => prev.map((t) => (t.event_type === tpl.event_type ? data : t)));
      setDrafts((prev) => ({
        ...prev,
        [tpl.event_type]: {
          subject_template: data.subject_template,
          body_template: data.body_template,
        },
      }));
      flashToast(`Reset "${tpl.label}" back to default template.`);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusyEvent(null);
    }
  };

  const insertPlaceholder = (eventType, tag) => {
    setDrafts((prev) => {
      const cur = prev[eventType] || { subject_template: "", body_template: "" };
      return {
        ...prev,
        [eventType]: {
          ...cur,
          body_template: `${cur.body_template || ""}${cur.body_template ? " " : ""}${tag}`,
        },
      };
    });
  };

  const content = (
    <div style={{ display: "grid", gap: 14 }}>
      {error && <div className="ad-alert" role="alert">{error}</div>}
      {toast && (
        <div
          style={{
            background: "#fdf4ff",
            border: "1px solid #f0abfc",
            color: "#86198f",
            padding: "10px 14px",
            borderRadius: 10,
            fontSize: 13,
            fontWeight: 600,
          }}
        >
          ✅ {toast}
        </div>
      )}

      {loading ? (
        <div style={{ background: "#fff", borderRadius: 14, padding: 24, color: "#64748b" }}>
          Loading notification templates...
        </div>
      ) : (
        templates.map((tpl) => {
          const isOpen = !!expanded[tpl.event_type];
          const draft = drafts[tpl.event_type] || {
            subject_template: tpl.subject_template,
            body_template: tpl.body_template,
          };
          const isBusy = busyEvent === tpl.event_type;

          return (
            <div
              key={tpl.event_type}
              style={{
                background: "#ffffff",
                border: tpl.is_enabled ? "1px solid #f0abfc" : "1px solid #e2e8f0",
                borderRadius: 14,
                padding: "16px 18px",
                opacity: tpl.is_enabled ? 1 : 0.78,
              }}
            >
              {/* Card Header & Channel Toggles */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <h4 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: "#0f172a" }}>{tpl.label}</h4>
                    {tpl.is_customized && (
                      <span style={{ fontSize: 10.5, fontWeight: 700, padding: "2px 8px", borderRadius: 10, background: "#fdf4ff", color: "#a21caf" }}>
                        Customized
                      </span>
                    )}
                  </div>
                  <p style={{ margin: "3px 0 0", fontSize: 12.5, color: "#64748b" }}>{tpl.description}</p>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
                  <ToggleSwitch checked={tpl.is_enabled} disabled={isBusy} onChange={() => handleToggle(tpl, "is_enabled")} label="Enabled" />
                  <ToggleSwitch checked={tpl.whatsapp_enabled} disabled={isBusy || !tpl.is_enabled} onChange={() => handleToggle(tpl, "whatsapp_enabled")} label="WhatsApp" />
                  <ToggleSwitch checked={tpl.email_enabled} disabled={isBusy || !tpl.is_enabled} onChange={() => handleToggle(tpl, "email_enabled")} label="Email" />
                  <button
                    type="button"
                    onClick={() => setExpanded((p) => ({ ...p, [tpl.event_type]: !p[tpl.event_type] }))}
                    style={{
                      padding: "7px 12px",
                      borderRadius: 10,
                      border: "1px solid #e2e8f0",
                      background: isOpen ? "#fdf4ff" : "#fff",
                      color: isOpen ? "#a21caf" : "#334155",
                      fontWeight: 600,
                      fontSize: 12.5,
                      cursor: "pointer",
                    }}
                  >
                    {isOpen ? "▲ Hide Editor" : "✏️ Edit Template"}
                  </button>
                </div>
              </div>

              {/* Expandable Editor + Placeholders + Live Preview */}
              {isOpen && (
                <div style={{ marginTop: 16, paddingTop: 16, borderTop: "1px solid #f1f5f9", display: "grid", gap: 12 }}>
                  <div>
                    <label style={{ display: "block", fontSize: 12, fontWeight: 700, color: "#475569", marginBottom: 5 }}>
                      Email Subject Template
                    </label>
                    <input
                      value={draft.subject_template}
                      onChange={(e) =>
                        setDrafts((p) => ({
                          ...p,
                          [tpl.event_type]: { ...draft, subject_template: e.target.value },
                        }))
                      }
                      style={{ width: "100%", padding: "9px 12px", borderRadius: 10, border: "1px solid #e2e8f0", fontSize: 13.5 }}
                    />
                  </div>

                  <div>
                    <label style={{ display: "block", fontSize: 12, fontWeight: 700, color: "#475569", marginBottom: 5 }}>
                      Message Body (WhatsApp &amp; Email)
                    </label>
                    <textarea
                      rows={4}
                      value={draft.body_template}
                      onChange={(e) =>
                        setDrafts((p) => ({
                          ...p,
                          [tpl.event_type]: { ...draft, body_template: e.target.value },
                        }))
                      }
                      style={{ width: "100%", padding: "10px 12px", borderRadius: 10, border: "1px solid #e2e8f0", fontSize: 13.5, fontFamily: "inherit" }}
                    />
                  </div>

                  {/* Clickable Placeholder Chips */}
                  <div>
                    <div style={{ fontSize: 11.5, fontWeight: 700, color: "#64748b", marginBottom: 6 }}>
                      Insert Placeholder Tag:
                    </div>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                      {placeholders.map((ph) => (
                        <button
                          key={ph.tag}
                          type="button"
                          title={ph.description}
                          onClick={() => insertPlaceholder(tpl.event_type, ph.tag)}
                          style={{
                            padding: "4px 10px",
                            borderRadius: 999,
                            border: "1px solid #f0abfc",
                            background: "#fdf4ff",
                            color: "#a21caf",
                            fontSize: 11.5,
                            fontWeight: 600,
                            cursor: "pointer",
                          }}
                        >
                          + {ph.tag}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Live Preview Box */}
                  <div style={{ background: "#f8fafc", border: "1px dashed #d8b4fe", borderRadius: 12, padding: 12 }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: "#a21caf", textTransform: "uppercase", marginBottom: 4 }}>
                      Live Preview (Sample Customer Data)
                    </div>
                    <div style={{ fontSize: 12.5, fontWeight: 700, color: "#1e293b", marginBottom: 6 }}>
                      Subject: {renderSamplePreview(draft.subject_template, companyName)}
                    </div>
                    <div style={{ fontSize: 13, color: "#334155", whiteSpace: "pre-wrap", lineHeight: 1.45 }}>
                      {renderSamplePreview(draft.body_template, companyName)}
                    </div>
                  </div>

                  {/* Save & Reset Buttons */}
                  <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                    <button
                      type="button"
                      disabled={isBusy}
                      onClick={() => handleSave(tpl)}
                      style={{
                        padding: "9px 16px",
                        borderRadius: 10,
                        border: "none",
                        background: "#ff77ff",
                        color: "#ffffff",
                        fontWeight: 700,
                        fontSize: 13,
                        cursor: "pointer",
                        boxShadow: "0 3px 10px rgba(255,119,255,0.35)",
                      }}
                    >
                      {isBusy ? "Saving..." : "Save Changes"}
                    </button>
                    <button
                      type="button"
                      disabled={isBusy}
                      onClick={() => handleReset(tpl)}
                      style={{
                        padding: "9px 14px",
                        borderRadius: 10,
                        border: "1px solid #e2e8f0",
                        background: "#ffffff",
                        color: "#475569",
                        fontWeight: 600,
                        fontSize: 13,
                        cursor: "pointer",
                      }}
                    >
                      Reset to Default
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })
      )}
    </div>
  );

  if (embedded) return content;

  return (
    <OwnerLayout
      title="Notification Templates & Toggles"
      subtitle="Customize automated WhatsApp & Email messages and toggle individual lifecycle alerts."
    >
      {content}
    </OwnerLayout>
  );
}
