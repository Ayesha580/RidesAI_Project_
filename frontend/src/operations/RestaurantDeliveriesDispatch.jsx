import { useCallback, useEffect, useMemo, useState } from "react";
import OwnerLayout from "../owner/components/OwnerLayout";
import StaffLayout from "../staff/components/StaffLayout";
import { restaurantDeliveryApi } from "../api/operationsApi";

const ACCENT = "#ff77ff";

const STATUS_BADGES = {
  new: { label: "New", bg: "#f1f5f9", color: "#334155", border: "#cbd5e1" },
  pending: { label: "Pending", bg: "#f1f5f9", color: "#334155", border: "#cbd5e1" },
  confirmed: { label: "Confirmed", bg: "#eff6ff", color: "#1d4ed8", border: "#bfdbfe" },
  preparing: { label: "Preparing", bg: "#fffbeb", color: "#b45309", border: "#fde68a" },
  prepared: { label: "Prepared", bg: "#fefce8", color: "#a16207", border: "#fef08a" },
  ready: { label: "Ready for Pickup", bg: "#fdf4ff", color: "#a21caf", border: "#f5d0fe" },
  assigned: { label: "Rider Assigned", bg: "#eef2ff", color: "#4338ca", border: "#c7d2fe" },
  picked_up: { label: "Picked Up", bg: "#ecfeff", color: "#0e7490", border: "#a5f3fc" },
  on_the_way: { label: "On the Way", bg: "#e0f2fe", color: "#0369a1", border: "#bae6fd" },
  out_for_delivery: { label: "Out for Delivery", bg: "#e0f2fe", color: "#0369a1", border: "#7dd3fc" },
  delivered: { label: "Delivered", bg: "#ecfdf5", color: "#047857", border: "#a7f3d0" },
  cancelled: { label: "Cancelled", bg: "#fef2f2", color: "#b91c1c", border: "#fecaca" },
};

const FILTER_PILLS = [
  { key: "all", label: "All Deliveries" },
  { key: "unassigned", label: "Unassigned" },
  { key: "active", label: "Out for Delivery" },
  { key: "delivered", label: "Delivered" },
];

