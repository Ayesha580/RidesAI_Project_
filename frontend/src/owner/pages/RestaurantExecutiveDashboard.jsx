import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import OwnerLayout from "../components/OwnerLayout";
import { useAuth } from "../../context/AuthContext";
import { restaurantDashboardApi } from "../../api/operationsApi";

const PERIODS = [
  { key: "today", label: "Today" },
  { key: "7d", label: "7 Days" },
  { key: "30d", label: "30 Days" },
];

const STATUS_STYLE = {
  new: { bg: "#fdf2ff", color: "#b822b8", border: "#f5c2f5", label: "New" },
  confirmed: { bg: "#eff6ff", color: "#1d4ed8", border: "#bfdbfe", label: "Confirmed" },
  preparing: { bg: "#fff7ed", color: "#c2410c", border: "#fed7aa", label: "Preparing" },
  ready: { bg: "#f0fdf4", color: "#15803d", border: "#bbf7d0", label: "Ready" },
  dispatched: { bg: "#eef2ff", color: "#4338ca", border: "#c7d2fe", label: "Dispatched" },
  delivered: { bg: "#ecfdf5", color: "#047857", border: "#a7f3d0", label: "Delivered" },
  completed: { bg: "#ecfdf5", color: "#047857", border: "#a7f3d0", label: "Completed" },
  cancelled: { bg: "#fef2f2", color: "#b91c1c", border: "#fecaca", label: "Cancelled" },
};

function fmtCurrency(val) {
  const num = Number(val || 0);
  return `Rs. ${num.toLocaleString("en-PK", { maximumFractionDigits: 0 })}`;
}

