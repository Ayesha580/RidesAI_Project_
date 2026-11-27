import { useCallback, useEffect, useMemo, useState } from "react";
import OwnerLayout from "../owner/components/OwnerLayout";
import StaffLayout from "../staff/components/StaffLayout";
import { hospitalApi } from "../api/operationsApi";

const ACCENT = "#ff77ff";

const STATUS_META = {
  available: { label: "Available", bg: "#ecfdf5", color: "#047857", border: "#6ee7b7" },
  in_opd: { label: "In OPD", bg: "#eff6ff", color: "#1d4ed8", border: "#bfdbfe" },
  on_leave: { label: "On Leave", bg: "#fffbeb", color: "#b45309", border: "#fcd34d" },
  off_duty: { label: "Off Duty", bg: "#f1f5f9", color: "#475569", border: "#cbd5e1" },
};

const DAYS = [
  { key: "mon", label: "Mon" },
  { key: "tue", label: "Tue" },
  { key: "wed", label: "Wed" },
  { key: "thu", label: "Thu" },
  { key: "fri", label: "Fri" },
  { key: "sat", label: "Sat" },
  { key: "sun", label: "Sun" },
];

function formatMoney(val) {
  const num = Number(val || 0);
  return `Rs. ${num.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

export default function HospitalDoctorsDirectory({ staff = false }) {
  const Layout = staff ? StaffLayout : OwnerLayout;

  const [doctors, setDoctors] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [search, setSearch] = useState("");
  const [deptFilter, setDeptFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");

  // Add / Edit Doctor Modal
  const [showModal, setShowModal] = useState(false);
  const [editingDoc, setEditingDoc] = useState(null);
  const [form, setForm] = useState({
    full_name: "",
    department_id: "",
    specialization: "",
    qualification: "",
    license_number: "",
    phone: "",
    email: "",
    consultation_fee: "2000",
    follow_up_fee: "1000",
    slot_duration_minutes: "15",
    availability_status: "available",
    room_number: "",
    bio: "",
  });
  const [schedules, setSchedules] = useState([
    { day_of_week: "mon", start_time: "09:00", end_time: "14:00", max_patients: 20 },
    { day_of_week: "wed", start_time: "09:00", end_time: "14:00", max_patients: 20 },
    { day_of_week: "fri", start_time: "09:00", end_time: "14:00", max_patients: 20 },
  ]);

  const showToast = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(""), 3500);
  };

  const loadData = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    setError("");
    try {
      const [docRes, deptRes] = await Promise.all([
        hospitalApi.listDoctors(),
        hospitalApi.listDepartments(),
      ]);
      setDoctors(Array.isArray(docRes.data) ? docRes.data : []);
      setDepartments(Array.isArray(deptRes.data) ? deptRes.data : []);
    } catch (err) {
      setError(err?.response?.data?.detail || "Could not load doctors directory.");
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData(false);
  }, [loadData]);

  const filteredDoctors = useMemo(() => {
    const q = search.trim().toLowerCase();
    return doctors.filter((d) => {
      if (deptFilter && String(d.department_id || "") !== String(deptFilter)) return false;
      if (statusFilter !== "all" && d.availability_status !== statusFilter) return false;
      if (q) {
        const hay = `${d.full_name} ${d.specialization} ${d.qualification} ${d.department_name} ${d.room_number}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [doctors, deptFilter, statusFilter, search]);

  const kpis = useMemo(() => {
    const total = doctors.length;
    const activeCount = doctors.filter((d) =>
      ["available", "in_opd"].includes(d.availability_status)
    ).length;
    const onLeave = doctors.filter((d) => d.availability_status === "on_leave").length;
    const avgFee =
      total > 0
        ? doctors.reduce((acc, d) => acc + Number(d.consultation_fee || 0), 0) / total
        : 0;
    return { total, activeCount, onLeave, avgFee };
  }, [doctors]);

  const openAddModal = () => {
    setEditingDoc(null);
    setForm({
      full_name: "",
      department_id: "",
      specialization: "",
      qualification: "",
      license_number: "",
      phone: "",
      email: "",
      consultation_fee: "2000",
      follow_up_fee: "1000",
      slot_duration_minutes: "15",
      availability_status: "available",
      room_number: "",
      bio: "",
    });
    setSchedules([
      { day_of_week: "mon", start_time: "09:00", end_time: "14:00", max_patients: 20 },
      { day_of_week: "wed", start_time: "09:00", end_time: "14:00", max_patients: 20 },
      { day_of_week: "fri", start_time: "09:00", end_time: "14:00", max_patients: 20 },
    ]);
    setShowModal(true);
  };

  const openEditModal = (doc) => {
    setEditingDoc(doc);
    setForm({
      full_name: doc.full_name || "",
      department_id: doc.department_id ? String(doc.department_id) : "",
      specialization: doc.specialization || "",
      qualification: doc.qualification || "",
      license_number: doc.license_number || "",
      phone: doc.phone || "",
      email: doc.email || "",
      consultation_fee: String(doc.consultation_fee ?? "0"),
      follow_up_fee: String(doc.follow_up_fee ?? "0"),
      slot_duration_minutes: String(doc.slot_duration_minutes ?? "15"),
      availability_status: doc.availability_status || "available",
      room_number: doc.room_number || "",
      bio: doc.bio || "",
    });
    setSchedules(
      (doc.schedules || []).map((s) => ({
        day_of_week: s.day_of_week,
        start_time: s.start_time,
        end_time: s.end_time,
        max_patients: s.max_patients || 20,
      }))
    );
    setShowModal(true);
  };

  const handleSave = async (e) => {
    e.preventDefault();
    if (!form.full_name.trim()) return;
    setSaving(true);
    setError("");
    try {
      const payload = {
        ...form,
        department_id: form.department_id ? Number(form.department_id) : null,
        consultation_fee: Number(form.consultation_fee || 0),
        follow_up_fee: Number(form.follow_up_fee || 0),
        slot_duration_minutes: Number(form.slot_duration_minutes || 15),
        schedules: schedules.filter((s) => s.day_of_week && s.start_time && s.end_time),
      };
      if (editingDoc) {
        await hospitalApi.updateDoctor(editingDoc.id, payload);
        showToast(`Updated ${form.full_name} & synced AI OPD schedule.`);
      } else {
        await hospitalApi.createDoctor(payload);
        showToast(`Added ${form.full_name} to Doctors Directory & AI Agent.`);
      }
      setShowModal(false);
      await loadData(true);
    } catch (err) {
      setError(err?.response?.data?.detail || "Could not save doctor profile.");
    } finally {
      setSaving(false);
    }
  };

  const handleQuickStatus = async (doc, nextStatus) => {
    setError("");
    try {
      await hospitalApi.updateDoctorStatus(doc.id, nextStatus);
      showToast(`${doc.full_name} status updated to ${STATUS_META[nextStatus]?.label || nextStatus}.`);
      await loadData(true);
    } catch (err) {
      setError(err?.response?.data?.detail || "Could not update status.");
    }
  };

  const handleDelete = async (doc) => {
    if (!window.confirm(`Remove ${doc.full_name} from Doctors Directory?`)) return;
    try {
      await hospitalApi.deleteDoctor(doc.id);
      showToast(`Removed ${doc.full_name}.`);
      await loadData(true);
    } catch (err) {
      setError(err?.response?.data?.detail || "Failed to delete doctor.");
    }
  };

  const addScheduleRow = () => {
    setSchedules((prev) => [
      ...prev,
      { day_of_week: "tue", start_time: "10:00", end_time: "15:00", max_patients: 20 },
    ]);
  };

  const kpiCards = [
    { label: "Total Doctors", value: kpis.total, sub: "Active specialists & physicians", accent: "#6366f1" },
    { label: "Available / In OPD", value: kpis.activeCount, sub: "Ready for consultations", accent: "#059669", highlight: true },
    { label: "On Leave", value: kpis.onLeave, sub: "AI alerts patients automatically", accent: "#d97706" },
    { label: "Avg Consultation Fee", value: formatMoney(kpis.avgFee), sub: "Across all departments", accent: "#c026d3" },
  ];

  return (
    <Layout
      title="Doctors Directory & OPD Schedules"
      subtitle="Manage hospital consultants, fees, rooms, and weekly OPD rosters synced live with your WhatsApp & Voice AI."
    >
      <div style={{ maxWidth: 1280, margin: "0 auto", padding: "4px 0 36px", display: "grid", gap: 16 }}>
        {/* KPI Strip */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: 12 }}>
          {kpiCards.map((c) => (
            <div
              key={c.label}
              style={{
                background: "#fff",
                borderRadius: 14,
                padding: "16px 18px",
                border: c.highlight ? `1.5px solid ${ACCENT}` : "1px solid #e2e8f0",
                boxShadow: "0 1px 3px rgba(15,23,42,0.04)",
              }}
            >
              <div style={{ fontSize: 12, fontWeight: 600, color: "#64748b", marginBottom: 6 }}>{c.label}</div>
              <div style={{ fontSize: 24, fontWeight: 800, color: "#0f172a" }}>{loading ? "—" : c.value}</div>
              <div style={{ fontSize: 11.5, fontWeight: 600, color: c.accent, marginTop: 6 }}>{c.sub}</div>
            </div>
          ))}
        </div>

        {/* Filters & Actions */}
        <div
          style={{
            background: "#fff",
            border: "1px solid #e2e8f0",
            borderRadius: 14,
            padding: "12px 16px",
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 10,
          }}
        >
          <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8 }}>
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search doctor, specialization, room..."
              style={{ minWidth: 220, padding: "8px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }}
            />
            <select
              value={deptFilter}
              onChange={(e) => setDeptFilter(e.target.value)}
              style={{ padding: "8px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13, background: "#fff" }}
            >
              <option value="">All Departments</option>
              {departments.map((d) => (
                <option key={d.id} value={d.id}>{d.name}</option>
              ))}
            </select>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {[
                { key: "all", label: "All" },
                { key: "available", label: "Available" },
                { key: "in_opd", label: "In OPD" },
                { key: "on_leave", label: "On Leave" },
              ].map((pill) => (
                <button
                  key={pill.key}
                  type="button"
                  onClick={() => setStatusFilter(pill.key)}
                  style={{
                    border: statusFilter === pill.key ? `1.5px solid ${ACCENT}` : "1px solid #e2e8f0",
                    background: statusFilter === pill.key ? "#0f172a" : "#fff",
                    color: statusFilter === pill.key ? "#fff" : "#475569",
                    borderRadius: 999,
                    padding: "6px 12px",
                    fontSize: 12,
                    fontWeight: 700,
                    cursor: "pointer",
                  }}
                >
                  {pill.label}
                </button>
              ))}
            </div>
          </div>

          <button
            type="button"
            onClick={openAddModal}
            style={{
              border: "none",
              background: ACCENT,
              color: "#240729",
              borderRadius: 10,
              padding: "9px 16px",
              fontSize: 13,
              fontWeight: 800,
              cursor: "pointer",
            }}
          >
            + Add Doctor
          </button>
        </div>

        {toast && (
          <div style={{ padding: "10px 14px", borderRadius: 10, background: "#ecfdf5", border: "1px solid #a7f3d0", color: "#065f46", fontSize: 13, fontWeight: 600 }}>
            ✓ {toast}
          </div>
        )}
        {error && (
          <div style={{ padding: "10px 14px", borderRadius: 10, background: "#fef2f2", border: "1px solid #fecaca", color: "#991b1b", fontSize: 13, fontWeight: 600 }}>
            ⚠ {error}
          </div>
        )}

        {/* Doctor Cards Grid */}
        {loading ? (
          <div style={{ background: "#fff", borderRadius: 14, border: "1px solid #e2e8f0", padding: 44, textAlign: "center", color: "#64748b" }}>
            Loading doctors directory...
          </div>
        ) : filteredDoctors.length === 0 ? (
          <div style={{ background: "#fff", borderRadius: 14, border: "1px dashed #cbd5e1", padding: 48, textAlign: "center", color: "#64748b" }}>
            <div style={{ fontSize: 32, marginBottom: 8 }}>👨‍⚕️</div>
            <div style={{ fontSize: 15, fontWeight: 700, color: "#0f172a", marginBottom: 4 }}>
              No doctors found
            </div>
            <div style={{ fontSize: 13 }}>
              Click <strong>+ Add Doctor</strong> to add specialists and sync their OPD timings with your AI Agent.
            </div>
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))", gap: 14 }}>
            {filteredDoctors.map((doc) => {
              const st = STATUS_META[doc.availability_status] || STATUS_META.available;
              return (
                <div
                  key={doc.id}
                  style={{
                    background: "#ffffff",
                    border: "1px solid #e2e8f0",
                    borderRadius: 14,
                    padding: 16,
                    display: "flex",
                    flexDirection: "column",
                    gap: 10,
                    boxShadow: "0 1px 3px rgba(15,23,42,0.04)",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
                    <div>
                      <div style={{ fontSize: 16, fontWeight: 800, color: "#0f172a" }}>{doc.full_name}</div>
                      <div style={{ fontSize: 12.5, color: "#64748b", marginTop: 2 }}>
                        {doc.specialization || "General Physician"}
                        {doc.qualification ? ` • ${doc.qualification}` : ""}
                      </div>
                    </div>
                    <span
                      style={{
                        fontSize: 11,
                        fontWeight: 800,
                        padding: "3px 9px",
                        borderRadius: 999,
                        background: st.bg,
                        color: st.color,
                        border: `1px solid ${st.border}`,
                        whiteSpace: "nowrap",
                      }}
                    >
                      {st.label}
                    </span>
                  </div>

                  <div style={{ display: "flex", flexWrap: "wrap", gap: 8, fontSize: 12 }}>
                    {doc.department_name && (
                      <span style={{ padding: "3px 9px", borderRadius: 999, background: "#fdf4ff", color: "#86198f", border: `1px solid ${ACCENT}`, fontWeight: 700 }}>
                        🏥 {doc.department_name}
                      </span>
                    )}
                    <span style={{ padding: "3px 9px", borderRadius: 999, background: "#f8fafc", color: "#0f172a", border: "1px solid #e2e8f0", fontWeight: 700 }}>
                      💵 {formatMoney(doc.consultation_fee)}
                    </span>
                    {doc.room_number && (
                      <span style={{ padding: "3px 9px", borderRadius: 999, background: "#f8fafc", color: "#475569", border: "1px solid #e2e8f0", fontWeight: 600 }}>
                        🚪 {doc.room_number}
                      </span>
                    )}
                  </div>

                  {/* Weekly OPD Schedule Pills */}
                  <div>
                    <div style={{ fontSize: 11, fontWeight: 700, color: "#64748b", marginBottom: 5 }}>
                      WEEKLY OPD SCHEDULE
                    </div>
                    {(doc.schedules || []).length === 0 ? (
                      <div style={{ fontSize: 12, color: "#94a3b8" }}>No OPD slots configured</div>
                    ) : (
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
                        {doc.schedules.map((s) => (
                          <span
                            key={s.id}
                            style={{
                              fontSize: 11,
                              fontWeight: 700,
                              padding: "3px 8px",
                              borderRadius: 7,
                              background: "#f1f5f9",
                              color: "#334155",
                            }}
                          >
                            {s.day_of_week.toUpperCase()} · {s.start_time}–{s.end_time}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Footer Controls */}
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: 8,
                      paddingTop: 8,
                      borderTop: "1px solid #f1f5f9",
                      marginTop: "auto",
                    }}
                  >
                    <select
                      value={doc.availability_status}
                      onChange={(e) => handleQuickStatus(doc, e.target.value)}
                      style={{
                        padding: "5px 8px",
                        borderRadius: 8,
                        border: "1px solid #cbd5e1",
                        fontSize: 12,
                        fontWeight: 700,
                        background: "#fff",
                      }}
                    >
                      <option value="available">Available</option>
                      <option value="in_opd">In OPD</option>
                      <option value="on_leave">On Leave</option>
                      <option value="off_duty">Off Duty</option>
                    </select>
                    <div style={{ display: "flex", gap: 6 }}>
                      <button
                        type="button"
                        onClick={() => openEditModal(doc)}
                        style={{ border: "1px solid #cbd5e1", background: "#fff", color: "#0f172a", borderRadius: 8, padding: "5px 10px", fontSize: 12, fontWeight: 700, cursor: "pointer" }}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDelete(doc)}
                        style={{ border: "1px solid #fecaca", background: "#fff", color: "#b91c1c", borderRadius: 8, padding: "5px 10px", fontSize: 12, fontWeight: 700, cursor: "pointer" }}
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ADD / EDIT DOCTOR MODAL */}
      {showModal && (
        <div
          onClick={() => setShowModal(false)}
          style={{ position: "fixed", inset: 0, background: "rgba(15,23,42,0.5)", zIndex: 1000, display: "grid", placeItems: "center", padding: 16 }}
        >
          <form
            onClick={(e) => e.stopPropagation()}
            onSubmit={handleSave}
            style={{
              width: "100%",
              maxWidth: 600,
              maxHeight: "90vh",
              overflowY: "auto",
              background: "#fff",
              borderRadius: 16,
              padding: 22,
              display: "grid",
              gap: 12,
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h3 style={{ margin: 0, fontSize: 17.5, fontWeight: 800 }}>
                {editingDoc ? `Edit ${editingDoc.full_name}` : "👨‍⚕️ Add Hospital Doctor"}
              </h3>
              <button type="button" onClick={() => setShowModal(false)} style={{ border: "none", background: "transparent", fontSize: 18, cursor: "pointer" }}>
                ✕
              </button>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <input
                required
                placeholder="Full Name * (e.g. Dr. Ayesha Khan)"
                value={form.full_name}
                onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                style={{ padding: "8px 11px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }}
              />
              <select
                value={form.department_id}
                onChange={(e) => setForm({ ...form, department_id: e.target.value })}
                style={{ padding: "8px 11px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13, background: "#fff" }}
              >
                <option value="">— Select Department —</option>
                {departments.map((d) => (
                  <option key={d.id} value={d.id}>{d.name}</option>
                ))}
              </select>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <input
                placeholder="Specialization (e.g. Cardiologist)"
                value={form.specialization}
                onChange={(e) => setForm({ ...form, specialization: e.target.value })}
                style={{ padding: "8px 11px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }}
              />
              <input
                placeholder="Qualification (e.g. MBBS, FCPS)"
                value={form.qualification}
                onChange={(e) => setForm({ ...form, qualification: e.target.value })}
                style={{ padding: "8px 11px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }}
              />
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10 }}>
              <input
                type="number"
                min="0"
                placeholder="Consultation Fee (Rs.)"
                value={form.consultation_fee}
                onChange={(e) => setForm({ ...form, consultation_fee: e.target.value })}
                style={{ padding: "8px 11px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }}
              />
              <input
                type="number"
                min="0"
                placeholder="Follow-up Fee (Rs.)"
                value={form.follow_up_fee}
                onChange={(e) => setForm({ ...form, follow_up_fee: e.target.value })}
                style={{ padding: "8px 11px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }}
              />
              <input
                placeholder="Room # (e.g. OPD 4)"
                value={form.room_number}
                onChange={(e) => setForm({ ...form, room_number: e.target.value })}
                style={{ padding: "8px 11px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }}
              />
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10 }}>
              <input
                placeholder="Phone"
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
                style={{ padding: "8px 11px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }}
              />
              <input
                placeholder="PMDC / License #"
                value={form.license_number}
                onChange={(e) => setForm({ ...form, license_number: e.target.value })}
                style={{ padding: "8px 11px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }}
              />
              <select
                value={form.availability_status}
                onChange={(e) => setForm({ ...form, availability_status: e.target.value })}
                style={{ padding: "8px 11px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13, background: "#fff" }}
              >
                <option value="available">Available</option>
                <option value="in_opd">In OPD</option>
                <option value="on_leave">On Leave</option>
                <option value="off_duty">Off Duty</option>
              </select>
            </div>

            {/* Weekly OPD Schedule Builder */}
            <div style={{ background: "#fdf4ff", border: `1px solid ${ACCENT}`, borderRadius: 12, padding: 12, display: "grid", gap: 8 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: 12.5, fontWeight: 800, color: "#86198f" }}>
                  🗓️ Weekly OPD Schedule (Synced with AI Agent)
                </span>
                <button
                  type="button"
                  onClick={addScheduleRow}
                  style={{ border: "none", background: "#0f172a", color: "#fff", borderRadius: 7, padding: "4px 10px", fontSize: 11.5, fontWeight: 700, cursor: "pointer" }}
                >
                  + Add Slot
                </button>
              </div>
              {schedules.map((row, idx) => (
                <div key={idx} style={{ display: "grid", gridTemplateColumns: "90px 1fr 1fr 76px 34px", gap: 6, alignItems: "center" }}>
                  <select
                    value={row.day_of_week}
                    onChange={(e) =>
                      setSchedules((prev) => prev.map((r, i) => (i === idx ? { ...r, day_of_week: e.target.value } : r)))
                    }
                    style={{ padding: "6px 8px", borderRadius: 7, border: "1px solid #cbd5e1", fontSize: 12, background: "#fff" }}
                  >
                    {DAYS.map((d) => (
                      <option key={d.key} value={d.key}>{d.label}</option>
                    ))}
                  </select>
                  <input
                    type="time"
                    value={row.start_time}
                    onChange={(e) =>
                      setSchedules((prev) => prev.map((r, i) => (i === idx ? { ...r, start_time: e.target.value } : r)))
                    }
                    style={{ padding: "6px 8px", borderRadius: 7, border: "1px solid #cbd5e1", fontSize: 12, background: "#fff" }}
                  />
                  <input
                    type="time"
                    value={row.end_time}
                    onChange={(e) =>
                      setSchedules((prev) => prev.map((r, i) => (i === idx ? { ...r, end_time: e.target.value } : r)))
                    }
                    style={{ padding: "6px 8px", borderRadius: 7, border: "1px solid #cbd5e1", fontSize: 12, background: "#fff" }}
                  />
                  <input
                    type="number"
                    min="1"
                    title="Max patients"
                    value={row.max_patients}
                    onChange={(e) =>
                      setSchedules((prev) => prev.map((r, i) => (i === idx ? { ...r, max_patients: Number(e.target.value || 20) } : r)))
                    }
                    style={{ padding: "6px 8px", borderRadius: 7, border: "1px solid #cbd5e1", fontSize: 12, background: "#fff" }}
                  />
                  <button
                    type="button"
                    onClick={() => setSchedules((prev) => prev.filter((_, i) => i !== idx))}
                    style={{ border: "1px solid #fecaca", background: "#fff", color: "#b91c1c", borderRadius: 7, padding: "5px", fontSize: 12, fontWeight: 700, cursor: "pointer" }}
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
              <button type="button" onClick={() => setShowModal(false)} style={{ border: "1px solid #cbd5e1", background: "#fff", borderRadius: 9, padding: "8px 14px", fontSize: 12.5, fontWeight: 700, cursor: "pointer" }}>
                Cancel
              </button>
              <button type="submit" disabled={saving} style={{ border: "none", background: ACCENT, color: "#240729", borderRadius: 9, padding: "8px 16px", fontSize: 13, fontWeight: 800, cursor: "pointer" }}>
                {saving ? "Saving..." : "Save Doctor"}
              </button>
            </div>
          </form>
        </div>
      )}
    </Layout>
  );
}
