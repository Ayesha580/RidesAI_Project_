import { useCallback, useEffect, useState } from "react";
import { dashboardApi, restaurantKdsApi } from "../../api/operationsApi";
import { errorText } from "../../api/axiosClient";

const STATIONS = [
  { key: "all", label: "All Stations", icon: "🍽️" },
  { key: "grill", label: "Grill", icon: "🔥" },
  { key: "fryer", label: "Fryer", icon: "🍟" },
  { key: "drinks", label: "Drinks", icon: "🥤" },
  { key: "dessert", label: "Dessert", icon: "🍰" },
  { key: "general", label: "General", icon: "👨‍🍳" },
];

const ORDER_TYPE_META = {
  dine_in: { label: "DINE-IN", bg: "#fdf2ff", color: "#9c1e9c", border: "#f5b8f5" },
  takeaway: { label: "TAKEAWAY", bg: "#fff7ed", color: "#c2410c", border: "#fed7aa" },
  delivery: { label: "DELIVERY", bg: "#eff6ff", color: "#1d4ed8", border: "#bfdbfe" },
};

function getTimerStyle(minutes) {
  if (minutes >= 20) {
    return { bg: "#fef2f2", color: "#b91c1c", border: "#fca5a5", dot: "#ef4444" };
  }
  if (minutes >= 10) {
    return { bg: "#fffbeb", color: "#b45309", border: "#fcd34d", dot: "#f59e0b" };
  }
  return { bg: "#ecfdf5", color: "#047857", border: "#a7f3d0", dot: "#10b981" };
}

function getBumpAction(ticket) {
  const st = String(ticket.status || "").toLowerCase();
  if (st === "new" || st === "pending" || st === "confirmed") {
    return { label: "🔥 Start Preparing", bg: "#ff77ff", color: "#26082b" };
  }
  if (st === "preparing") {
    return { label: "✅ Mark Ready", bg: "#10b981", color: "#ffffff" };
  }
  if (st === "ready") {
    if (ticket.order_type === "dine_in") {
      return { label: "🍽️ Mark Served", bg: "#3b82f6", color: "#ffffff" };
    }
    if (ticket.order_type === "takeaway") {
      return { label: "🥡 Mark Picked Up", bg: "#3b82f6", color: "#ffffff" };
    }
    return { label: "🛵 Dispatch Rider", bg: "#3b82f6", color: "#ffffff" };
  }
  return null;
}

