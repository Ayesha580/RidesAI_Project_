import { useCallback, useEffect, useState } from "react";
import OwnerLayout from "../owner/components/OwnerLayout";
import StaffLayout from "../staff/components/StaffLayout";
import { attendanceApi } from "../api/operationsApi";
import { errorText } from "../api/axiosClient";

const STATUS_OPTIONS = [
  { key: "present", label: "Present", bg: "#ecfdf5", color: "#047857", border: "#10b981" },
  { key: "late", label: "Late", bg: "#fffbeb", color: "#b45309", border: "#f59e0b" },
  { key: "half_day", label: "Half Day", bg: "#eff6ff", color: "#1d4ed8", border: "#3b82f6" },
  { key: "on_leave", label: "On Leave", bg: "#fdf4ff", color: "#a21caf", border: "#d946ef" },
  { key: "absent", label: "Absent", bg: "#fef2f2", color: "#b91c1c", border: "#ef4444" },
];

export default function StaffAttendance({ staff = false }) {
  const todayStr = new Date().toISOString().slice(0, 10);
  const [date, setDate] = useState(todayStr);
  const [summary, setSummary] = useState({ present: 0, late: 0, absent: 0, half_day: 0, on_leave: 0, unmarked: 0 });
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const loadAttendance = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const { data } = await attendanceApi.getByDate(date);
      setSummary(data.summary || { present: 0, late: 0, absent: 0, half_day: 0, on_leave: 0, unmarked: 0 });
      setRows(Array.isArray(data.staff) ? data.staff : []);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setLoading(false);
    }
  }, [date]);

  useEffect(() => {
    loadAttendance();
  }, [loadAttendance]);

  const saveRow = async (row, overrides = {}) => {
    const payload = {
      staff_user_id: row.staff_user_id,
      date,
      status: overrides.status || (row.status === "unmarked" ? "present" : row.status),
      check_in_time: overrides.check_in_time !== undefined ? overrides.check_in_time : row.check_in_time,
      check_out_time: overrides.check_out_time !== undefined ? overrides.check_out_time : row.check_out_time,
      notes: overrides.notes !== undefined ? overrides.notes : row.notes,
    };
    setBusyId(row.staff_user_id);
    setError("");
    try {
      await attendanceApi.mark(payload);
      setNotice(`Saved attendance for ${row.name}.`);
      setTimeout(() => setNotice(""), 2400);
      await loadAttendance();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusyId(null);
    }
  };

  const Layout = staff ? StaffLayout : OwnerLayout;

  return (
    <Layout
      title="Staff Attendance"
      subtitle="Track daily check-ins, check-outs, late arrivals, and leaves across your team."
    >
      {error && <div className="ad-alert" role="alert">{error}</div>}
      {notice && (
        <div style={{ background: "#fdf4ff", border: "1px solid #f0abfc", color: "#86198f", padding: "9px 14px", borderRadius: 10, fontSize: 13, fontWeight: 600, marginBottom: 14 }}>
          ✅ {notice}
        </div>
      )}

      {/* Date Picker & KPI Row */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12, marginBottom: 16 }}>
        <label style={{ display: "inline-flex", alignItems: "center", gap: 8, background: "#fff", border: "1px solid #f0abfc", borderRadius: 12, padding: "8px 14px", fontSize: 13, fontWeight: 700 }}>
          <span>📅 Date:</span>
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            style={{ border: "none", outline: "none", fontSize: 13, fontWeight: 700, color: "#0f172a" }}
          />
        </label>

        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {[
            { label: "Present", val: summary.present, bg: "#ecfdf5", color: "#047857" },
            { label: "Late", val: summary.late, bg: "#fffbeb", color: "#b45309" },
            { label: "Absent", val: summary.absent, bg: "#fef2f2", color: "#b91c1c" },
            { label: "On Leave", val: summary.on_leave, bg: "#fdf4ff", color: "#a21caf" },
          ].map((k) => (
            <span key={k.label} style={{ padding: "6px 12px", borderRadius: 999, background: k.bg, color: k.color, fontSize: 12.5, fontWeight: 700 }}>
              {k.label}: {k.val ?? 0}
            </span>
          ))}
        </div>
      </div>

      {/* Staff Attendance Cards */}
      <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 16, padding: 18 }}>
        {loading ? (
          <p style={{ color: "#64748b", margin: 0 }}>Loading attendance sheet...</p>
        ) : rows.length === 0 ? (
          <p style={{ color: "#64748b", margin: 0 }}>No active staff members found for this business.</p>
        ) : (
          <div style={{ display: "grid", gap: 12 }}>
            {rows.map((row) => {
              const isBusy = busyId === row.staff_user_id;
              return (
                <div
                  key={row.staff_user_id}
                  style={{
                    border: "1px solid #f1f5f9",
                    borderRadius: 14,
                    padding: 14,
                    display: "grid",
                    gap: 10,
                    background: "#fffcff",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 10 }}>
                    <div>
                      <strong style={{ fontSize: 15, color: "#0f172a" }}>{row.name}</strong>
                      <div style={{ fontSize: 12, color: "#64748b" }}>{row.role} · {row.email}</div>
                    </div>

                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                      {STATUS_OPTIONS.map((opt) => {
                        const active = row.status === opt.key;
                        return (
                          <button
                            key={opt.key}
                            type="button"
                            disabled={isBusy}
                            onClick={() => saveRow(row, { status: opt.key })}
                            style={{
                              padding: "6px 11px",
                              borderRadius: 999,
                              border: active ? `1.5px solid ${opt.border}` : "1px solid #e2e8f0",
                              background: active ? opt.bg : "#fff",
                              color: active ? opt.color : "#64748b",
                              fontWeight: 700,
                              fontSize: 12,
                              cursor: isBusy ? "wait" : "pointer",
                            }}
                          >
                            {opt.label}
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 8, alignItems: "center" }}>
                    <label style={{ fontSize: 11.5, fontWeight: 600, color: "#64748b", display: "grid", gap: 3 }}>
                      Check-In
                      <input
                        type="time"
                        value={row.check_in_time || ""}
                        onChange={(e) => {
                          const val = e.target.value;
                          setRows((prev) => prev.map((r) => (r.staff_user_id === row.staff_user_id ? { ...r, check_in_time: val } : r)));
                        }}
                        onBlur={(e) => saveRow(row, { check_in_time: e.target.value })}
                        style={{ padding: "6px 8px", borderRadius: 8, border: "1px solid #d1d5db", fontSize: 12.5 }}
                      />
                    </label>
                    <label style={{ fontSize: 11.5, fontWeight: 600, color: "#64748b", display: "grid", gap: 3 }}>
                      Check-Out
                      <input
                        type="time"
                        value={row.check_out_time || ""}
                        onChange={(e) => {
                          const val = e.target.value;
                          setRows((prev) => prev.map((r) => (r.staff_user_id === row.staff_user_id ? { ...r, check_out_time: val } : r)));
                        }}
                        onBlur={(e) => saveRow(row, { check_out_time: e.target.value })}
                        style={{ padding: "6px 8px", borderRadius: 8, border: "1px solid #d1d5db", fontSize: 12.5 }}
                      />
                    </label>
                    <label style={{ fontSize: 11.5, fontWeight: 600, color: "#64748b", display: "grid", gap: 3 }}>
                      Notes
                      <input
                        placeholder="Optional shift note..."
                        value={row.notes || ""}
                        onChange={(e) => {
                          const val = e.target.value;
                          setRows((prev) => prev.map((r) => (r.staff_user_id === row.staff_user_id ? { ...r, notes: val } : r)));
                        }}
                        onBlur={(e) => saveRow(row, { notes: e.target.value })}
                        style={{ padding: "6px 8px", borderRadius: 8, border: "1px solid #d1d5db", fontSize: 12.5 }}
                      />
                    </label>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </Layout>
  );
}
