import { useCallback, useEffect, useMemo, useState } from "react";
import OwnerLayout from "../owner/components/OwnerLayout";
import StaffLayout from "../staff/components/StaffLayout";
import { analyticsApi } from "../api/operationsApi";
import { errorText } from "../api/axiosClient";

const PALETTE = ["#ff77ff", "#8b5cf6", "#ec4899", "#06b6d4", "#10b981", "#f59e0b", "#64748b"];

const RANGES = [
  ["7d", "Last 7 Days"],
  ["30d", "Last 30 Days"],
  ["90d", "Last 90 Days"],
  ["custom", "Custom Range"],
];

function formatRs(val) {
  const num = Number(val || 0);
  return `Rs. ${num.toLocaleString("en-PK", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;
}

function RevenueTrendChart({ series, metric }) {
  const [hoveredIdx, setHoveredIdx] = useState(null);
  const W = 760;
  const H = 250;
  const P = { t: 22, r: 22, b: 36, l: 58 };

  const values = series.map((d) => (metric === "revenue" ? Number(d.revenue || 0) : Number(d.orders_count || 0)));
  const maxVal = Math.max(metric === "revenue" ? 100 : 4, ...values);
  const innerW = W - P.l - P.r;
  const innerH = H - P.t - P.b;

  const xPos = (i) => P.l + (series.length <= 1 ? innerW / 2 : (i * innerW) / (series.length - 1));
  const yPos = (v) => P.t + (1 - v / maxVal) * innerH;

  const pts = series.map((d, i) => [xPos(i), yPos(values[i])]);
  const linePath = pts
    .map(([px, py], i) => {
      if (i === 0) return `M ${px} ${py}`;
      const [prevX, prevY] = pts[i - 1];
      const mid = (prevX + px) / 2;
      return `C ${mid} ${prevY}, ${mid} ${py}, ${px} ${py}`;
    })
    .join(" ");

  const areaPath = pts.length > 0 ? `${linePath} L ${pts[pts.length - 1][0]} ${H - P.b} L ${pts[0][0]} ${H - P.b} Z` : "";
  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((t) => Math.round(maxVal * t));
  const labelStep = Math.max(1, Math.ceil(series.length / 8));
  const activePoint = hoveredIdx !== null && series[hoveredIdx] ? series[hoveredIdx] : null;

  return (
    <div style={{ position: "relative" }}>
      {activePoint && (
        <div
          style={{
            position: "absolute",
            top: 4,
            right: 8,
            background: "#0f172a",
            color: "#fff",
            padding: "8px 12px",
            borderRadius: 10,
            fontSize: 12,
            zIndex: 5,
            boxShadow: "0 6px 18px rgba(15,23,42,0.2)",
          }}
        >
          <div style={{ fontWeight: 700, color: "#ff77ff" }}>{activePoint.label} ({activePoint.date})</div>
          <div>Revenue: <strong>{formatRs(activePoint.revenue)}</strong></div>
          <div>Orders / Bookings: <strong>{activePoint.orders_count}</strong> · AI Chats: <strong>{activePoint.ai_conversations}</strong></div>
        </div>
      )}

      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto", display: "block" }} role="img" aria-label="Revenue and orders trend chart">
        <defs>
          <linearGradient id="ridesAnalyticsGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#ff77ff" stopOpacity="0.34" />
            <stop offset="100%" stopColor="#ff77ff" stopOpacity="0.02" />
          </linearGradient>
        </defs>

        {yTicks.map((tv, idx) => (
          <g key={idx}>
            <line x1={P.l} x2={W - P.r} y1={yPos(tv)} y2={yPos(tv)} stroke="#f1e8f4" strokeDasharray="4 4" />
            <text x={P.l - 8} y={yPos(tv) + 4} textAnchor="end" fontSize="11" fill="#94a3b8">
              {metric === "revenue" ? (tv >= 1000 ? `${(tv / 1000).toFixed(1)}k` : tv) : tv}
            </text>
          </g>
        ))}

        {metric === "revenue" ? (
          <>
            {areaPath && <path d={areaPath} fill="url(#ridesAnalyticsGrad)" />}
            {linePath && <path d={linePath} fill="none" stroke="#e44fe4" strokeWidth="3" strokeLinecap="round" />}
          </>
        ) : (
          series.map((d, i) => {
            const bw = Math.max(8, Math.min(28, innerW / Math.max(1, series.length) - 4));
            const bh = Math.max(2, H - P.b - yPos(values[i]));
            return (
              <rect
                key={d.date}
                x={xPos(i) - bw / 2}
                y={yPos(values[i])}
                width={bw}
                height={bh}
                rx="4"
                fill={hoveredIdx === i ? "#c026d3" : "#ff77ff"}
                opacity={hoveredIdx === i ? 1 : 0.85}
                onMouseEnter={() => setHoveredIdx(i)}
                onMouseLeave={() => setHoveredIdx(null)}
                style={{ cursor: "pointer" }}
              />
            );
          })
        )}

        {pts.map(([px, py], i) => (
          <g key={series[i].date}>
            {metric === "revenue" && (
              <circle
                cx={px}
                cy={py}
                r={hoveredIdx === i ? 6 : 3.5}
                fill="#ffffff"
                stroke="#e44fe4"
                strokeWidth="2.5"
                onMouseEnter={() => setHoveredIdx(i)}
                onMouseLeave={() => setHoveredIdx(null)}
                style={{ cursor: "pointer" }}
              />
            )}
            {(i % labelStep === 0 || i === series.length - 1) && (
              <text x={px} y={H - 10} textAnchor="middle" fontSize="10.5" fill="#94a3b8">
                {series[i].label}
              </text>
            )}
          </g>
        ))}
      </svg>
    </div>
  );
}

function DonutBreakdown({ items, centerLabel }) {
  const total = items.reduce((acc, it) => acc + Number(it.count || 0), 0);
  const R = 52;
  const C = 2 * Math.PI * R;
  let offset = 0;

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 18, flexWrap: "wrap" }}>
      <svg viewBox="0 0 140 140" style={{ width: 132, height: 132, flexShrink: 0 }} role="img" aria-label={centerLabel}>
        <circle cx="70" cy="70" r={R} fill="none" stroke="#f5eff7" strokeWidth="16" />
        {total > 0 &&
          items.map((item, idx) => {
            const val = Number(item.count || 0);
            if (val <= 0) return null;
            const len = (val / total) * C;
            const seg = (
              <circle
                key={item.label}
                cx="70"
                cy="70"
                r={R}
                fill="none"
                stroke={PALETTE[idx % PALETTE.length]}
                strokeWidth="16"
                strokeDasharray={`${Math.max(0, len - 2)} ${C}`}
                strokeDashoffset={-offset}
                transform="rotate(-90 70 70)"
              />
            );
            offset += len;
            return seg;
          })}
        <text x="70" y="67" textAnchor="middle" fontSize="22" fontWeight="800" fill="#0f172a">{total}</text>
        <text x="70" y="84" textAnchor="middle" fontSize="10.5" fill="#94a3b8">{centerLabel}</text>
      </svg>

      <div style={{ flex: 1, minWidth: 150, display: "grid", gap: 7 }}>
        {items.length === 0 || total === 0 ? (
          <p style={{ margin: 0, fontSize: 13, color: "#94a3b8" }}>No activity recorded in this date range.</p>
        ) : (
          items.map((it, idx) => {
            const pct = total > 0 ? Math.round((Number(it.count || 0) / total) * 100) : 0;
            return (
              <div key={it.label} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: 12.5 }}>
                <span style={{ display: "flex", alignItems: "center", gap: 7, color: "#334155", fontWeight: 600 }}>
                  <span style={{ width: 10, height: 10, borderRadius: "50%", background: PALETTE[idx % PALETTE.length], display: "inline-block" }} />
                  {it.label}
                </span>
                <span style={{ color: "#64748b", fontWeight: 700 }}>{it.count} ({pct}%)</span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

export default function AnalyticsReports({ staff = false }) {
  const [range, setRange] = useState("30d");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [metric, setMetric] = useState("revenue");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [exportingCsv, setExportingCsv] = useState(false);
  const [error, setError] = useState("");

  const queryParams = useMemo(() => {
    const p = { range };
    if (range === "custom") {
      if (startDate) p.start_date = startDate;
      if (endDate) p.end_date = endDate;
    }
    return p;
  }, [range, startDate, endDate]);

  const loadAnalytics = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await analyticsApi.getOverview(queryParams);
      setData(res.data);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setLoading(false);
    }
  }, [queryParams]);

  useEffect(() => {
    if (range === "custom" && (!startDate || !endDate)) return;
    loadAnalytics();
  }, [range, startDate, endDate, loadAnalytics]);

  const handleExportCsv = async () => {
    setExportingCsv(true);
    setError("");
    try {
      const res = await analyticsApi.exportCsv(queryParams);
      const blob = new Blob([res.data], { type: "text/csv;charset=utf-8;" });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const slug = (data?.company_name || "business").toLowerCase().replace(/[^a-z0-9]+/g, "-");
      a.download = `ridesai-report-${slug}-${range}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setExportingCsv(false);
    }
  };

  const handleExportPdf = () => {
    if (!data) return;
    const kpis = data.kpis || {};
    const rowsHtml = (data.recent_records || [])
      .map(
        (r) => `
        <tr>
          <td>${r.id}</td>
          <td>${r.date}</td>
          <td>${r.customer}</td>
          <td>${r.items}</td>
          <td>${r.status}</td>
          <td>${r.channel}</td>
          <td style="text-align:right;font-weight:700;">Rs. ${Number(r.total || 0).toFixed(2)}</td>
        </tr>`
      )
      .join("");

    const topHtml = (data.top_items || [])
      .map((it) => `<tr><td>${it.name}</td><td style="text-align:right;">${it.quantity}</td><td style="text-align:right;font-weight:700;">Rs. ${Number(it.revenue || 0).toFixed(2)}</td></tr>`)
      .join("");

    const win = window.open("", "_blank", "width=960,height=760");
    if (!win) return;
    win.document.write(`<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>RidesAI Operational Report - ${data.company_name}</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; color: #0f172a; margin: 28px; }
    .hdr { display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 3px solid #ff77ff; padding-bottom: 14px; margin-bottom: 20px; }
    .brand { font-size: 12px; font-weight: 700; color: #a21caf; text-transform: uppercase; letter-spacing: 0.08em; }
    h1 { margin: 4px 0 2px; font-size: 24px; }
    .sub { font-size: 12.5px; color: #64748b; }
    .kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 22px; }
    .kpi { border: 1px solid #f0abfc; border-radius: 10px; padding: 12px; background: #fdf4ff; }
    .kpi-lbl { font-size: 11px; color: #64748b; font-weight: 600; text-transform: uppercase; }
    .kpi-val { font-size: 18px; font-weight: 800; margin-top: 4px; color: #0f172a; }
    h2 { font-size: 15px; margin: 20px 0 8px; color: #1e293b; }
    table { width: 100%; border-collapse: collapse; font-size: 12px; }
    th, td { border-bottom: 1px solid #e2e8f0; padding: 8px 6px; text-align: left; }
    th { background: #f8fafc; font-weight: 700; color: #475569; }
    .footer { margin-top: 28px; font-size: 11px; color: #94a3b8; text-align: center; border-top: 1px solid #e2e8f0; padding-top: 10px; }
    @media print { body { margin: 12mm; } }
  </style>
</head>
<body>
  <div class="hdr">
    <div>
      <div class="brand">Owned by Rides Technologies</div>
      <h1>${data.company_name} — Operational Report</h1>
      <div class="sub">Period: ${data.start_date} to ${data.end_date} (${data.range.toUpperCase()}) · Generated ${new Date().toLocaleString()}</div>
    </div>
  </div>
  <div class="kpis">
    <div class="kpi"><div class="kpi-lbl">Total Revenue</div><div class="kpi-val">${formatRs(kpis.total_revenue)}</div></div>
    <div class="kpi"><div class="kpi-lbl">Orders / Bookings</div><div class="kpi-val">${kpis.total_orders ?? 0}</div></div>
    <div class="kpi"><div class="kpi-lbl">Avg. Order Value</div><div class="kpi-val">${formatRs(kpis.average_order_value)}</div></div>
    <div class="kpi"><div class="kpi-lbl">Completion Rate</div><div class="kpi-val">${kpis.completion_rate ?? 0}%</div></div>
  </div>
  ${topHtml ? `<h2>Top Selling Items &amp; Services</h2><table><thead><tr><th>Item / Service</th><th style="text-align:right;">Qty</th><th style="text-align:right;">Revenue</th></tr></thead><tbody>${topHtml}</tbody></table>` : ""}
  <h2>Itemized Orders &amp; Bookings (${(data.recent_records || []).length})</h2>
  <table>
    <thead><tr><th>ID</th><th>Date</th><th>Customer</th><th>Items / Service</th><th>Status</th><th>Channel</th><th style="text-align:right;">Total</th></tr></thead>
    <tbody>${rowsHtml || '<tr><td colspan="7" style="text-align:center;color:#94a3b8;">No records in this period.</td></tr>'}</tbody>
  </table>
  <div class="footer">RidesAI Multi-Business Operations Platform · Owned by Rides Technologies</div>
  <script>window.onload = function(){ window.print(); };</script>
</body>
</html>`);
    win.document.close();
  };

  const Layout = staff ? StaffLayout : OwnerLayout;
  const kpis = data?.kpis || {};
  const series = data?.time_series || [];

  return (
    <Layout
      title="Analytics & Operational Reports"
      subtitle="Live time-series revenue, orders, AI voice metrics, and 1-click CSV / PDF report exports."
    >
      {error && <div className="ad-alert" role="alert">{error}</div>}

      {/* Controls Bar */}
      <div
        style={{
          background: "#fff",
          border: "1px solid #f0abfc",
          borderRadius: 14,
          padding: "14px 18px",
          marginBottom: 18,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          {RANGES.map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => setRange(key)}
              style={{
                padding: "8px 14px",
                borderRadius: 10,
                border: range === key ? "1px solid #ff77ff" : "1px solid #e2e8f0",
                background: range === key ? "#ff77ff" : "#ffffff",
                color: range === key ? "#ffffff" : "#475569",
                fontWeight: 700,
                fontSize: 12.5,
                cursor: "pointer",
              }}
            >
              {label}
            </button>
          ))}

          {range === "custom" && (
            <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
              <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} style={{ padding: "6px 8px", borderRadius: 8, border: "1px solid #d8b4fe", fontSize: 12.5 }} />
              <span style={{ fontSize: 12, color: "#64748b" }}>to</span>
              <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} style={{ padding: "6px 8px", borderRadius: 8, border: "1px solid #d8b4fe", fontSize: 12.5 }} />
            </div>
          )}
        </div>

        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button
            type="button"
            disabled={exportingCsv || loading}
            onClick={handleExportCsv}
            style={{
              padding: "9px 14px",
              borderRadius: 10,
              border: "1px solid #e2e8f0",
              background: "#ffffff",
              color: "#0f172a",
              fontWeight: 700,
              fontSize: 12.5,
              cursor: "pointer",
            }}
          >
            {exportingCsv ? "Exporting..." : "📥 Export CSV"}
          </button>
          <button
            type="button"
            disabled={loading || !data}
            onClick={handleExportPdf}
            style={{
              padding: "9px 14px",
              borderRadius: 10,
              border: "none",
              background: "#ff77ff",
              color: "#ffffff",
              fontWeight: 700,
              fontSize: 12.5,
              cursor: "pointer",
              boxShadow: "0 4px 12px rgba(255,119,255,0.35)",
            }}
          >
            📄 Export PDF
          </button>
        </div>
      </div>

      {loading ? (
        <div style={{ background: "#fff", borderRadius: 14, padding: 28, textAlign: "center", color: "#64748b" }}>
          Loading live PostgreSQL analytics...
        </div>
      ) : !data ? (
        <div style={{ background: "#fff", borderRadius: 14, padding: 28, textAlign: "center", color: "#64748b" }}>
          Select a date range to view analytics.
        </div>
      ) : (
        <>
          {/* KPI Cards Row */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(175px, 1fr))", gap: 12, marginBottom: 18 }}>
            {[
              { icon: "💰", label: "Total Revenue", value: formatRs(kpis.total_revenue), sub: `${data.start_date} → ${data.end_date}` },
              { icon: "📦", label: "Orders / Bookings", value: kpis.total_orders ?? 0, sub: `${kpis.completed_count ?? 0} completed · ${kpis.cancelled_count ?? 0} cancelled` },
              { icon: "🧾", label: "Avg. Order Value", value: formatRs(kpis.average_order_value), sub: "Non-cancelled average" },
              { icon: "✅", label: "Completion Rate", value: `${kpis.completion_rate ?? 0}%`, sub: "Delivered / Completed ratio" },
              { icon: "🎙️", label: "AI Voice Turns", value: kpis.ai_voice_turns ?? 0, sub: `${kpis.active_ai_conversations ?? 0} chats · Quota ${kpis.messages_used ?? 0}/${kpis.message_limit ?? 0}` },
            ].map((card) => (
              <div key={card.label} style={{ background: "#fff", border: "1px solid #f0abfc", borderRadius: 14, padding: "14px 16px" }}>
                <div style={{ fontSize: 12, color: "#64748b", fontWeight: 600 }}>{card.icon} {card.label}</div>
                <div style={{ fontSize: 21, fontWeight: 800, color: "#0f172a", marginTop: 4 }}>{card.value}</div>
                <div style={{ fontSize: 11.5, color: "#94a3b8", marginTop: 3 }}>{card.sub}</div>
              </div>
            ))}
          </div>

          {/* Time-Series Trend Chart */}
          <section style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 14, padding: 18, marginBottom: 18 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 10, marginBottom: 12 }}>
              <div>
                <h3 style={{ margin: 0, fontSize: 16 }}>Revenue &amp; Orders Trend ({data.granularity})</h3>
                <p style={{ margin: "2px 0 0", fontSize: 12.5, color: "#64748b" }}>Hover over any point or bar to inspect daily metrics.</p>
              </div>
              <div style={{ display: "flex", gap: 6 }}>
                <button
                  type="button"
                  onClick={() => setMetric("revenue")}
                  style={{
                    padding: "6px 12px",
                    borderRadius: 8,
                    border: metric === "revenue" ? "1px solid #ff77ff" : "1px solid #e2e8f0",
                    background: metric === "revenue" ? "#fdf4ff" : "#fff",
                    color: metric === "revenue" ? "#a21caf" : "#475569",
                    fontWeight: 700,
                    fontSize: 12,
                    cursor: "pointer",
                  }}
                >
                  Revenue (Rs.)
                </button>
                <button
                  type="button"
                  onClick={() => setMetric("orders")}
                  style={{
                    padding: "6px 12px",
                    borderRadius: 8,
                    border: metric === "orders" ? "1px solid #ff77ff" : "1px solid #e2e8f0",
                    background: metric === "orders" ? "#fdf4ff" : "#fff",
                    color: metric === "orders" ? "#a21caf" : "#475569",
                    fontWeight: 700,
                    fontSize: 12,
                    cursor: "pointer",
                  }}
                >
                  Orders Count
                </button>
              </div>
            </div>

            {series.length === 0 ? (
              <p style={{ color: "#94a3b8", textAlign: "center", padding: 24 }}>No time-series data for this period.</p>
            ) : (
              <RevenueTrendChart series={series} metric={metric} />
            )}
          </section>

          {/* Breakdown Row: Status + Channel */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 16, marginBottom: 18 }}>
            <section style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 14, padding: 18 }}>
              <h3 style={{ margin: "0 0 14px", fontSize: 15.5 }}>Status Distribution</h3>
              <DonutBreakdown items={data.status_breakdown || []} centerLabel="Total" />
            </section>

            <section style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 14, padding: 18 }}>
              <h3 style={{ margin: "0 0 14px", fontSize: 15.5 }}>Channel Distribution</h3>
              <DonutBreakdown items={data.channel_breakdown || []} centerLabel="Channels" />
            </section>
          </div>

          {/* Top Performing Items / Services */}
          <section style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 14, padding: 18 }}>
            <h3 style={{ margin: "0 0 12px", fontSize: 15.5 }}>Top Performing Items &amp; Services</h3>
            {(data.top_items || []).length === 0 ? (
              <p style={{ color: "#94a3b8", margin: 0, fontSize: 13 }}>
                No sales or bookings yet in this date range. Once orders arrive via Public Link, Widget, or WhatsApp, top performers will appear here.
              </p>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13.5 }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid #e2e8f0", color: "#64748b", textAlign: "left" }}>
                      <th style={{ padding: "8px 6px" }}>#</th>
                      <th style={{ padding: "8px 6px" }}>Item / Service</th>
                      <th style={{ padding: "8px 6px", textAlign: "right" }}>Quantity Sold</th>
                      <th style={{ padding: "8px 6px", textAlign: "right" }}>Revenue</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.top_items.map((item, idx) => (
                      <tr key={item.name} style={{ borderBottom: "1px solid #f1f5f9" }}>
                        <td style={{ padding: "10px 6px", fontWeight: 700, color: "#a21caf" }}>{idx + 1}</td>
                        <td style={{ padding: "10px 6px", fontWeight: 600, color: "#0f172a" }}>{item.name}</td>
                        <td style={{ padding: "10px 6px", textAlign: "right", color: "#475569" }}>{item.quantity}</td>
                        <td style={{ padding: "10px 6px", textAlign: "right", fontWeight: 700, color: "#0f172a" }}>{formatRs(item.revenue)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </Layout>
  );
}
