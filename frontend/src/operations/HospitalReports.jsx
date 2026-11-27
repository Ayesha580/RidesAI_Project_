import { useCallback, useEffect, useState } from "react";
import OwnerLayout from "../owner/components/OwnerLayout";
import StaffLayout from "../staff/components/StaffLayout";
import { hospitalApi } from "../api/operationsApi";

const ACCENT = "#ff77ff";

function formatMoney(v) {
  return `Rs. ${Number(v || 0).toLocaleString("en-PK", { maximumFractionDigits: 0 })}`;
}

export default function HospitalReports({ staff = false }) {
  const Layout = staff ? StaffLayout : OwnerLayout;
  const [days, setDays] = useState(30);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadReports = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await hospitalApi.getReportsSummary({ days });
      setData(res.data);
    } catch (err) {
      setError(err?.response?.data?.detail || "Could not load hospital analytics.");
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    loadReports();
  }, [loadReports]);

  const handleExportCsv = () => {
    if (!data) return;
    const rows = [
      ["Hospital Financial & Operational Summary", `${data.start_date} to ${data.end_date}`],
      [],
      ["Metric", "Value"],
      ["Total Revenue (Rs.)", data.revenue?.total_revenue ?? 0],
      ["OPD Revenue (Rs.)", data.revenue?.opd_revenue ?? 0],
      ["IPD Bed Revenue (Rs.)", data.revenue?.ipd_revenue ?? 0],
      ["Lab Revenue (Rs.)", data.revenue?.lab_revenue ?? 0],
      ["Total Registered Patients", data.operational?.total_patients ?? 0],
      ["OPD Appointments", data.operational?.total_appointments ?? 0],
      ["Completed Appointments", data.operational?.completed_appointments ?? 0],
      ["IPD Admissions", data.operational?.total_admissions ?? 0],
      ["IPD Discharges", data.operational?.total_discharges ?? 0],
      ["Digital Prescriptions", data.operational?.total_prescriptions ?? 0],
      ["Lab Orders Completed", data.operational?.completed_lab_orders ?? 0],
      ["Bed Occupancy (%)", data.operational?.bed_occupancy_rate ?? 0],
      [],
      ["Daily Revenue Trend"],
      ["Date", "OPD (Rs.)", "IPD (Rs.)", "Lab (Rs.)", "Total (Rs.)"],
      ...(data.daily_trend || []).map((d) => [d.date, d.opd, d.ipd, d.lab, d.total]),
    ];
    const csv = rows.map((r) => r.map((c) => `"${String(c ?? "").replace(/"/g, '""')}"`).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `hospital-report-${days}d-${data.end_date}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const rev = data?.revenue || {};
  const ops = data?.operational || {};

  return (
    <Layout
      title="Hospital Financial & Operational Analytics"
      subtitle="Unified revenue analytics across OPD consultations, IPD bed charges, and Diagnostic Lab orders."
    >
      <div style={{ maxWidth: 1280, margin: "0 auto", padding: "4px 0 40px", display: "grid", gap: 16 }}>
        {/* Period Selector + Export CSV */}
        <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 14, padding: "12px 16px", display: "flex", flexWrap: "wrap", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
          <div style={{ display: "flex", gap: 8 }}>
            {[7, 30, 90].map((d) => (
              <button
                key={d}
                type="button"
                onClick={() => setDays(d)}
                style={{
                  border: days === d ? `1.5px solid ${ACCENT}` : "1px solid #e2e8f0",
                  background: days === d ? "#fdf4ff" : "#fff",
                  color: days === d ? "#86198f" : "#475569",
                  borderRadius: 10,
                  padding: "7px 16px",
                  fontSize: 13,
                  fontWeight: 700,
                  cursor: "pointer",
                }}
              >
                Last {d}D
              </button>
            ))}
          </div>
          <button
            type="button"
            disabled={!data}
            onClick={handleExportCsv}
            style={{
              border: "none",
              background: ACCENT,
              color: "#240729",
              borderRadius: 10,
              padding: "8px 16px",
              fontSize: 12.5,
              fontWeight: 800,
              cursor: data ? "pointer" : "not-allowed",
            }}
          >
            ⬇ Export CSV
          </button>
        </div>

        {error && (
          <div style={{ padding: "10px 14px", borderRadius: 10, background: "#fef2f2", border: "1px solid #fecaca", color: "#991b1b", fontSize: 13, fontWeight: 600 }}>
            ⚠ {error}
          </div>
        )}

        {loading ? (
          <div style={{ background: "#fff", borderRadius: 14, border: "1px solid #e2e8f0", padding: 48, textAlign: "center", color: "#64748b" }}>
            Loading hospital analytics...
          </div>
        ) : (
          <>
            {/* Revenue Breakdown KPI Strip */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
              {[
                { label: "Total Hospital Revenue", value: formatMoney(rev.total_revenue), color: "#0f172a", highlight: true },
                { label: "OPD Consultation Revenue", value: formatMoney(rev.opd_revenue), color: "#86198f" },
                { label: "IPD Bed Charges Revenue", value: formatMoney(rev.ipd_revenue), color: "#1d4ed8" },
                { label: "Diagnostic Lab Revenue", value: formatMoney(rev.lab_revenue), color: "#047857" },
              ].map((k) => (
                <div
                  key={k.label}
                  style={{
                    background: "#fff",
                    border: k.highlight ? `1.5px solid ${ACCENT}` : "1px solid #e2e8f0",
                    borderRadius: 14,
                    padding: "16px 18px",
                  }}
                >
                  <div style={{ fontSize: 12, fontWeight: 700, color: "#64748b" }}>{k.label}</div>
                  <div style={{ fontSize: 24, fontWeight: 800, color: k.color, marginTop: 6 }}>{k.value}</div>
                </div>
              ))}
            </div>

            {/* Operational Metrics Row */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(165px, 1fr))", gap: 10 }}>
              {[
                { label: "Total Patients", value: ops.total_patients ?? 0 },
                { label: "OPD Visits", value: `${ops.completed_appointments ?? 0} / ${ops.total_appointments ?? 0}` },
                { label: "IPD Adm / Disch", value: `${ops.total_admissions ?? 0} / ${ops.total_discharges ?? 0}` },
                { label: "Prescriptions", value: ops.total_prescriptions ?? 0 },
                { label: "Lab Completed", value: `${ops.completed_lab_orders ?? 0} / ${ops.total_lab_orders ?? 0}` },
                { label: "Bed Occupancy", value: `${ops.bed_occupancy_rate ?? 0}%` },
              ].map((m) => (
                <div key={m.label} style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 12, padding: "12px 14px" }}>
                  <div style={{ fontSize: 11.5, fontWeight: 700, color: "#64748b" }}>{m.label}</div>
                  <div style={{ fontSize: 19, fontWeight: 800, color: "#0f172a", marginTop: 4 }}>{m.value}</div>
                </div>
              ))}
            </div>

            {/* Department Performance & Top Doctors */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(420px, 1fr))", gap: 14 }}>
              <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 14, overflow: "hidden" }}>
                <div style={{ padding: "14px 16px", borderBottom: "1px solid #e2e8f0", fontWeight: 800, fontSize: 14.5 }}>
                  🏥 Department Performance
                </div>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                  <thead>
                    <tr style={{ background: "#f8fafc", textAlign: "left", color: "#475569" }}>
                      <th style={{ padding: "10px 14px" }}>Department</th>
                      <th style={{ padding: "10px 12px" }}>Doctors</th>
                      <th style={{ padding: "10px 12px" }}>OPD Visits</th>
                      <th style={{ padding: "10px 14px", textAlign: "right" }}>OPD Revenue</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(data?.departments || []).length === 0 ? (
                      <tr><td colSpan={4} style={{ padding: 24, textAlign: "center", color: "#94a3b8" }}>No department data in this period.</td></tr>
                    ) : (
                      data.departments.map((d) => (
                        <tr key={d.department_id} style={{ borderTop: "1px solid #f1f5f9" }}>
                          <td style={{ padding: "10px 14px", fontWeight: 700 }}>{d.department_name}</td>
                          <td style={{ padding: "10px 12px" }}>{d.doctor_count}</td>
                          <td style={{ padding: "10px 12px" }}>{d.appointment_count}</td>
                          <td style={{ padding: "10px 14px", textAlign: "right", fontWeight: 700 }}>{formatMoney(d.opd_revenue)}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 14, overflow: "hidden" }}>
                <div style={{ padding: "14px 16px", borderBottom: "1px solid #e2e8f0", fontWeight: 800, fontSize: 14.5 }}>
                  🩺 Top Doctors by OPD Volume &amp; Revenue
                </div>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                  <thead>
                    <tr style={{ background: "#f8fafc", textAlign: "left", color: "#475569" }}>
                      <th style={{ padding: "10px 14px" }}>Doctor</th>
                      <th style={{ padding: "10px 12px" }}>Department</th>
                      <th style={{ padding: "10px 12px" }}>Visits</th>
                      <th style={{ padding: "10px 14px", textAlign: "right" }}>Revenue</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(data?.top_doctors || []).length === 0 ? (
                      <tr><td colSpan={4} style={{ padding: 24, textAlign: "center", color: "#94a3b8" }}>No doctor OPD activity in this period.</td></tr>
                    ) : (
                      data.top_doctors.map((doc) => (
                        <tr key={doc.doctor_id} style={{ borderTop: "1px solid #f1f5f9" }}>
                          <td style={{ padding: "10px 14px", fontWeight: 700 }}>{doc.doctor_name}</td>
                          <td style={{ padding: "10px 12px", color: "#64748b" }}>{doc.department_name || "OPD"}</td>
                          <td style={{ padding: "10px 12px" }}>{doc.appointment_count}</td>
                          <td style={{ padding: "10px 14px", textAlign: "right", fontWeight: 700 }}>{formatMoney(doc.opd_revenue)}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </div>
    </Layout>
  );
}