function fmtShortTime(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

function TrendChart({ trend = [], metric, period }) {
  const [hovered, setHovered] = useState(null);

  const W = 680;
  const H = 240;
  const P = { t: 22, r: 18, b: 36, l: 54 };

  const values = trend.map((d) =>
    metric === "revenue" ? Number(d.revenue || 0) : Number(d.orders_count || 0)
  );
  const rawMax = Math.max(0, ...values);
  const maxVal = rawMax > 0 ? rawMax * 1.15 : metric === "revenue" ? 1000 : 5;

  const innerW = W - P.l - P.r;
  const innerH = H - P.t - P.b;
  const count = Math.max(1, trend.length);

  const xPos = (i) =>
    trend.length <= 1 ? P.l + innerW / 2 : P.l + (i * innerW) / (count - 1);
  const yPos = (v) => P.t + (1 - v / maxVal) * innerH;

  const pts = trend.map((d, i) => [xPos(i), yPos(values[i])]);

  const linePath = pts
    .map(([px, py], i) => {
      if (i === 0) return `M ${px} ${py}`;
      const [prevX, prevY] = pts[i - 1];
      const midX = (prevX + px) / 2;
      return `C ${midX} ${prevY}, ${midX} ${py}, ${px} ${py}`;
    })
    .join(" ");

  const areaPath =
    pts.length > 0
      ? `${linePath} L ${pts[pts.length - 1][0]} ${H - P.b} L ${pts[0][0]} ${H - P.b} Z`
      : "";

  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((t) => maxVal * t);

  const labelStep =
    period === "today" ? 4 : period === "30d" ? 5 : 1;

  const activePoint = hovered !== null && trend[hovered] ? trend[hovered] : null;
  const activeCoord = hovered !== null && pts[hovered] ? pts[hovered] : null;

  return (
    <div style={{ position: "relative", width: "100%" }}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        style={{ width: "100%", height: "auto", display: "block", overflow: "visible" }}
        role="img"
        aria-label="Restaurant revenue and orders trend"
        onMouseLeave={() => setHovered(null)}
      >
        <defs>
          <linearGradient id="restTrendFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#ff77ff" stopOpacity="0.32" />
            <stop offset="100%" stopColor="#ff77ff" stopOpacity="0.02" />
          </linearGradient>
        </defs>

        {yTicks.map((val, idx) => {
          const y = yPos(val);
          const label =
            metric === "revenue"
              ? val >= 1000
                ? `${(val / 1000).toFixed(val >= 10000 ? 0 : 1)}k`
                : Math.round(val)
              : Math.round(val);
          return (
            <g key={idx}>
              <line
                x1={P.l}
                x2={W - P.r}
                y1={y}
                y2={y}
                stroke="#f2e9f5"
                strokeDasharray="4 4"
              />
              <text
                x={P.l - 10}
                y={y + 4}
                textAnchor="end"
                fontSize="11"
                fill="#998da3"
              >
                {label}
              </text>
            </g>
          );
        })}

        {areaPath && <path d={areaPath} fill="url(#restTrendFill)" />}
        {linePath && (
          <path
            d={linePath}
            fill="none"
            stroke="#e040e0"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        )}

        {activeCoord && (
          <line
            x1={activeCoord[0]}
            x2={activeCoord[0]}
            y1={P.t}
            y2={H - P.b}
            stroke="#ff77ff"
            strokeWidth="1.5"
            strokeDasharray="3 3"
          />
        )}

        {pts.map(([px, py], i) => {
          const isHov = hovered === i;
          const showLabel = i % labelStep === 0 || i === trend.length - 1;
          const bandW = innerW / count;
          return (
            <g key={trend[i]?.key || i}>
              <rect
                x={px - bandW / 2}
                y={P.t}
                width={Math.max(bandW, 14)}
                height={innerH}
                fill="transparent"
                style={{ cursor: "pointer" }}
                onMouseEnter={() => setHovered(i)}
              />
              {(isHov || trend.length <= 12) && (
                <circle
                  cx={px}
                  cy={py}
                  r={isHov ? 6.5 : 4}
                  fill="#ffffff"
                  stroke="#d936d9"
                  strokeWidth={isHov ? 3 : 2.5}
                  style={{ pointerEvents: "none" }}
                />
              )}
              {showLabel && (
                <text
                  x={px}
                  y={H - 10}
                  textAnchor="middle"
                  fontSize="11"
                  fill={isHov ? "#2c1b33" : "#998da3"}
                  fontWeight={isHov ? "700" : "400"}
                >
                  {trend[i].label}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      {activePoint && activeCoord && (
        <div
          style={{
            position: "absolute",
            top: 8,
            right: 12,
            background: "#26162b",
            color: "#ffffff",
            padding: "8px 12px",
            borderRadius: 10,
            fontSize: 12,
            boxShadow: "0 8px 20px rgba(38, 22, 43, 0.22)",
            pointerEvents: "none",
            minWidth: 145,
          }}
        >
          <div style={{ fontWeight: 700, color: "#ff9eff", marginBottom: 4 }}>
            {activePoint.label}
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 14 }}>
            <span style={{ opacity: 0.78 }}>Revenue</span>
            <strong style={{ fontWeight: 700 }}>{fmtCurrency(activePoint.revenue)}</strong>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 14, marginTop: 2 }}>
            <span style={{ opacity: 0.78 }}>Orders</span>
            <strong style={{ fontWeight: 700 }}>{activePoint.orders_count}</strong>
          </div>
        </div>
      )}
    </div>
  );
}

export default function RestaurantExecutiveDashboard() {
  const { user } = useAuth();
  const [period, setPeriod] = useState("today");
  const [chartMetric, setChartMetric] = useState("revenue");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const fetchSummary = useCallback(async (selectedPeriod, isManual = false) => {
    if (isManual) setRefreshing(true);
    else setLoading(true);
    setError("");
    try {
      const res = await restaurantDashboardApi.getSummary(selectedPeriod);
      setData(res.data);
    } catch (err) {
      setError(
        err?.response?.data?.detail || "Unable to load restaurant dashboard summary."
      );
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchSummary(period, false);
  }, [period, fetchSummary]);

  const firstName = (user?.first_name || user?.full_name || "Owner").split(" ")[0];
  const formattedDate = useMemo(
    () =>
      new Date().toLocaleDateString("en-GB", {
        weekday: "long",
        day: "numeric",
        month: "long",
        year: "numeric",
      }),
    []
  );

  const kpis = data?.kpis || {};
  const tables = data?.tables || {};
  const alerts = data?.alerts || {};
  const trend = data?.trend || [];
  const topItems = data?.top_items || [];
  const channels = data?.channel_breakdown || {};
  const recentOrders = data?.recent_orders || [];

  const totalAlerts =
    (alerts.unassigned_orders_count || 0) +
    (alerts.low_stock_items_count || 0) +
    (alerts.pending_faq_suggestions_count || 0);

  const maxTopQty = Math.max(1, ...topItems.map((i) => Number(i.quantity || 0)));

  const totalTables = Number(tables.tables_total || 0);
  const occPct = totalTables > 0 ? Math.round((Number(tables.tables_occupied || 0) / totalTables) * 100) : 0;
  const resPct = totalTables > 0 ? Math.round((Number(tables.tables_reserved || 0) / totalTables) * 100) : 0;
  const availPct = Math.max(0, 100 - occPct - resPct);

  const channelPills = [
    { key: "whatsapp", label: "WhatsApp", count: channels.whatsapp || 0, icon: "💬" },
    { key: "public_web", label: "Public Link", count: channels.public_web || 0, icon: "🌐" },
    { key: "widget", label: "Widget", count: channels.widget || 0, icon: "🧩" },
    { key: "dashboard", label: "Dashboard", count: channels.dashboard || 0, icon: "🖥️" },
  ];

  const cardStyle = {
    background: "#ffffff",
    border: "1px solid #f0e6f2",
    borderRadius: 16,
    padding: 20,
    boxShadow: "0 2px 10px rgba(42, 16, 48, 0.03)",
  };

  return (
    <OwnerLayout title="Dashboard">
      <style>{`
        .rest-exec-charts-grid {
          display: grid;
          grid-template-columns: 1fr;
          gap: 16px;
          align-items: stretch;
        }
        @media (min-width: 980px) {
          .rest-exec-charts-grid {
            grid-template-columns: 1.85fr 1fr;
          }
        }
      `}</style>
      <div style={{ maxWidth: 1320, margin: "0 auto", display: "flex", flexDirection: "column", gap: 20 }}>
        {/* Header Row */}
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 14,
          }}
        >
          <div>
            <h1 style={{ margin: 0, fontSize: 24, fontWeight: 800, color: "#211426", letterSpacing: "-0.02em" }}>
              Welcome back, {firstName}
            </h1>
            <p style={{ margin: "4px 0 0", fontSize: 13.5, color: "#7f7288" }}>
              {formattedDate} · Live Restaurant Command Center
            </p>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <div
              style={{
                display: "inline-flex",
                background: "#faf5fb",
                border: "1px solid #eedff0",
                borderRadius: 12,
                padding: 4,
                gap: 4,
              }}
            >
              {PERIODS.map((p) => {
                const active = period === p.key;
                return (
                  <button
                    key={p.key}
                    type="button"
                    onClick={() => setPeriod(p.key)}
                    style={{
                      border: "none",
                      borderRadius: 9,
                      padding: "7px 14px",
                      fontSize: 13,
                      fontWeight: active ? 700 : 500,
                      cursor: "pointer",
                      background: active ? "#ff77ff" : "transparent",
                      color: active ? "#240729" : "#6f6278",
                      transition: "all 0.15s ease",
                    }}
                  >
                    {p.label}
                  </button>
                );
              })}
            </div>

            <button
              type="button"
              onClick={() => fetchSummary(period, true)}
              disabled={refreshing || loading}
              style={{
                border: "1px solid #ead8ec",
                background: "#ffffff",
                color: "#36203e",
                borderRadius: 11,
                padding: "9px 14px",
                fontSize: 13,
                fontWeight: 600,
                cursor: refreshing || loading ? "wait" : "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              <span>{refreshing ? "↻ Refreshing..." : "↻ Refresh"}</span>
            </button>
          </div>
        </div>

        {/* Error Banner */}
        {error && (
          <div
            style={{
              background: "#fef2f2",
              border: "1px solid #fecaca",
              color: "#991b1b",
              padding: "12px 16px",
              borderRadius: 12,
              fontSize: 13.5,
            }}
          >
            {error}
          </div>
        )}

        {/* High-Visibility Action Required Banner (renders when > 0 alerts exist) */}
        {!loading && totalAlerts > 0 && (
          <div
            style={{
              background: "linear-gradient(135deg, #fff5ff 0%, #fff9f5 100%)",
              border: "2px solid #f0abfc",
              borderRadius: 16,
              padding: "16px 20px",
              boxShadow: "0 8px 24px rgba(192, 38, 211, 0.10)",
              display: "flex",
              flexDirection: "column",
              gap: 14,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: 10,
                    background: "linear-gradient(135deg, #ef4444, #d946ef)",
                    color: "#ffffff",
                    display: "grid",
                    placeItems: "center",
                    fontSize: 16,
                    fontWeight: 800,
                    boxShadow: "0 4px 10px rgba(217, 70, 239, 0.30)",
                  }}
                >
                  !
                </span>
                <div>
                  <div style={{ fontSize: 15, fontWeight: 800, color: "#2b0d33" }}>
                    Action Required
                  </div>
                  <div style={{ fontSize: 12.5, color: "#7a3b82" }}>
                    {totalAlerts} {totalAlerts === 1 ? "item needs" : "items need"} your immediate attention
                  </div>
                </div>
              </div>
              <span
                style={{
                  fontSize: 11.5,
                  fontWeight: 800,
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                  background: "#ef4444",
                  color: "#ffffff",
                  padding: "4px 11px",
                  borderRadius: 999,
                }}
              >
                {totalAlerts} Pending
              </span>
            </div>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                gap: 12,
              }}
            >
              {(alerts.unassigned_orders_count || 0) > 0 && (
                <Link
                  to="/owner/m/orders"
                  style={{
                    textDecoration: "none",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: 12,
                    background: "#ffffff",
                    border: "1.5px solid #f0abfc",
                    borderLeft: "5px solid #d946ef",
                    borderRadius: 12,
                    padding: "12px 14px",
                    color: "#2b0d33",
                    boxShadow: "0 2px 8px rgba(217, 70, 239, 0.08)",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span style={{ fontSize: 20 }}>🔔</span>
                    <div>
                      <div style={{ fontSize: 13.5, fontWeight: 800, color: "#86198f" }}>
                        {alerts.unassigned_orders_count} New / Unassigned Orders
                      </div>
                      <div style={{ fontSize: 12, color: "#6b7280" }}>Open Orders Queue →</div>
                    </div>
                  </div>
                </Link>
              )}

              {(alerts.pending_faq_suggestions_count || 0) > 0 && (
                <Link
                  to="/owner/knowledge"
                  style={{
                    textDecoration: "none",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: 12,
                    background: "#ffffff",
                    border: "1.5px solid #c4b5fd",
                    borderLeft: "5px solid #7c3aed",
                    borderRadius: 12,
                    padding: "12px 14px",
                    color: "#2e1065",
                    boxShadow: "0 2px 8px rgba(124, 58, 237, 0.08)",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span style={{ fontSize: 20 }}>✨</span>
                    <div>
                      <div style={{ fontSize: 13.5, fontWeight: 800, color: "#5b21b6" }}>
                        {alerts.pending_faq_suggestions_count} Pending AI FAQs
                      </div>
                      <div style={{ fontSize: 12, color: "#6b7280" }}>Review & Approve FAQs →</div>
                    </div>
                  </div>
                </Link>
              )}

              {(alerts.low_stock_items_count || 0) > 0 && (
                <Link
                  to="/owner/m/inventory"
                  style={{
                    textDecoration: "none",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: 12,
                    background: "#ffffff",
                    border: "1.5px solid #fdba74",
                    borderLeft: "5px solid #ea580c",
                    borderRadius: 12,
                    padding: "12px 14px",
                    color: "#431407",
                    boxShadow: "0 2px 8px rgba(234, 88, 12, 0.08)",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span style={{ fontSize: 20 }}>⚠️</span>
                    <div>
                      <div style={{ fontSize: 13.5, fontWeight: 800, color: "#c2410c" }}>
                        {alerts.low_stock_items_count} Low Stock Items
                      </div>
                      <div style={{ fontSize: 12, color: "#6b7280" }}>Restock Inventory →</div>
                    </div>
                  </div>
                </Link>
              )}
            </div>
          </div>
        )}

        {/* 4 Executive KPI Cards */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(230px, 1fr))",
            gap: 16,
          }}
        >
          {/* Card 1: Revenue */}
          <div style={cardStyle}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: "#7f7288" }}>Revenue</span>
              <span
                style={{
                  width: 34,
                  height: 34,
                  borderRadius: 10,
                  background: "#fdf2ff",
                  display: "grid",
                  placeItems: "center",
                  fontSize: 16,
                }}
              >
                💰
              </span>
            </div>
            <div style={{ fontSize: 27, fontWeight: 800, color: "#211426", letterSpacing: "-0.02em" }}>
              {loading ? "—" : fmtCurrency(kpis.revenue)}
            </div>
            <div style={{ marginTop: 8, fontSize: 12.5, color: "#7f7288" }}>
              Avg Order Value:{" "}
              <strong style={{ color: "#3d2447" }}>
                {loading ? "—" : fmtCurrency(kpis.avg_order_value)}
              </strong>
            </div>
          </div>

          {/* Card 2: Orders */}
          <div style={cardStyle}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: "#7f7288" }}>Orders</span>
              <span
                style={{
                  width: 34,
                  height: 34,
                  borderRadius: 10,
                  background: "#f5f3ff",
                  display: "grid",
                  placeItems: "center",
                  fontSize: 16,
                }}
              >
                🧾
              </span>
            </div>
            <div style={{ fontSize: 27, fontWeight: 800, color: "#211426", letterSpacing: "-0.02em" }}>
              {loading ? "—" : Number(kpis.total_orders || 0).toLocaleString()}
            </div>
            <div style={{ marginTop: 8, fontSize: 12.5, color: "#7f7288", display: "flex", gap: 10, flexWrap: "wrap" }}>
              <span>
                <strong style={{ color: "#c2410c" }}>{kpis.active_orders ?? 0}</strong> Active
              </span>
              <span>·</span>
              <span>
                <strong style={{ color: "#047857" }}>{kpis.completed_orders ?? 0}</strong> Completed
              </span>
              {(kpis.cancelled_orders || 0) > 0 && (
                <>
                  <span>·</span>
                  <span>
                    <strong style={{ color: "#b91c1c" }}>{kpis.cancelled_orders}</strong> Cancelled
                  </span>
                </>
              )}
            </div>
          </div>

          {/* Card 3: Live Floor & Tables */}
          <div style={cardStyle}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: "#7f7288" }}>Live Floor & Tables</span>
              <span
                style={{
                  width: 34,
                  height: 34,
                  borderRadius: 10,
                  background: "#ecfdf5",
                  display: "grid",
                  placeItems: "center",
                  fontSize: 16,
                }}
              >
                🪑
              </span>
            </div>
            <div style={{ fontSize: 27, fontWeight: 800, color: "#211426", letterSpacing: "-0.02em" }}>
              {loading ? "—" : `${tables.tables_occupied ?? 0} / ${tables.tables_total ?? 0}`}
              <span style={{ fontSize: 13, fontWeight: 600, color: "#7f7288", marginLeft: 6 }}>
                Occupied
              </span>
            </div>
            <div style={{ marginTop: 8, fontSize: 12.5, color: "#7f7288", display: "flex", gap: 10 }}>
              <span>
                <strong style={{ color: "#047857" }}>{tables.tables_available ?? 0}</strong> Available
              </span>
              <span>·</span>
              <span>
                <strong style={{ color: "#b45309" }}>{tables.tables_reserved ?? 0}</strong> Reserved
              </span>
            </div>
          </div>

          {/* Card 4: AI Agent Performance */}
          <div style={cardStyle}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: "#7f7288" }}>AI Agent Performance</span>
              <span
                style={{
                  width: 34,
                  height: 34,
                  borderRadius: 10,
                  background: "#fdf2ff",
                  display: "grid",
                  placeItems: "center",
                  fontSize: 16,
                }}
              >
                🤖
              </span>
            </div>
            <div style={{ fontSize: 27, fontWeight: 800, color: "#211426", letterSpacing: "-0.02em" }}>
              {loading ? "—" : Number(kpis.ai_conversations_count || 0).toLocaleString()}
              <span style={{ fontSize: 13, fontWeight: 600, color: "#7f7288", marginLeft: 6 }}>
                Chats
              </span>
            </div>
            <div style={{ marginTop: 8, fontSize: 12.5, color: "#7f7288" }}>
              AI-Generated Orders:{" "}
              <strong style={{ color: "#9c1e9c" }}>
                {loading ? "—" : kpis.ai_orders_count ?? 0}
              </strong>
            </div>
          </div>
        </div>

        {/* Charts & Insights Row (2-Column Grid — ~65% / 35%) */}
        <div className="rest-exec-charts-grid">
          {/* Left: Revenue & Orders Trend */}
          <div style={cardStyle}>
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                justifyContent: "space-between",
                alignItems: "center",
                gap: 10,
                marginBottom: 14,
              }}
            >
              <div>
                <h2 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: "#211426" }}>
                  {chartMetric === "revenue" ? "Revenue Trend" : "Orders Trend"}
                </h2>
                <p style={{ margin: "2px 0 0", fontSize: 12.5, color: "#7f7288" }}>
                  {period === "today"
                    ? "Hourly breakdown for today"
                    : period === "7d"
                    ? "Daily performance over the last 7 days"
                    : "Daily performance over the last 30 days"}
                </p>
              </div>

              <div
                style={{
                  display: "inline-flex",
                  background: "#faf5fb",
                  border: "1px solid #eedff0",
                  borderRadius: 10,
                  padding: 3,
                  gap: 3,
                }}
              >
                <button
                  type="button"
                  onClick={() => setChartMetric("revenue")}
                  style={{
                    border: "none",
                    borderRadius: 7,
                    padding: "5px 11px",
                    fontSize: 12,
                    fontWeight: chartMetric === "revenue" ? 700 : 500,
                    background: chartMetric === "revenue" ? "#ff77ff" : "transparent",
                    color: chartMetric === "revenue" ? "#240729" : "#6f6278",
                    cursor: "pointer",
                  }}
                >
                  Revenue (Rs.)
                </button>
                <button
                  type="button"
                  onClick={() => setChartMetric("orders")}
                  style={{
                    border: "none",
                    borderRadius: 7,
                    padding: "5px 11px",
                    fontSize: 12,
                    fontWeight: chartMetric === "orders" ? 700 : 500,
                    background: chartMetric === "orders" ? "#ff77ff" : "transparent",
                    color: chartMetric === "orders" ? "#240729" : "#6f6278",
                    cursor: "pointer",
                  }}
                >
                  Orders
                </button>
              </div>
            </div>

            {loading ? (
              <div style={{ height: 220, display: "grid", placeItems: "center", color: "#998da3", fontSize: 13.5 }}>
                Loading chart...
              </div>
            ) : (
              <TrendChart trend={trend} metric={chartMetric} period={period} />
            )}
          </div>

          {/* Right: Top Selling Menu Items + Order Channels */}
          <div style={{ ...cardStyle, display: "flex", flexDirection: "column", justifyContent: "space-between", gap: 18 }}>
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
                <div>
                  <h2 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: "#211426" }}>
                    Top Selling Menu Items
                  </h2>
                  <p style={{ margin: "2px 0 0", fontSize: 12.5, color: "#7f7288" }}>
                    Top 5 dishes by quantity ordered
                  </p>
                </div>
                <Link
                  to="/owner/m/menu"
                  style={{ fontSize: 12.5, fontWeight: 600, color: "#b324b3", textDecoration: "none" }}
                >
                  Menu →
                </Link>
              </div>

              {loading ? (
                <div style={{ padding: "24px 0", textAlign: "center", color: "#998da3", fontSize: 13 }}>
                  Loading top items...
                </div>
              ) : topItems.length === 0 ? (
                <div
                  style={{
                    padding: "24px 12px",
                    textAlign: "center",
                    background: "#faf7fb",
                    borderRadius: 12,
                    color: "#8e8097",
                    fontSize: 13,
                  }}
                >
                  No menu items sold in this period yet.
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  {topItems.map((item, idx) => {
                    const pct = Math.max(8, Math.round((Number(item.quantity || 0) / maxTopQty) * 100));
                    return (
                      <div key={`${item.name}-${idx}`}>
                        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 5 }}>
                          <span style={{ fontWeight: 600, color: "#28192e", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: "60%" }}>
                            {idx + 1}. {item.name}
                          </span>
                          <span style={{ color: "#6f6278", fontSize: 12.5 }}>
                            <strong style={{ color: "#28192e" }}>{item.quantity}</strong> sold · {fmtCurrency(item.revenue)}
                          </span>
                        </div>
                        <div style={{ height: 7, borderRadius: 999, background: "#f4ecf6", overflow: "hidden" }}>
                          <div
                            style={{
                              width: `${pct}%`,
                              height: "100%",
                              borderRadius: 999,
                              background: "linear-gradient(90deg, #ff77ff 0%, #d946ef 100%)",
                            }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Order Channels Breakdown */}
            <div style={{ borderTop: "1px solid #f2e9f5", paddingTop: 14 }}>
              <div style={{ fontSize: 12.5, fontWeight: 700, color: "#7f7288", marginBottom: 10, textTransform: "uppercase", letterSpacing: "0.04em" }}>
                Order Channels
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 8 }}>
                {channelPills.map((ch) => (
                  <div
                    key={ch.key}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      background: "#faf6fc",
                      border: "1px solid #f0e4f3",
                      borderRadius: 10,
                      padding: "8px 11px",
                      fontSize: 12.5,
                    }}
                  >
                    <span style={{ color: "#4e3c57", fontWeight: 500 }}>
                      {ch.icon} {ch.label}
                    </span>
                    <strong style={{ color: "#211426", fontWeight: 800 }}>{ch.count}</strong>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Live Snapshot Row (2-Column Grid) */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
            gap: 16,
            alignItems: "stretch",
          }}
        >
          {/* Left: Recent Orders (Latest 5) */}
          <div style={cardStyle}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
              <div>
                <h2 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: "#211426" }}>
                  Recent Orders
                </h2>
                <p style={{ margin: "2px 0 0", fontSize: 12.5, color: "#7f7288" }}>
                  Latest 5 incoming restaurant orders
                </p>
              </div>
              <Link
                to="/owner/m/orders"
                style={{
                  fontSize: 13,
                  fontWeight: 700,
                  color: "#b324b3",
                  textDecoration: "none",
                }}
              >
                View All Orders →
              </Link>
            </div>

            {loading ? (
              <div style={{ padding: "28px 0", textAlign: "center", color: "#998da3", fontSize: 13.5 }}>
                Loading recent orders...
              </div>
            ) : recentOrders.length === 0 ? (
              <div
                style={{
                  padding: "32px 16px",
                  textAlign: "center",
                  background: "#faf7fb",
                  borderRadius: 12,
                  color: "#8e8097",
                  fontSize: 13.5,
                }}
              >
                No orders yet. Incoming AI & dashboard orders will appear here live.
              </div>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid #f1e7f4", textAlign: "left", color: "#8e8097", fontSize: 12 }}>
                      <th style={{ padding: "8px 6px", fontWeight: 600 }}>Order #</th>
                      <th style={{ padding: "8px 6px", fontWeight: 600 }}>Customer</th>
                      <th style={{ padding: "8px 6px", fontWeight: 600 }}>Amount</th>
                      <th style={{ padding: "8px 6px", fontWeight: 600, textAlign: "right" }}>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recentOrders.map((ord) => {
                      const st = STATUS_STYLE[String(ord.status || "").toLowerCase()] || {
                        bg: "#f3f4f6",
                        color: "#374151",
                        border: "#e5e7eb",
                        label: ord.status || "Unknown",
                      };
                      return (
                        <tr key={ord.id} style={{ borderBottom: "1px solid #f7f1f9" }}>
                          <td style={{ padding: "11px 6px", fontWeight: 700, color: "#24152a", whiteSpace: "nowrap" }}>
                            {ord.order_number}
                            <div style={{ fontSize: 11, fontWeight: 400, color: "#998da3" }}>
                              {fmtShortTime(ord.created_at)}
                            </div>
                          </td>
                          <td style={{ padding: "11px 6px", color: "#3d2e45", fontWeight: 500 }}>
                            {ord.customer_name || "Walk-in Customer"}
                          </td>
                          <td style={{ padding: "11px 6px", fontWeight: 700, color: "#24152a", whiteSpace: "nowrap" }}>
                            {fmtCurrency(ord.total_amount)}
                          </td>
                          <td style={{ padding: "11px 6px", textAlign: "right" }}>
                            <span
                              style={{
                                display: "inline-block",
                                padding: "3px 10px",
                                borderRadius: 999,
                                fontSize: 11.5,
                                fontWeight: 700,
                                background: st.bg,
                                color: st.color,
                                border: `1px solid ${st.border}`,
                              }}
                            >
                              {st.label}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Right: Quick Operations & Floor Summary */}
          <div style={{ ...cardStyle, display: "flex", flexDirection: "column", justifyContent: "space-between", gap: 18 }}>
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
                <div>
                  <h2 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: "#211426" }}>
                    Floor & Table Status
                  </h2>
                  <p style={{ margin: "2px 0 0", fontSize: 12.5, color: "#7f7288" }}>
                    Real-time dining room occupancy
                  </p>
                </div>
                <Link
                  to="/owner/tables"
                  style={{ fontSize: 13, fontWeight: 700, color: "#b324b3", textDecoration: "none" }}
                >
                  Open Floor Plan →
                </Link>
              </div>

              {totalTables === 0 ? (
                <div
                  style={{
                    padding: "16px",
                    background: "#faf7fb",
                    borderRadius: 12,
                    fontSize: 13,
                    color: "#7f7288",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    gap: 10,
                  }}
                >
                  <span>No dining tables configured yet.</span>
                  <Link
                    to="/owner/tables"
                    style={{
                      background: "#ff77ff",
                      color: "#240729",
                      textDecoration: "none",
                      padding: "6px 12px",
                      borderRadius: 8,
                      fontWeight: 700,
                      fontSize: 12,
                      whiteSpace: "nowrap",
                    }}
                  >
                    + Add Tables
                  </Link>
                </div>
              ) : (
                <div>
                  {/* Stacked Progress Bar */}
                  <div
                    style={{
                      height: 12,
                      borderRadius: 999,
                      background: "#f1e8f5",
                      overflow: "hidden",
                      display: "flex",
                    }}
                  >
                    {occPct > 0 && (
                      <div style={{ width: `${occPct}%`, background: "#e040e0" }} title={`Occupied: ${tables.tables_occupied}`} />
                    )}
                    {resPct > 0 && (
                      <div style={{ width: `${resPct}%`, background: "#f59e0b" }} title={`Reserved: ${tables.tables_reserved}`} />
                    )}
                    {availPct > 0 && (
                      <div style={{ width: `${availPct}%`, background: "#10b981" }} title={`Available: ${tables.tables_available}`} />
                    )}
                  </div>

                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "repeat(3, 1fr)",
                      gap: 10,
                      marginTop: 12,
                    }}
                  >
                    <div style={{ background: "#fdf2ff", borderRadius: 10, padding: "10px 12px" }}>
                      <div style={{ fontSize: 11.5, color: "#8c2b8c", fontWeight: 600 }}>Occupied</div>
                      <div style={{ fontSize: 20, fontWeight: 800, color: "#211426", marginTop: 2 }}>
                        {tables.tables_occupied ?? 0}
                      </div>
                    </div>
                    <div style={{ background: "#fffbeb", borderRadius: 10, padding: "10px 12px" }}>
                      <div style={{ fontSize: 11.5, color: "#b45309", fontWeight: 600 }}>Reserved</div>
                      <div style={{ fontSize: 20, fontWeight: 800, color: "#211426", marginTop: 2 }}>
                        {tables.tables_reserved ?? 0}
                      </div>
                    </div>
                    <div style={{ background: "#ecfdf5", borderRadius: 10, padding: "10px 12px" }}>
                      <div style={{ fontSize: 11.5, color: "#047857", fontWeight: 600 }}>Available</div>
                      <div style={{ fontSize: 20, fontWeight: 800, color: "#211426", marginTop: 2 }}>
                        {tables.tables_available ?? 0}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* 4 Clean 1-Click Operational Shortcuts */}
            <div style={{ borderTop: "1px solid #f2e9f5", paddingTop: 14 }}>
              <div style={{ fontSize: 12.5, fontWeight: 700, color: "#7f7288", marginBottom: 10, textTransform: "uppercase", letterSpacing: "0.04em" }}>
                Quick Operations
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 10 }}>
                {[
                  { to: "/owner/m/orders", icon: "📦", title: "Orders", sub: "Manage live orders" },
                  { to: "/owner/m/menu", icon: "🍽️", title: "Menu", sub: "Items & pricing" },
                  { to: "/owner/reports", icon: "📊", title: "Reports", sub: "CSV & PDF exports" },
                  { to: "/owner/ai-agent", icon: "🎙️", title: "AI Settings", sub: "Voice & prompts" },
                ].map((item) => (
                  <Link
                    key={item.to}
                    to={item.to}
                    style={{
                      textDecoration: "none",
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                      padding: "11px 12px",
                      borderRadius: 12,
                      border: "1px solid #efe4f2",
                      background: "#ffffff",
                      color: "#211426",
                      transition: "border-color 0.15s ease, background 0.15s ease",
                    }}
                  >
                    <span
                      style={{
                        width: 34,
                        height: 34,
                        borderRadius: 9,
                        background: "#fdf2ff",
                        display: "grid",
                        placeItems: "center",
                        fontSize: 16,
                        flexShrink: 0,
                      }}
                    >
                      {item.icon}
                    </span>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontSize: 13.5, fontWeight: 700, color: "#211426" }}>
                        {item.title}
                      </div>
                      <div style={{ fontSize: 11.5, color: "#8c7d96", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                        {item.sub}
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </OwnerLayout>
  );
}
