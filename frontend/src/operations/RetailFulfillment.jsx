import { useCallback, useEffect, useState } from "react";
import OwnerLayout from "../owner/components/OwnerLayout";
import StaffLayout from "../staff/components/StaffLayout";
import { retailApi } from "../api/operationsApi";
import { errorText } from "../api/axiosClient";

const css = `
.rf-container {
  display: flex;
  flex-direction: column;
  gap: 18px;
  width: 100%;
}
.rf-kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 14px;
}
.rf-kpi-card {
  background: #ffffff;
  border: 1px solid #e8e3ec;
  border-radius: 14px;
  padding: 16px 18px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.02);
}
.rf-kpi-label {
  font-size: 11.5px;
  color: #6b7280;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.rf-kpi-val {
  font-size: 26px;
  font-weight: 800;
  margin-top: 4px;
  color: #1e1b24;
}
.rf-panel {
  background: #ffffff;
  border: 1px solid #e8e3ec;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 2px 10px rgba(0,0,0,0.03);
}
.rf-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 16px 20px;
  border-bottom: 1px solid #f1ebf4;
  flex-wrap: wrap;
}
.rf-tabs {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.rf-tab-btn {
  padding: 8px 14px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid #e2dce6;
  background: #ffffff;
  color: #555;
  transition: all .2s;
}
.rf-tab-btn.active {
  background: #ff77ff;
  color: #ffffff;
  border-color: #ff77ff;
  box-shadow: 0 3px 8px rgba(255,119,255,0.25);
}
.rf-filter-group {
  display: flex;
  align-items: center;
  gap: 10px;
}
.rf-search-input {
  height: 38px;
  padding: 0 14px;
  border: 1px solid #e2dce6;
  border-radius: 10px;
  font-size: 13.5px;
  outline: none;
  background: #ffffff;
  color: #1e1b24;
  transition: border-color .2s;
}
.rf-search-input:focus {
  border-color: #ff77ff;
}
.rf-refresh-btn {
  height: 38px;
  padding: 0 14px;
  border: 1px solid #e2dce6;
  background: #ffffff;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  color: #555;
  transition: all .2s;
}
.rf-refresh-btn:hover {
  background: #faf7fc;
  border-color: #ff77ff;
  color: #ff77ff;
}
.rf-orders-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 16px;
  padding: 20px;
}
.rf-order-card {
  background: #ffffff;
  border: 1px solid #e8e3ec;
  border-radius: 14px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  transition: transform .2s, box-shadow .2s;
}
.rf-order-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 18px rgba(0,0,0,0.05);
}
.rf-order-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  border-bottom: 1px solid #f6f3f8;
  padding-bottom: 10px;
}
.rf-order-num {
  font-weight: 800;
  font-size: 14.5px;
  color: #1e1b24;
}
.rf-order-time {
  font-size: 11.5px;
  color: #888;
  margin-top: 2px;
}
.rf-pill {
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 11.5px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.4px;
}
.rf-pill-to_pack { background: #eff6ff; color: #2563eb; }
.rf-pill-packing { background: #fef3c7; color: #d97706; }
.rf-pill-ready { background: #fdf2f8; color: #db2777; }
.rf-pill-dispatched { background: #e0f2fe; color: #0284c7; }
.rf-pill-delivered { background: #dcfce7; color: #16a34a; }
.rf-pill-cancelled { background: #fee2e2; color: #dc2626; }
.rf-swap-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: rgba(255, 119, 255, 0.14);
  color: #c026d3;
  border: 1px solid rgba(255, 119, 255, 0.4);
  border-radius: 20px;
  padding: 3px 8px;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.3px;
}
.rf-swap-alert {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  background: #fdf4ff;
  border: 1px solid #f0abfc;
  border-radius: 10px;
  padding: 8px 10px;
  font-size: 12px;
  color: #86198f;
  line-height: 1.35;
}
.rf-cust-info {
  font-size: 13px;
  color: #4b5563;
  line-height: 1.45;
}
.rf-items-box {
  background: #faf8fb;
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 12.5px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.rf-item-row {
  display: flex;
  justify-content: space-between;
  color: #374151;
}
.rf-total-row {
  display: flex;
  justify-content: space-between;
  font-weight: 700;
  font-size: 13.5px;
  color: #1e1b24;
  padding-top: 6px;
  border-top: 1px dashed #e2dce6;
}
.rf-actions-row {
  display: flex;
  gap: 8px;
  margin-top: auto;
  padding-top: 10px;
  border-top: 1px solid #f6f3f8;
}
.rf-btn-step {
  flex: 1;
  height: 38px;
  background: #ff77ff;
  color: #ffffff;
  border: none;
  border-radius: 9px;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  transition: all .2s;
  box-shadow: 0 2px 6px rgba(255,119,255,0.2);
}
.rf-btn-step:hover {
  background: #f05cf0;
}
.rf-btn-step:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
  box-shadow: none;
}
.rf-btn-cancel {
  height: 38px;
  padding: 0 12px;
  background: #fff;
  border: 1px solid #fca5a5;
  color: #ef4444;
  border-radius: 9px;
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
  transition: all .2s;
}
.rf-btn-cancel:hover {
  background: #fee2e2;
}
.rf-empty {
  padding: 40px;
  text-align: center;
  color: #888;
}
.rf-toast {
  background: #dcfce7;
  border: 1px solid #86efac;
  color: #15803d;
  padding: 12px 18px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 12px;
}
`;

