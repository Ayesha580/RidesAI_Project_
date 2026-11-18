import React, { useState, useEffect, useCallback } from "react";
import { kitchenApi } from "../api/operationsApi";
import { errorText } from "../api/axiosClient";
import { useAuth } from "../context/AuthContext";

export default function KitchenDashboard() {
  const { user, signOut } = useAuth();
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [updatingId, setUpdatingId] = useState(null);
  const [filter, setFilter] = useState("all"); // 'all' | 'pending' | 'preparing'
  const [lastRefreshed, setLastRefreshed] = useState(new Date());

  const loadKitchenOrders = useCallback(async (isPoll = false) => {
    if (!isPoll) setLoading(true);
    try {
      const res = await kitchenApi.getOrders();
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
    loadKitchenOrders();
    // Poll every 6 seconds for fresh kitchen tickets
    const timer = setInterval(() => {
      loadKitchenOrders(true);
    }, 6000);
    return () => clearInterval(timer);
  }, [loadKitchenOrders]);

  const handleStatusChange = async (orderId, newStatus) => {
    setUpdatingId(orderId);
    try {
      await kitchenApi.updateOrderStatus(orderId, newStatus);
      await loadKitchenOrders(true);
    } catch (err) {
      alert("Failed to update kitchen ticket: " + errorText(err));
    } finally {
      setUpdatingId(null);
    }
  };

  const filteredOrders = orders.filter((o) => {
    if (filter === "pending") return ["new", "pending", "confirmed"].includes(o.status);
    if (filter === "preparing") return o.status === "preparing";
    return true;
  });

  return (
    <div className="kds-root">
      <style>{`
        .kds-root {
          min-height: 100vh;
          background: #fbf9fc;
          color: #1e293b;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
          padding: 24px;
          box-sizing: border-box;
        }

        /* Top Header */
        .kds-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          background: #ffffff;
          padding: 18px 24px;
          border-radius: 16px;
          border: 1px solid #e8e3ec;
          box-shadow: 0 2px 12px rgba(0, 0, 0, 0.03);
          margin-bottom: 24px;
          flex-wrap: wrap;
          gap: 16px;
        }

        .kds-title-area {
          display: flex;
          align-items: center;
          gap: 14px;
        }

        .kds-badge-live {
          display: flex;
          align-items: center;
          gap: 6px;
          background: #fdf4ff;
          color: #c026d3;
          font-size: 11.5px;
          font-weight: 750;
          padding: 5px 12px;
          border-radius: 20px;
          border: 1px solid #f0abfc;
          text-transform: uppercase;
          letter-spacing: 0.3px;
        }

        .kds-live-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: #ff77ff;
          box-shadow: 0 0 8px #ff77ff;
          animation: kdsPulse 1.5s infinite;
        }

        @keyframes kdsPulse {
          0% { transform: scale(0.95); opacity: 0.8; }
          50% { transform: scale(1.3); opacity: 1; }
          100% { transform: scale(0.95); opacity: 0.8; }
        }

        .kds-controls {
          display: flex;
          align-items: center;
          gap: 10px;
          flex-wrap: wrap;
        }

        .kds-filter-btn {
          padding: 8px 16px;
          border-radius: 10px;
          border: 1px solid #e2e8f0;
          background: #f8fafc;
          color: #475569;
          font-size: 13px;
          font-weight: 650;
          cursor: pointer;
          transition: all 0.15s ease;
        }

        .kds-filter-btn:hover {
          background: #f1f5f9;
        }

        .kds-filter-btn.active {
          background: #ff77ff;
          border-color: #f0abfc;
          color: #ffffff;
          box-shadow: 0 2px 8px rgba(255, 119, 255, 0.35);
        }

        .kds-refresh-btn {
          padding: 8px 16px;
          border-radius: 10px;
          border: 1px solid #e2e8f0;
          background: #ffffff;
          color: #334155;
          font-size: 13px;
          font-weight: 650;
          cursor: pointer;
          transition: all 0.15s ease;
        }

        .kds-refresh-btn:hover {
          background: #f8fafc;
          border-color: #cbd5e1;
        }

        /* Grid */
        .kds-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
          gap: 20px;
        }

        /* Cards */
        .kds-card {
          background: #ffffff;
          border: 1px solid #e8e3ec;
          border-radius: 16px;
          display: flex;
          flex-direction: column;
          overflow: hidden;
          box-shadow: 0 4px 18px rgba(0, 0, 0, 0.04);
          transition: transform 0.15s ease, border-color 0.15s ease;
        }

        .kds-card.status-preparing {
          border: 2px solid #ff77ff;
          box-shadow: 0 4px 20px rgba(255, 119, 255, 0.18);
        }

        .kds-card.urgent {
          border: 2px solid #ef4444;
          box-shadow: 0 4px 20px rgba(239, 68, 68, 0.18);
        }

        .kds-card-header {
          padding: 14px 18px;
          background: #fdfafd;
          display: flex;
          align-items: center;
          justify-content: space-between;
          border-bottom: 1px solid #f1ebf5;
        }

        .kds-order-num {
          font-size: 19px;
          font-weight: 850;
          font-family: monospace;
          color: #c026d3;
        }

        .kds-timer-badge {
          font-size: 12px;
          font-weight: 750;
          padding: 4px 10px;
          border-radius: 8px;
        }

        .timer-normal { background: #ecfdf5; color: #065f46; border: 1px solid #a7f3d0; }
        .timer-warning { background: #fffbeb; color: #92400e; border: 1px solid #fde68a; }
        .timer-urgent { background: #fef2f2; color: #991b1b; border: 1px solid #fecaca; animation: kdsPulse 2s infinite; }

        .kds-card-meta {
          padding: 10px 18px;
          font-size: 12.5px;
          color: #64748b;
          border-bottom: 1px dashed #f0ebf3;
          display: flex;
          justify-content: space-between;
          background: #ffffff;
        }

        /* Items Body */
        .kds-card-body {
          padding: 16px 18px;
          flex: 1;
          background: #ffffff;
        }

        .kds-item-row {
          display: flex;
          align-items: baseline;
          gap: 10px;
          margin-bottom: 10px;
          font-size: 15px;
          line-height: 1.4;
        }

        .kds-item-qty {
          font-size: 17px;
          font-weight: 850;
          color: #a21caf;
          background: #fdf4ff;
          padding: 2px 8px;
          border-radius: 6px;
          border: 1px solid #fae8ff;
          min-width: 32px;
          text-align: center;
        }

        .kds-item-name {
          font-weight: 700;
          color: #1e293b;
        }

        /* High Visibility Special Instructions Box */
        .kds-notes-alert {
          background: #fef2f2;
          border: 1.5px dashed #f87171;
          border-radius: 10px;
          padding: 12px 14px;
          margin-top: 14px;
          color: #991b1b;
        }

        .kds-notes-title {
          font-size: 11.5px;
          font-weight: 800;
          text-transform: uppercase;
          color: #dc2626;
          margin-bottom: 4px;
          display: flex;
          align-items: center;
          gap: 6px;
        }

        .kds-notes-content {
          font-size: 13.5px;
          font-weight: 750;
          line-height: 1.35;
          color: #7f1d1d;
        }

        /* Card Footer */
        .kds-card-footer {
          padding: 14px 18px;
          background: #faf8fc;
          border-top: 1px solid #f0ebf5;
        }

        .kds-btn-action {
          width: 100%;
          padding: 13px;
          font-size: 15px;
          font-weight: 800;
          border-radius: 10px;
          border: none;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          transition: all 0.15s ease;
        }

        .kds-btn-action:active {
          transform: scale(0.98);
        }

        .btn-start {
          background: #f59e0b;
          color: #ffffff;
          box-shadow: 0 3px 10px rgba(245, 158, 11, 0.25);
        }

        .btn-start:hover {
          background: #d97706;
        }

        .btn-prepared {
          background: #ff77ff;
          color: #ffffff;
          box-shadow: 0 4px 14px rgba(255, 119, 255, 0.35);
        }

        .btn-prepared:hover {
          background: #e066e0;
        }

        .kds-empty {
          text-align: center;
          padding: 80px 20px;
          color: #64748b;
        }
      `}</style>

      {/* Header */}
      <header className="kds-header">
        <div className="kds-title-area">
          <span style={{ fontSize: 32 }}>🍳</span>
          <div>
            <h1 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: "#0f172a" }}>
              Kitchen Display System (KDS)
            </h1>
            <div style={{ fontSize: 13, color: "#64748b", marginTop: 3 }}>
              {user?.company_name || "Store"} • Active Orders: <strong>{orders.length}</strong>
            </div>
          </div>
          <div className="kds-badge-live">
            <span className="kds-live-dot" />
            Live Sync
          </div>
        </div>

        <div className="kds-controls">
          <button
            className={`kds-filter-btn ${filter === "all" ? "active" : ""}`}
            onClick={() => setFilter("all")}
          >
            All Tickets ({orders.length})
          </button>
          <button
            className={`kds-filter-btn ${filter === "pending" ? "active" : ""}`}
            onClick={() => setFilter("pending")}
          >
            New / Queued ({orders.filter((o) => ["new", "pending", "confirmed"].includes(o.status)).length})
          </button>
          <button
            className={`kds-filter-btn ${filter === "preparing" ? "active" : ""}`}
            onClick={() => setFilter("preparing")}
          >
            In Prep ({orders.filter((o) => o.status === "preparing").length})
          </button>

          <button className="kds-refresh-btn" onClick={() => loadKitchenOrders(false)}>
            ↻ Refresh ({lastRefreshed.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })})
          </button>

          {signOut && (
            <button
              onClick={signOut}
              style={{
                background: "transparent",
                border: "1px solid #cbd5e1",
                color: "#64748b",
                padding: "8px 14px",
                borderRadius: 10,
                cursor: "pointer",
                fontWeight: 600,
                fontSize: 13,
              }}
            >
              Sign Out
            </button>
          )}
        </div>
      </header>

      {error && (
        <div style={{ background: "#fef2f2", border: "1px solid #fecaca", color: "#991b1b", padding: "14px 18px", borderRadius: 12, marginBottom: 20 }}>
          {error}
        </div>
      )}

      {/* Grid of Kitchen Tickets */}
      {loading && orders.length === 0 ? (
        <div className="kds-empty">
          <div style={{ fontSize: 40, marginBottom: 12 }}>⏳</div>
          <h2 style={{ color: "#334155" }}>Loading Kitchen Queue...</h2>
        </div>
      ) : filteredOrders.length === 0 ? (
        <div className="kds-empty">
          <div style={{ fontSize: 48, marginBottom: 14 }}>✨</div>
          <h2 style={{ color: "#334155" }}>All Caught Up!</h2>
          <p>No active food orders in the preparation queue right now.</p>
        </div>
      ) : (
        <div className="kds-grid">
          {filteredOrders.map((o) => {
            const isPreparing = o.status === "preparing";
            const isUrgent = o.elapsed_minutes >= 20;
            const timerClass =
              o.elapsed_minutes >= 20
                ? "timer-urgent"
                : o.elapsed_minutes >= 10
                ? "timer-warning"
                : "timer-normal";

            return (
              <div
                key={o.id}
                className={`kds-card ${isPreparing ? "status-preparing" : ""} ${isUrgent ? "urgent" : ""}`}
              >
                {/* Card Header */}
                <div className="kds-card-header">
                  <span className="kds-order-num">#{o.order_number}</span>
                  <span className={`kds-timer-badge ${timerClass}`}>
                    ⏱️ {o.elapsed_minutes}m ago
                  </span>
                </div>

                {/* Card Meta */}
                <div className="kds-card-meta">
                  <span>Customer: <strong>{o.customer_name}</strong></span>
                  <span>{o.source === "agent" ? "🤖 WhatsApp AI" : "💻 Dashboard"}</span>
                </div>

                {/* Items List */}
                <div className="kds-card-body">
                  {o.items.map((item, idx) => (
                    <div key={idx} className="kds-item-row">
                      <span className="kds-item-qty">{item.quantity}x</span>
                      <span className="kds-item-name">{item.name}</span>
                    </div>
                  ))}

                  {/* High Visibility Special Preparation Notes */}
                  {o.has_notes && (
                    <div className="kds-notes-alert">
                      <div className="kds-notes-title">
                        <span>🚨</span> SPECIAL PREPARATION INSTRUCTIONS
                      </div>
                      <div className="kds-notes-content">{o.notes}</div>
                    </div>
                  )}
                </div>

                {/* Card Action */}
                <div className="kds-card-footer">
                  {!isPreparing ? (
                    <button
                      className="kds-btn-action btn-start"
                      disabled={updatingId === o.id}
                      onClick={() => handleStatusChange(o.id, "preparing")}
                    >
                      {updatingId === o.id ? "Updating..." : "🔥 Start Preparing"}
                    </button>
                  ) : (
                    <button
                      className="kds-btn-action btn-prepared"
                      disabled={updatingId === o.id}
                      onClick={() => handleStatusChange(o.id, "prepared")}
                    >
                      {updatingId === o.id ? "Auto-Assigning..." : "✅ Mark as Prepared"}
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
