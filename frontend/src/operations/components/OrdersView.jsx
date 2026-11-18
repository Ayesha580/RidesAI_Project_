import { useCallback, useEffect, useState } from "react";
import { dashboardApi } from "../../api/operationsApi";
import { errorText } from "../../api/axiosClient";
import { useAuth } from "../../context/AuthContext";

const css = `
.ov-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
  width: 100%;
}

.ov-panel {
  background: #ffffff;
  border: 1px solid #e8e3ec;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 2px 10px rgba(0,0,0,0.03);
}

.ov-toolbar {
  padding: 16px 20px;
  border-bottom: 1px solid #f0ebf3;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  background: #ffffff;
}

.ov-search-box {
  position: relative;
  display: flex;
  align-items: center;
}

.ov-search-input {
  width: 100%;
  padding: 9px 12px 9px 34px;
  background: #f8f6fa;
  border: 1px solid #e4dfe9;
  border-radius: 10px;
  font-size: 13.5px;
  outline: none;
  transition: border-color 0.2s ease;
}

.ov-search-input:focus {
  border-color: #c026d3;
  background: #ffffff;
}

.ov-search-icon {
  position: absolute;
  left: 10px;
  color: #9891a0;
  font-size: 14px;
}

.ov-filter-select {
  padding: 9px 14px;
  background: #f8f6fa;
  border: 1px solid #e4dfe9;
  border-radius: 10px;
  font-size: 13.5px;
  color: #312b39;
  outline: none;
  cursor: pointer;
  transition: border-color 0.2s ease;
}

.ov-filter-select:focus {
  border-color: #c026d3;
  background: #ffffff;
}

.ov-btn-refresh {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 9px 16px;
  border-radius: 10px;
  border: 1px solid #dbd4e0;
  background: #ffffff;
  color: #4b4454;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}

.ov-btn-refresh:hover {
  background: #f6f3f8;
  border-color: #c0b8c6;
}

.ov-table-wrap {
  overflow-x: auto;
  width: 100%;
}

.ov-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
}

.ov-table th {
  padding: 13px 18px;
  font-size: 11.5px;
  font-weight: 750;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #797182;
  background: #faf8fc;
  border-bottom: 1px solid #ede8f2;
  white-space: nowrap;
}

.ov-table td {
  padding: 14px 18px;
  font-size: 13.5px;
  color: #312b39;
  border-bottom: 1px solid #f4f0f6;
  vertical-align: middle;
}

.ov-table tr:hover td {
  background: #fdfbfe;
}

.ov-order-num {
  font-family: monospace;
  font-weight: 750;
  color: #a21caf;
  background: #fdf2fe;
  padding: 4px 9px;
  border-radius: 6px;
  font-size: 12.5px;
  display: inline-block;
  border: 1px solid #fae8ff;
}

.ov-source-badge {
  font-size: 11px;
  color: #8c8594;
  margin-top: 4px;
}

.ov-status-badge {
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 750;
  text-transform: uppercase;
  letter-spacing: 0.3px;
  display: inline-block;
}

.badge-new { background: #dbeafe; color: #1e40af; }
.badge-confirmed { background: #fef3c7; color: #92400e; }
.badge-preparing { background: #f3e8ff; color: #6b21a8; }
.badge-ready { background: #ccfbf1; color: #115e59; }
.badge-delivered { background: #dcfce7; color: #166534; }
.badge-cancelled { background: #fee2e2; color: #991b1b; }

.ov-status-select {
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 600;
  border-radius: 8px;
  border: 1px solid #d1c9d8;
  background: #ffffff;
  color: #312b39;
  cursor: pointer;
  outline: none;
  transition: border-color 0.2s ease;
}

.ov-status-select:focus {
  border-color: #c026d3;
}

.ov-footer {
  padding: 13px 20px;
  border-top: 1px solid #f0ebf3;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #faf8fc;
  font-size: 12.5px;
  color: #71697a;
  flex-wrap: wrap;
  gap: 10px;
}

.ov-page-btn {
  padding: 6px 14px;
  border-radius: 8px;
  border: 1px solid #dbd4e0;
  background: #ffffff;
  color: #4b4454;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}

.ov-page-btn:hover:not(:disabled) {
  background: #f6f3f8;
  border-color: #c0b8c6;
}

.ov-page-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.ov-empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 65px 20px;
  text-align: center;
  color: #8c8594;
}

.ov-empty-icon {
  font-size: 42px;
  margin-bottom: 12px;
}

.ov-empty-state h4 {
  margin: 0;
  color: #312b39;
  font-size: 16px;
  font-weight: 700;
}

.ov-empty-state p {
  margin: 6px 0 0;
  font-size: 13px;
  color: #8c8594;
}

.ov-error-banner {
  padding: 12px 16px;
  background: #fee2e2;
  color: #991b1b;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 12px;
}
`;