export default function RetailFulfillment({ staff = false }) {
  const [orders, setOrders] = useState([]);
  const [kpis, setKpis] = useState({
    total: 0,
    to_pack: 0,
    packing: 0,
    ready: 0,
    dispatched: 0,
    delivered: 0,
  });
  const [selectedStage, setSelectedStage] = useState("all");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(null);
  const [toastMsg, setToastMsg] = useState("");
  const [errorMsg, setErrorMsg] = useState("");

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setErrorMsg("");
      const params = {};
      if (selectedStage !== "all") {
        params.stage = selectedStage;
      }
      if (search.trim()) {
        params.search = search.trim();
      }
      const res = await retailApi.getFulfillmentOrders(params);
      setOrders(res.data?.results || []);
      if (res.data?.kpis) {
        setKpis(res.data.kpis);
      }
    } catch (err) {
      setErrorMsg(errorText(err) || "Failed to load fulfillment orders.");
    } finally {
      setLoading(false);
    }
  }, [selectedStage, search]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleAdvanceStatus = async (order, targetStatus) => {
    try {
      setActionLoading(order.id);
      setErrorMsg("");
      const res = await retailApi.updateFulfillmentStatus(order.id, { status: targetStatus });
      setToastMsg(`Order ${order.order_number} moved to ${targetStatus.replace(/_/g, " ")}. WhatsApp notification sent!`);
      setTimeout(() => setToastMsg(""), 4500);
      loadData();
    } catch (err) {
      setErrorMsg(errorText(err) || "Failed to update order status.");
    } finally {
      setActionLoading(null);
    }
  };

  const getStageButton = (order) => {
    const stage = order.stage;
    const allowed = order.allowed_next_statuses || [];

    if (stage === "to_pack") {
      return (
        <button
          className="rf-btn-step"
          disabled={actionLoading === order.id}
          onClick={() => handleAdvanceStatus(order, "preparing")}
        >
          {actionLoading === order.id ? "Updating..." : "📦 Start Packing"}
        </button>
      );
    }
    if (stage === "packing") {
      return (
        <button
          className="rf-btn-step"
          disabled={actionLoading === order.id}
          onClick={() => handleAdvanceStatus(order, "ready")}
        >
          {actionLoading === order.id ? "Updating..." : "✅ Mark Ready"}
        </button>
      );
    }
    if (stage === "ready") {
      return (
        <button
          className="rf-btn-step"
          disabled={actionLoading === order.id}
          onClick={() => handleAdvanceStatus(order, "out_for_delivery")}
        >
          {actionLoading === order.id ? "Updating..." : "🚚 Dispatch Order"}
        </button>
      );
    }
    if (stage === "dispatched") {
      return (
        <button
          className="rf-btn-step"
          disabled={actionLoading === order.id}
          onClick={() => handleAdvanceStatus(order, "delivered")}
        >
          {actionLoading === order.id ? "Updating..." : "🎉 Mark Delivered"}
        </button>
      );
    }
    if (stage === "delivered") {
      return (
        <span style={{ fontSize: "12px", color: "#16a34a", fontWeight: "700" }}>
          ✓ Completed & Delivered
        </span>
      );
    }
    return (
      <span style={{ fontSize: "12px", color: "#888" }}>
        No actions available
      </span>
    );
  };

  const content = (
    <div className="rf-container">
      <style>{css}</style>

      {toastMsg && <div className="rf-toast">{toastMsg}</div>}
      {errorMsg && <div className="rf-toast" style={{ background: "#fee2e2", borderColor: "#fca5a5", color: "#b91c1c" }}>{errorMsg}</div>}

      {/* KPI Cards */}
      <div className="rf-kpi-grid">
        <div className="rf-kpi-card">
          <div className="rf-kpi-label">Total Active</div>
          <div className="rf-kpi-val">{kpis.total || 0}</div>
        </div>
        <div className="rf-kpi-card" style={{ borderLeft: "4px solid #2563eb" }}>
          <div className="rf-kpi-label">To Pack</div>
          <div className="rf-kpi-val" style={{ color: "#2563eb" }}>{kpis.to_pack || 0}</div>
        </div>
        <div className="rf-kpi-card" style={{ borderLeft: "4px solid #d97706" }}>
          <div className="rf-kpi-label">Packing (In Progress)</div>
          <div className="rf-kpi-val" style={{ color: "#d97706" }}>{kpis.packing || 0}</div>
        </div>
        <div className="rf-kpi-card" style={{ borderLeft: "4px solid #db2777" }}>
          <div className="rf-kpi-label">Ready for Dispatch</div>
          <div className="rf-kpi-val" style={{ color: "#db2777" }}>{kpis.ready || 0}</div>
        </div>
        <div className="rf-kpi-card" style={{ borderLeft: "4px solid #0284c7" }}>
          <div className="rf-kpi-label">Dispatched</div>
          <div className="rf-kpi-val" style={{ color: "#0284c7" }}>{kpis.dispatched || 0}</div>
        </div>
        <div className="rf-kpi-card" style={{ borderLeft: "4px solid #16a34a" }}>
          <div className="rf-kpi-label">Delivered</div>
          <div className="rf-kpi-val" style={{ color: "#16a34a" }}>{kpis.delivered || 0}</div>
        </div>
      </div>

      {/* Main Panel */}
      <div className="rf-panel">
        <div className="rf-toolbar">
          <div className="rf-tabs">
            {[
              { id: "all", label: "All Orders" },
              { id: "to_pack", label: "To Pack" },
              { id: "packing", label: "Packing" },
              { id: "ready", label: "Ready" },
              { id: "dispatched", label: "Dispatched" },
              { id: "delivered", label: "Delivered" },
            ].map((tab) => (
              <button
                key={tab.id}
                className={`rf-tab-btn ${selectedStage === tab.id ? "active" : ""}`}
                onClick={() => setSelectedStage(tab.id)}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div className="rf-filter-group">
            <input
              type="text"
              className="rf-search-input"
              placeholder="Search order #, customer..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <button className="rf-refresh-btn" onClick={loadData}>
              {loading ? "Refreshing..." : "↻ Refresh"}
            </button>
          </div>
        </div>

        {loading && orders.length === 0 ? (
          <div className="rf-empty">Loading fulfillment orders...</div>
        ) : orders.length === 0 ? (
          <div className="rf-empty">No orders found in this fulfillment stage.</div>
        ) : (
          <div className="rf-orders-grid">
            {orders.map((o) => (
              <div key={o.id} className="rf-order-card">
                <div className="rf-order-header">
                  <div>
                    <div className="rf-order-num">{o.order_number}</div>
                    <div className="rf-order-time">{new Date(o.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} • {new Date(o.created_at).toLocaleDateString()}</div>
                  </div>
                  <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                    {(o.is_exchange || (o.notes && o.notes.includes("EXCHANGE SWAP"))) && (
                      <span className="rf-swap-badge" title="Doorstep Exchange Order">
                        🔄 EXCHANGE SWAP
                      </span>
                    )}
                    <span className={`rf-pill rf-pill-${o.stage}`}>
                      {o.status.replace(/_/g, " ")}
                    </span>
                  </div>
                </div>

                <div className="rf-cust-info">
                  <strong>{o.customer_name}</strong> • {o.customer_phone}
                  {o.delivery_address && (
                    <div style={{ color: "#6b7280", marginTop: "2px" }}>
                      📍 {o.delivery_address}
                    </div>
                  )}
                  {o.notes && (
                    <div style={{ color: "#b45309", marginTop: "2px", fontSize: "12px" }}>
                      Note: {o.notes}
                    </div>
                  )}
                </div>

                {(o.is_exchange || (o.notes && o.notes.includes("EXCHANGE SWAP"))) && (
                  <div className="rf-swap-alert">
                    <span style={{ fontSize: "15px" }}>🔄</span>
                    <div>
                      <strong>DOORSTEP SWAP:</strong> Deliver replacement item &amp; <u>collect original item</u> from customer before completing delivery!
                    </div>
                  </div>
                )}

                <div className="rf-items-box">
                  {o.items.map((it) => (
                    <div key={it.id} className="rf-item-row">
                      <span>{it.quantity}x {it.item_name}</span>
                      <span>Rs. {parseFloat(it.line_total || 0).toLocaleString()}</span>
                    </div>
                  ))}
                  <div className="rf-total-row">
                    <span>Total (Inc. Delivery)</span>
                    <span>Rs. {parseFloat(o.total || 0).toLocaleString()}</span>
                  </div>
                </div>

                <div className="rf-actions-row">
                  {getStageButton(o)}
                  {o.allowed_next_statuses?.includes("cancelled") && o.stage !== "delivered" && (
                    <button
                      className="rf-btn-cancel"
                      disabled={actionLoading === o.id}
                      onClick={() => handleAdvanceStatus(o, "cancelled")}
                      title="Cancel Order"
                    >
                      Cancel
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );

  return staff ? (
    <StaffLayout title="Packing & Dispatch (Fulfillment)">{content}</StaffLayout>
  ) : (
    <OwnerLayout title="Packing & Dispatch (Fulfillment)">{content}</OwnerLayout>
  );
}