function formatMoney(val) {
  const num = Number(val || 0);
  return `Rs. ${num.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function formatTime(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "—";
  }
}

export default function RestaurantDeliveriesDispatch({ staff = false }) {
  const Layout = staff ? StaffLayout : OwnerLayout;

  const [tab, setTab] = useState("dispatch"); // "dispatch" | "cod"
  const [statusFilter, setStatusFilter] = useState("all");
  const [dateFilter, setDateFilter] = useState("all"); // "today" | "all"
  const [search, setSearch] = useState("");

  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const [settlingKey, setSettlingKey] = useState(null);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");

  const [kpis, setKpis] = useState({
    pending_dispatch: 0,
    out_for_delivery: 0,
    delivered_today: 0,
    avg_delivery_minutes: 0,
    unsettled_cod_total: 0,
    unsettled_cod_count: 0,
  });
  const [riders, setRiders] = useState([]);
  const [unassignedCod, setUnassignedCod] = useState({ count: 0, total: 0, order_ids: [] });
  const [orders, setOrders] = useState([]);

  const showToast = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(""), 3500);
  };

  const loadBoard = useCallback(
    async (silent = false) => {
      if (!silent) setLoading(true);
      setError("");
      try {
        const res = await restaurantDeliveryApi.getBoard({
          status: statusFilter,
          date: dateFilter,
        });
        const data = res.data || {};
        setKpis(
          data.kpis || {
            pending_dispatch: 0,
            out_for_delivery: 0,
            delivered_today: 0,
            avg_delivery_minutes: 0,
            unsettled_cod_total: 0,
            unsettled_cod_count: 0,
          }
        );
        setRiders(Array.isArray(data.riders) ? data.riders : []);
        setUnassignedCod(data.unassigned_cod || { count: 0, total: 0, order_ids: [] });
        setOrders(Array.isArray(data.orders) ? data.orders : []);
      } catch (err) {
        setError(
          err?.response?.data?.detail ||
            err?.response?.data?.error ||
            "Could not load delivery dispatch board."
        );
      } finally {
        if (!silent) setLoading(false);
      }
    },
    [statusFilter, dateFilter]
  );

  useEffect(() => {
    loadBoard(false);
    const timer = setInterval(() => loadBoard(true), 20000);
    return () => clearInterval(timer);
  }, [loadBoard]);

  const filteredOrders = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return orders;
    return orders.filter(
      (o) =>
        String(o.order_number || "").toLowerCase().includes(q) ||
        String(o.customer_name || "").toLowerCase().includes(q) ||
        String(o.customer_phone || "").toLowerCase().includes(q) ||
        String(o.delivery_address || "").toLowerCase().includes(q) ||
        String(o.assigned_rider_name || "").toLowerCase().includes(q)
    );
  }, [orders, search]);

  const handleAssignRider = async (orderId, payload) => {
    setBusyId(orderId);
    setError("");
    try {
      const res = await restaurantDeliveryApi.assignRider(orderId, payload);
      const updatedOrder = res.data?.order;
      const riderName = res.data?.assigned_rider_name || res.data?.rider?.name || "rider";
      if (updatedOrder) {
        setOrders((prev) =>
          prev.map((o) => (o.id === orderId ? { ...o, ...updatedOrder } : o))
        );
      }
      showToast(`Assigned to ${riderName}.`);
      await loadBoard(true);
    } catch (err) {
      setError(err?.response?.data?.detail || "Failed to assign rider.");
    } finally {
      setBusyId(null);
    }
  };

  const handleStatusChange = async (orderId, nextStatus) => {
    setBusyId(orderId);
    setError("");
    try {
      await restaurantDeliveryApi.updateStatus(orderId, nextStatus);
      const label =
        nextStatus === "out_for_delivery"
          ? "Marked Out for Delivery"
          : nextStatus === "delivered"
          ? "Marked Delivered (COD Collected)"
          : "Order Cancelled";
      showToast(label);
      await loadBoard(true);
    } catch (err) {
      setError(err?.response?.data?.detail || "Failed to update delivery status.");
    } finally {
      setBusyId(null);
    }
  };

  const handleSettleRiderCod = async (rider) => {
    if (!rider || rider.unsettled_cod_count <= 0) return;
    const confirmed = window.confirm(
      `Confirm receiving ${formatMoney(rider.unsettled_cod_total)} cash from ${rider.name} for ${rider.unsettled_cod_count} delivered order(s)?`
    );
    if (!confirmed) return;
    setSettlingKey(`rider-${rider.id}`);
    setError("");
    try {
      const res = await restaurantDeliveryApi.settleCod({ rider_id: rider.id });
      showToast(
        `Settled ${formatMoney(res.data?.settled_amount)} (${res.data?.settled_count || 0} orders) for ${rider.name}.`
      );
      await loadBoard(true);
    } catch (err) {
      setError(err?.response?.data?.detail || "Failed to settle COD cash.");
    } finally {
      setSettlingKey(null);
    }
  };

  const handleSettleUnassignedCod = async () => {
    if (!unassignedCod.order_ids?.length) return;
    const confirmed = window.confirm(
      `Confirm settling ${formatMoney(unassignedCod.total)} across ${unassignedCod.count} unassigned delivered order(s)?`
    );
    if (!confirmed) return;
    setSettlingKey("unassigned");
    setError("");
    try {
      const res = await restaurantDeliveryApi.settleCod({ order_ids: unassignedCod.order_ids });
      showToast(
        `Settled ${formatMoney(res.data?.settled_amount)} (${res.data?.settled_count || 0} orders).`
      );
      await loadBoard(true);
    } catch (err) {
      setError(err?.response?.data?.detail || "Failed to settle COD cash.");
    } finally {
      setSettlingKey(null);
    }
  };

  const kpiCards = [
    {
      label: "Pending Dispatch",
      value: kpis.pending_dispatch,
      sub: "Awaiting rider / departure",
      accent: "#6366f1",
    },
    {
      label: "Out for Delivery",
      value: kpis.out_for_delivery,
      sub: "Currently on the road",
      accent: "#0284c7",
    },
    {
      label: "Delivered Today",
      value: kpis.delivered_today,
      sub: "Completed drop-offs",
      accent: "#059669",
    },
    {
      label: "Avg Delivery Time",
      value: `${kpis.avg_delivery_minutes || 0} min`,
      sub: "Dispatch to doorstep",
      accent: "#d97706",
    },
    {
      label: "Pending COD Cash",
      value: formatMoney(kpis.unsettled_cod_total),
      sub: `${kpis.unsettled_cod_count || 0} unsettled order${kpis.unsettled_cod_count === 1 ? "" : "s"}`,
      accent: "#c026d3",
      highlight: kpis.unsettled_cod_total > 0,
    },
  ];

  return (
    <Layout title="Deliveries & Dispatch">
      <div style={{ maxWidth: 1280, margin: "0 auto", padding: "8px 4px 32px" }}>
        {/* Header Bar */}
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 12,
            marginBottom: 18,
          }}
        >
          <div>
            <h2 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: "#0f172a" }}>
              Deliveries, Rider Dispatch &amp; COD
            </h2>
            <p style={{ margin: "4px 0 0", fontSize: 13, color: "#64748b" }}>
              Assign riders in 1 click, track live doorstep deliveries, and reconcile Cash-on-Delivery.
            </p>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div
              style={{
                display: "inline-flex",
                background: "#fff",
                border: "1px solid #e2e8f0",
                borderRadius: 10,
                padding: 3,
              }}
            >
              {[
                { key: "today", label: "Today" },
                { key: "all", label: "All Time" },
              ].map((opt) => (
                <button
                  key={opt.key}
                  type="button"
                  onClick={() => setDateFilter(opt.key)}
                  style={{
                    border: "none",
                    borderRadius: 7,
                    padding: "6px 12px",
                    fontSize: 12,
                    fontWeight: 700,
                    cursor: "pointer",
                    background: dateFilter === opt.key ? "#0f172a" : "transparent",
                    color: dateFilter === opt.key ? "#fff" : "#475569",
                  }}
                >
                  {opt.label}
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={() => loadBoard(false)}
              style={{
                border: "1px solid #e2e8f0",
                background: "#fff",
                color: "#0f172a",
                borderRadius: 10,
                padding: "8px 14px",
                fontSize: 13,
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              ↻ Refresh
            </button>
          </div>
        </div>

        {/* Alerts */}
        {toast && (
          <div
            style={{
              marginBottom: 14,
              padding: "10px 14px",
              borderRadius: 10,
              background: "#ecfdf5",
              border: "1px solid #a7f3d0",
              color: "#065f46",
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            ✓ {toast}
          </div>
        )}
        {error && (
          <div
            style={{
              marginBottom: 14,
              padding: "10px 14px",
              borderRadius: 10,
              background: "#fef2f2",
              border: "1px solid #fecaca",
              color: "#991b1b",
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            ⚠ {error}
          </div>
        )}

        {/* Top KPI Strip */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
            gap: 12,
            marginBottom: 20,
          }}
        >
          {kpiCards.map((card) => (
            <div
              key={card.label}
              style={{
                background: "#ffffff",
                borderRadius: 14,
                padding: "16px 18px",
                border: card.highlight ? `1.5px solid ${ACCENT}` : "1px solid #e2e8f0",
                boxShadow: "0 1px 3px rgba(15, 23, 42, 0.04)",
              }}
            >
              <div style={{ fontSize: 12, fontWeight: 600, color: "#64748b", marginBottom: 6 }}>
                {card.label}
              </div>
              <div style={{ fontSize: 24, fontWeight: 800, color: "#0f172a", lineHeight: 1.15 }}>
                {card.value}
              </div>
              <div style={{ fontSize: 11, color: card.accent, fontWeight: 600, marginTop: 6 }}>
                {card.sub}
              </div>
            </div>
          ))}
        </div>

        {/* Main Navigation Tabs */}
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 12,
            marginBottom: 16,
            borderBottom: "1px solid #e2e8f0",
            paddingBottom: 10,
          }}
        >
          <div style={{ display: "flex", gap: 8 }}>
            <button
              type="button"
              onClick={() => setTab("dispatch")}
              style={{
                border: tab === "dispatch" ? `1.5px solid ${ACCENT}` : "1px solid #e2e8f0",
                background: tab === "dispatch" ? "#fdf4ff" : "#fff",
                color: tab === "dispatch" ? "#86198f" : "#475569",
                borderRadius: 10,
                padding: "9px 16px",
                fontSize: 13,
                fontWeight: 700,
                cursor: "pointer",
              }}
            >
              🛵 Live Dispatch Board
            </button>
            <button
              type="button"
              onClick={() => setTab("cod")}
              style={{
                border: tab === "cod" ? `1.5px solid ${ACCENT}` : "1px solid #e2e8f0",
                background: tab === "cod" ? "#fdf4ff" : "#fff",
                color: tab === "cod" ? "#86198f" : "#475569",
                borderRadius: 10,
                padding: "9px 16px",
                fontSize: 13,
                fontWeight: 700,
                cursor: "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              💵 Rider COD Settlement
              {kpis.unsettled_cod_total > 0 && (
                <span
                  style={{
                    background: "#c026d3",
                    color: "#fff",
                    fontSize: 11,
                    fontWeight: 800,
                    padding: "2px 7px",
                    borderRadius: 999,
                  }}
                >
                  {formatMoney(kpis.unsettled_cod_total)}
                </span>
              )}
            </button>
          </div>

          {tab === "dispatch" && (
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search order #, customer, phone, address, rider..."
              style={{
                minWidth: 260,
                padding: "8px 12px",
                borderRadius: 10,
                border: "1px solid #cbd5e1",
                fontSize: 13,
                background: "#fff",
                color: "#0f172a",
              }}
            />
          )}
        </div>

        {/* TAB 1: LIVE DISPATCH BOARD */}
        {tab === "dispatch" && (
          <div>
            {/* Filter Pills */}
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 16 }}>
              {FILTER_PILLS.map((pill) => {
                const active = statusFilter === pill.key;
                return (
                  <button
                    key={pill.key}
                    type="button"
                    onClick={() => setStatusFilter(pill.key)}
                    style={{
                      border: active ? `1.5px solid ${ACCENT}` : "1px solid #e2e8f0",
                      background: active ? "#0f172a" : "#fff",
                      color: active ? "#fff" : "#475569",
                      borderRadius: 999,
                      padding: "6px 14px",
                      fontSize: 12,
                      fontWeight: 700,
                      cursor: "pointer",
                    }}
                  >
                    {pill.label}
                  </button>
                );
              })}
            </div>

            {loading ? (
              <div
                style={{
                  background: "#fff",
                  borderRadius: 14,
                  border: "1px solid #e2e8f0",
                  padding: 40,
                  textAlign: "center",
                  color: "#64748b",
                  fontSize: 14,
                }}
              >
                Loading delivery orders...
              </div>
            ) : filteredOrders.length === 0 ? (
              <div
                style={{
                  background: "#fff",
                  borderRadius: 14,
                  border: "1px dashed #cbd5e1",
                  padding: 44,
                  textAlign: "center",
                  color: "#64748b",
                }}
              >
                <div style={{ fontSize: 32, marginBottom: 8 }}>🛵</div>
                <div style={{ fontSize: 15, fontWeight: 700, color: "#0f172a", marginBottom: 4 }}>
                  No delivery orders match this filter
                </div>
                <div style={{ fontSize: 13 }}>
                  New delivery orders from POS or WhatsApp AI will appear here automatically.
                </div>
              </div>
            ) : (
              <div style={{ display: "grid", gap: 12 }}>
                {filteredOrders.map((order) => {
                  const badge = STATUS_BADGES[order.status] || {
                    label: order.status,
                    bg: "#f1f5f9",
                    color: "#334155",
                    border: "#cbd5e1",
                  };
                  const isTerminal =
                    order.status === "delivered" || order.status === "cancelled";
                  const isOut = ["out_for_delivery", "on_the_way", "picked_up"].includes(
                    order.status
                  );
                  const isBusy = busyId === order.id;

                  return (
                    <div
                      key={order.id}
                      style={{
                        background: "#ffffff",
                        border: "1px solid #e2e8f0",
                        borderRadius: 14,
                        padding: "16px 18px",
                        display: "grid",
                        gridTemplateColumns: "minmax(240px, 1.3fr) minmax(220px, 1fr) minmax(240px, 1.1fr)",
                        gap: 16,
                        alignItems: "center",
                        boxShadow: "0 1px 2px rgba(15, 23, 42, 0.03)",
                      }}
                    >
                      {/* Column 1: Order & Customer */}
                      <div>
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            flexWrap: "wrap",
                            gap: 8,
                            marginBottom: 6,
                          }}
                        >
                          <span style={{ fontWeight: 800, fontSize: 15, color: "#0f172a" }}>
                            #{order.order_number}
                          </span>
                          <span
                            style={{
                              fontSize: 11,
                              fontWeight: 700,
                              padding: "3px 9px",
                              borderRadius: 999,
                              background: badge.bg,
                              color: badge.color,
                              border: `1px solid ${badge.border}`,
                            }}
                          >
                            {badge.label}
                          </span>
                          {order.status === "delivered" && (
                            <span
                              style={{
                                fontSize: 11,
                                fontWeight: 700,
                                padding: "3px 9px",
                                borderRadius: 999,
                                background: order.cod_settled ? "#ecfdf5" : "#fdf4ff",
                                color: order.cod_settled ? "#047857" : "#a21caf",
                                border: order.cod_settled
                                  ? "1px solid #a7f3d0"
                                  : `1px solid ${ACCENT}`,
                              }}
                            >
                              {order.cod_settled ? "COD Settled" : "COD Unsettled"}
                            </span>
                          )}
                        </div>
                        <div style={{ fontSize: 14, fontWeight: 700, color: "#1e293b" }}>
                          {order.customer_name || "Guest Customer"}{" "}
                          {order.customer_phone && (
                            <span style={{ fontWeight: 500, color: "#64748b", fontSize: 12 }}>
                              • {order.customer_phone}
                            </span>
                          )}
                        </div>
                        <div
                          style={{
                            fontSize: 12,
                            color: "#475569",
                            marginTop: 4,
                            lineHeight: 1.4,
                          }}
                        >
                          📍 {order.delivery_address || "No delivery address provided"}
                        </div>
                        <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 6 }}>
                          Placed {formatTime(order.created_at)}
                          {order.dispatched_at ? ` • Dispatched ${formatTime(order.dispatched_at)}` : ""}
                          {order.delivered_at ? ` • Delivered ${formatTime(order.delivered_at)}` : ""}
                          {order.delivery_minutes != null ? ` (${order.delivery_minutes} min)` : ""}
                        </div>
                      </div>

                      {/* Column 2: Items & Amount */}
                      <div>
                        <div style={{ fontSize: 18, fontWeight: 800, color: "#0f172a" }}>
                          {formatMoney(order.total)}
                        </div>
                        <div style={{ fontSize: 11, color: "#64748b", marginBottom: 6 }}>
                          Subtotal {formatMoney(order.subtotal)} + Delivery{" "}
                          {formatMoney(order.delivery_fee)}
                        </div>
                        <div style={{ fontSize: 12, color: "#334155", lineHeight: 1.45 }}>
                          {(order.items || []).slice(0, 3).map((it) => (
                            <div key={it.id}>
                              {it.quantity}× {it.item_name}
                            </div>
                          ))}
                          {(order.items || []).length > 3 && (
                            <div style={{ color: "#64748b", fontSize: 11 }}>
                              +{order.items.length - 3} more item(s)
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Column 3: Rider Assignment & 1-Click Lifecycle Actions */}
                      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                        {/* Rider Assignment Row (read-only badge on delivered/cancelled orders) */}
                        {isTerminal ? (
                          <div
                            style={{
                              display: "inline-flex",
                              alignItems: "center",
                              gap: 6,
                              padding: "7px 11px",
                              borderRadius: 9,
                              background: order.status === "delivered" ? "#f8fafc" : "#fef2f2",
                              border:
                                order.status === "delivered"
                                  ? "1px solid #e2e8f0"
                                  : "1px solid #fecaca",
                              fontSize: 12,
                              fontWeight: 700,
                              color: order.assigned_rider_name ? "#334155" : "#64748b",
                            }}
                          >
                            <span>🛵</span>
                            <span>
                              {order.assigned_rider_name
                                ? order.status === "delivered"
                                  ? `Delivered by ${order.assigned_rider_name}`
                                  : `Rider: ${order.assigned_rider_name}`
                                : "No rider assigned"}
                            </span>
                          </div>
                        ) : (
                          <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                            {(() => {
                              const currentIdStr = order.assigned_rider_id
                                ? String(order.assigned_rider_id)
                                : "";
                              const riderInList = riders.some(
                                (r) => String(r.id) === currentIdStr
                              );
                              return (
                                <select
                                  disabled={isBusy}
                                  value={currentIdStr}
                                  onChange={(e) => {
                                    const rid = e.target.value;
                                    if (rid && rid !== currentIdStr) {
                                      handleAssignRider(order.id, {
                                        rider_id: Number(rid),
                                        auto: false,
                                      });
                                    }
                                  }}
                                  style={{
                                    flex: 1,
                                    minWidth: 145,
                                    padding: "7px 10px",
                                    borderRadius: 8,
                                    border: "1px solid #cbd5e1",
                                    fontSize: 12,
                                    fontWeight: 600,
                                    background: "#fff",
                                    color: "#0f172a",
                                  }}
                                >
                                  {!currentIdStr && (
                                    <option value="">— Select Rider —</option>
                                  )}
                                  {currentIdStr && !riderInList && (
                                    <option value={currentIdStr}>
                                      {order.assigned_rider_name || `Rider #${currentIdStr}`}
                                    </option>
                                  )}
                                  {riders.map((r) => (
                                    <option key={r.id} value={String(r.id)}>
                                      {r.name} ({r.active_deliveries} active)
                                    </option>
                                  ))}
                                </select>
                              );
                            })()}

                            {!order.assigned_rider_id && (
                              <button
                                type="button"
                                disabled={isBusy}
                                onClick={() => handleAssignRider(order.id, { auto: true })}
                                style={{
                                  border: `1px solid ${ACCENT}`,
                                  background: "#fdf4ff",
                                  color: "#86198f",
                                  borderRadius: 8,
                                  padding: "7px 10px",
                                  fontSize: 12,
                                  fontWeight: 700,
                                  cursor: isBusy ? "wait" : "pointer",
                                  whiteSpace: "nowrap",
                                }}
                              >
                                ⚡ Auto-Assign
                              </button>
                            )}
                          </div>
                        )}

                        {/* 1-Click Lifecycle Buttons */}
                        {!isTerminal && (
                          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                            {!isOut && (
                              <button
                                type="button"
                                disabled={isBusy}
                                onClick={() => handleStatusChange(order.id, "out_for_delivery")}
                                style={{
                                  flex: 1,
                                  border: "none",
                                  background: "#0284c7",
                                  color: "#fff",
                                  borderRadius: 8,
                                  padding: "8px 10px",
                                  fontSize: 12,
                                  fontWeight: 700,
                                  cursor: isBusy ? "wait" : "pointer",
                                  whiteSpace: "nowrap",
                                }}
                              >
                                🚀 Mark Out for Delivery
                              </button>
                            )}
                            <button
                              type="button"
                              disabled={isBusy}
                              onClick={() => handleStatusChange(order.id, "delivered")}
                              style={{
                                flex: 1,
                                border: "none",
                                background: "#059669",
                                color: "#fff",
                                borderRadius: 8,
                                padding: "8px 10px",
                                fontSize: 12,
                                fontWeight: 700,
                                cursor: isBusy ? "wait" : "pointer",
                                whiteSpace: "nowrap",
                              }}
                            >
                              ✅ Mark Delivered
                            </button>
                            <button
                              type="button"
                              disabled={isBusy}
                              onClick={() => {
                                if (window.confirm(`Cancel delivery order #${order.order_number}?`)) {
                                  handleStatusChange(order.id, "cancelled");
                                }
                              }}
                              title="Cancel Order"
                              style={{
                                border: "1px solid #fecaca",
                                background: "#fff",
                                color: "#b91c1c",
                                borderRadius: 8,
                                padding: "8px 10px",
                                fontSize: 12,
                                fontWeight: 700,
                                cursor: isBusy ? "wait" : "pointer",
                              }}
                            >
                              ✕
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* TAB 2: RIDER COD SETTLEMENT */}
        {tab === "cod" && (
          <div style={{ display: "grid", gap: 14 }}>
            <div
              style={{
                background: "#ffffff",
                border: "1px solid #e2e8f0",
                borderRadius: 14,
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  padding: "14px 18px",
                  borderBottom: "1px solid #e2e8f0",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  flexWrap: "wrap",
                  gap: 8,
                }}
              >
                <div>
                  <div style={{ fontSize: 15, fontWeight: 800, color: "#0f172a" }}>
                    Rider Cash-on-Delivery Ledger
                  </div>
                  <div style={{ fontSize: 12, color: "#64748b" }}>
                    Reconcile cash collected by each rider from delivered orders.
                  </div>
                </div>
                <div style={{ fontSize: 13, fontWeight: 700, color: "#a21caf" }}>
                  Total Pending Cash: {formatMoney(kpis.unsettled_cod_total)}
                </div>
              </div>

              {riders.length === 0 && unassignedCod.count === 0 ? (
                <div style={{ padding: 40, textAlign: "center", color: "#64748b", fontSize: 13 }}>
                  No active riders found. Add a Rider staff member under Employees to track COD cash.
                </div>
              ) : (
                <div style={{ overflowX: "auto" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                    <thead>
                      <tr style={{ background: "#f8fafc", textAlign: "left", color: "#475569" }}>
                        <th style={{ padding: "12px 18px", fontWeight: 700 }}>Rider</th>
                        <th style={{ padding: "12px 14px", fontWeight: 700 }}>Active Deliveries</th>
                        <th style={{ padding: "12px 14px", fontWeight: 700 }}>Completed Today</th>
                        <th style={{ padding: "12px 14px", fontWeight: 700 }}>Unsettled Orders</th>
                        <th style={{ padding: "12px 14px", fontWeight: 700 }}>Cash-in-Hand (COD)</th>
                        <th style={{ padding: "12px 18px", fontWeight: 700, textAlign: "right" }}>
                          Action
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {riders.map((rider) => {
                        const hasCash = rider.unsettled_cod_count > 0;
                        const isSettling = settlingKey === `rider-${rider.id}`;
                        return (
                          <tr
                            key={rider.id}
                            style={{ borderTop: "1px solid #f1f5f9", color: "#0f172a" }}
                          >
                            <td style={{ padding: "14px 18px" }}>
                              <div style={{ fontWeight: 700 }}>{rider.name}</div>
                              <div style={{ fontSize: 11, color: "#64748b" }}>
                                {rider.phone || rider.username}
                              </div>
                            </td>
                            <td style={{ padding: "14px" }}>
                              <span
                                style={{
                                  padding: "3px 10px",
                                  borderRadius: 999,
                                  fontSize: 12,
                                  fontWeight: 700,
                                  background: rider.active_deliveries > 0 ? "#e0f2fe" : "#f1f5f9",
                                  color: rider.active_deliveries > 0 ? "#0369a1" : "#475569",
                                }}
                              >
                                {rider.active_deliveries} active
                              </span>
                            </td>
                            <td style={{ padding: "14px", fontWeight: 600 }}>
                              {rider.completed_today}
                            </td>
                            <td style={{ padding: "14px", fontWeight: 600 }}>
                              {rider.unsettled_cod_count}
                            </td>
                            <td
                              style={{
                                padding: "14px",
                                fontWeight: 800,
                                fontSize: 15,
                                color: hasCash ? "#a21caf" : "#64748b",
                              }}
                            >
                              {formatMoney(rider.unsettled_cod_total)}
                            </td>
                            <td style={{ padding: "14px 18px", textAlign: "right" }}>
                              {hasCash ? (
                                <button
                                  type="button"
                                  disabled={isSettling}
                                  onClick={() => handleSettleRiderCod(rider)}
                                  style={{
                                    border: "none",
                                    background: "#0f172a",
                                    color: "#fff",
                                    borderRadius: 9,
                                    padding: "8px 14px",
                                    fontSize: 12,
                                    fontWeight: 700,
                                    cursor: isSettling ? "wait" : "pointer",
                                  }}
                                >
                                  {isSettling ? "Settling..." : "✓ Settle Cash"}
                                </button>
                              ) : (
                                <span
                                  style={{
                                    fontSize: 12,
                                    fontWeight: 700,
                                    color: "#059669",
                                    background: "#ecfdf5",
                                    padding: "5px 10px",
                                    borderRadius: 999,
                                  }}
                                >
                                  ✓ All Settled
                                </span>
                              )}
                            </td>
                          </tr>
                        );
                      })}

                      {unassignedCod.count > 0 && (
                        <tr style={{ borderTop: "1px solid #f1f5f9", background: "#fffbeb" }}>
                          <td style={{ padding: "14px 18px" }}>
                            <div style={{ fontWeight: 700, color: "#92400e" }}>
                              Unassigned / Walk-out Deliveries
                            </div>
                            <div style={{ fontSize: 11, color: "#b45309" }}>
                              Delivered without a linked rider account
                            </div>
                          </td>
                          <td style={{ padding: "14px" }}>—</td>
                          <td style={{ padding: "14px" }}>—</td>
                          <td style={{ padding: "14px", fontWeight: 700 }}>
                            {unassignedCod.count}
                          </td>
                          <td
                            style={{
                              padding: "14px",
                              fontWeight: 800,
                              fontSize: 15,
                              color: "#a21caf",
                            }}
                          >
                            {formatMoney(unassignedCod.total)}
                          </td>
                          <td style={{ padding: "14px 18px", textAlign: "right" }}>
                            <button
                              type="button"
                              disabled={settlingKey === "unassigned"}
                              onClick={handleSettleUnassignedCod}
                              style={{
                                border: "none",
                                background: "#0f172a",
                                color: "#fff",
                                borderRadius: 9,
                                padding: "8px 14px",
                                fontSize: 12,
                                fontWeight: 700,
                                cursor: settlingKey === "unassigned" ? "wait" : "pointer",
                              }}
                            >
                              {settlingKey === "unassigned" ? "Settling..." : "✓ Settle Cash"}
                            </button>
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
}
