import React, { useState, useEffect, useRef } from "react";
import { operationsApi } from "../../../api/operationsApi";
import { errorText } from "../../../api/axiosClient";
import { useAuth } from "../../../context/AuthContext";

function getVerticalLiveCopy(businessType, businessLabel) {
  const b = `${businessType || ""} ${businessLabel || ""}`.toLowerCase();
  if (b.includes("hospital")) {
    return {
      title: "Your WhatsApp AI Agent is live!",
      desc: "Patient messages sent to this WhatsApp account will be handled automatically by your Hospital AI Assistant (doctors, OPD appointments, consultation fees, and lab inquiries).",
    };
  }
  if (b.includes("clinic")) {
    return {
      title: "Your WhatsApp AI Agent is live!",
      desc: "Patient messages sent to this WhatsApp account will be handled automatically by your Clinic AI Receptionist for doctor schedules and appointment bookings.",
    };
  }
  if (b.includes("pharmacy")) {
    return {
      title: "Your WhatsApp AI Agent is live!",
      desc: "Customer medicine inquiries and prescription requests sent to this WhatsApp account will be handled automatically by your Pharmacy AI Assistant.",
    };
  }
  if (["restaurant", "cafe", "café", "food", "bakery", "fast food", "hotel"].some((k) => b.includes(k))) {
    return {
      title: "Your WhatsApp AI Agent is live and taking orders!",
      desc: "Customer messages sent to this WhatsApp account will be automatically parsed, confirmed, and entered into your kitchen dashboard.",
    };
  }
  return {
    title: "Your WhatsApp AI Agent is live!",
    desc: "Customer messages sent to this WhatsApp account will be handled automatically by your Business AI Assistant and synced to your dashboard.",
  };
}

