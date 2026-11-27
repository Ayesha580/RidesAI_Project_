import { useCallback, useEffect, useState } from "react";
import OwnerLayout from "../owner/components/OwnerLayout";
import StaffLayout from "../staff/components/StaffLayout";
import { hospitalApi } from "../api/operationsApi";

const ACCENT = "#ff77ff";

const STATUS_BADGES = {
  booked: { label: "Booked", bg: "#eff6ff", color: "#1d4ed8", border: "#bfdbfe" },
  checked_in: { label: "Checked In", bg: "#fefce8", color: "#a16207", border: "#fde047" },
  in_consultation: { label: "In Consultation", bg: "#fdf4ff", color: "#86198f", border: "#f0abfc" },
  completed: { label: "Completed", bg: "#ecfdf5", color: "#047857", border: "#a7f3d0" },
  cancelled: { label: "Cancelled", bg: "#fef2f2", color: "#b91c1c", border: "#fecaca" },
  no_show: { label: "No Show", bg: "#f1f5f9", color: "#475569", border: "#cbd5e1" },
};

const SOURCE_BADGES = {
  walk_in: { label: "Walk-in", bg: "#f8fafc", color: "#334155" },
  phone: { label: "Phone", bg: "#eff6ff", color: "#1d4ed8" },
  whatsapp_ai: { label: "WhatsApp AI", bg: "#ecfdf5", color: "#047857" },
  web_voice_ai: { label: "Voice AI", bg: "#fdf4ff", color: "#86198f" },
};

const STATUS_FILTER_OPTIONS = [
  { key: "all", label: "All" },
  { key: "booked", label: "Booked" },
  { key: "checked_in", label: "Checked In" },
  { key: "in_consultation", label: "In Consultation" },
  { key: "completed", label: "Completed" },
  { key: "cancelled", label: "Cancelled" },
  { key: "no_show", label: "No Show" },
];

function todayISO() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function formatMoney(v) {
  return `Rs. ${Number(v || 0).toLocaleString("en-PK", { maximumFractionDigits: 0 })}`;
}

function formatTime12h(hhmm) {
  if (!hhmm) return "—";
  const parts = String(hhmm).split(":");
  if (parts.length < 2) return hhmm;
  const h = parseInt(parts[0], 10);
  const m = parts[1].slice(0, 2);
  if (Number.isNaN(h)) return hhmm;
  const ampm = h >= 12 ? "PM" : "AM";
  const h12 = h % 12 || 12;
  return `${h12}:${m} ${ampm}`;
}

const EMPTY_FORM = {
  doctor_id: "",
  department_id: "",
  visit_type: "new",
  appointment_date: todayISO(),
  appointment_time: "",
  patient_name: "",
  patient_phone: "",
  patient_age: "",
  patient_gender: "",
  consultation_fee: "",
  payment_status: "unpaid",
  booking_source: "walk_in",
  chief_complaint: "",
  notes: "",
};