export default function OrdersView() {
  const { user } = useAuth();

  const [orders, setOrders] = useState([]);
  const [ordersLoading, setOrdersLoading] = useState(true);
  const [ordersError, setOrdersError] = useState("");
  const [orderSearch, setOrderSearch] = useState("");
  const [orderStatus, setOrderStatus] = useState("");
  const [orderPage, setOrderPage] = useState(1);
  const [orderTotalPages, setOrderTotalPages] = useState(1);
  const [orderCount, setOrderCount] = useState(0);

  // --- Load Orders ---
  const loadOrders = useCallback(async (page = 1) => {
    setOrdersLoading(true);
    setOrdersError("");
    try {
      const params = { page, page_size: 15 };
      const companyId = user?.company_id || user?.company;
      if (companyId) params.company_id = companyId;
      if (orderSearch.trim()) params.search = orderSearch.trim();
      if (orderStatus) params.status = orderStatus;

      const { data } = await dashboardApi.getOrders(params);
      setOrders(data.results || []);
      setOrderTotalPages(data.total_pages || 1);
      setOrderPage(data.current_page || 1);
      setOrderCount(data.count || 0);
    } catch (err) {
      setOrdersError(errorText(err));
    } finally {
      setOrdersLoading(false);
    }
  }, [user, orderSearch, orderStatus]);

  useEffect(() => {
    loadOrders(1);
  }, [loadOrders]);

  const handleUpdateOrderStatus = async (orderId, newStatus) => {
    try {
      await dashboardApi.updateOrderStatus(orderId, { status: newStatus });
      await loadOrders(orderPage);
    } catch (err) {
      alert("Failed to update order status: " + errorText(err));
    }
  };

  return (
    <div className="ov-container">
      <style>{css}</style>

      {ordersError && (
        <div className="ov-error-banner" role="alert">
          {ordersError}
        </div>
      )}

      <section className="ov-panel">
        {/* Toolbar */}
        <div className="ov-toolbar">
          <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap", flex: 1 }}>
            <div className="ov-search-box" style={{ maxWidth: 320, flex: 1 }}>
              <span className="ov-search-icon">🔍</span>
              <input
                type="text"
                className="ov-search-input"
                placeholder="Search by Order #, phone, address..."
                value={orderSearch}
                onChange={(e) => {
                  setOrderSearch(e.target.value);
                  setOrderPage(1);
                }}
              />
            </div>

            <select
              className="ov-filter-select"
              value={orderStatus}
              onChange={(e) => {
                setOrderStatus(e.target.value);
                setOrderPage(1);
              }}
            >
              <option value="">All Order Statuses</option>
              <option value="new">New</option>
              <option value="confirmed">Confirmed</option>
              <option value="preparing">Preparing</option>
              <option value="ready">Ready</option>
              <option value="delivered">Delivered</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </div>

          <button className="ov-btn-refresh" onClick={() => loadOrders(orderPage)}>
            <span>↻</span> Refresh Orders
          </button>
        </div>

        {/* Orders Table */}
        <div className="ov-table-wrap">
          {ordersLoading && orders.length === 0 ? (
            <div className="ov-empty-state">
              <div className="ov-empty-icon">⏳</div>
              <p>Loading database orders...</p>
            </div>
          ) : orders.length === 0 ? (
            <div className="ov-empty-state">
              <div className="ov-empty-icon">📦</div>
              <h4>No orders found</h4>
              <p>Orders created by the AI Agent or dashboard will appear here in real time.</p>
            </div>
          ) : (
            <table className="ov-table">
              <thead>
                <tr>
                  <th>Order Reference</th>
                  <th>Customer</th>
                  <th>Ordered Items</th>
                  <th>Total</th>
                  <th>Delivery Address</th>
                  <th>Status</th>
                  <th>Date & Time</th>
                  <th>Status Action</th>
                </tr>
              </thead>
              <tbody>
                {orders.map((o) => {
                  const statusClass =
                    o.status === "new" ? "badge-new"
                    : o.status === "confirmed" ? "badge-confirmed"
                    : o.status === "preparing" ? "badge-preparing"
                    : o.status === "ready" ? "badge-ready"
                    : o.status === "delivered" ? "badge-delivered"
                    : "badge-cancelled";

                  return (
                    <tr key={o.id}>
                      <td>
                        <span className="ov-order-num">{o.order_number}</span>
                        <div className="ov-source-badge">
                          {o.source === "agent" ? "🤖 WhatsApp AI" : "💻 Dashboard"}
                        </div>
                      </td>
                      <td>
                        <div style={{ fontWeight: 650 }}>{o.customer_name}</div>
                        <div style={{ fontSize: 12, color: "#787081", fontFamily: "monospace", marginTop: 2 }}>
                          {o.customer_phone}
                        </div>
                      </td>
                      <td>
                        <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
                          {(o.items || []).map((it, idx) => (
                            <span key={idx} style={{ fontSize: 12.5 }}>
                              <strong>{parseInt(it.quantity)}x</strong> {it.item_name}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td>
                        <strong style={{ fontSize: 14.5, color: "#166534" }}>Rs. {o.total}</strong>
                      </td>
                      <td style={{ maxWidth: 220 }}>
                        <span
                          style={{
                            fontSize: 12.5,
                            color: "#544d5c",
                            display: "-webkit-box",
                            WebkitLineClamp: 2,
                            WebkitBoxOrient: "vertical",
                            overflow: "hidden",
                          }}
                        >
                          {o.delivery_address || "No address provided"}
                        </span>
                      </td>
                      <td>
                        <span className={`ov-status-badge ${statusClass}`}>
                          {o.status_display}
                        </span>
                      </td>
                      <td style={{ fontSize: 12, color: "#787081", whiteSpace: "nowrap" }}>
                        {o.formatted_date || new Date(o.created_at).toLocaleString([], { dateStyle: "short", timeStyle: "short" })}
                      </td>
                      <td>
                        <select
                          className="ov-status-select"
                          value={o.status}
                          onChange={(e) => handleUpdateOrderStatus(o.id, e.target.value)}
                        >
                          <option value="new">New</option>
                          <option value="confirmed">Confirmed</option>
                          <option value="preparing">Preparing</option>
                          <option value="ready">Ready</option>
                          <option value="delivered">Delivered</option>
                          <option value="cancelled">Cancelled</option>
                        </select>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        {/* Orders Pagination Footer */}
        <footer className="ov-footer">
          <span>Showing {orders.length} of {orderCount} total orders</span>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span>Page {orderPage} of {orderTotalPages || 1}</span>
            <button
              className="ov-page-btn"
              disabled={orderPage <= 1 || ordersLoading}
              onClick={() => {
                const p = Math.max(1, orderPage - 1);
                setOrderPage(p);
                loadOrders(p);
              }}
            >
              ◀ Prev
            </button>
            <button
              className="ov-page-btn"
              disabled={orderPage >= orderTotalPages || ordersLoading}
              onClick={() => {
                const p = orderPage + 1;
                setOrderPage(p);
                loadOrders(p);
              }}
            >
              Next ▶
            </button>
          </div>
        </footer>
      </section>
    </div>
  );
}
