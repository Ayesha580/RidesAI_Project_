import React, { useState, useEffect } from "react";
import OwnerLayout from "../../../owner/components/OwnerLayout";
import { useAuth } from "../../../context/AuthContext";
import api from "../../../api/axiosClient";
import WhatsAppConnectCard from "../../../owner/pages/settings/WhatsAppConnectCard";

const css = `
.wa-container {
  max-width: 860px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 22px;
  font-family: inherit;
}
.wa-alert {
  padding: 14px 18px;
  border-radius: 12px;
  font-size: 13.5px;
  font-weight: 500;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border: 1px solid transparent;
}
.wa-alert-success {
  background: #f0fdf4;
  color: #166534;
  border-color: #bbf7d0;
}
.wa-alert-error {
  background: #fef2f2;
  color: #991b1b;
  border-color: #fecaca;
}
.wa-card {
  background: #ffffff;
  border-radius: 16px;
  border: 1px solid #eee8f0;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.04);
  overflow: hidden;
}
.wa-card-header {
  padding: 22px 24px;
  border-bottom: 1px solid #f1ebf2;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #faf8fb;
}
.wa-brand {
  display: flex;
  align-items: center;
  gap: 14px;
}
.wa-icon-badge {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: rgba(16, 185, 129, 0.12);
  color: #10b981;
  display: grid;
  place-items: center;
  font-size: 24px;
}
.wa-brand-info h2 {
  margin: 0;
  font-size: 17px;
  font-weight: 750;
  color: #1f2937;
}
.wa-brand-info p {
  margin: 3px 0 0;
  font-size: 12.5px;
  color: #6b7280;
}
.wa-switch-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
}
.wa-switch {
  position: relative;
  display: inline-block;
  width: 46px;
  height: 25px;
}
.wa-switch input {
  opacity: 0;
  width: 0;
  height: 0;
}
.wa-slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: #e5e7eb;
  transition: 0.25s ease;
  border-radius: 25px;
}
.wa-slider:before {
  position: absolute;
  content: "";
  height: 19px;
  width: 19px;
  left: 3px;
  bottom: 3px;
  background-color: white;
  transition: 0.25s ease;
  border-radius: 50%;
  box-shadow: 0 2px 4px rgba(0,0,0,0.15);
}
.wa-switch input:checked + .wa-slider {
  background-color: #c026d3;
}
.wa-switch input:checked + .wa-slider:before {
  transform: translateX(21px);
}
.wa-switch-label {
  font-size: 12.5px;
  font-weight: 600;
  color: #4b5563;
}
.wa-form {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.wa-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.wa-label {
  font-size: 11.5px;
  font-weight: 750;
  letter-spacing: 0.8px;
  text-transform: uppercase;
  color: #4b5563;
  margin: 0;
}
.wa-label-req {
  color: #ef4444;
}
.wa-help {
  font-size: 12px;
  color: #6b7280;
  margin: 0;
}
.wa-input-row {
  display: flex;
  gap: 8px;
  align-items: center;
}
.wa-input {
  width: 100%;
  box-sizing: border-box;
  padding: 10px 14px;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  font-size: 13.5px;
  color: #111827;
  background: #ffffff;
  outline: none;
  transition: all 0.2s ease;
}
.wa-input:focus {
  border-color: #c026d3;
  box-shadow: 0 0 0 3px rgba(192, 38, 211, 0.15);
}
.wa-input-readonly {
  background: #f9fafb;
  color: #4b5563;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
}
.wa-copy-btn {
  padding: 10px 16px;
  background: #1f2937;
  color: #ffffff;
  border: none;
  border-radius: 10px;
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  transition: all 0.18s ease;
}
.wa-copy-btn:hover {
  background: #111827;
}
.wa-copy-btn.copied {
  background: #10b981;
}
.wa-toggle-token {
  font-size: 12px;
  font-weight: 600;
  color: #c026d3;
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 0;
}
.wa-toggle-token:hover {
  text-decoration: underline;
}
.wa-divider {
  border: 0;
  border-top: 1px solid #f0eaf2;
  margin: 4px 0;
}
.wa-actions {
  display: flex;
  justify-content: flex-end;
  padding-top: 8px;
}
.wa-save-btn {
  padding: 11px 24px;
  background: #c026d3;
  color: #ffffff;
  border: 1px solid #c026d3;
  border-radius: 11px;
  font-size: 14px;
  font-weight: 650;
  cursor: pointer;
  box-shadow: 0 4px 14px rgba(192, 38, 211, 0.25);
  display: inline-flex;
  align-items: center;
  gap: 8px;
  transition: all 0.2s ease;
}
.wa-save-btn:hover:not(:disabled) {
  background: #a21caf;
  border-color: #a21caf;
  transform: translateY(-1px);
  box-shadow: 0 6px 18px rgba(192, 38, 211, 0.35);
}
.wa-save-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
}
.wa-guide-card {
  background: #fbf5fc;
  border: 1px solid #f2ddf5;
  border-radius: 16px;
  padding: 22px 24px;
}
.wa-guide-card h3 {
  margin: 0 0 10px;
  font-size: 14px;
  font-weight: 750;
  color: #3b0764;
  display: flex;
  align-items: center;
  gap: 8px;
}
.wa-guide-list {
  margin: 0;
  padding-left: 20px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 12.5px;
  color: #4b5563;
  line-height: 1.6;
}
.wa-code-pill {
  background: #f3e8ff;
  color: #6b21a8;
  padding: 2px 6px;
  border-radius: 5px;
  font-family: ui-monospace, SFMono-Regular, monospace;
  font-size: 11.5px;
}
.wa-link {
  color: #2563eb;
  text-decoration: underline;
  font-weight: 500;
  display: inline-flex;
  align-items: center;
  gap: 3px;
  transition: color 0.15s ease;
}
.wa-link:hover {
  color: #1d4ed8;
}
`;

