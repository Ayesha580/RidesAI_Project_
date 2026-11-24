import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import OwnerLayout from "../owner/components/OwnerLayout";
import StaffLayout from "../staff/components/StaffLayout";
import { clinicApi, hospitalApi } from "../api/operationsApi";
import { errorText } from "../api/axiosClient";

const WARD_TYPES = [
  ["opd", "OPD"],
  ["emergency", "Emergency"],
  ["icu", "ICU"],
  ["general_ward", "General Ward"],
  ["maternity", "Maternity"],
  ["diagnostics", "Lab / Diagnostics"],
];

const LAB_STATUS_COLORS = {
  scheduled: { bg: "#fdf4ff", color: "#a21caf" },
  checked_in: { bg: "#eff6ff", color: "#1d4ed8" },
  completed: { bg: "#f0fdf4", color: "#15803d" },
  cancelled: { bg: "#fef2f2", color: "#b91c1c" },
};

export default function HospitalDashboard({ staff = false, defaultTab = "departments" }) {
  const [activeTab, setActiveTab] = useState(defaultTab);
  const [summary, setSummary] = useState(null);
  const [departments, setDepartments] = useState([]);
  const [doctors, setDoctors] = useState([]);
  const [appointments, setAppointments] = useState([]);
  const [labBookings, setLabBookings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState(null);

  const [deptForm, setDeptForm] = useState({
    name: "",
    ward_type: "opd",
    floor_or_location: "",
    total_beds: 0,
    available_beds: 0,
    is_24_7: false,
  });

  const [labForm, setLabForm] = useState({
    patient_name: "",
    patient_phone: "",
    test_name: "",
    price: "",
    scheduled_time: "",
  });

  const loadAll = async () => {
    setError("");
    try {
      const [sumRes, deptRes, docRes, apptRes, labRes] = await Promise.allSettled([
        hospitalApi.getSummary(),
        hospitalApi.getDepartments(),
        clinicApi.getDoctors(),
        clinicApi.getAppointments(),
        hospitalApi.getLabBookings(),
      ]);
      if (sumRes.status === "fulfilled") setSummary(sumRes.value.data);
      if (deptRes.status === "fulfilled") setDepartments(Array.isArray(deptRes.value.data) ? deptRes.value.data : []);
      if (docRes.status === "fulfilled") setDoctors(Array.isArray(docRes.value.data) ? docRes.value.data : []);
      if (apptRes.status === "fulfilled") setAppointments(Array.isArray(apptRes.value.data) ? apptRes.value.data : []);
      if (labRes.status === "fulfilled") setLabBookings(Array.isArray(labRes.value.data) ? labRes.value.data : []);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
  }, []);

  const createDepartment = async (e) => {
    e.preventDefault();
    if (!deptForm.name.trim()) return;
    setError("");
    try {
      await hospitalApi.createDepartment({
        ...deptForm,
        total_beds: Number(deptForm.total_beds || 0),
        available_beds: Number(deptForm.available_beds || 0),
      });
      setDeptForm({ name: "", ward_type: "opd", floor_or_location: "", total_beds: 0, available_beds: 0, is_24_7: false });
      await loadAll();
    } catch (err) {
      setError(errorText(err));
    }
  };

  const adjustBeds = async (dept, delta) => {
    const nextBeds = Math.max(0, Math.min(dept.total_beds, dept.available_beds + delta));
    setBusyId(`bed-${dept.id}`);
    try {
      await hospitalApi.updateDepartment(dept.id, { available_beds: nextBeds });
      await loadAll();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusyId(null);
    }
  };

  const deleteDepartment = async (deptId) => {
    setBusyId(`del-${deptId}`);
    try {
      await hospitalApi.deleteDepartment(deptId);
      await loadAll();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusyId(null);
    }
  };

  const createLabBooking = async (e) => {
    e.preventDefault();
    if (!labForm.patient_name.trim() || !labForm.test_name.trim()) return;
    setError("");
    try {
      await hospitalApi.createLabBooking(labForm);
      setLabForm({ patient_name: "", patient_phone: "", test_name: "", price: "", scheduled_time: "" });
      await loadAll();
    } catch (err) {
      setError(errorText(err));
    }
  };

  const updateLabStatus = async (bookingId, status) => {
    setBusyId(`lab-${bookingId}`);
    try {
      await hospitalApi.updateLabBookingStatus(bookingId, { status });
      await loadAll();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusyId(null);
    }
  };

  const Layout = staff ? StaffLayout : OwnerLayout;

  return (
    <Layout
      title="Hospital Operations"
      subtitle="Departments, ward bed availability, specialist doctors, OPD appointments & diagnostic lab bookings."
    >
      {error && <div className="ad-alert" role="alert">{error}</div>}

      {/* Top KPI Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 12, marginBottom: 18 }}>
        {[
          { icon: "🏥", label: "Departments", value: summary?.departments_count ?? departments.length },
          { icon: "🛏️", label: "Available Beds", value: `${summary?.available_beds ?? 0} / ${summary?.total_beds ?? 0}` },
          { icon: "👨‍⚕️", label: "Doctors on Duty", value: summary?.doctors_on_duty ?? doctors.length },
          { icon: "🩺", label: "Today's OPD", value: summary?.today_opd_appointments ?? 0 },
          { icon: "🧪", label: "Active Lab Bookings", value: summary?.scheduled_lab_bookings ?? 0 },
        ].map((card) => (
          <div key={card.label} style={{ background: "#fff", border: "1px solid #f0abfc", borderRadius: 14, padding: "14px 16px" }}>
            <div style={{ fontSize: 12, color: "#64748b", fontWeight: 600 }}>{card.icon} {card.label}</div>
            <div style={{ fontSize: 22, fontWeight: 800, color: "#0f172a", marginTop: 4 }}>{card.value}</div>
          </div>
        ))}
      </div>

      {/* Tab Navigation + AI Voice Agent Shortcut */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 10, marginBottom: 18 }}>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {[
            ["departments", "🏥 Departments & Beds"],
            ["doctors", "👨‍⚕️ Doctors & OPD"],
            ["lab_tests", "🧪 Lab Bookings"],
            ["appointments", "🩺 OPD Appointments"],
          ].map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => setActiveTab(key)}
              style={{
                padding: "9px 15px",
                borderRadius: 12,
                border: activeTab === key ? "1px solid #ff77ff" : "1px solid #e2e8f0",
                background: activeTab === key ? "#ff77ff" : "#fff",
                color: activeTab === key ? "#fff" : "#475569",
                fontWeight: 700,
                fontSize: 13,
                cursor: "pointer",
              }}
            >
              {label}
            </button>
          ))}
        </div>

        {!staff && (
          <Link
            to="/owner/ai-agent"
            style={{
              padding: "9px 14px",
              borderRadius: 12,
              background: "#fdf4ff",
              border: "1px solid #f0abfc",
              color: "#a21caf",
              fontWeight: 700,
              fontSize: 12.5,
              textDecoration: "none",
            }}
          >
            🎙️ AI Voice Agent
          </Link>
        )}
      </div>

      {loading ? (
        <p style={{ color: "#64748b" }}>Loading hospital operations...</p>
      ) : activeTab === "departments" ? (
        <div style={{ display: "grid", gap: 18 }}>
          <form onSubmit={createDepartment} style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 14, padding: 16 }}>
            <h4 style={{ margin: "0 0 12px" }}>Add Department / Ward</h4>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 10 }}>
              <input placeholder="Department name (e.g. Cardiology)" value={deptForm.name} onChange={(e) => setDeptForm({ ...deptForm, name: e.target.value })} required />
              <select value={deptForm.ward_type} onChange={(e) => setDeptForm({ ...deptForm, ward_type: e.target.value })}>
                {WARD_TYPES.map(([val, lbl]) => <option key={val} value={val}>{lbl}</option>)}
              </select>
              <input placeholder="Floor / Wing (e.g. 2nd Floor)" value={deptForm.floor_or_location} onChange={(e) => setDeptForm({ ...deptForm, floor_or_location: e.target.value })} />
              <input type="number" min="0" placeholder="Total Beds" value={deptForm.total_beds} onChange={(e) => setDeptForm({ ...deptForm, total_beds: e.target.value, available_beds: e.target.value })} />
              <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}>
                <input type="checkbox" checked={deptForm.is_24_7} onChange={(e) => setDeptForm({ ...deptForm, is_24_7: e.target.checked })} />
                24/7 Open
              </label>
            </div>
            <button type="submit" className="ad-btn ad-btn-primary" style={{ marginTop: 12 }}>+ Add Department</button>
          </form>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 12 }}>
            {departments.length === 0 ? (
              <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 14, padding: 20, color: "#64748b" }}>
                No hospital departments configured yet. Add Emergency, OPD, Cardiology, or Lab/Diagnostics above.
              </div>
            ) : departments.map((dept) => (
              <div key={dept.id} style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 14, padding: 16 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
                  <div>
                    <h4 style={{ margin: 0, fontSize: 15.5 }}>{dept.name}</h4>
                    <div style={{ fontSize: 12, color: "#64748b", marginTop: 3 }}>
                      {dept.ward_type_label}{dept.floor_or_location ? ` · ${dept.floor_or_location}` : ""}
                    </div>
                  </div>
                  {dept.is_24_7 && (
                    <span style={{ fontSize: 11, fontWeight: 700, padding: "2px 8px", borderRadius: 10, background: "#fef2f2", color: "#dc2626" }}>24/7</span>
                  )}
                </div>

                {dept.total_beds > 0 && (
                  <div style={{ marginTop: 12, display: "flex", alignItems: "center", justifyContent: "space-between", background: "#faf5ff", padding: "8px 12px", borderRadius: 10 }}>
                    <span style={{ fontSize: 13, fontWeight: 700, color: "#7e22ce" }}>
                      🛏️ {dept.available_beds} / {dept.total_beds} beds free
                    </span>
                    <div style={{ display: "flex", gap: 6 }}>
                      <button type="button" disabled={busyId === `bed-${dept.id}`} onClick={() => adjustBeds(dept, -1)} style={{ padding: "3px 9px", borderRadius: 8, border: "1px solid #d8b4fe", background: "#fff", cursor: "pointer" }}>-</button>
                      <button type="button" disabled={busyId === `bed-${dept.id}`} onClick={() => adjustBeds(dept, 1)} style={{ padding: "3px 9px", borderRadius: 8, border: "1px solid #d8b4fe", background: "#fff", cursor: "pointer" }}>+</button>
                    </div>
                  </div>
                )}

                {!staff && (
                  <button
                    type="button"
                    disabled={busyId === `del-${dept.id}`}
                    onClick={() => deleteDepartment(dept.id)}
                    style={{ marginTop: 10, fontSize: 12, color: "#ef4444", background: "none", border: "none", cursor: "pointer", padding: 0 }}
                  >
                    Remove
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      ) : activeTab === "lab_tests" ? (
        <div style={{ display: "grid", gap: 18 }}>
          <form onSubmit={createLabBooking} style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 14, padding: 16 }}>
            <h4 style={{ margin: "0 0 12px" }}>New Lab / Diagnostic Test Booking</h4>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 10 }}>
              <input placeholder="Patient Name" value={labForm.patient_name} onChange={(e) => setLabForm({ ...labForm, patient_name: e.target.value })} required />
              <input placeholder="Phone (03xx...)" value={labForm.patient_phone} onChange={(e) => setLabForm({ ...labForm, patient_phone: e.target.value })} />
              <input placeholder="Test Name (e.g. CBC, Lipid Profile)" value={labForm.test_name} onChange={(e) => setLabForm({ ...labForm, test_name: e.target.value })} required />
              <input type="number" min="0" placeholder="Fee (Rs.)" value={labForm.price} onChange={(e) => setLabForm({ ...labForm, price: e.target.value })} />
              <input placeholder="Time (e.g. 10:00 AM)" value={labForm.scheduled_time} onChange={(e) => setLabForm({ ...labForm, scheduled_time: e.target.value })} />
            </div>
            <button type="submit" className="ad-btn ad-btn-primary" style={{ marginTop: 12 }}>+ Book Lab Test</button>
          </form>

          <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 14, padding: 16 }}>
            <h4 style={{ marginTop: 0 }}>Diagnostic & Lab Bookings ({labBookings.length})</h4>
            {labBookings.length === 0 ? (
              <p style={{ color: "#64748b" }}>No lab test bookings yet.</p>
            ) : (
              <div style={{ display: "grid", gap: 10 }}>
                {labBookings.map((b) => {
                  const badge = LAB_STATUS_COLORS[b.status] || { bg: "#f1f5f9", color: "#334155" };
                  return (
                    <div key={b.id} style={{ border: "1px solid #f1f5f9", borderRadius: 12, padding: 12, display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 10 }}>
                      <div>
                        <div style={{ fontWeight: 700, fontSize: 14 }}>{b.booking_number} · {b.test_name}</div>
                        <div style={{ fontSize: 12.5, color: "#64748b" }}>
                          {b.patient_name}{b.patient_phone ? ` (${b.patient_phone})` : ""} · Rs. {b.price} · {b.scheduled_date} {b.scheduled_time}
                        </div>
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span style={{ fontSize: 11, fontWeight: 700, padding: "3px 9px", borderRadius: 10, background: badge.bg, color: badge.color, textTransform: "uppercase" }}>
                          {b.status.replace("_", " ")}
                        </span>
                        {b.status === "scheduled" && (
                          <button type="button" disabled={busyId === `lab-${b.id}`} onClick={() => updateLabStatus(b.id, "checked_in")} className="ad-btn" style={{ fontSize: 12 }}>Check In</button>
                        )}
                        {(b.status === "scheduled" || b.status === "checked_in") && (
                          <button type="button" disabled={busyId === `lab-${b.id}`} onClick={() => updateLabStatus(b.id, "completed")} className="ad-btn ad-btn-primary" style={{ fontSize: 12 }}>Complete</button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      ) : activeTab === "doctors" ? (
        <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 14, padding: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <h4 style={{ margin: 0 }}>Specialist Doctors ({doctors.length})</h4>
            <Link to={staff ? "/staff/doctors" : "/owner/m/doctors"} style={{ fontSize: 13, color: "#a21caf", fontWeight: 600 }}>Manage Doctors →</Link>
          </div>
          {doctors.length === 0 ? (
            <p style={{ color: "#64748b" }}>No doctors added yet. Open Doctors Directory to add specialists & OPD schedules.</p>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(230px, 1fr))", gap: 10 }}>
              {doctors.map((d) => (
                <div key={d.id} style={{ border: "1px solid #f1f5f9", borderRadius: 12, padding: 12 }}>
                  <div style={{ fontWeight: 700 }}>{d.name}</div>
                  <div style={{ fontSize: 12.5, color: "#64748b" }}>{d.specialty}{d.qualification ? ` · ${d.qualification}` : ""}</div>
                  <div style={{ fontSize: 12, color: "#7e22ce", marginTop: 4 }}>Rs. {d.consultation_fee} · {d.available_days} ({d.available_hours})</div>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 14, padding: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <h4 style={{ margin: 0 }}>OPD Appointments ({appointments.length})</h4>
            <Link to={staff ? "/staff/appointments" : "/owner/m/appointments"} style={{ fontSize: 13, color: "#a21caf", fontWeight: 600 }}>Manage OPD Appointments →</Link>
          </div>
          {appointments.length === 0 ? (
            <p style={{ color: "#64748b" }}>No OPD appointments booked yet.</p>
          ) : (
            <div style={{ display: "grid", gap: 8 }}>
              {appointments.slice(0, 20).map((a) => (
                <div key={a.id} style={{ border: "1px solid #f1f5f9", borderRadius: 10, padding: 10, display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
                  <div>
                    <strong>{a.appointment_number}</strong> · {a.patient_name} ({a.patient_phone})
                    <div style={{ fontSize: 12, color: "#64748b" }}>{a.doctor_name || "OPD"} · {a.appointment_date} {a.appointment_time}</div>
                  </div>
                  <span style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", color: "#a21caf" }}>{a.status}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </Layout>
  );
}
