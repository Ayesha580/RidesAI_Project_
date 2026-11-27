import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import OwnerLayout from "../owner/components/OwnerLayout";
import { hospitalApi } from "../api/operationsApi";

const ACCENT = "#ff77ff";

function formatMoney(val) {
  const num = Number(val || 0);
  return `Rs. ${num.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function formatDateTime(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString([], {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "—";
  }
}

export default function HospitalExecutiveDashboard() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [data, setData] = useState(null);

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await hospitalApi.getDashboard();
      setData(res.data || null);
    } catch (err) {
      setError(err?.response?.data?.detail || "Could not load hospital executive dashboard.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDashboard();
    const timer = setInterval(loadDashboard, 30000);
    return () => clearInterval(timer);
  }, [loadDashboard]);

  const kpis = data?.kpis || {
    total_departments: 0,
    total_wards: 0,
    total_beds: 0,
    available_beds: 0,
    occupied_beds: 0,
    cleaning_beds: 0,
    bed_occupancy_pct: 0,
    active_admissions_count: 0,
    admissions_today: 0,
    discharges_today: 0,
    appointments_today: 0,
    active_ai_conversations: 0,
  };

  const wards = data?.ward_occupancy_summary || [];
  const admissions = data?.recent_admissions || [];

  const kpiCards = [
    {
      label: "Available Beds & Occupancy",
      value: `${kpis.available_beds} / ${kpis.total_beds}`,
      sub: `${kpis.bed_occupancy_pct || 0}% occupied • ${kpis.cleaning_beds || 0} cleaning`,
      accent: "#059669",
      highlight: true,
    },
    {
      label: "Active IPD Admissions",
      value: kpis.active_admissions_count,
      sub: `+${kpis.admissions_today} admitted • ${kpis.discharges_today} discharged today`,
      accent: "#c026d3",
    },
    {
      label: "Departments & Wards",
      value: `${kpis.total_departments} / ${kpis.total_wards}`,
      sub: `${kpis.total_departments} departments • ${kpis.total_wards} active wards`,
      accent: "#6366f1",
    },
    {
      label: "Today's OPD & AI Chats",
      value: `${kpis.appointments_today} OPD`,
      sub: `${kpis.active_ai_conversations} active AI patient chats`,
      accent: "#0284c7",
    },
  ];

  return (
    <OwnerLayout
      title="Hospital Executive Dashboard"
      subtitle="Live IPD bed occupancy, admissions, ward capacity, and OPD activity."
    >
      <div style={{ maxWidth: 1280, margin: "0 auto", padding: "4px 0 36px", display: "grid", gap: 18 }}>
        {/* Quick Actions Bar */}
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 12,
          }}
        >
          <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
            <Link
              to="/owner/m/departments"
              style={{
                textDecoration: "none",
                background: ACCENT,
                color: "#240729",
                borderRadius: 10,
                padding: "9px 16px",
                fontSize: 13,
                fontWeight: 800,
                boxShadow: "0 4px 12px rgba(255, 119, 255, 0.3)",
              }}
            >
              🛏️ + Admit Patient / Live Bed Map
            </Link>
            <Link
              to="/owner/m/departments?tab=departments"
              style={{
                textDecoration: "none",
                background: "#fff",
                color: "#0f172a",
                border: "1px solid #e2e8f0",
                borderRadius: 10,
                padding: "9px 14px",
                fontSize: 13,
                fontWeight: 700,
              }}
            >
              🏥 Manage Wards &amp; Departments
            </Link>
            <Link
              to="/owner/m/appointments"
              style={{
                textDecoration: "none",
                background: "#fff",
                color: "#0f172a",
                border: "1px solid #e2e8f0",
                borderRadius: 10,
                padding: "9px 14px",
                fontSize: 13,
                fontWeight: 700,
              }}
            >
              🩺 Appointments
            </Link>
          </div>
          <button
            type="button"
            onClick={loadDashboard}
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

        {error && (
          <div
            style={{
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

        {/* Top KPI Cards */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            gap: 14,
          }}
        >
          {kpiCards.map((card) => (
            <div
              key={card.label}
              style={{
                background: "#ffffff",
                borderRadius: 14,
                padding: "18px 20px",
                border: card.highlight ? `1.5px solid ${ACCENT}` : "1px solid #e2e8f0",
                boxShadow: "0 1px 3px rgba(15, 23, 42, 0.04)",
              }}
            >
              <div style={{ fontSize: 12, fontWeight: 600, color: "#64748b", marginBottom: 6 }}>
                {card.label}
              </div>
              <div style={{ fontSize: 26, fontWeight: 800, color: "#0f172a", lineHeight: 1.15 }}>
                {loading ? "—" : card.value}
              </div>
              <div style={{ fontSize: 11.5, color: card.accent, fontWeight: 700, marginTop: 6 }}>
                {card.sub}
              </div>
            </div>
          ))}
        </div>

        {/* Ward Occupancy Progress Bars */}
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
              marginBottom: 14,
              flexWrap: "wrap",
              gap: 8,
            }}
          >
            <div>
              <div style={{ fontSize: 16, fontWeight: 800, color: "#0f172a" }}>
                🏥 Ward Occupancy Overview
              </div>
              <div style={{ fontSize: 12, color: "#64748b" }}>
                Real-time bed utilization across ICU, General, Private, Emergency &amp; Specialty wards
              </div>
            </div>
            <Link
              to="/owner/m/departments"
              style={{ fontSize: 12.5, fontWeight: 700, color: "#a21caf", textDecoration: "none" }}
            >
              Open Live Bed Map →
            </Link>
          </div>

          {loading ? (
            <div style={{ padding: 28, textAlign: "center", color: "#64748b", fontSize: 13 }}>
              Loading ward occupancy...
            </div>
          ) : wards.length === 0 ? (
            <div style={{ padding: 32, textAlign: "center", color: "#64748b", fontSize: 13 }}>
              No wards configured yet. Go to{" "}
              <Link to="/owner/m/departments" style={{ color: "#a21caf", fontWeight: 700 }}>
                Departments &amp; Wards
              </Link>{" "}
              to create your first ward and auto-generate beds.
            </div>
          ) : (
            <div style={{ display: "grid", gap: 12 }}>
              {wards.map((w) => {
                const pct = Number(w.occupancy_pct || 0);
                const barColor = pct >= 85 ? "#e11d48" : pct >= 60 ? "#d97706" : "#10b981";
                return (
                  <div key={w.id}>
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        fontSize: 13,
                        fontWeight: 700,
                        color: "#1e293b",
                        marginBottom: 5,
                        flexWrap: "wrap",
                        gap: 6,
                      }}
                    >
                      <span>
                        {w.name}{" "}
                        <span style={{ fontWeight: 500, color: "#64748b", fontSize: 12 }}>
                          ({w.ward_type_label}
                          {w.floor ? ` • ${w.floor}` : ""})
                        </span>
                      </span>
                      <span>
                        {w.occupied_beds}/{w.total_beds} occupied ({pct}%) •{" "}
                        <span style={{ color: "#059669" }}>{w.available_beds} free</span>
                      </span>
                    </div>
                    <div style={{ height: 9, background: "#f1f5f9", borderRadius: 999, overflow: "hidden" }}>
                      <div
                        style={{
                          width: `${Math.min(100, pct)}%`,
                          height: "100%",
                          background: barColor,
                          borderRadius: 999,
                          transition: "width 0.3s ease",
                        }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Recent / Active Admissions Table */}
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
              🩺 Recent IPD Admissions &amp; Discharges
            </div>
            <div style={{ fontSize: 12, color: "#64748b" }}>
              Latest inpatient admissions across all wards
            </div>
          </div>
          {admissions.length === 0 ? (
            <div style={{ padding: 36, textAlign: "center", color: "#64748b", fontSize: 13 }}>
              No IPD admissions recorded yet.
            </div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr style={{ background: "#f8fafc", textAlign: "left", color: "#475569" }}>
                    <th style={{ padding: "12px 16px", fontWeight: 700 }}>Patient</th>
                    <th style={{ padding: "12px 14px", fontWeight: 700 }}>Ward / Bed</th>
                    <th style={{ padding: "12px 14px", fontWeight: 700 }}>Attending Doctor</th>
                    <th style={{ padding: "12px 14px", fontWeight: 700 }}>Admitted</th>
                    <th style={{ padding: "12px 14px", fontWeight: 700 }}>Status</th>
                    <th style={{ padding: "12px 16px", fontWeight: 700, textAlign: "right" }}>
                      Bed Charges
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {admissions.map((a) => {
                    const isAdmitted = a.status === "admitted";
                    return (
                      <tr key={a.id} style={{ borderTop: "1px solid #f1f5f9" }}>
                        <td style={{ padding: "12px 16px" }}>
                          <div style={{ fontWeight: 700, color: "#0f172a" }}>{a.patient_name}</div>
                          <div style={{ fontSize: 11.5, color: "#64748b" }}>
                            {a.patient_phone || "—"}
                            {a.diagnosis ? ` • ${a.diagnosis}` : ""}
                          </div>
                        </td>
                        <td style={{ padding: "12px 14px", fontWeight: 600 }}>
                          {a.ward_name || "—"} {a.bed_number ? `(${a.bed_number})` : ""}
                        </td>
                        <td style={{ padding: "12px 14px", color: "#334155" }}>
                          {a.attending_doctor || "—"}
                        </td>
                        <td style={{ padding: "12px 14px", color: "#64748b", fontSize: 12 }}>
                          {formatDateTime(a.admitted_at)}
                        </td>
                        <td style={{ padding: "12px 14px" }}>
                          <span
                            style={{
                              fontSize: 11,
                              fontWeight: 800,
                              padding: "3px 9px",
                              borderRadius: 999,
                              background: isAdmitted ? "#fdf4ff" : "#ecfdf5",
                              color: isAdmitted ? "#a21caf" : "#047857",
                              border: isAdmitted ? `1px solid ${ACCENT}` : "1px solid #a7f3d0",
                            }}
                          >
                            {isAdmitted ? "Admitted" : "Discharged"}
                          </span>
                        </td>
                        <td style={{ padding: "12px 16px", textAlign: "right", fontWeight: 700 }}>
                          {isAdmitted
                            ? `${formatMoney(a.daily_rate)}/day`
                            : formatMoney(a.total_bed_charges)}
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
    </OwnerLayout>
  );
}