export default function RestaurantKDSBoard({ refreshTrigger = 0 }) {
  const [station, setStation] = useState("all");
  const [tickets, setTickets] = useState([]);
  const [stationCounts, setStationCounts] = useState({});
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [loading, setLoading] = useState(true);
  const [bumpingId, setBumpingId] = useState(null);
  const [printingId, setPrintingId] = useState(null);
  const [error, setError] = useState("");
  const [lastSynced, setLastSynced] = useState(null);

  const loadKds = useCallback(async (selectedStation = station, silent = false) => {
    if (!silent) setLoading(true);
    setError("");
    try {
      const { data } = await restaurantKdsApi.getTickets(selectedStation);
      setTickets(Array.isArray(data?.tickets) ? data.tickets : []);
      setStationCounts(data?.station_counts || {});
      setLastSynced(new Date());
    } catch (e) {
      setError(errorText(e) || "Failed to load Kitchen Display tickets.");
    } finally {
      if (!silent) setLoading(false);
    }
  }, [station]);

  useEffect(() => {
    loadKds(station, false);
  }, [station, refreshTrigger, loadKds]);

  useEffect(() => {
    if (!autoRefresh) return;
    const timer = setInterval(() => {
      loadKds(station, true);
    }, 10000);
    return () => clearInterval(timer);
  }, [autoRefresh, station, loadKds]);

  const handleBump = async (ticket) => {
    setBumpingId(ticket.id);
    setError("");
    try {
      await restaurantKdsApi.bumpOrder(ticket.id);
      await loadKds(station, true);
    } catch (e) {
      setError(errorText(e) || "Failed to update ticket status.");
    } finally {
      setBumpingId(null);
    }
  };

  const handlePrintKot = async (ticket) => {
    setPrintingId(ticket.id);
    try {
      const { data } = await dashboardApi.getOrderReceipt(ticket.id, "kot");
      const html = data?.html || "";
      const win = window.open("", "_blank", "width=420,height=640");
      if (win) {
        if (html) {
          win.document.write(html);
        } else {
          const itemLines = (ticket.items || [])
            .map((it) => {
              const mods = (it.selected_modifiers || [])
                .map((m) => `+ ${m.name}`)
                .join(", ");
              return `<div style="margin:6px 0;font-size:14px;"><strong>${it.quantity}x ${it.name}</strong>${
                mods ? `<div style="padding-left:14px;font-size:12px;">${mods}</div>` : ""
              }${it.item_notes ? `<div style="padding-left:14px;font-size:12px;font-style:italic;">Note: ${it.item_notes}</div>` : ""}</div>`;
            })
            .join("");
          win.document.write(`
            <html><head><title>KOT #${ticket.order_number}</title></head>
            <body style="font-family:monospace;padding:16px;">
              <h2 style="margin:0 0 6px;">KOT — ${ticket.order_number}</h2>
              <div>Type: ${(ticket.order_type || "delivery").toUpperCase()}${ticket.table_number ? ` · Table ${ticket.table_number}` : ""}</div>
              <div>Customer: ${ticket.customer_name || "Guest"}</div>
              <hr />
              ${itemLines}
              ${ticket.notes ? `<hr /><div><strong>Order Notes:</strong> ${ticket.notes}</div>` : ""}
            </body></html>
          `);
        }
        win.document.close();
        win.focus();
        setTimeout(() => win.print(), 250);
      }
    } catch (e) {
      setError(errorText(e) || "Could not load KOT receipt.");
    } finally {
      setPrintingId(null);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Station Filter Pills + Auto-Refresh Controls */}
      <div
        style={{
          background: "#ffffff",
          border: "1px solid #f0e6f2",
          borderRadius: 16,
          padding: "14px 16px",
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
        }}
      >
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {STATIONS.map((st) => {
            const active = station === st.key;
            const count = stationCounts[st.key] ?? 0;
            return (
              <button
                key={st.key}
                type="button"
                onClick={() => setStation(st.key)}
                style={{
                  border: active ? "1px solid #e040e0" : "1px solid #eedff0",
                  background: active ? "#ff77ff" : "#faf6fb",
                  color: active ? "#240729" : "#564861",
                  borderRadius: 999,
                  padding: "7px 14px",
                  fontSize: 13,
                  fontWeight: active ? 800 : 600,
                  cursor: "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 7,
                }}
              >
                <span>{st.icon}</span>
                <span>{st.label}</span>
                <span
                  style={{
                    fontSize: 11.5,
                    fontWeight: 800,
                    padding: "1px 7px",
                    borderRadius: 999,
                    background: active ? "rgba(36, 7, 41, 0.14)" : "#ffffff",
                    color: active ? "#240729" : "#7a6985",
                  }}
                >
                  {count}
                </span>
              </button>
            );
          })}
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <label
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              fontSize: 12.5,
              fontWeight: 600,
              color: "#564861",
              cursor: "pointer",
            }}
          >
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              style={{ accentColor: "#d946ef" }}
            />
            <span>Auto-refresh (10s)</span>
          </label>

          <button
            type="button"
            onClick={() => loadKds(station, false)}
            style={{
              border: "1px solid #ead8ec",
              background: "#ffffff",
              color: "#36203e",
              borderRadius: 10,
              padding: "7px 12px",
              fontSize: 12.5,
              fontWeight: 700,
              cursor: "pointer",
            }}
          >
            ↻ Refresh
          </button>
        </div>
      </div>

      {error && (
        <div
          style={{
            background: "#fef2f2",
            border: "1px solid #fecaca",
            color: "#991b1b",
            borderRadius: 12,
            padding: "12px 16px",
            fontSize: 13,
          }}
        >
          {error}
        </div>
      )}

      {/* Tickets Grid */}
      {loading ? (
        <div
          style={{
            background: "#ffffff",
            border: "1px solid #f0e6f2",
            borderRadius: 16,
            padding: 48,
            textAlign: "center",
            color: "#8c7d96",
            fontSize: 14,
          }}
        >
          Loading live kitchen tickets...
        </div>
      ) : tickets.length === 0 ? (
        <div
          style={{
            background: "#ffffff",
            border: "1px solid #f0e6f2",
            borderRadius: 16,
            padding: 52,
            textAlign: "center",
          }}
        >
          <div style={{ fontSize: 36, marginBottom: 8 }}>👨‍🍳</div>
          <h3 style={{ margin: 0, fontSize: 17, fontWeight: 800, color: "#24142b" }}>
            Kitchen is All Caught Up!
          </h3>
          <p style={{ margin: "6px 0 0", fontSize: 13.5, color: "#7f7288" }}>
            No active tickets in this station. New Dine-In, Takeaway, Delivery, and AI orders will appear here live.
          </p>
          {lastSynced && (
            <div style={{ marginTop: 10, fontSize: 11.5, color: "#a194ab" }}>
              Last synced at {lastSynced.toLocaleTimeString()}
            </div>
          )}
        </div>
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(310px, 1fr))",
            gap: 16,
            alignItems: "start",
          }}
        >
          {tickets.map((ticket) => {
            const timerSt = getTimerStyle(ticket.elapsed_minutes || 0);
            const typeMeta = ORDER_TYPE_META[ticket.order_type] || ORDER_TYPE_META.delivery;
            const bump = getBumpAction(ticket);
            const isReady = String(ticket.status).toLowerCase() === "ready";
            const isPreparing = String(ticket.status).toLowerCase() === "preparing";

            return (
              <div
                key={ticket.id}
                style={{
                  background: "#ffffff",
                  border: isReady
                    ? "2px solid #10b981"
                    : isPreparing
                    ? "2px solid #f0abfc"
                    : "1px solid #ece0ef",
                  borderRadius: 16,
                  overflow: "hidden",
                  boxShadow: "0 4px 16px rgba(42, 16, 48, 0.05)",
                  display: "flex",
                  flexDirection: "column",
                }}
              >
                {/* Ticket Header */}
                <div
                  style={{
                    padding: "13px 16px",
                    background: isReady ? "#ecfdf5" : isPreparing ? "#fdf4ff" : "#faf7fb",
                    borderBottom: "1px solid #f1e7f4",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: 8,
                  }}
                >
                  <div>
                    <div style={{ fontSize: 15, fontWeight: 800, color: "#211426" }}>
                      #{ticket.order_number}
                    </div>
                    <div style={{ fontSize: 12, color: "#6f6278", marginTop: 2 }}>
                      {ticket.customer_name || "Guest"} ·{" "}
                      <span style={{ textTransform: "uppercase", fontWeight: 700 }}>
                        {ticket.status}
                      </span>
                    </div>
                  </div>

                  {/* Live Elapsed Timer Badge */}
                  <div
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 6,
                      padding: "5px 10px",
                      borderRadius: 999,
                      background: timerSt.bg,
                      color: timerSt.color,
                      border: `1px solid ${timerSt.border}`,
                      fontSize: 12.5,
                      fontWeight: 800,
                      whiteSpace: "nowrap",
                    }}
                  >
                    <span
                      style={{
                        width: 7,
                        height: 7,
                        borderRadius: "50%",
                        background: timerSt.dot,
                      }}
                    />
                    <span>{ticket.elapsed_minutes ?? 0} min</span>
                  </div>
                </div>

                {/* Order Type & Table Strip */}
                <div
                  style={{
                    padding: "9px 16px",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: 8,
                    borderBottom: "1px solid #f6eff8",
                  }}
                >
                  <span
                    style={{
                      fontSize: 11.5,
                      fontWeight: 800,
                      letterSpacing: "0.04em",
                      padding: "3px 9px",
                      borderRadius: 7,
                      background: typeMeta.bg,
                      color: typeMeta.color,
                      border: `1px solid ${typeMeta.border}`,
                    }}
                  >
                    {typeMeta.label}
                    {ticket.order_type === "dine_in" && ticket.table_number
                      ? ` · TABLE ${ticket.table_number}`
                      : ""}
                  </span>

                  <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                    {(ticket.stations || []).map((st) => (
                      <span
                        key={st}
                        style={{
                          fontSize: 11,
                          fontWeight: 600,
                          textTransform: "capitalize",
                          padding: "2px 8px",
                          borderRadius: 6,
                          background: "#f5eff7",
                          color: "#6b5a75",
                        }}
                      >
                        {st}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Items List with Highlighted Modifiers & Notes */}
                <div style={{ padding: "12px 16px", display: "flex", flexDirection: "column", gap: 10 }}>
                  {(ticket.items || []).map((item) => (
                    <div
                      key={item.id}
                      style={{
                        paddingBottom: 9,
                        borderBottom: "1px dashed #efe5f2",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 8 }}>
                        <div style={{ fontSize: 14, fontWeight: 750, color: "#211426" }}>
                          <span
                            style={{
                              display: "inline-block",
                              minWidth: 24,
                              padding: "1px 6px",
                              borderRadius: 6,
                              background: "#fdf2ff",
                              color: "#a21caf",
                              fontWeight: 800,
                              marginRight: 6,
                              textAlign: "center",
                            }}
                          >
                            {item.quantity}×
                          </span>
                          {item.name}
                        </div>
                      </div>

                      {/* Highlighted Modifiers / Add-ons */}
                      {Array.isArray(item.selected_modifiers) && item.selected_modifiers.length > 0 && (
                        <div style={{ display: "flex", flexWrap: "wrap", gap: 5, marginTop: 6, paddingLeft: 30 }}>
                          {item.selected_modifiers.map((mod, idx) => (
                            <span
                              key={`${mod.name}-${idx}`}
                              style={{
                                fontSize: 11.5,
                                fontWeight: 700,
                                background: "#fff1ff",
                                color: "#9c1e9c",
                                border: "1px solid #f5b8f5",
                                borderRadius: 6,
                                padding: "2px 8px",
                              }}
                            >
                              + {mod.name}
                              {Number(mod.price || 0) > 0 ? ` (+Rs. ${mod.price})` : ""}
                            </span>
                          ))}
                        </div>
                      )}

                      {/* Item Special Notes */}
                      {item.item_notes && (
                        <div
                          style={{
                            marginTop: 5,
                            marginLeft: 30,
                            fontSize: 12,
                            fontWeight: 600,
                            color: "#b45309",
                            background: "#fffbeb",
                            border: "1px solid #fde68a",
                            borderRadius: 6,
                            padding: "4px 8px",
                          }}
                        >
                          📝 {item.item_notes}
                        </div>
                      )}
                    </div>
                  ))}

                  {ticket.notes && (
                    <div
                      style={{
                        fontSize: 12,
                        color: "#78350f",
                        background: "#fff7ed",
                        border: "1px solid #fed7aa",
                        borderRadius: 8,
                        padding: "7px 10px",
                      }}
                    >
                      <strong>Order Note:</strong> {ticket.notes}
                    </div>
                  )}
                </div>

                {/* Action Footer: 1-Click Bump + KOT Print */}
                <div
                  style={{
                    padding: "12px 16px",
                    borderTop: "1px solid #f2e9f5",
                    background: "#fcfafd",
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                  }}
                >
                  {bump && (
                    <button
                      type="button"
                      disabled={bumpingId === ticket.id}
                      onClick={() => handleBump(ticket)}
                      style={{
                        flex: 1,
                        border: "none",
                        borderRadius: 10,
                        padding: "10px 14px",
                        fontSize: 13,
                        fontWeight: 800,
                        cursor: bumpingId === ticket.id ? "wait" : "pointer",
                        background: bump.bg,
                        color: bump.color,
                        opacity: bumpingId === ticket.id ? 0.7 : 1,
                      }}
                    >
                      {bumpingId === ticket.id ? "Updating..." : bump.label}
                    </button>
                  )}

                  <button
                    type="button"
                    disabled={printingId === ticket.id}
                    onClick={() => handlePrintKot(ticket)}
                    title="Print Kitchen Order Ticket"
                    style={{
                      border: "1px solid #e5d6ea",
                      background: "#ffffff",
                      color: "#36203e",
                      borderRadius: 10,
                      padding: "10px 12px",
                      fontSize: 12.5,
                      fontWeight: 700,
                      cursor: "pointer",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {printingId === ticket.id ? "..." : "🖨️ KOT"}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