export default function WhatsAppConnectCard() {
  const { user } = useAuth();
  const liveCopy = getVerticalLiveCopy(user?.business_type, user?.business_label);
  const [status, setStatus] = useState("disconnected");
  const [instanceName, setInstanceName] = useState("");
  const [qrcodeBase64, setQrcodeBase64] = useState(null);
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [reconnecting, setReconnecting] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [error, setError] = useState("");
  const [infoMsg, setInfoMsg] = useState("");
  const [justConnected, setJustConnected] = useState(false);

  const pollTimerRef = useRef(null);

  // 1. Initial Status Check on Mount
  useEffect(() => {
    let mounted = true;

    async function checkStatus() {
      try {
        setLoadingStatus(true);
        setError("");
        const res = await operationsApi.whatsappConnectStatus();
        if (mounted && res.data) {
          const currentStatus = res.data.status || "disconnected";
          setStatus(currentStatus);
          setInstanceName(res.data.instance_name || "");
        }
      } catch (err) {
        if (mounted) {
          console.warn("[WhatsAppConnectCard] Status check failed:", err);
        }
      } finally {
        if (mounted) setLoadingStatus(false);
      }
    }

    checkStatus();

    return () => {
      mounted = false;
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    };
  }, []);

  // 2. Polling Effect when QR is displayed and awaiting connection
  useEffect(() => {
    if (qrcodeBase64 && status !== "connected") {
      pollTimerRef.current = setInterval(async () => {
        try {
          const res = await operationsApi.whatsappConnectStatus();
          if (res.data && res.data.status === "connected") {
            setStatus("connected");
            setQrcodeBase64(null);
            setJustConnected(true);
            if (pollTimerRef.current) clearInterval(pollTimerRef.current);
          }
        } catch (pollErr) {
          console.warn("[WhatsAppConnectCard] Polling error:", pollErr);
        }
      }, 4000);
    } else {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    }

    return () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    };
  }, [qrcodeBase64, status]);

  // 3. Connect / Generate QR Code Handler
  const handleConnectWhatsApp = async () => {
    setGenerating(true);
    setError("");
    setInfoMsg("");
    setJustConnected(false);
    try {
      const res = await operationsApi.whatsappConnectGenerate();
      if (res.data) {
        setInstanceName(res.data.instance_name || "");
        if (res.data.qrcode_base64) {
          setQrcodeBase64(res.data.qrcode_base64);
          setStatus("disconnected");
        } else if (res.data.status === "connected") {
          setStatus("connected");
          setQrcodeBase64(null);
          setJustConnected(true);
        } else {
          setError("Could not generate QR code. WhatsApp engine is preparing the instance. Please retry in a few seconds.");
        }
      }
    } catch (err) {
      console.error("[WhatsAppConnectCard] Failed to connect WhatsApp:", err);
      const serverErr = errorText(err);
      if (serverErr && serverErr.toLowerCase().includes("network")) {
        setError("WhatsApp engine is currently offline. Please try again shortly.");
      } else {
        setError(serverErr || "Failed to initiate WhatsApp connection. Please try again.");
      }
    } finally {
      setGenerating(false);
    }
  };

  // 4. Force Reconnect / Regenerate QR (works even if DB currently thinks status is connected)
  const handleReconnectWhatsApp = async () => {
    setReconnecting(true);
    setError("");
    setInfoMsg("");
    setJustConnected(false);
    try {
      const res = await operationsApi.whatsappReconnect();
      if (res.data) {
        setInstanceName(res.data.instance_name || "");
        setStatus("disconnected");
        if (res.data.qrcode_base64) {
          setQrcodeBase64(res.data.qrcode_base64);
          setInfoMsg("Previous session cleared. Scan the fresh QR code below to reconnect.");
        } else {
          setQrcodeBase64(null);
          setError("Session reset, but QR code was not returned yet. Click 'Connect WhatsApp' to fetch the fresh QR.");
        }
      }
    } catch (err) {
      console.error("[WhatsAppConnectCard] Failed to force reconnect:", err);
      setError(errorText(err) || "Failed to force reconnect WhatsApp session. Please try again.");
    } finally {
      setReconnecting(false);
    }
  };

  // 5. Disconnect / Logout current session
  const handleDisconnectWhatsApp = async () => {
    setDisconnecting(true);
    setError("");
    setInfoMsg("");
    setJustConnected(false);
    try {
      await operationsApi.whatsappDisconnect();
      setStatus("disconnected");
      setQrcodeBase64(null);
      setInfoMsg("WhatsApp session disconnected cleanly. Click 'Connect WhatsApp' whenever you are ready to link again.");
    } catch (err) {
      console.error("[WhatsAppConnectCard] Failed to disconnect:", err);
      setError(errorText(err) || "Failed to disconnect WhatsApp session.");
    } finally {
      setDisconnecting(false);
    }
  };

  // 6. Live status sync check
  const handleSyncStatus = async () => {
    setLoadingStatus(true);
    setError("");
    setInfoMsg("");
    try {
      const res = await operationsApi.whatsappConnectStatus();
      if (res.data) {
        const liveStatus = res.data.status || "disconnected";
        setStatus(liveStatus);
        setInstanceName(res.data.instance_name || "");
        if (liveStatus === "disconnected") {
          setJustConnected(false);
          setInfoMsg("Live check confirmed WhatsApp is currently disconnected.");
        } else {
          setInfoMsg("Live check confirmed WhatsApp session is actively connected.");
        }
      }
    } catch (err) {
      setError(errorText(err) || "Could not verify live WhatsApp connection state.");
    } finally {
      setLoadingStatus(false);
    }
  };

  // Helper for QR base64 image prefix
  const getQrImageSrc = (b64) => {
    if (!b64) return "";
    return b64.startsWith("data:") ? b64 : `data:image/png;base64,${b64}`;
  };

  const isConnected = status === "connected";

  return (
    <div className="wa-connect-card">
      <style>{`
        .wa-connect-card {
          background: #ffffff;
          border: 1px solid #e8e3ec;
          border-radius: 16px;
          padding: 24px;
          box-shadow: 0 2px 10px rgba(0, 0, 0, 0.03);
          margin-bottom: 20px;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
          color: #1e293b;
        }

        .wa-card-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          flex-wrap: wrap;
          gap: 12px;
          margin-bottom: 16px;
        }

        .wa-card-title-group {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .wa-card-icon {
          width: 44px;
          height: 44px;
          border-radius: 12px;
          background: #fdf4ff;
          border: 1px solid #f0abfc;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 22px;
          color: #c026d3;
          flex-shrink: 0;
        }

        .wa-card-title {
          margin: 0;
          font-size: 17px;
          font-weight: 800;
          color: #0f172a;
        }

        .wa-card-subtitle {
          margin: 2px 0 0 0;
          font-size: 13px;
          color: #64748b;
        }

        /* Status Badges */
        .wa-badge {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 5px 12px;
          border-radius: 20px;
          font-size: 12px;
          font-weight: 750;
          text-transform: capitalize;
        }

        .wa-badge-connected {
          background: #ecfdf5;
          color: #065f46;
          border: 1px solid #a7f3d0;
        }

        .wa-badge-disconnected {
          background: #fffbeb;
          color: #92400e;
          border: 1px solid #fde68a;
        }

        .wa-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
        }

        .wa-dot-connected {
          background: #10b981;
          box-shadow: 0 0 0 2px #d1fae5;
        }

        .wa-dot-disconnected {
          background: #f59e0b;
        }

        /* Success & Alert banners */
        .wa-banner-success {
          background: #f0fdf4;
          border: 1px solid #bbf7d0;
          border-radius: 12px;
          padding: 14px 18px;
          margin-bottom: 18px;
          display: flex;
          align-items: center;
          gap: 12px;
          color: #166534;
          font-size: 13.5px;
          animation: waFadeIn 0.25s ease-out;
        }

        .wa-banner-error {
          background: #fef2f2;
          border: 1px solid #fecaca;
          border-radius: 12px;
          padding: 14px 18px;
          margin-bottom: 18px;
          color: #991b1b;
          font-size: 13px;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          animation: waFadeIn 0.25s ease-out;
        }

        @keyframes waFadeIn {
          from { opacity: 0; transform: translateY(-4px); }
          to { opacity: 1; transform: translateY(0); }
        }

        /* Buttons */
        .wa-btn-primary {
          background: #ff77ff;
          color: #ffffff;
          border: none;
          padding: 10px 20px;
          border-radius: 10px;
          font-size: 14px;
          font-weight: 750;
          cursor: pointer;
          display: inline-flex;
          align-items: center;
          gap: 8px;
          box-shadow: 0 4px 14px rgba(255, 119, 255, 0.35);
          transition: background 0.15s ease, transform 0.1s ease;
        }

        .wa-btn-primary:hover:not(:disabled) {
          background: #e066e0;
        }

        .wa-btn-primary:active:not(:disabled) {
          transform: scale(0.98);
        }

        .wa-btn-primary:disabled {
          opacity: 0.65;
          cursor: not-allowed;
          box-shadow: none;
        }

        .wa-btn-secondary {
          background: #ffffff;
          color: #475569;
          border: 1px solid #cbd5e1;
          padding: 7px 14px;
          border-radius: 8px;
          font-size: 12.5px;
          font-weight: 650;
          cursor: pointer;
          transition: background 0.1s ease;
        }

        .wa-btn-secondary:hover {
          background: #f8fafc;
          border-color: #94a3b8;
        }

        /* QR Scan Layout */
        .wa-qr-container {
          background: #fafafc;
          border: 1px solid #e8e3ec;
          border-radius: 14px;
          padding: 20px;
          margin-top: 18px;
          display: grid;
          grid-template-columns: auto 1fr;
          gap: 24px;
          align-items: center;
          animation: waFadeIn 0.3s ease-out;
        }

        @media (max-width: 640px) {
          .wa-qr-container {
            grid-template-columns: 1fr;
            text-align: center;
          }
        }

        .wa-qr-box {
          background: #ffffff;
          border: 1px solid #cbd5e1;
          border-radius: 12px;
          padding: 12px;
          display: inline-flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
        }

        .wa-qr-img {
          width: 190px;
          height: 190px;
          object-fit: contain;
          border-radius: 6px;
        }

        .wa-instructions {
          display: flex;
          flex-direction: column;
          gap: 10px;
        }

        .wa-instructions h4 {
          margin: 0;
          font-size: 15px;
          font-weight: 800;
          color: #0f172a;
        }

        .wa-steps {
          margin: 0;
          padding-left: 20px;
          font-size: 13.5px;
          color: #334155;
          display: flex;
          flex-direction: column;
          gap: 6px;
          line-height: 1.45;
        }

        .wa-steps li strong {
          color: #0f172a;
        }

        .wa-poll-hint {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 12px;
          color: #c026d3;
          margin-top: 6px;
          font-weight: 650;
        }

        .wa-spinner {
          width: 14px;
          height: 14px;
          border: 2px solid #f0abfc;
          border-top-color: #c026d3;
          border-radius: 50%;
          animation: waSpin 0.8s linear infinite;
          display: inline-block;
        }

        @keyframes waSpin {
          to { transform: rotate(360deg); }
        }
      `}</style>

      {/* Top Header */}
      <div className="wa-card-header">
        <div className="wa-card-title-group">
          <div className="wa-card-icon">💬</div>
          <div>
            <h3 className="wa-card-title">WhatsApp AI Connection</h3>
            <p className="wa-card-subtitle">
              Link your business WhatsApp number using WhatsApp Web QR scan.
            </p>
          </div>
        </div>

        {/* Live Status Badge */}
        {!loadingStatus && (
          <div className={`wa-badge ${isConnected ? "wa-badge-connected" : "wa-badge-disconnected"}`}>
            <span className={`wa-dot ${isConnected ? "wa-dot-connected" : "wa-dot-disconnected"}`} />
            <span>{isConnected ? "Connected" : "Disconnected"}</span>
          </div>
        )}
      </div>

      {/* Success Notification Banner */}
      {(isConnected || justConnected) && (
        <div className="wa-banner-success">
          <span style={{ fontSize: 20 }}>✅</span>
          <div>
            <strong>{liveCopy.title}</strong>
            <div style={{ fontSize: 12.5, color: "#15803d", marginTop: 2 }}>
              {liveCopy.desc}
            </div>
          </div>
        </div>
      )}

      {/* Error Alert Banner */}
      {error && (
        <div className="wa-banner-error" role="alert">
          <div>
            <strong>Connection Error:</strong> {error}
          </div>
          <button
            type="button"
            className="wa-btn-secondary"
            onClick={handleConnectWhatsApp}
          >
            Retry
          </button>
        </div>
      )}

      {/* Info Notification Banner */}
      {infoMsg && (
        <div
          style={{
            background: "#fdf4ff",
            border: "1px solid #f0abfc",
            borderRadius: 12,
            padding: "11px 16px",
            marginBottom: 16,
            color: "#86198f",
            fontSize: 13,
            fontWeight: 600,
          }}
        >
          {infoMsg}
        </div>
      )}

      {/* Content Area */}
      {loadingStatus ? (
        <div style={{ padding: "16px 0", color: "#64748b", fontSize: 13.5 }}>
          Checking live WhatsApp engine connection state...
        </div>
      ) : isConnected ? (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12, paddingTop: 6 }}>
          <div style={{ fontSize: 13, color: "#475569" }}>
            Connected Instance: <strong style={{ color: "#0f172a", fontFamily: "monospace" }}>{instanceName || "Active"}</strong>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <button
              type="button"
              className="wa-btn-secondary"
              onClick={handleSyncStatus}
              disabled={reconnecting || disconnecting}
            >
              ↻ Verify Live Status
            </button>
            <button
              type="button"
              className="wa-btn-secondary"
              onClick={handleReconnectWhatsApp}
              disabled={reconnecting || disconnecting}
              style={{ borderColor: "#f0abfc", color: "#a21caf", background: "#fdf4ff" }}
            >
              {reconnecting ? "Resetting & Generating QR..." : "🔄 Reconnect / Regenerate QR"}
            </button>
            <button
              type="button"
              className="wa-btn-secondary"
              onClick={handleDisconnectWhatsApp}
              disabled={reconnecting || disconnecting}
              style={{ borderColor: "#fecaca", color: "#b91c1c", background: "#fef2f2" }}
            >
              {disconnecting ? "Disconnecting..." : "🔌 Disconnect"}
            </button>
          </div>
        </div>
      ) : (
        <div>
          {!qrcodeBase64 && (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 14, paddingTop: 4 }}>
              <p style={{ margin: 0, fontSize: 13.5, color: "#475569" }}>
                Connect your business phone in seconds. No Meta Business Verification required.
              </p>
              <button
                type="button"
                className="wa-btn-primary"
                onClick={handleConnectWhatsApp}
                disabled={generating}
              >
                {generating ? (
                  <>
                    <span className="wa-spinner" /> Generating QR Code...
                  </>
                ) : (
                  <>
                    <span>📱</span> Connect WhatsApp
                  </>
                )}
              </button>
            </div>
          )}

          {/* QR Code + 3-step Instructions */}
          {qrcodeBase64 && (
            <div className="wa-qr-container">
              <div className="wa-qr-box">
                <img
                  src={getQrImageSrc(qrcodeBase64)}
                  alt="WhatsApp Linked Devices QR Code"
                  className="wa-qr-img"
                />
                <span style={{ fontSize: 11, color: "#64748b", marginTop: 6, fontWeight: 600 }}>
                  Scan with WhatsApp
                </span>
              </div>

              <div className="wa-instructions">
                <h4>Link WhatsApp via Phone:</h4>
                <ol className="wa-steps">
                  <li>Open <strong>WhatsApp</strong> on your phone.</li>
                  <li>Tap <strong>Settings</strong> or <strong>Menu (⋮)</strong> → <strong>Linked Devices</strong> → <strong>Link a Device</strong>.</li>
                  <li>Point your phone camera at this QR code to scan and authorize.</li>
                </ol>

                <div className="wa-poll-hint">
                  <span className="wa-spinner" />
                  <span>Waiting for scan... Status updates automatically once linked.</span>
                </div>

                <div style={{ marginTop: 8 }}>
                  <button
                    type="button"
                    className="wa-btn-secondary"
                    onClick={handleConnectWhatsApp}
                    disabled={generating}
                    style={{ fontSize: 12 }}
                  >
                    {generating ? "Regenerating..." : "↻ Refresh QR Code"}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
