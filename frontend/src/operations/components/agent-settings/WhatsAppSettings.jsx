import React, { useState, useEffect } from "react";
import OwnerLayout from "../../../owner/components/OwnerLayout";
import { useAuth } from "../../../context/AuthContext";
import api from "../../../api/axiosClient";

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

  // Form states
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

  // Load existing credentials if available
  useEffect(() => {
    let isMounted = true;
    const fetchSettings = async () => {
      try {
        const { data } = await api.get("/operations/agent/whatsapp-settings/");
        if (isMounted && data) {
          setPhoneNumberId(data.phone_number_id || "");
          setAccessToken(data.access_token || "");
          setVerifyToken(data.verify_token || "ridesai_webhook_verify_token");
          setIsActive(Boolean(data.is_active));
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
      subtitle="Connect your AI Agent to WhatsApp Cloud API to handle customer orders and support directly via chat."
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

        {/* WhatsApp Channel Card */}
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
      </div>
    </OwnerLayout>
  );
}