export default function HospitalAppointments({ staff = false }) {
  const Layout = staff ? StaffLayout : OwnerLayout;
  const [tab, setTab] = useState("queue"); // "queue" | "appointments"

  const [doctors, setDoctors] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [queueData, setQueueData] = useState({ date: todayISO(), summary: {}, queues: [] });
  const [appointments, setAppointments] = useState([]);
  const [summary, setSummary] = useState({
    today_appointments: 0,
    waiting_in_opd: 0,
    in_consultation: 0,
    completed: 0,
    today_opd_revenue: 0,
  });

  // Filters
  const [queueDate, setQueueDate] = useState(todayISO());
  const [filterDate, setFilterDate] = useState(todayISO());
  const [filterDoctor, setFilterDoctor] = useState("");
  const [filterStatus, setFilterStatus] = useState("all");
  const [search, setSearch] = useState("");

  // UI states
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState("");
  const [error, setError] = useState("");

  // Modal states
  const [showModal, setShowModal] = useState(false);
  const [editingAppt, setEditingAppt] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);

  const showToast = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(""), 3500);
  };

  const loadMeta = useCallback(async () => {
    try {
      const [docRes, deptRes] = await Promise.all([
        hospitalApi.listDoctors(),
        hospitalApi.listDepartments(),
      ]);
      setDoctors(docRes.data?.results || docRes.data || []);
      setDepartments(deptRes.data?.results || deptRes.data || []);
    } catch {
      // non-blocking
    }
  }, []);

  const loadQueue = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const params = { date: queueDate };
      if (filterDoctor) params.doctor_id = filterDoctor;
      const { data } = await hospitalApi.getOpdQueue(params);
      setQueueData(data || { date: queueDate, summary: {}, queues: [] });
      if (data?.summary) setSummary(data.summary);
    } catch (err) {
      setError(err?.response?.data?.detail || "Could not load live OPD queue.");
    } finally {
      if (!silent) setLoading(false);
    }
  }, [queueDate, filterDoctor]);

  const loadAppointments = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const params = {};
      if (filterDate) params.date = filterDate;
      if (filterDoctor) params.doctor_id = filterDoctor;
      if (filterStatus && filterStatus !== "all") params.status = filterStatus;
      if (search.trim()) params.search = search.trim();
      const { data } = await hospitalApi.listAppointments(params);
      setAppointments(data?.results || []);
      if (data?.summary) setSummary(data.summary);
    } catch (err) {
      setError(err?.response?.data?.detail || "Could not load OPD appointments.");
    } finally {
      if (!silent) setLoading(false);
    }
  }, [filterDate, filterDoctor, filterStatus, search]);

  useEffect(() => {
    loadMeta();
  }, [loadMeta]);

  useEffect(() => {
    if (tab === "queue") {
      loadQueue();
    } else {
      loadAppointments();
    }
  }, [tab, loadQueue, loadAppointments]);

  const refreshActive = async () => {
    await Promise.all([loadQueue(true), loadAppointments(true)]);
  };

  const openBookModal = (preselectDoctorId = "") => {
    setEditingAppt(null);
    const chosenDoc = doctors.find((d) => String(d.id) === String(preselectDoctorId));
    setForm({
      ...EMPTY_FORM,
      appointment_date: tab === "queue" ? queueDate : filterDate || todayISO(),
      doctor_id: chosenDoc ? String(chosenDoc.id) : "",
      department_id: chosenDoc?.department_id ? String(chosenDoc.department_id) : "",
      consultation_fee: chosenDoc ? String(chosenDoc.consultation_fee ?? "") : "",
    });
    setShowModal(true);
  };

  const openEditModal = (appt) => {
    setEditingAppt(appt);
    setForm({
      doctor_id: String(appt.doctor_id || ""),
      department_id: appt.department_id ? String(appt.department_id) : "",
      visit_type: appt.visit_type || "new",
      appointment_date: appt.appointment_date || todayISO(),
      appointment_time: appt.appointment_time || "",
      patient_name: appt.patient_name || "",
      patient_phone: appt.patient_phone || "",
      patient_age: appt.patient_age ?? "",
      patient_gender: appt.patient_gender || "",
      consultation_fee: String(appt.consultation_fee ?? ""),
      payment_status: appt.payment_status || "unpaid",
      booking_source: appt.booking_source || "walk_in",
      chief_complaint: appt.chief_complaint || "",
      notes: appt.notes || "",
    });
    setShowModal(true);
  };

  const handleDoctorChange = (nextDocId) => {
    const doc = doctors.find((d) => String(d.id) === String(nextDocId));
    if (!doc) {
      setForm((prev) => ({ ...prev, doctor_id: nextDocId }));
      return;
    }
    const autoFee =
      form.visit_type === "follow_up" && Number(doc.follow_up_fee || 0) > 0
        ? doc.follow_up_fee
        : doc.consultation_fee;
    setForm((prev) => ({
      ...prev,
      doctor_id: nextDocId,
      department_id: doc.department_id ? String(doc.department_id) : prev.department_id,
      consultation_fee: String(autoFee ?? ""),
    }));
  };

  const handleVisitTypeChange = (nextVisitType) => {
    const doc = doctors.find((d) => String(d.id) === String(form.doctor_id));
    if (!editingAppt && doc) {
      const autoFee =
        nextVisitType === "follow_up" && Number(doc.follow_up_fee || 0) > 0
          ? doc.follow_up_fee
          : doc.consultation_fee;
      setForm((prev) => ({
        ...prev,
        visit_type: nextVisitType,
        consultation_fee: String(autoFee ?? ""),
      }));
      return;
    }
    setForm((prev) => ({ ...prev, visit_type: nextVisitType }));
  };

  const handleSaveAppointment = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      const payload = {
        ...form,
        doctor_id: form.doctor_id ? Number(form.doctor_id) : undefined,
        department_id: form.department_id ? Number(form.department_id) : null,
        patient_age: form.patient_age !== "" ? Number(form.patient_age) : null,
        consultation_fee: form.consultation_fee !== "" ? Number(form.consultation_fee) : undefined,
      };
      if (editingAppt) {
        await hospitalApi.updateAppointment(editingAppt.id, payload);
        showToast(`Updated Token #${String(editingAppt.token_number).padStart(2, "0")} for ${form.patient_name}.`);
      } else {
        const { data } = await hospitalApi.createAppointment(payload);
        showToast(`Booked Token ${data.token_display || "#" + data.token_number} for ${data.patient_name}.`);
      }
      setShowModal(false);
      setEditingAppt(null);
      await refreshActive();
    } catch (err) {
      const d = err?.response?.data;
      setError(d?.detail || d?.doctor_id || d?.patient_name || "Could not save appointment.");
    } finally {
      setSaving(false);
    }
  };

  const handleStatusUpdate = async (appt, payload, msg) => {
    setError("");
    try {
      await hospitalApi.updateAppointmentStatus(appt.id, payload);
      showToast(msg || `Updated Token ${appt.token_display}.`);
      await refreshActive();
    } catch (err) {
      setError(err?.response?.data?.detail || "Could not update appointment status.");
    }
  };

  const handleDeleteAppointment = async (appt) => {
    if (!window.confirm(`Delete Token ${appt.token_display} (${appt.patient_name})?`)) return;
    try {
      await hospitalApi.deleteAppointment(appt.id);
      showToast(`Removed Token ${appt.token_display}.`);
      await refreshActive();
    } catch (err) {
      setError(err?.response?.data?.detail || "Failed to delete appointment.");
    }
  };

  const kpiCards = [
    { label: "Today's Appointments", value: summary.today_appointments || 0, icon: "📅", accent: "#0f172a" },
    { label: "Waiting in Queue", value: summary.waiting_in_opd || 0, icon: "⏳", accent: "#a16207" },
    { label: "In Consultation", value: summary.in_consultation || 0, icon: "🩺", accent: "#86198f" },
    { label: "Completed", value: summary.completed || 0, icon: "✅", accent: "#047857" },
    { label: "Today's OPD Revenue", value: formatMoney(summary.today_opd_revenue), icon: "💳", accent: "#0f172a" },
  ];

  return (
    <Layout
      title="OPD Appointments & Live Token Queue"
      subtitle="Atomic daily token queue per doctor, check-in workflow, consultation fee tracking, and AI booking sync."
    >
      <div style={{ maxWidth: 1280, margin: "0 auto", padding: "4px 0 40px", display: "grid", gap: 16 }}>
        {/* Top KPI Strip */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(195px, 1fr))",
            gap: 12,
          }}
        >
          {kpiCards.map((k) => (
            <div
              key={k.label}
              style={{
                background: "#ffffff",
                border: "1px solid #e2e8f0",
                borderRadius: 14,
                padding: "14px 16px",
                boxShadow: "0 1px 3px rgba(15, 23, 42, 0.04)",
              }}
            >
              <div style={{ fontSize: 12, fontWeight: 700, color: "#64748b", display: "flex", alignItems: "center", gap: 6 }}>
                <span>{k.icon}</span>
                <span>{k.label}</span>
              </div>
              <div style={{ fontSize: 22, fontWeight: 800, color: k.accent, marginTop: 6 }}>
                {k.value}
              </div>
            </div>
          ))}
        </div>

        {/* Tab Bar + Primary CTA */}
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
            gap: 12,
          }}
        >
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button
              type="button"
              onClick={() => setTab("queue")}
              style={{
                border: tab === "queue" ? `1.5px solid ${ACCENT}` : "1px solid #e2e8f0",
                background: tab === "queue" ? "#fdf4ff" : "#fff",
                color: tab === "queue" ? "#86198f" : "#475569",
                borderRadius: 10,
                padding: "8px 16px",
                fontSize: 13,
                fontWeight: 700,
                cursor: "pointer",
              }}
            >
              🚦 Live OPD Queue
            </button>
            <button
              type="button"
              onClick={() => setTab("appointments")}
              style={{
                border: tab === "appointments" ? `1.5px solid ${ACCENT}` : "1px solid #e2e8f0",
                background: tab === "appointments" ? "#fdf4ff" : "#fff",
                color: tab === "appointments" ? "#86198f" : "#475569",
                borderRadius: 10,
                padding: "8px 16px",
                fontSize: 13,
                fontWeight: 700,
                cursor: "pointer",
              }}
            >
              📋 All Appointments
            </button>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <button
              type="button"
              onClick={refreshActive}
              style={{
                border: "1px solid #cbd5e1",
                background: "#fff",
                color: "#334155",
                borderRadius: 10,
                padding: "8px 12px",
                fontSize: 12.5,
                fontWeight: 700,
                cursor: "pointer",
              }}
            >
              ↻ Refresh
            </button>
            <button
              type="button"
              onClick={() => openBookModal(filterDoctor)}
              style={{
                border: "none",
                background: ACCENT,
                color: "#240729",
                borderRadius: 10,
                padding: "8px 16px",
                fontSize: 12.5,
                fontWeight: 800,
                cursor: "pointer",
              }}
            >
              + Book OPD Appointment
            </button>
          </div>
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

        {/* TAB 1: LIVE OPD QUEUE */}
        {tab === "queue" && (
          <div style={{ display: "grid", gap: 14 }}>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
              <input
                type="date"
                value={queueDate}
                onChange={(e) => setQueueDate(e.target.value)}
                style={{ padding: "8px 12px", borderRadius: 10, border: "1px solid #cbd5e1", fontSize: 13, background: "#fff" }}
              />
              <select
                value={filterDoctor}
                onChange={(e) => setFilterDoctor(e.target.value)}
                style={{ padding: "8px 12px", borderRadius: 10, border: "1px solid #cbd5e1", fontSize: 13, background: "#fff" }}
              >
                <option value="">All Doctors</option>
                {doctors.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.full_name} {d.department_name ? `(${d.department_name})` : ""}
                  </option>
                ))}
              </select>
            </div>

            {loading ? (
              <div style={{ background: "#fff", borderRadius: 14, border: "1px solid #e2e8f0", padding: 44, textAlign: "center", color: "#64748b" }}>
                Loading live OPD token queue...
              </div>
            ) : (queueData.queues || []).length === 0 ? (
              <div style={{ background: "#fff", borderRadius: 14, border: "1px dashed #cbd5e1", padding: 48, textAlign: "center", color: "#64748b" }}>
                <div style={{ fontSize: 32, marginBottom: 8 }}>🩺</div>
                <div style={{ fontSize: 15, fontWeight: 700, color: "#0f172a", marginBottom: 4 }}>
                  No active doctors configured yet
                </div>
                <div style={{ fontSize: 13 }}>
                  Add doctors in <strong>Doctors Directory</strong> first, then book OPD appointments to run the live token queue.
                </div>
              </div>
            ) : (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(380px, 1fr))", gap: 14 }}>
                {(queueData.queues || []).map((q) => (
                  <div
                    key={q.doctor_id}
                    style={{
                      background: "#ffffff",
                      border: "1px solid #e2e8f0",
                      borderRadius: 14,
                      padding: 16,
                      display: "grid",
                      gap: 12,
                      boxShadow: "0 1px 3px rgba(15, 23, 42, 0.04)",
                    }}
                  >
                    {/* Doctor Header */}
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
                      <div>
                        <div style={{ fontSize: 15.5, fontWeight: 800, color: "#0f172a" }}>{q.doctor_name}</div>
                        <div style={{ fontSize: 12, color: "#64748b", marginTop: 2 }}>
                          {q.department_name || q.specialization || "OPD"}
                          {q.room_number ? ` • ${q.room_number}` : ""} • {formatMoney(q.consultation_fee)}
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => openBookModal(q.doctor_id)}
                        style={{
                          border: "1px solid #e2e8f0",
                          background: "#fdf4ff",
                          color: "#86198f",
                          borderRadius: 8,
                          padding: "5px 10px",
                          fontSize: 11.5,
                          fontWeight: 700,
                          cursor: "pointer",
                        }}
                      >
                        + Token
                      </button>
                    </div>

                    {/* Now Serving / Next Token Banner */}
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
                      <div style={{ background: "#fdf4ff", border: `1px solid ${ACCENT}`, borderRadius: 10, padding: "8px 10px" }}>
                        <div style={{ fontSize: 10.5, fontWeight: 700, color: "#86198f", textTransform: "uppercase" }}>Now Serving</div>
                        <div style={{ fontSize: 20, fontWeight: 800, color: "#240729", marginTop: 2 }}>
                          {q.current_token ? `#${String(q.current_token).padStart(2, "0")}` : "—"}
                        </div>
                      </div>
                      <div style={{ background: "#fefce8", border: "1px solid #fde047", borderRadius: 10, padding: "8px 10px" }}>
                        <div style={{ fontSize: 10.5, fontWeight: 700, color: "#a16207", textTransform: "uppercase" }}>Next Token</div>
                        <div style={{ fontSize: 20, fontWeight: 800, color: "#713f12", marginTop: 2 }}>
                          {q.next_token ? `#${String(q.next_token).padStart(2, "0")}` : "—"}
                        </div>
                      </div>
                      <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 10, padding: "8px 10px" }}>
                        <div style={{ fontSize: 10.5, fontWeight: 700, color: "#475569", textTransform: "uppercase" }}>Waiting / Done</div>
                        <div style={{ fontSize: 18, fontWeight: 800, color: "#0f172a", marginTop: 2 }}>
                          {q.waiting_count} / {q.completed_count}
                        </div>
                      </div>
                    </div>

                    {/* Quick Call Next / Complete Bar */}
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                      {q.current_appointment && (
                        <button
                          type="button"
                          onClick={() =>
                            handleStatusUpdate(
                              q.current_appointment,
                              { status: "completed" },
                              `Completed Token ${q.current_appointment.token_display}.`
                            )
                          }
                          style={{
                            border: "none",
                            background: "#059669",
                            color: "#fff",
                            borderRadius: 8,
                            padding: "6px 12px",
                            fontSize: 12,
                            fontWeight: 700,
                            cursor: "pointer",
                          }}
                        >
                          ✓ Complete {q.current_appointment.token_display}
                        </button>
                      )}
                      {q.next_appointment && (
                        <button
                          type="button"
                          onClick={() =>
                            handleStatusUpdate(
                              q.next_appointment,
                              { status: "in_consultation" },
                              `Called Token ${q.next_appointment.token_display} into consultation.`
                            )
                          }
                          style={{
                            border: "none",
                            background: "#0f172a",
                            color: "#fff",
                            borderRadius: 8,
                            padding: "6px 12px",
                            fontSize: 12,
                            fontWeight: 700,
                            cursor: "pointer",
                          }}
                        >
                          ▶ Call Next ({q.next_appointment.token_display})
                        </button>
                      )}
                    </div>

                    {/* Queue List */}
                    {(q.queue || []).length === 0 ? (
                      <div style={{ fontSize: 12.5, color: "#94a3b8", padding: "8px 0", textAlign: "center" }}>
                        No appointments scheduled for {queueDate}.
                      </div>
                    ) : (
                      <div style={{ display: "grid", gap: 6, maxHeight: 290, overflowY: "auto" }}>
                        {q.queue.map((a) => {
                          const st = STATUS_BADGES[a.status] || STATUS_BADGES.booked;
                          return (
                            <div
                              key={a.id}
                              style={{
                                border: `1px solid ${a.status === "in_consultation" ? ACCENT : "#e2e8f0"}`,
                                background: a.status === "in_consultation" ? "#fdf4ff" : "#f8fafc",
                                borderRadius: 10,
                                padding: "8px 10px",
                                display: "flex",
                                justifyContent: "space-between",
                                alignItems: "center",
                                gap: 8,
                                flexWrap: "wrap",
                              }}
                            >
                              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                                <span
                                  style={{
                                    background: "#0f172a",
                                    color: "#fff",
                                    fontWeight: 800,
                                    fontSize: 12,
                                    borderRadius: 8,
                                    padding: "3px 8px",
                                  }}
                                >
                                  {a.token_display}
                                </span>
                                <div>
                                  <div style={{ fontSize: 13, fontWeight: 700, color: "#0f172a" }}>
                                    {a.patient_name}
                                  </div>
                                  <div style={{ fontSize: 11.5, color: "#64748b" }}>
                                    {a.patient_phone || "—"} • {formatMoney(a.consultation_fee)}{" "}
                                    <span style={{ fontWeight: 700, color: a.payment_status === "paid" ? "#047857" : "#b45309" }}>
                                      ({a.payment_status === "paid" ? "Paid" : "Unpaid"})
                                    </span>
                                  </div>
                                </div>
                              </div>

                              <div style={{ display: "flex", alignItems: "center", gap: 5, flexWrap: "wrap" }}>
                                <span
                                  style={{
                                    fontSize: 10.5,
                                    fontWeight: 700,
                                    background: st.bg,
                                    color: st.color,
                                    border: `1px solid ${st.border}`,
                                    borderRadius: 999,
                                    padding: "2px 8px",
                                  }}
                                >
                                  {st.label}
                                </span>
                                {a.status === "booked" && (
                                  <button
                                    type="button"
                                    onClick={() => handleStatusUpdate(a, { status: "checked_in" }, `Checked in Token ${a.token_display}.`)}
                                    style={{ border: "1px solid #cbd5e1", background: "#fff", color: "#0f172a", borderRadius: 6, padding: "3px 7px", fontSize: 11, fontWeight: 700, cursor: "pointer" }}
                                  >
                                    Check In
                                  </button>
                                )}
                                {(a.status === "booked" || a.status === "checked_in") && (
                                  <button
                                    type="button"
                                    onClick={() => handleStatusUpdate(a, { status: "in_consultation" }, `Started consultation for Token ${a.token_display}.`)}
                                    style={{ border: "none", background: ACCENT, color: "#240729", borderRadius: 6, padding: "3px 8px", fontSize: 11, fontWeight: 800, cursor: "pointer" }}
                                  >
                                    Start
                                  </button>
                                )}
                                {a.status === "in_consultation" && (
                                  <button
                                    type="button"
                                    onClick={() => handleStatusUpdate(a, { status: "completed" }, `Completed Token ${a.token_display}.`)}
                                    style={{ border: "none", background: "#059669", color: "#fff", borderRadius: 6, padding: "3px 8px", fontSize: 11, fontWeight: 700, cursor: "pointer" }}
                                  >
                                    Complete
                                  </button>
                                )}
                                {a.payment_status !== "paid" && a.status !== "cancelled" && (
                                  <button
                                    type="button"
                                    onClick={() => handleStatusUpdate(a, { payment_status: "paid" }, `Marked Token ${a.token_display} as Paid.`)}
                                    style={{ border: "1px solid #a7f3d0", background: "#ecfdf5", color: "#047857", borderRadius: 6, padding: "3px 7px", fontSize: 11, fontWeight: 700, cursor: "pointer" }}
                                  >
                                    Mark Paid
                                  </button>
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* TAB 2: ALL APPOINTMENTS */}
        {tab === "appointments" && (
          <div style={{ display: "grid", gap: 12 }}>
            {/* Filter Controls */}
            <div
              style={{
                background: "#fff",
                border: "1px solid #e2e8f0",
                borderRadius: 14,
                padding: 14,
                display: "grid",
                gap: 10,
              }}
            >
              <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
                <input
                  type="date"
                  value={filterDate}
                  onChange={(e) => setFilterDate(e.target.value)}
                  style={{ padding: "8px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }}
                />
                {filterDate && (
                  <button
                    type="button"
                    onClick={() => setFilterDate("")}
                    style={{ border: "1px solid #e2e8f0", background: "#f8fafc", color: "#475569", borderRadius: 8, padding: "7px 10px", fontSize: 12, fontWeight: 600, cursor: "pointer" }}
                  >
                    All Dates
                  </button>
                )}
                <select
                  value={filterDoctor}
                  onChange={(e) => setFilterDoctor(e.target.value)}
                  style={{ padding: "8px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13, background: "#fff" }}
                >
                  <option value="">All Doctors</option>
                  {doctors.map((d) => (
                    <option key={d.id} value={d.id}>{d.full_name}</option>
                  ))}
                </select>
                <input
                  type="text"
                  placeholder="Search patient name, phone, or token #..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  style={{ flex: "1 1 220px", padding: "8px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }}
                />
              </div>

              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {STATUS_FILTER_OPTIONS.map((opt) => (
                  <button
                    key={opt.key}
                    type="button"
                    onClick={() => setFilterStatus(opt.key)}
                    style={{
                      border: filterStatus === opt.key ? `1.5px solid ${ACCENT}` : "1px solid #e2e8f0",
                      background: filterStatus === opt.key ? "#0f172a" : "#fff",
                      color: filterStatus === opt.key ? "#fff" : "#475569",
                      borderRadius: 999,
                      padding: "5px 12px",
                      fontSize: 12,
                      fontWeight: 700,
                      cursor: "pointer",
                    }}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Table */}
            <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 14, overflow: "hidden" }}>
              {loading ? (
                <div style={{ padding: 40, textAlign: "center", color: "#64748b", fontSize: 13 }}>
                  Loading appointments...
                </div>
              ) : appointments.length === 0 ? (
                <div style={{ padding: 44, textAlign: "center", color: "#64748b", fontSize: 13 }}>
                  No OPD appointments match your filters. Click <strong>+ Book OPD Appointment</strong> to add one.
                </div>
              ) : (
                <div style={{ overflowX: "auto" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                    <thead>
                      <tr style={{ background: "#f8fafc", textAlign: "left", color: "#475569" }}>
                        <th style={{ padding: "12px 14px", fontWeight: 700 }}>Token</th>
                        <th style={{ padding: "12px 14px", fontWeight: 700 }}>Patient</th>
                        <th style={{ padding: "12px 14px", fontWeight: 700 }}>Doctor &amp; Dept</th>
                        <th style={{ padding: "12px 14px", fontWeight: 700 }}>Date &amp; Time</th>
                        <th style={{ padding: "12px 14px", fontWeight: 700 }}>Fee / Payment</th>
                        <th style={{ padding: "12px 14px", fontWeight: 700 }}>Source</th>
                        <th style={{ padding: "12px 14px", fontWeight: 700 }}>Status</th>
                        <th style={{ padding: "12px 14px", fontWeight: 700, textAlign: "right" }}>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {appointments.map((a) => {
                        const st = STATUS_BADGES[a.status] || STATUS_BADGES.booked;
                        const src = SOURCE_BADGES[a.booking_source] || SOURCE_BADGES.walk_in;
                        return (
                          <tr key={a.id} style={{ borderTop: "1px solid #f1f5f9" }}>
                            <td style={{ padding: "12px 14px" }}>
                              <span style={{ background: "#0f172a", color: "#fff", borderRadius: 8, padding: "4px 9px", fontWeight: 800, fontSize: 12 }}>
                                {a.token_display}
                              </span>
                            </td>
                            <td style={{ padding: "12px 14px" }}>
                              <div style={{ fontWeight: 700, color: "#0f172a" }}>{a.patient_name}</div>
                              <div style={{ fontSize: 11.5, color: "#64748b" }}>
                                {a.patient_phone || "—"}
                                {a.patient_age ? ` • ${a.patient_age}y` : ""}
                                {a.patient_gender ? ` • ${a.patient_gender}` : ""}
                              </div>
                            </td>
                            <td style={{ padding: "12px 14px" }}>
                              <div style={{ fontWeight: 700, color: "#0f172a" }}>{a.doctor_name}</div>
                              <div style={{ fontSize: 11.5, color: "#64748b" }}>
                                {a.department_name || a.doctor_specialization || "OPD"}
                                {a.visit_type === "follow_up" ? " • Follow-up" : a.visit_type === "emergency" ? " • Emergency" : ""}
                              </div>
                            </td>
                            <td style={{ padding: "12px 14px", color: "#334155" }}>
                              <div style={{ fontWeight: 600 }}>{a.appointment_date}</div>
                              <div style={{ fontSize: 11.5, color: "#64748b" }}>{formatTime12h(a.appointment_time)}</div>
                            </td>
                            <td style={{ padding: "12px 14px" }}>
                              <div style={{ fontWeight: 700, color: "#0f172a" }}>{formatMoney(a.consultation_fee)}</div>
                              <span
                                style={{
                                  display: "inline-block",
                                  marginTop: 2,
                                  fontSize: 10.5,
                                  fontWeight: 700,
                                  padding: "1px 7px",
                                  borderRadius: 999,
                                  background: a.payment_status === "paid" ? "#ecfdf5" : "#fffbeb",
                                  color: a.payment_status === "paid" ? "#047857" : "#b45309",
                                }}
                              >
                                {a.payment_status === "paid" ? "Paid" : "Unpaid"}
                              </span>
                            </td>
                            <td style={{ padding: "12px 14px" }}>
                              <span style={{ fontSize: 11, fontWeight: 700, background: src.bg, color: src.color, padding: "3px 8px", borderRadius: 999 }}>
                                {src.label}
                              </span>
                            </td>
                            <td style={{ padding: "12px 14px" }}>
                              <span
                                style={{
                                  fontSize: 11,
                                  fontWeight: 700,
                                  background: st.bg,
                                  color: st.color,
                                  border: `1px solid ${st.border}`,
                                  padding: "3px 9px",
                                  borderRadius: 999,
                                }}
                              >
                                {st.label}
                              </span>
                            </td>
                            <td style={{ padding: "12px 14px", textAlign: "right" }}>
                              <div style={{ display: "inline-flex", gap: 5, flexWrap: "wrap", justifyContent: "flex-end" }}>
                                {a.status === "booked" && (
                                  <button
                                    type="button"
                                    onClick={() => handleStatusUpdate(a, { status: "checked_in" }, `Checked in ${a.token_display}.`)}
                                    style={{ border: "1px solid #cbd5e1", background: "#fff", color: "#0f172a", borderRadius: 6, padding: "4px 8px", fontSize: 11, fontWeight: 700, cursor: "pointer" }}
                                  >
                                    Check In
                                  </button>
                                )}
                                {(a.status === "booked" || a.status === "checked_in") && (
                                  <button
                                    type="button"
                                    onClick={() => handleStatusUpdate(a, { status: "in_consultation" }, `Started ${a.token_display}.`)}
                                    style={{ border: "none", background: ACCENT, color: "#240729", borderRadius: 6, padding: "4px 8px", fontSize: 11, fontWeight: 800, cursor: "pointer" }}
                                  >
                                    Start
                                  </button>
                                )}
                                {a.status === "in_consultation" && (
                                  <button
                                    type="button"
                                    onClick={() => handleStatusUpdate(a, { status: "completed" }, `Completed ${a.token_display}.`)}
                                    style={{ border: "none", background: "#059669", color: "#fff", borderRadius: 6, padding: "4px 8px", fontSize: 11, fontWeight: 700, cursor: "pointer" }}
                                  >
                                    Complete
                                  </button>
                                )}
                                {a.payment_status !== "paid" && a.status !== "cancelled" && (
                                  <button
                                    type="button"
                                    onClick={() => handleStatusUpdate(a, { payment_status: "paid" }, `Marked ${a.token_display} Paid.`)}
                                    style={{ border: "1px solid #a7f3d0", background: "#ecfdf5", color: "#047857", borderRadius: 6, padding: "4px 8px", fontSize: 11, fontWeight: 700, cursor: "pointer" }}
                                  >
                                    Mark Paid
                                  </button>
                                )}
                                <button
                                  type="button"
                                  onClick={() => openEditModal(a)}
                                  style={{ border: "1px solid #cbd5e1", background: "#fff", color: "#334155", borderRadius: 6, padding: "4px 8px", fontSize: 11, fontWeight: 700, cursor: "pointer" }}
                                >
                                  Edit
                                </button>
                                <button
                                  type="button"
                                  onClick={() => handleDeleteAppointment(a)}
                                  style={{ border: "1px solid #fecaca", background: "#fff", color: "#b91c1c", borderRadius: 6, padding: "4px 8px", fontSize: 11, fontWeight: 700, cursor: "pointer" }}
                                >
                                  Delete
                                </button>
                              </div>
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

      {/* BOOK / EDIT APPOINTMENT MODAL */}
      {showModal && (
        <div
          onClick={() => {
            setShowModal(false);
            setEditingAppt(null);
          }}
          style={{ position: "fixed", inset: 0, background: "rgba(15,23,42,0.48)", zIndex: 1000, display: "grid", placeItems: "center", padding: 16 }}
        >
          <form
            onClick={(e) => e.stopPropagation()}
            onSubmit={handleSaveAppointment}
            style={{ width: "100%", maxWidth: 520, maxHeight: "90vh", overflowY: "auto", background: "#fff", borderRadius: 16, padding: 22, display: "grid", gap: 12 }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h3 style={{ margin: 0, fontSize: 17, fontWeight: 800 }}>
                {editingAppt ? `✏️ Edit Appointment (${editingAppt.token_display})` : "📅 Book OPD Appointment"}
              </h3>
              <button
                type="button"
                onClick={() => {
                  setShowModal(false);
                  setEditingAppt(null);
                }}
                style={{ border: "none", background: "transparent", fontSize: 18, cursor: "pointer" }}
              >
                ✕
              </button>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <div>
                <label style={{ fontSize: 11.5, fontWeight: 700, color: "#475569", display: "block", marginBottom: 4 }}>Doctor *</label>
                <select
                  required
                  disabled={Boolean(editingAppt)}
                  value={form.doctor_id}
                  onChange={(e) => handleDoctorChange(e.target.value)}
                  style={{ width: "100%", padding: "9px 10px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13, background: editingAppt ? "#f8fafc" : "#fff" }}
                >
                  <option value="">— Select Doctor —</option>
                  {doctors.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.full_name} {d.department_name ? `(${d.department_name})` : ""}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label style={{ fontSize: 11.5, fontWeight: 700, color: "#475569", display: "block", marginBottom: 4 }}>Department</label>
                <select
                  value={form.department_id}
                  onChange={(e) => setForm({ ...form, department_id: e.target.value })}
                  style={{ width: "100%", padding: "9px 10px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13, background: "#fff" }}
                >
                  <option value="">— Auto from Doctor —</option>
                  {departments.map((d) => (
                    <option key={d.id} value={d.id}>{d.name}</option>
                  ))}
                </select>
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10 }}>
              <div>
                <label style={{ fontSize: 11.5, fontWeight: 700, color: "#475569", display: "block", marginBottom: 4 }}>Visit Type</label>
                <select
                  value={form.visit_type}
                  onChange={(e) => handleVisitTypeChange(e.target.value)}
                  style={{ width: "100%", padding: "9px 10px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13, background: "#fff" }}
                >
                  <option value="new">New Visit</option>
                  <option value="follow_up">Follow-up</option>
                  <option value="emergency">Emergency</option>
                </select>
              </div>
              <div>
                <label style={{ fontSize: 11.5, fontWeight: 700, color: "#475569", display: "block", marginBottom: 4 }}>Date *</label>
                <input
                  required
                  type="date"
                  disabled={Boolean(editingAppt)}
                  value={form.appointment_date}
                  onChange={(e) => setForm({ ...form, appointment_date: e.target.value })}
                  style={{ width: "100%", padding: "8px 10px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }}
                />
              </div>
              <div>
                <label style={{ fontSize: 11.5, fontWeight: 700, color: "#475569", display: "block", marginBottom: 4 }}>Time</label>
                <input
                  type="time"
                  value={form.appointment_time}
                  onChange={(e) => setForm({ ...form, appointment_time: e.target.value })}
                  style={{ width: "100%", padding: "8px 10px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }}
                />
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <input
                required
                placeholder="Patient Full Name *"
                value={form.patient_name}
                onChange={(e) => setForm({ ...form, patient_name: e.target.value })}
                style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }}
              />
              <input
                required
                placeholder="Patient Phone * (03xx-xxxxxxx)"
                value={form.patient_phone}
                onChange={(e) => setForm({ ...form, patient_phone: e.target.value })}
                style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }}
              />
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10 }}>
              <input
                type="number"
                min="0"
                max="150"
                placeholder="Age (yrs)"
                value={form.patient_age}
                onChange={(e) => setForm({ ...form, patient_age: e.target.value })}
                style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }}
              />
              <select
                value={form.patient_gender}
                onChange={(e) => setForm({ ...form, patient_gender: e.target.value })}
                style={{ padding: "9px 10px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13, background: "#fff" }}
              >
                <option value="">Gender</option>
                <option value="Male">Male</option>
                <option value="Female">Female</option>
                <option value="Other">Other</option>
              </select>
              <input
                type="number"
                min="0"
                step="50"
                placeholder="Fee (Rs.)"
                value={form.consultation_fee}
                onChange={(e) => setForm({ ...form, consultation_fee: e.target.value })}
                style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }}
              />
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <select
                value={form.payment_status}
                onChange={(e) => setForm({ ...form, payment_status: e.target.value })}
                style={{ padding: "9px 10px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13, background: "#fff" }}
              >
                <option value="unpaid">Payment: Unpaid</option>
                <option value="paid">Payment: Paid</option>
              </select>
              <select
                value={form.booking_source}
                onChange={(e) => setForm({ ...form, booking_source: e.target.value })}
                style={{ padding: "9px 10px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13, background: "#fff" }}
              >
                <option value="walk_in">Source: Walk-in</option>
                <option value="phone">Source: Phone</option>
                <option value="whatsapp_ai">Source: WhatsApp AI</option>
                <option value="web_voice_ai">Source: Website Voice AI</option>
              </select>
            </div>

            <textarea
              rows={2}
              placeholder="Chief Complaint / Reason for Visit"
              value={form.chief_complaint}
              onChange={(e) => setForm({ ...form, chief_complaint: e.target.value })}
              style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }}
            />

            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
              <button
                type="button"
                onClick={() => {
                  setShowModal(false);
                  setEditingAppt(null);
                }}
                style={{ border: "1px solid #cbd5e1", background: "#fff", borderRadius: 9, padding: "8px 14px", fontSize: 12.5, fontWeight: 700, cursor: "pointer" }}
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={saving}
                style={{ border: "none", background: ACCENT, color: "#240729", borderRadius: 9, padding: "8px 16px", fontSize: 13, fontWeight: 800, cursor: "pointer" }}
              >
                {saving ? "Saving..." : editingAppt ? "Save Changes" : "Book & Issue Token"}
              </button>
            </div>
          </form>
        </div>
      )}
    </Layout>
  );
}