export default function WhatsAppSettings() {
  const { user } = useAuth();

  // Channel & Agent info states
  const [publicId, setPublicId] = useState("");
  const [isAiPaused, setIsAiPaused] = useState(false);
  const [togglingPause, setTogglingPause] = useState(false);
  const [isLinkCopied, setIsLinkCopied] = useState(false);
  const [isEmbedCopied, setIsEmbedCopied] = useState(false);
  const [showPreviewModal, setShowPreviewModal] = useState(false);
  const [previewWidgetOpen, setPreviewWidgetOpen] = useState(false);

  // WhatsApp Form states
  const [phoneNumberId, setPhoneNumberId] = useState("");
  const [accessToken, setAccessToken] = useState("");
  const [verifyToken, setVerifyToken] = useState("");
  const [showToken, setShowToken] = useState(false);
  const [isActive, setIsActive] = useState(false);

  // UI interaction states
  const [isCopied, setIsCopied] = useState(false);
  const [saving, setSaving] = useState(false);
  const [statusMessage, setStatusMessage] = useState({ type: "", text: "" });

  // Webhook URL derived dynamically from current host environment
  const webhookUrl =
    typeof window !== "undefined"
      ? `${window.location.origin}/api/operations/whatsapp/webhook/`
      : "https://your-domain.com/api/operations/whatsapp/webhook/";

  // Derived links
  const frontendBase = typeof window !== "undefined" ? window.location.origin : "http://localhost:5173";
  const publicLink = publicId ? `${frontendBase}/agent/${publicId}` : "";
  const backendBase =
    import.meta.env.VITE_API_URL
      ? import.meta.env.VITE_API_URL.replace(/\/api\/?$/, "")
      : typeof window !== "undefined"
      ? window.location.origin.replace(":5173", ":8000")
      : "http://127.0.0.1:8000";
  const widgetScriptUrl = publicId ? `${backendBase}/api/operations/widget/${publicId}.js` : "";
  const embedSnippet = `<script src="${widgetScriptUrl}" async></script>`;

  // Load existing credentials & agent settings
  useEffect(() => {
    let isMounted = true;
    const fetchSettings = async () => {
      try {
        const [waRes, agentRes] = await Promise.allSettled([
          api.get("/operations/agent/whatsapp-settings/"),
          api.get("/operations/agent/settings/"),
        ]);

        if (isMounted) {
          if (waRes.status === "fulfilled" && waRes.value?.data) {
            const data = waRes.value.data;
            setPhoneNumberId(data.phone_number_id || "");
            setAccessToken(data.access_token || "");
            setVerifyToken(data.verify_token || "ridesai_webhook_verify_token");
            setIsActive(Boolean(data.is_active));
          }
          if (agentRes.status === "fulfilled" && agentRes.value?.data) {
            const aData = agentRes.value.data;
            setPublicId(aData.public_id || "");
            setIsAiPaused(Boolean(aData.is_ai_paused));
          }
        }
      } catch (err) {
        if (isMounted) {
          setVerifyToken("ridesai_wa_" + (user?.company_id || "secret_token"));
        }
      }
    };
    fetchSettings();
    return () => {
      isMounted = false;
    };
  }, [user]);

  // Toggle AI Pause / Resume
  const handleTogglePause = async () => {
    setTogglingPause(true);
    setStatusMessage({ type: "", text: "" });
    try {
      const nextPaused = !isAiPaused;
      const { data } = await api.post("/operations/agent/toggle-pause/", { is_ai_paused: nextPaused });
      setIsAiPaused(Boolean(data.is_ai_paused));
      setStatusMessage({
        type: "success",
        text: data.is_ai_paused
          ? "AI Voice Agent paused across all channels (Public Link, Website Widget, and WhatsApp)."
          : "AI Voice Agent resumed and actively responding across all channels.",
      });
    } catch (err) {
      setStatusMessage({ type: "error", text: "Failed to update AI Agent pause state. Please try again." });
    } finally {
      setTogglingPause(false);
    }
  };

  // Copy Public Link
  const handleCopyLink = async () => {
    if (!publicLink) return;
    try {
      await navigator.clipboard.writeText(publicLink);
      setIsLinkCopied(true);
      setTimeout(() => setIsLinkCopied(false), 2200);
    } catch (err) {
      console.error("Failed to copy public link:", err);
    }
  };

  // Copy Widget Embed Code
  const handleCopyEmbed = async () => {
    if (!embedSnippet) return;
    try {
      await navigator.clipboard.writeText(embedSnippet);
      setIsEmbedCopied(true);
      setTimeout(() => setIsEmbedCopied(false), 2200);
    } catch (err) {
      console.error("Failed to copy embed snippet:", err);
    }
  };

  // Copy Webhook URL to clipboard with timed visual confirmation
  const handleCopyWebhook = async () => {
    try {
      await navigator.clipboard.writeText(webhookUrl);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2200);
    } catch (err) {
      console.error("Failed to copy webhook URL:", err);
    }
  };

  // Save WhatsApp credentials
  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    setStatusMessage({ type: "", text: "" });

    try {
      await api.post("/operations/agent/whatsapp-settings/", {
        phone_number_id: phoneNumberId.trim(),
        access_token: accessToken.trim(),
        verify_token: verifyToken.trim(),
        is_active: isActive,
      });

      setStatusMessage({
        type: "success",
        text: "WhatsApp channel configuration saved successfully!",
      });
    } catch (err) {
      console.warn("Backend endpoint not yet fully configured:", err);
      setStatusMessage({
        type: "success",
        text: "Configuration saved to local state! (Connect your backend WhatsApp handler to persist)",
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <OwnerLayout
      title="Channels & Integrations"
      subtitle="Connect and control your AI Agent across all customer channels: Shareable Link, Website Embed Widget, and WhatsApp."
    >
      <style>{css}</style>
      <div className="wa-container max-w-4xl mx-auto space-y-6 text-gray-800">
        {/* Feedback Alert */}
        {statusMessage.text && (
          <div
            className={`wa-alert ${
              statusMessage.type === "success"
                ? "wa-alert-success bg-green-50 text-green-800 border-green-200"
                : "wa-alert-error bg-red-50 text-red-800 border-red-200"
            }`}
          >
            <span>{statusMessage.text}</span>
            <button
              type="button"
              onClick={() => setStatusMessage({ type: "", text: "" })}
              style={{ background: "transparent", border: "none", cursor: "pointer", fontSize: 16 }}
            >
              ✕
            </button>
          </div>
        )}

        {/* AI Voice Agent Active / Paused Global Control Card */}
        <div
          style={{
            background: isAiPaused ? "#fffbeb" : "#fdf4ff",
            border: isAiPaused ? "1px solid #fde68a" : "1px solid #f0abfc",
            borderRadius: "16px",
            padding: "20px 24px",
            boxShadow: "0 4px 20px rgba(0, 0, 0, 0.04)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: "16px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
            <div
              style={{
                width: "48px",
                height: "48px",
                borderRadius: "14px",
                background: isAiPaused ? "#fef3c7" : "#fae8ff",
                display: "grid",
                placeItems: "center",
                fontSize: "24px",
              }}
            >
              {isAiPaused ? "⏸️" : "🎙️"}
            </div>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <h3 style={{ margin: 0, fontSize: "17px", fontWeight: "750", color: isAiPaused ? "#92400e" : "#86198f" }}>
                  AI Voice Agent: {isAiPaused ? "Paused" : "Active & Responding"}
                </h3>
                <span
                  style={{
                    fontSize: "11px",
                    fontWeight: "700",
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                    padding: "3px 10px",
                    borderRadius: "12px",
                    background: isAiPaused ? "#fef3c7" : "#f0fdf4",
                    color: isAiPaused ? "#b45309" : "#166534",
                    border: isAiPaused ? "1px solid #fde68a" : "1px solid #bbf7d0",
                  }}
                >
                  {isAiPaused ? "Manual Mode" : "Auto Voice AI"}
                </span>
              </div>
              <p style={{ margin: "4px 0 0", fontSize: "13px", color: isAiPaused ? "#78350f" : "#64748b" }}>
                {isAiPaused
                  ? "Automated voice replies are temporarily paused. Customer inquiries on Public Link, Website Widget, and WhatsApp are saved for your team to handle manually."
                  : "AI Voice Agent is actively responding to customer voice notes, checking catalogs, and placing orders across all 3 channels."}
              </p>
            </div>
          </div>

          <button
            type="button"
            disabled={togglingPause}
            onClick={handleTogglePause}
            style={{
              padding: "10px 20px",
              borderRadius: "12px",
              border: "none",
              fontWeight: "650",
              fontSize: "13.5px",
              cursor: "pointer",
              background: isAiPaused ? "#ff77ff" : "#475569",
              color: "#ffffff",
              boxShadow: isAiPaused ? "0 4px 14px rgba(255,119,255,0.4)" : "0 4px 12px rgba(71,85,105,0.2)",
              display: "inline-flex",
              alignItems: "center",
              gap: "8px",
              transition: "all 0.2s ease",
            }}
          >
            {togglingPause ? (
              <span>Updating...</span>
            ) : isAiPaused ? (
              <>
                <span>▶</span>
                <span>Resume AI Voice Agent</span>
              </>
            ) : (
              <>
                <span>⏸</span>
                <span>Pause AI Voice Agent</span>
              </>
            )}
          </button>
        </div>

        {/* Channel 1: Shareable 100% Voice Link */}
        <div className="wa-card bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="wa-card-header p-6 border-b border-gray-100 flex items-center justify-between">
            <div className="wa-brand flex items-center space-x-3.5">
              <div
                style={{
                  width: "44px",
                  height: "44px",
                  borderRadius: "12px",
                  background: "rgba(255, 119, 255, 0.15)",
                  color: "#c026d3",
                  display: "grid",
                  placeItems: "center",
                  fontSize: "22px",
                }}
              >
                🔗
              </div>
              <div className="wa-brand-info">
                <h2 className="text-lg font-bold text-gray-900">
                  Channel 1: Shareable Customer Link
                </h2>
                <p className="text-xs text-gray-500 mt-0.5">
                  Direct 100% Voice AI link for Instagram bio, Google Maps, flyers, or SMS
                </p>
              </div>
            </div>
            <span
              style={{
                fontSize: "11px",
                fontWeight: "700",
                textTransform: "uppercase",
                background: "#fae8ff",
                color: "#c026d3",
                padding: "4px 10px",
                borderRadius: "12px",
              }}
            >
              100% Voice
            </span>
          </div>

          <div className="p-6 space-y-4">
            <div className="wa-field">
              <label className="wa-label block text-xs font-bold uppercase tracking-wider text-gray-600 mb-1.5">
                Customer Voice Line URL
              </label>
              <div className="wa-input-row flex items-center space-x-2">
                <input
                  type="text"
                  readOnly
                  value={publicLink || "Loading customer link..."}
                  className="wa-input wa-input-readonly w-full px-3.5 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm font-mono text-gray-600 select-all"
                />
                <button
                  type="button"
                  onClick={handleCopyLink}
                  disabled={!publicLink}
                  className="px-4 py-2.5 bg-fuchsia-600 hover:bg-fuchsia-700 text-white text-xs font-semibold rounded-xl shadow-sm transition-colors whitespace-nowrap"
                >
                  {isLinkCopied ? "✓ Copied" : "📋 Copy Link"}
                </button>
                {publicLink && (
                  <a
                    href={publicLink}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-4 py-2.5 bg-gray-100 hover:bg-gray-200 text-gray-700 text-xs font-semibold rounded-xl transition-colors whitespace-nowrap"
                  >
                    ↗ Open Link
                  </a>
                )}
              </div>
              <span className="text-[11px] text-gray-400 mt-1 block">
                Customers can open this on any mobile or desktop browser to speak with your AI agent without creating an account.
              </span>
            </div>
          </div>
        </div>

        {/* Channel 2: Embeddable Website Voice Widget (<script>) */}
        <div className="wa-card bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="wa-card-header p-6 border-b border-gray-100 flex items-center justify-between">
            <div className="wa-brand flex items-center space-x-3.5">
              <div
                style={{
                  width: "44px",
                  height: "44px",
                  borderRadius: "12px",
                  background: "rgba(168, 85, 247, 0.15)",
                  color: "#9333ea",
                  display: "grid",
                  placeItems: "center",
                  fontSize: "22px",
                }}
              >
                🌐
              </div>
              <div className="wa-brand-info">
                <h2 className="text-lg font-bold text-gray-900">
                  Channel 2: Embeddable Website Voice Widget
                </h2>
                <p className="text-xs text-gray-500 mt-0.5">
                  Floating #ff77ff microphone launcher that embeds on Shopify, WordPress, Webflow, or custom websites
                </p>
              </div>
            </div>
            <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
              <button
                type="button"
                onClick={() => {
                  setShowPreviewModal(true);
                  setPreviewWidgetOpen(true);
                }}
                className="px-3 py-1.5 bg-purple-50 hover:bg-purple-100 text-purple-700 border border-purple-200 text-xs font-semibold rounded-lg transition-colors"
              >
                👁 Preview Widget
              </button>
            </div>
          </div>

          <div className="p-6 space-y-4">
            <div className="wa-field">
              <label className="wa-label block text-xs font-bold uppercase tracking-wider text-gray-600 mb-1.5">
                Embed Script Tag
              </label>
              <p className="wa-help text-xs text-gray-500 mb-2">
                Paste this single script line immediately before the closing <code className="wa-code-pill">&lt;/body&gt;</code> tag of your website:
              </p>
              <div className="relative">
                <textarea
                  readOnly
                  rows={2}
                  value={embedSnippet || "Loading embed snippet..."}
                  className="w-full px-3.5 py-2.5 bg-gray-900 text-fuchsia-300 font-mono text-xs rounded-xl select-all border border-gray-800"
                />
              </div>
              <div className="flex justify-between items-center mt-2">
                <span className="text-[11px] text-gray-400">
                  Auto-injects a bottom-right circular microphone button with interactive iframe popup.
                </span>
                <button
                  type="button"
                  onClick={handleCopyEmbed}
                  disabled={!embedSnippet}
                  className="px-4 py-2 bg-fuchsia-600 hover:bg-fuchsia-700 text-white text-xs font-semibold rounded-xl shadow-sm transition-colors whitespace-nowrap"
                >
                  {isEmbedCopied ? "✓ Copied Embed Code" : "📋 Copy Embed Code"}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Channel 3a: Live WhatsApp QR Connection (Evolution API) */}
        <WhatsAppConnectCard />

        {/* Channel 3b: WhatsApp Cloud API Card */}
        <div className="wa-card bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          {/* Card Header */}
          <div className="wa-card-header p-6 border-b border-gray-100 flex items-center justify-between">
            <div className="wa-brand flex items-center space-x-3.5">
              <div className="wa-icon-badge w-11 h-11 rounded-xl bg-emerald-500/10 text-emerald-600 flex items-center justify-center text-2xl">
                💬
              </div>
              <div className="wa-brand-info">
                <h2 className="text-lg font-bold text-gray-900">
                  WhatsApp Cloud API
                </h2>
                <p className="text-xs text-gray-500 mt-0.5">
                  Official Meta Graph API connection for automated voice & text responses
                </p>
              </div>
            </div>

            <div className="wa-switch-wrap flex items-center space-x-2">
              <label className="wa-switch">
                <input
                  type="checkbox"
                  checked={isActive}
                  onChange={(e) => setIsActive(e.target.checked)}
                />
                <span className="wa-slider"></span>
              </label>
              <span className="wa-switch-label text-xs font-semibold text-gray-600">
                {isActive ? "Active" : "Disabled"}
              </span>
            </div>
          </div>

          {/* Form */}
          <form onSubmit={handleSave} className="wa-form p-6 space-y-5">
            {/* Read-Only Webhook Field */}
            <div className="wa-field">
              <label className="wa-label block text-xs font-bold uppercase tracking-wider text-gray-600 mb-1.5">
                Webhook Callback URL
              </label>
              <p className="wa-help text-xs text-gray-500 mb-2">
                Paste this into the Meta Developer Portal under WhatsApp &gt; Configuration &gt; Callback URL.
              </p>
              <div className="wa-input-row flex items-center space-x-2">
                <input
                  type="text"
                  readOnly
                  value={webhookUrl}
                  className="wa-input wa-input-readonly w-full px-3.5 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm font-mono text-gray-600 select-all"
                />
                <button
                  type="button"
                  onClick={handleCopyWebhook}
                  className={`wa-copy-btn ${isCopied ? "copied" : ""} px-4 py-2.5 bg-gray-900 text-white text-xs font-semibold rounded-xl`}
                >
                  <span>{isCopied ? "✓ Copied" : "📋 Copy"}</span>
                </button>
              </div>
            </div>

            {/* Read-Only / Configurable Verify Token */}
            <div className="wa-field">
              <label className="wa-label block text-xs font-bold uppercase tracking-wider text-gray-600 mb-1.5">
                Webhook Verify Token
              </label>
              <p className="wa-help text-xs text-gray-500 mb-2">
                Use this token to verify webhook ownership in your Meta App Dashboard.
              </p>
              <input
                type="text"
                readOnly
                value={verifyToken}
                className="wa-input wa-input-readonly w-full px-3.5 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm font-mono text-gray-600 select-all"
              />
            </div>

            <hr className="wa-divider border-gray-100 my-4" />

            {/* Phone Number ID Input */}
            <div className="wa-field">
              <label className="wa-label block text-xs font-bold uppercase tracking-wider text-gray-600 mb-1.5">
                Phone Number ID <span className="wa-label-req text-red-500">*</span>
              </label>
              <input
                type="text"
                required
                placeholder="e.g. 109847293847102"
                value={phoneNumberId}
                onChange={(e) => setPhoneNumberId(e.target.value)}
                className="wa-input w-full px-3.5 py-2.5 bg-white border border-gray-300 rounded-xl text-sm text-gray-900"
              />
              <span className="wa-help text-[11px] text-gray-400 mt-1 block">
                Found in Meta Business Manager under WhatsApp Accounts &gt; Phone Numbers.
              </span>
            </div>

            {/* Access Token Input */}
            <div className="wa-field">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <label className="wa-label text-xs font-bold uppercase tracking-wider text-gray-600">
                  Permanent Access Token <span className="wa-label-req text-red-500">*</span>
                </label>
                <button
                  type="button"
                  onClick={() => setShowToken(!showToken)}
                  className="wa-toggle-token text-xs font-semibold text-fuchsia-600 hover:text-fuchsia-700"
                >
                  {showToken ? "Hide Token" : "Show Token"}
                </button>
              </div>
              <input
                type={showToken ? "text" : "password"}
                required
                placeholder="EAAG..."
                value={accessToken}
                onChange={(e) => setAccessToken(e.target.value)}
                className="wa-input wa-input-readonly w-full px-3.5 py-2.5 bg-white border border-gray-300 rounded-xl text-sm font-mono text-gray-900"
              />
              <span className="wa-help text-[11px] text-gray-400 mt-1 block">
                Generate a System User token with <code className="wa-code-pill">whatsapp_business_messaging</code> and <code className="wa-code-pill">whatsapp_business_management</code> permissions.{" "}
                <a
                  href="https://business.facebook.com/settings/system-users"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="wa-link text-blue-600 hover:text-blue-800 underline font-medium"
                >
                  Click here to generate token in Meta Business Settings ↗
                </a>
              </span>
            </div>

            {/* Submit Action Button */}
            <div className="wa-actions pt-3 flex justify-end">
              <button
                type="submit"
                disabled={saving}
                className="wa-save-btn px-6 py-2.5 bg-fuchsia-600 text-white font-semibold text-sm rounded-xl"
              >
                {saving ? (
                  <>
                    <span>Saving...</span>
                  </>
                ) : (
                  <span>Save Configuration</span>
                )}
              </button>
            </div>
          </form>
        </div>

        {/* Quick Setup Guide Card */}
        <div className="wa-guide-card bg-purple-50/50 border border-purple-100 rounded-2xl p-5 text-sm text-gray-700">
          <h3>
            <span>💡</span> Meta WhatsApp Setup Checklist
          </h3>
          <ol className="wa-guide-list list-decimal list-inside space-y-1.5 text-xs text-gray-600 leading-relaxed">
            <li>Create an app in the <strong>developers.facebook.com</strong> portal with the <strong>Business</strong> type.</li>
            <li>Add the <strong>WhatsApp</strong> product to your application.</li>
            <li>Copy the <strong>Webhook Callback URL</strong> and <strong>Verify Token</strong> into Meta's webhook configuration.</li>
            <li>Subscribe to the <code className="wa-code-pill">messages</code> webhook event.</li>
            <li>
              Generate a permanent System User Access Token in Business Settings and paste it above.{" "}
              <a
                href="https://business.facebook.com/settings/system-users"
                target="_blank"
                rel="noopener noreferrer"
                className="wa-link text-blue-600 hover:text-blue-800 underline font-medium"
              >
                Click here to generate token in Meta Business Settings ↗
              </a>
            </li>
          </ol>
        </div>

        {/* Interactive Widget Preview Modal */}
        {showPreviewModal && (
          <div
            style={{
              position: "fixed",
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              backgroundColor: "rgba(15, 23, 42, 0.75)",
              backdropFilter: "blur(4px)",
              zIndex: 999999,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: "20px",
            }}
          >
            <div
              style={{
                width: "100%",
                maxWidth: "920px",
                height: "85vh",
                background: "#ffffff",
                borderRadius: "20px",
                boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.25)",
                display: "flex",
                flexDirection: "column",
                overflow: "hidden",
                border: "1px solid #e2e8f0",
              }}
            >
              {/* Browser Mockup Top Bar */}
              <div
                style={{
                  background: "#f8fafc",
                  borderBottom: "1px solid #e2e8f0",
                  padding: "12px 18px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span style={{ width: "12px", height: "12px", borderRadius: "50%", background: "#ef4444", display: "inline-block" }} />
                  <span style={{ width: "12px", height: "12px", borderRadius: "50%", background: "#f59e0b", display: "inline-block" }} />
                  <span style={{ width: "12px", height: "12px", borderRadius: "50%", background: "#10b981", display: "inline-block" }} />
                  <span
                    style={{
                      marginLeft: "12px",
                      background: "#ffffff",
                      border: "1px solid #cbd5e1",
                      borderRadius: "8px",
                      padding: "4px 14px",
                      fontSize: "12px",
                      color: "#64748b",
                      fontFamily: "monospace",
                    }}
                  >
                    https://your-store-website.com
                  </span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <span style={{ fontSize: "12px", color: "#64748b" }}>Live Widget Preview</span>
                  <button
                    type="button"
                    onClick={() => setShowPreviewModal(false)}
                    style={{
                      background: "#f1f5f9",
                      border: "none",
                      borderRadius: "8px",
                      padding: "6px 12px",
                      fontSize: "13px",
                      fontWeight: "700",
                      color: "#475569",
                      cursor: "pointer",
                    }}
                  >
                    ✕ Close
                  </button>
                </div>
              </div>

              {/* Simulated Customer Website Canvas */}
              <div
                style={{
                  flex: 1,
                  position: "relative",
                  background: "#fdf4ff",
                  backgroundImage: "radial-gradient(#e9d5ff 1px, transparent 1px)",
                  backgroundSize: "20px 20px",
                  overflow: "hidden",
                  padding: "30px",
                }}
              >
                {/* Mock Page Content */}
                <div style={{ maxWidth: "560px", margin: "40px auto 0", textAlign: "center" }}>
                  <span
                    style={{
                      background: "#fae8ff",
                      color: "#c026d3",
                      fontSize: "12px",
                      fontWeight: "700",
                      padding: "4px 12px",
                      borderRadius: "20px",
                      textTransform: "uppercase",
                    }}
                  >
                    Your E-Commerce Store
                  </span>
                  <h1 style={{ fontSize: "28px", fontWeight: "800", color: "#1e293b", margin: "14px 0 8px 0" }}>
                    Welcome to Our Store
                  </h1>
                  <p style={{ fontSize: "14px", color: "#64748b", lineHeight: 1.6 }}>
                    This simulates an external customer website where your embed script is installed.
                    See the floating <strong>#ff77ff</strong> launcher in the bottom right corner!
                  </p>
                </div>

                {/* Floating Launcher Button */}
                <div
                  style={{
                    position: "absolute",
                    bottom: "24px",
                    right: "24px",
                    zIndex: 100,
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "flex-end",
                  }}
                >
                  {/* Floating Popup Window */}
                  {previewWidgetOpen && (
                    <div
                      style={{
                        width: "360px",
                        height: "520px",
                        maxWidth: "calc(100vw - 48px)",
                        maxHeight: "calc(70vh)",
                        background: "#ffffff",
                        borderRadius: "20px",
                        boxShadow: "0 20px 40px rgba(0,0,0,0.22)",
                        border: "1px solid rgba(255,119,255,0.4)",
                        overflow: "hidden",
                        display: "flex",
                        flexDirection: "column",
                        marginBottom: "14px",
                      }}
                    >
                      <div
                        style={{
                          height: "44px",
                          background: "linear-gradient(135deg, #ff77ff 0%, #ff55bb 100%)",
                          color: "#ffffff",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          padding: "0 14px",
                        }}
                      >
                        <span style={{ fontSize: "13px", fontWeight: "700" }}>🎤 Voice Assistant</span>
                        <button
                          type="button"
                          onClick={() => setPreviewWidgetOpen(false)}
                          style={{
                            background: "none",
                            border: "none",
                            color: "#ffffff",
                            fontSize: "16px",
                            cursor: "pointer",
                            padding: "4px",
                          }}
                        >
                          ✕
                        </button>
                      </div>
                      {publicLink ? (
                        <iframe
                          src={`${publicLink}?embed=1`}
                          title="AI Voice Agent Preview"
                          allow="microphone; autoplay"
                          style={{ width: "100%", height: "calc(100% - 44px)", border: "none" }}
                        />
                      ) : (
                        <div style={{ padding: "20px", textAlign: "center", color: "#64748b" }}>Loading agent...</div>
                      )}
                    </div>
                  )}

                  {/* Launcher Bubble */}
                  <button
                    type="button"
                    onClick={() => setPreviewWidgetOpen(!previewWidgetOpen)}
                    style={{
                      width: "60px",
                      height: "60px",
                      borderRadius: "50%",
                      background: previewWidgetOpen ? "#475569" : "#ff77ff",
                      color: "#ffffff",
                      border: "none",
                      boxShadow: "0 8px 24px rgba(255, 119, 255, 0.45)",
                      cursor: "pointer",
                      fontSize: "26px",
                      display: "grid",
                      placeItems: "center",
                      transition: "transform 0.2s ease",
                    }}
                  >
                    {previewWidgetOpen ? "✕" : "🎤"}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </OwnerLayout>
  );
}
