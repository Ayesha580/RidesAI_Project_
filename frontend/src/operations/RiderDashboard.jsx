import React, { useState, useEffect, useCallback } from "react";
import { riderApi } from "../api/operationsApi";
import { errorText } from "../api/axiosClient";
import { useAuth } from "../context/AuthContext";

export default function RiderDashboard() {
  const { user, signOut } = useAuth();
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [updatingId, setUpdatingId] = useState(null);
  const [lastRefreshed, setLastRefreshed] = useState(new Date());

  const loadRiderOrders = useCallback(async (isPoll = false) => {
    if (!isPoll) setLoading(true);
    try {
      const res = await riderApi.getOrders();
      setOrders(res.data.orders || []);
      setError("");
      setLastRefreshed(new Date());
    } catch (err) {
      if (!isPoll) setError(errorText(err));
    } finally {
      if (!isPoll) setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadRiderOrders();
    // Poll every 8s for new assigned deliveries
    const timer = setInterval(() => {
      loadRiderOrders(true);
    }, 8000);
    return () => clearInterval(timer);
  }, [loadRiderOrders]);

  const handleUpdateStatus = async (orderId, newStatus) => {
    setUpdatingId(orderId);
    try {
      await riderApi.updateOrderStatus(orderId, newStatus);
      await loadRiderOrders(true);
    } catch (err) {
      alert("Failed to update delivery status: " + errorText(err));
    } finally {
      setUpdatingId(null);
    }
  };

  const cleanPhone = (phone) => (phone || "").replace(/[^0-9+]/g, "");

  return (
    <div className="rd-root">
      <style>{`
        .rd-root {
          min-height: 100vh;
          background: #fbf9fc;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
          padding: 16px;
          max-width: 600px;
          margin: 0 auto;
          box-sizing: border-box;
          color: #0f172a;
        }

        .rd-header {
          background: #ffffff;
          border-radius: 16px;
          padding: 16px 20px;
          border: 1px solid #e8e3ec;
          box-shadow: 0 2px 10px rgba(0,0,0,0.03);
          margin-bottom: 16px;
          display: flex;
          align-items: center;
          justify-content: space-between;
        }

        .rd-title {
          font-size: 18px;
          font-weight: 850;
          color: #0f172a;
          margin: 0;
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .rd-badge-count {
          background: #ff77ff;
          color: #ffffff;
          font-size: 12px;
          font-weight: 800;
          padding: 2px 9px;
          border-radius: 12px;
          box-shadow: 0 2px 6px rgba(255, 119, 255, 0.35);
        }

        .rd-rider-sub {
          font-size: 12px;
          color: #64748b;
          margin-top: 3px;
          display: flex;
          align-items: center;
          gap: 6px;
        }

        .rd-pulse-dot {
          width: 8px;
          height: 8px;
          background: #ff77ff;
          border-radius: 50%;
          display: inline-block;
          animation: rdDotPulse 2s infinite ease-in-out;
        }

        @keyframes rdDotPulse {
          0% { transform: scale(0.9); opacity: 0.7; }
          50% { transform: scale(1.3); opacity: 1; }
          100% { transform: scale(0.9); opacity: 0.7; }
        }

        .rd-card {
          background: #ffffff;
          border: 1px solid #e8e3ec;
          border-radius: 16px;
          padding: 18px;
          margin-bottom: 16px;
          box-shadow: 0 4px 16px rgba(0,0,0,0.03);
          animation: rdFadeIn 0.2s ease-out;
          transition: border-color 0.2s ease;
        }

        .rd-card:hover {
          border-color: #f0abfc;
        }

        @keyframes rdFadeIn {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }

        .rd-card-top {
          display: flex;
          align-items: center;
          justify-content: space-between;
          border-bottom: 1px solid #f1f5f9;
          padding-bottom: 12px;
          margin-bottom: 14px;
        }

        .rd-order-ref {
          font-size: 17px;
          font-weight: 850;
          color: #0f172a;
          font-family: monospace;
        }

        .rd-status-badge {
          font-size: 11.5px;
          font-weight: 750;
          padding: 4px 10px;
          border-radius: 20px;
          text-transform: uppercase;
          letter-spacing: 0.3px;
        }

        .rd-status-assigned {
          background: #fef3c7;
          color: #92400e;
          border: 1px solid #fde68a;
        }

        .rd-status-out {
          background: #fdf4ff;
          color: #c026d3;
          border: 1px solid #f0abfc;
          animation: rdPulse 2s infinite;
        }

        @keyframes rdPulse {
          0% { opacity: 0.85; }
          50% { opacity: 1; transform: scale(1.02); }
          100% { opacity: 0.85; }
        }

        .rd-info-row {
          display: flex;
          align-items: flex-start;
          gap: 10px;
          margin-bottom: 12px;
          font-size: 14px;
          color: #334155;
        }

        .rd-info-icon {
          font-size: 16px;
          min-width: 20px;
          margin-top: 1px;
        }

        .rd-phone-links {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          margin-top: 6px;
        }

        .rd-phone-btn {
          display: inline-flex;
          align-items: center;
          gap: 5px;
          padding: 5px 11px;
          border-radius: 8px;
          font-size: 12px;
          font-weight: 750;
          text-decoration: none;
          color: #ffffff;
          box-shadow: 0 1px 3px rgba(0,0,0,0.1);
          transition: transform 0.1s ease, filter 0.1s ease;
        }

        .rd-phone-btn:hover {
          filter: brightness(1.08);
        }

        .rd-phone-btn:active {
          transform: scale(0.97);
        }

        .btn-call { background: #0284c7; }
        .btn-wa { background: #16a34a; }
        .btn-map { background: #7c3aed; }

        .rd-items-box {
          background: #f8fafc;
          border: 1px solid #e2e8f0;
          border-radius: 12px;
          padding: 12px 14px;
          margin: 14px 0;
          font-size: 13px;
        }

        .rd-total-bar {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 12px 16px;
          background: #f0fdf4;
          border: 1px solid #bbf7d0;
          border-radius: 12px;
          margin: 14px 0;
        }

        .rd-total-amount {
          font-size: 18px;
          font-weight: 850;
          color: #166534;
        }

        .rd-btn-action {
          width: 100%;
          padding: 14px 16px;
          border-radius: 12px;
          border: none;
          font-size: 15px;
          font-weight: 800;
          color: #ffffff;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          transition: transform 0.1s ease, background 0.15s ease;
        }

        .rd-btn-action:active {
          transform: scale(0.98);
        }

        .btn-pickup {
          background: #ff77ff;
          box-shadow: 0 4px 14px rgba(255, 119, 255, 0.35);
        }

        .btn-pickup:hover {
          background: #e066e0;
        }

        .btn-deliver {
          background: #16a34a;
          box-shadow: 0 4px 14px rgba(22, 163, 74, 0.3);
        }

        .btn-deliver:hover {
          background: #15803d;
        }

        .rd-empty {
          text-align: center;
          padding: 60px 20px;
          color: #64748b;
          background: #ffffff;
          border: 1px solid #e8e3ec;
          border-radius: 16px;
        }
      `}</style>

      {/* Header */}
      <header className="rd-header">
        <div>
          <h2 className="rd-title">
            <span>🛵</span> Active Deliveries
            <span className="rd-badge-count">{orders.length}</span>
          </h2>
          <div className="rd-rider-sub">
            <span className="rd-pulse-dot"></span>
            <span>Rider: <strong>{user?.username || "You"}</strong></span>
            <span>• Synced {lastRefreshed.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
          </div>
        </div>

        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <button
            onClick={() => loadRiderOrders(false)}
            title="Refresh Deliveries"
            style={{
              padding: "7px 12px",
              background: "#fdf4ff",
              border: "1px solid #f0abfc",
              borderRadius: 8,
              fontSize: 12,
              fontWeight: 750,
              color: "#c026d3",
              cursor: "pointer",
            }}
          >
            ↻
          </button>
          {signOut && (
            <button
              onClick={signOut}
              style={{
                padding: "7px 12px",
                background: "#ffffff",
                border: "1px solid #e2e8f0",
                borderRadius: 8,
                fontSize: 12,
                color: "#64748b",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              Sign Out
            </button>
          )}
        </div>
      </header>

      {error && (
        <div style={{ background: "#fee2e2", color: "#991b1b", padding: "10px 14px", borderRadius: 10, marginBottom: 14, fontSize: 13, fontWeight: 600 }}>
          {error}
        </div>
      )}

      {/* Deliveries List */}
      {loading && orders.length === 0 ? (
        <div className="rd-empty">
          <div style={{ fontSize: 36, marginBottom: 8 }}>⏳</div>
          <h3 style={{ margin: 0, color: "#1e293b", fontWeight: 750 }}>Loading assigned deliveries...</h3>
        </div>
      ) : orders.length === 0 ? (
        <div className="rd-empty">
          <div style={{ fontSize: 44, marginBottom: 12 }}>🏁</div>
          <h3 style={{ margin: "0 0 6px 0", color: "#0f172a", fontWeight: 800 }}>No Pending Deliveries</h3>
          <p style={{ margin: 0, fontSize: 13, color: "#64748b" }}>
            Orders prepared by the kitchen will automatically appear here.
          </p>
        </div>
      ) : (
        <div>
          {orders.map((o) => {
            const isOut = ["out_for_delivery", "on_the_way", "picked_up"].includes(o.status);
            const phoneDigits = cleanPhone(o.customer_phone);

            return (
              <div key={o.id} className="rd-card">
                {/* Top: Order # & Status */}
                <div className="rd-card-top">
                  <div>
                    <span className="rd-order-ref">#{o.order_number}</span>
                    <div style={{ fontSize: 11, color: "#64748b", marginTop: 2 }}>{o.formatted_date}</div>
                  </div>
                  <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                    {(o.is_exchange || (o.notes && o.notes.includes("EXCHANGE SWAP"))) && (
                      <span style={{
                        background: "rgba(255, 119, 255, 0.16)",
                        color: "#c026d3",
                        border: "1px solid rgba(255, 119, 255, 0.4)",
                        borderRadius: "20px",
                        padding: "3px 8px",
                        fontSize: "11px",
                        fontWeight: "800"
                      }}>
                        🔄 SWAP
                      </span>
                    )}
                    <span className={`rd-status-badge ${isOut ? "rd-status-out" : "rd-status-assigned"}`}>
                      {isOut ? "🛵 On The Way" : "📦 Ready for Pickup"}
                    </span>
                  </div>
                </div>

                {(o.is_exchange || (o.notes && o.notes.includes("EXCHANGE SWAP"))) && (
                  <div style={{
                    margin: "10px 0 6px 0",
                    padding: "9px 12px",
                    background: "#fdf4ff",
                    border: "1px solid #f0abfc",
                    borderRadius: "10px",
                    color: "#86198f",
                    fontSize: "12.5px",
                    fontWeight: "600",
                    display: "flex",
                    alignItems: "center",
                    gap: "8px"
                  }}>
                    <span style={{ fontSize: "16px" }}>🔄</span>
                    <div>
                      <strong>DOORSTEP SWAP:</strong> Collect customer&apos;s original item before marking delivered!
                    </div>
                  </div>
                )}

                {/* Customer Details */}
                <div className="rd-info-row">
                  <span className="rd-info-icon">👤</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 750, fontSize: 15, color: "#0f172a" }}>{o.customer_name}</div>
                    {o.customer_phone && (
                      <div className="rd-phone-links">
                        <a href={`tel:${phoneDigits}`} className="rd-phone-btn btn-call">
                          📞 Call ({o.customer_phone})
                        </a>
                        <a
                          href={`https://wa.me/${phoneDigits.replace("+", "")}`}
                          target="_blank"
                          rel="noreferrer"
                          className="rd-phone-btn btn-wa"
                        >
                          💬 WhatsApp
                        </a>
                      </div>
                    )}
                  </div>
                </div>

                {/* Address */}
                <div className="rd-info-row">
                  <span className="rd-info-icon">📍</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 650, color: "#1e293b" }}>{o.delivery_address || "No address provided"}</div>
                    {o.delivery_address && o.delivery_address !== "Store Pickup" && (
                      <a
                        href={`https://maps.google.com/?q=${encodeURIComponent(o.delivery_address)}`}
                        target="_blank"
                        rel="noreferrer"
                        className="rd-phone-btn btn-map"
                        style={{ marginTop: 8 }}
                      >
                        🗺️ Open Navigation
                      </a>
                    )}
                  </div>
                </div>

                {/* Items Summary */}
                <div className="rd-items-box">
                  <strong style={{ display: "block", marginBottom: 6, color: "#475569" }}>
                    Items to Deliver ({o.items?.length || 0}):
                  </strong>
                  {(o.items || []).map((it, idx) => (
                    <div key={idx} style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                      <span style={{ color: "#1e293b" }}><strong>{it.quantity}x</strong> {it.name}</span>
                      <span style={{ fontWeight: 600, color: "#475569" }}>Rs. {Number(it.line_total || 0).toFixed(2)}</span>
                    </div>
                  ))}
                  {o.notes && (
                    <div style={{ marginTop: 8, padding: "6px 10px", background: "#fef3c7", borderRadius: 6, color: "#92400e", fontWeight: 700, fontSize: 12 }}>
                      ⚠️ Note: {o.notes}
                    </div>
                  )}
                </div>

                {/* Cash / Total */}
                <div className="rd-total-bar">
                  <span style={{ fontSize: 13, fontWeight: 750, color: "#14532d" }}>
                    💵 Cash to Collect / Total:
                  </span>
                  <span className="rd-total-amount">Rs. {Number(o.total || 0).toFixed(2)}</span>
                </div>

                {/* Action Button */}
                <div>
                  {!isOut ? (
                    <button
                      className="rd-btn-action btn-pickup"
                      disabled={updatingId === o.id}
                      onClick={() => handleUpdateStatus(o.id, "out_for_delivery")}
                    >
                      {updatingId === o.id ? "Updating..." : "🛵 Pick Up Order"}
                    </button>
                  ) : (
                    <button
                      className="rd-btn-action btn-deliver"
                      disabled={updatingId === o.id}
                      onClick={() => handleUpdateStatus(o.id, "delivered")}
                    >
                      {updatingId === o.id ? "Completing..." : "🎉 Complete Delivery"}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
