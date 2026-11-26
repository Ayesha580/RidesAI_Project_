import { useCallback, useEffect, useState } from "react";
import OwnerLayout from "../owner/components/OwnerLayout";
import StaffLayout from "../staff/components/StaffLayout";
import { restaurantReportsApi } from "../api/operationsApi";

const ACCENT = "#ff77ff";

const RANGE_OPTIONS = [
  { key: "today", label: "Today" },
  { key: "7d", label: "Last 7 Days" },
  { key: "30d", label: "Last 30 Days" },
  { key: "all", label: "All Time" },
];

const ORDER_TYPE_COLORS = {
  dine_in: "#8b5cf6",
  takeaway: "#f59e0b",
  delivery: "#0284c7",
};

const CHANNEL_COLORS = {
  POS: "#0f172a",
  "WhatsApp AI": "#10b981",
  "Website Voice AI": "#c026d3",
};

function formatMoney(val) {
  const num = Number(val || 0);
  return `Rs. ${num.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function formatShortDate(iso) {
  if (!iso) return "";
  try {
    const parts = iso.split("-");
    if (parts.length === 3) {
      const d = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
      return d.toLocaleDateString([], { month: "short", day: "numeric" });
    }
    return iso;
  } catch {
    return iso;
  }
}

export default function RestaurantReportsAnalytics({ staff = false }) {
  const Layout = staff ? StaffLayout : OwnerLayout;

  const [range, setRange] = useState("30d");
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState("");
  const [data, setData] = useState(null);

  const loadReports = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await restaurantReportsApi.getSummary({ range });
      setData(res.data || null);
    } catch (err) {
      setError(
        err?.response?.data?.detail || "Could not load restaurant financial analytics."
      );
    } finally {
      setLoading(false);
    }
  }, [range]);

  useEffect(() => {
    loadReports();
  }, [loadReports]);

  const handleExportCsv = async () => {
    setExporting(true);
    setError("");
    try {
      const res = await restaurantReportsApi.downloadCsv({ range });
      const blob = new Blob([res.data], { type: "text/csv;charset=utf-8;" });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `restaurant_financial_report_${range}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err?.response?.data?.detail || "Failed to export CSV report.");
    } finally {
      setExporting(false);
    }
  };

  const kpis = data?.kpis || {
    net_revenue: 0,
    total_orders: 0,
    cancelled_orders: 0,
    avg_order_value: 0,
    delivery_fees_total: 0,
    estimated_cogs: 0,
    gross_profit: 0,
    gross_margin_pct: 0,
    unsettled_cod_total: 0,
  };

  const dailyTrend = data?.daily_trend || [];
  const maxDailyRevenue = Math.max(...dailyTrend.map((d) => Number(d.revenue || 0)), 1);

  const peakHours = data?.peak_hours || [];
  const maxHourOrders = Math.max(...peakHours.map((h) => Number(h.orders || 0)), 1);

  const kpiCards = [
    {
      label: "Net Revenue",
      value: formatMoney(kpis.net_revenue),
      sub: `${kpis.total_orders} active orders (${kpis.cancelled_orders} cancelled)`,
      accent: "#0f172a",
      highlight: true,
    },
    {
      label: "Gross Profit & Margin",
      value: formatMoney(kpis.gross_profit),
      sub: `${kpis.gross_margin_pct || 0}% gross margin`,
      accent: "#059669",
    },
    {
      label: "Avg Order Value",
      value: formatMoney(kpis.avg_order_value),
      sub: `${kpis.total_orders} completed/active orders`,
      accent: "#6366f1",
    },
    {
      label: "Estimated Food Cost (COGS)",
      value: formatMoney(kpis.estimated_cogs),
      sub: "Calculated from dish recipes",
      accent: "#d97706",
    },
    {
      label: "Delivery Fees & Pending COD",
      value: formatMoney(kpis.delivery_fees_total),
      sub: `Pending COD: ${formatMoney(kpis.unsettled_cod_total)}`,
      accent: "#c026d3",
    },
  ];

  return (
    <Layout title="Reports & Analytics">
      <div style={{ maxWidth: 1280, margin: "0 auto", padding: "8px 4px 40px" }}>
        {/* Header Controls */}
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
              Reports &amp; Financial Analytics
            </h2>
            <p style={{ margin: "4px 0 0", fontSize: 13, color: "#64748b" }}>
              Revenue, recipe-based food cost &amp; margins, channel split, and peak ordering hours.
            </p>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8 }}>
            <div
              style={{
                display: "inline-flex",
                background: "#fff",
                border: "1px solid #e2e8f0",
                borderRadius: 10,
                padding: 3,
                gap: 2,
              }}
            >
              {RANGE_OPTIONS.map((opt) => (
                <button
                  key={opt.key}
                  type="button"
                  onClick={() => setRange(opt.key)}
                  style={{
                    border: "none",
                    borderRadius: 7,
                    padding: "6px 12px",
                    fontSize: 12,
                    fontWeight: 700,
                    cursor: "pointer",
                    background: range === opt.key ? "#0f172a" : "transparent",
                    color: range === opt.key ? "#fff" : "#475569",
                  }}
                >
                  {opt.label}
                </button>
              ))}
            </div>
            <button
              type="button"
              disabled={exporting}
              onClick={handleExportCsv}
              style={{
                border: `1.5px solid ${ACCENT}`,
                background: "#fdf4ff",
                color: "#86198f",
                borderRadius: 10,
                padding: "8px 14px",
                fontSize: 12,
                fontWeight: 800,
                cursor: exporting ? "wait" : "pointer",
              }}
            >
              {exporting ? "Exporting..." : "📥 Export CSV"}
            </button>
          </div>
        </div>

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
            gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
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
              <div style={{ fontSize: 23, fontWeight: 800, color: "#0f172a", lineHeight: 1.15 }}>
                {loading ? "—" : card.value}
              </div>
              <div style={{ fontSize: 11, color: card.accent, fontWeight: 600, marginTop: 6 }}>
                {card.sub}
              </div>
            </div>
          ))}
        </div>

        {loading ? (
          <div
            style={{
              background: "#fff",
              border: "1px solid #e2e8f0",
              borderRadius: 14,
              padding: 48,
              textAlign: "center",
              color: "#64748b",
            }}
          >
            Calculating financial analytics...
          </div>
        ) : (
          <div style={{ display: "grid", gap: 16 }}>
            {/* Daily Revenue Trend + Split Cards */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
                gap: 16,
              }}
            >
              {/* Daily Revenue Trend */}
              <div
                style={{
                  background: "#ffffff",
                  border: "1px solid #e2e8f0",
                  borderRadius: 14,
                  padding: 18,
                  boxShadow: "0 1px 3px rgba(15, 23, 42, 0.04)",
                }}
              >
                <div style={{ fontSize: 15, fontWeight: 800, color: "#0f172a", marginBottom: 4 }}>
                  📈 Daily Revenue Trend
                </div>
                <div style={{ fontSize: 12, color: "#64748b", marginBottom: 14 }}>
                  Revenue &amp; estimated gross profit per day
                </div>
                {dailyTrend.length === 0 ? (
                  <div style={{ padding: "32px 0", textAlign: "center", color: "#94a3b8", fontSize: 13 }}>
                    No non-cancelled orders in this period.
                  </div>
                ) : (
                  <div
                    style={{
                      display: "flex",
                      alignItems: "flex-end",
                      gap: 8,
                      height: 170,
                      paddingTop: 12,
                      overflowX: "auto",
                    }}
                  >
                    {dailyTrend.slice(-14).map((day) => {
                      const pct = Math.max(8, Math.round((Number(day.revenue || 0) / maxDailyRevenue) * 100));
                      return (
                        <div
                          key={day.date}
                          title={`${day.date}: ${formatMoney(day.revenue)} (${day.orders} orders, Est. Profit ${formatMoney(day.estimated_profit)})`}
                          style={{
                            flex: 1,
                            minWidth: 30,
                            display: "flex",
                            flexDirection: "column",
                            alignItems: "center",
                            height: "100%",
                            justifyContent: "flex-end",
                            gap: 6,
                          }}
                        >
                          <div style={{ fontSize: 10, fontWeight: 700, color: "#475569" }}>
                            {day.orders}
                          </div>
                          <div
                            style={{
                              width: "100%",
                              maxWidth: 34,
                              height: `${pct}%`,
                              borderRadius: "8px 8px 4px 4px",
                              background: `linear-gradient(180deg, ${ACCENT} 0%, #c026d3 100%)`,
                              minHeight: 8,
                            }}
                          />
                          <div style={{ fontSize: 10, color: "#64748b", whiteSpace: "nowrap" }}>
                            {formatShortDate(day.date)}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Order Type & Channel Splits */}
              <div
                style={{
                  background: "#ffffff",
                  border: "1px solid #e2e8f0",
                  borderRadius: 14,
                  padding: 18,
                  display: "grid",
                  gap: 18,
                  boxShadow: "0 1px 3px rgba(15, 23, 42, 0.04)",
                }}
              >
                {/* Order Type Breakdown */}
                <div>
                  <div style={{ fontSize: 14, fontWeight: 800, color: "#0f172a", marginBottom: 10 }}>
                    🍽️ Order Type Split
                  </div>
                  <div style={{ display: "grid", gap: 9 }}>
                    {(data?.order_type_breakdown || []).map((row) => (
                      <div key={row.key}>
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            fontSize: 12,
                            fontWeight: 700,
                            marginBottom: 4,
                            color: "#1e293b",
                          }}
                        >
                          <span>
                            {row.label} ({row.orders})
                          </span>
                          <span>
                            {formatMoney(row.revenue)} • {row.share_pct}%
                          </span>
                        </div>
                        <div style={{ height: 8, background: "#f1f5f9", borderRadius: 999, overflow: "hidden" }}>
                          <div
                            style={{
                              width: `${Math.min(100, row.share_pct || 0)}%`,
                              height: "100%",
                              background: ORDER_TYPE_COLORS[row.key] || "#6366f1",
                              borderRadius: 999,
                            }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Channel Breakdown */}
                <div>
                  <div style={{ fontSize: 14, fontWeight: 800, color: "#0f172a", marginBottom: 10 }}>
                    📡 Channel Split (POS vs AI)
                  </div>
                  <div style={{ display: "grid", gap: 9 }}>
                    {(data?.channel_breakdown || []).map((row) => (
                      <div key={row.channel}>
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            fontSize: 12,
                            fontWeight: 700,
                            marginBottom: 4,
                            color: "#1e293b",
                          }}
                        >
                          <span>
                            {row.channel} ({row.orders})
                          </span>
                          <span>
                            {formatMoney(row.revenue)} • {row.share_pct}%
                          </span>
                        </div>
                        <div style={{ height: 8, background: "#f1f5f9", borderRadius: 999, overflow: "hidden" }}>
                          <div
                            style={{
                              width: `${Math.min(100, row.share_pct || 0)}%`,
                              height: "100%",
                              background: CHANNEL_COLORS[row.channel] || "#c026d3",
                              borderRadius: 999,
                            }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Peak Hours Strip */}
            <div
              style={{
                background: "#ffffff",
                border: "1px solid #e2e8f0",
                borderRadius: 14,
                padding: 18,
                boxShadow: "0 1px 3px rgba(15, 23, 42, 0.04)",
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  flexWrap: "wrap",
                  gap: 8,
                  marginBottom: 12,
                }}
              >
                <div>
                  <div style={{ fontSize: 15, fontWeight: 800, color: "#0f172a" }}>
                    ⏰ Peak Ordering Hours (00:00 – 23:00)
                  </div>
                  <div style={{ fontSize: 12, color: "#64748b" }}>
                    Hourly order distribution to optimize kitchen &amp; rider shifts
                  </div>
                </div>
                {data?.peak_hour_label && (
                  <span
                    style={{
                      padding: "4px 10px",
                      borderRadius: 999,
                      fontSize: 12,
                      fontWeight: 800,
                      background: "#fdf4ff",
                      color: "#86198f",
                      border: `1px solid ${ACCENT}`,
                    }}
                  >
                    🔥 Busiest Hour: {data.peak_hour_label}
                  </span>
                )}
              </div>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(24, minmax(18px, 1fr))",
                  gap: 4,
                  alignItems: "end",
                  height: 92,
                  overflowX: "auto",
                }}
              >
                {peakHours.map((h) => {
                  const pct = h.orders > 0 ? Math.max(14, Math.round((h.orders / maxHourOrders) * 100)) : 6;
                  return (
                    <div
                      key={h.hour}
                      title={`${h.label}: ${h.orders} orders (${formatMoney(h.revenue)})`}
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        height: "100%",
                        justifyContent: "flex-end",
                        gap: 4,
                      }}
                    >
                      <div
                        style={{
                          width: "100%",
                          height: `${pct}%`,
                          borderRadius: 4,
                          background: h.is_peak
                            ? "#c026d3"
                            : h.orders > 0
                            ? "#94a3b8"
                            : "#e2e8f0",
                        }}
                      />
                      <span style={{ fontSize: 9, color: h.is_peak ? "#86198f" : "#94a3b8", fontWeight: h.is_peak ? 800 : 500 }}>
                        {h.hour}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Top Selling Dishes & Profitability Table */}
            <div
              style={{
                background: "#ffffff",
                border: "1px solid #e2e8f0",
                borderRadius: 14,
                overflow: "hidden",
                boxShadow: "0 1px 3px rgba(15, 23, 42, 0.04)",
              }}
            >
              <div style={{ padding: "14px 18px", borderBottom: "1px solid #e2e8f0" }}>
                <div style={{ fontSize: 15, fontWeight: 800, color: "#0f172a" }}>
                  🏆 Top Selling Dishes &amp; Margin Profitability
                </div>
                <div style={{ fontSize: 12, color: "#64748b" }}>
                  Top 15 dishes ranked by revenue with recipe-derived food cost &amp; gross profit margin
                </div>
              </div>
              {(data?.top_dishes || []).length === 0 ? (
                <div style={{ padding: 36, textAlign: "center", color: "#64748b", fontSize: 13 }}>
                  No dish sales recorded for this date range.
                </div>
              ) : (
                <div style={{ overflowX: "auto" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                    <thead>
                      <tr style={{ background: "#f8fafc", textAlign: "left", color: "#475569" }}>
                        <th style={{ padding: "12px 18px", fontWeight: 700 }}>Dish Name</th>
                        <th style={{ padding: "12px 14px", fontWeight: 700 }}>Qty Sold</th>
                        <th style={{ padding: "12px 14px", fontWeight: 700 }}>Revenue</th>
                        <th style={{ padding: "12px 14px", fontWeight: 700 }}>Est. Food Cost</th>
                        <th style={{ padding: "12px 14px", fontWeight: 700 }}>Gross Profit</th>
                        <th style={{ padding: "12px 18px", fontWeight: 700, textAlign: "right" }}>
                          Margin %
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {(data?.top_dishes || []).map((dish) => {
                        const margin = Number(dish.margin_pct || 0);
                        const marginColor =
                          margin >= 60 ? "#047857" : margin >= 35 ? "#b45309" : "#b91c1c";
                        const marginBg =
                          margin >= 60 ? "#ecfdf5" : margin >= 35 ? "#fffbeb" : "#fef2f2";
                        return (
                          <tr
                            key={dish.dish_name}
                            style={{ borderTop: "1px solid #f1f5f9", color: "#0f172a" }}
                          >
                            <td style={{ padding: "12px 18px", fontWeight: 700 }}>
                              {dish.dish_name}
                            </td>
                            <td style={{ padding: "12px 14px", fontWeight: 600 }}>
                              {dish.qty_sold}
                            </td>
                            <td style={{ padding: "12px 14px", fontWeight: 700 }}>
                              {formatMoney(dish.revenue)}
                            </td>
                            <td style={{ padding: "12px 14px", color: "#64748b" }}>
                              {formatMoney(dish.estimated_cogs)}
                            </td>
                            <td style={{ padding: "12px 14px", fontWeight: 700, color: "#059669" }}>
                              {formatMoney(dish.gross_profit)}
                            </td>
                            <td style={{ padding: "12px 18px", textAlign: "right" }}>
                              <span
                                style={{
                                  padding: "3px 10px",
                                  borderRadius: 999,
                                  fontSize: 12,
                                  fontWeight: 800,
                                  background: marginBg,
                                  color: marginColor,
                                }}
                              >
                                {margin.toFixed(1)}%
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
          </div>
        )}
      </div>
    </Layout>
  );
}
