import { useCallback, useEffect, useState } from "react";
import OwnerLayout from "../owner/components/OwnerLayout";
import StaffLayout from "../staff/components/StaffLayout";
import { clinicApi } from "../api/operationsApi";
import { errorText } from "../api/axiosClient";

const css = `
.cl-container {
  display: flex;
  flex-direction: column;
  gap: 18px;
  width: 100%;
}
.cl-kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 14px;
}
.cl-kpi-card {
  background: #ffffff;
  border: 1px solid #e8e3ec;
  border-radius: 14px;
  padding: 16px 18px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.02);
}
.cl-kpi-label {
  font-size: 12px;
  color: #6b7280;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.cl-kpi-val {
  font-size: 26px;
  font-weight: 800;
  margin-top: 4px;
  color: #1e1b24;
}
.cl-panel {
  background: #ffffff;
  border: 1px solid #e8e3ec;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 2px 10px rgba(0,0,0,0.03);
}
.cl-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 16px 20px;
  border-bottom: 1px solid #f1ebf4;
  flex-wrap: wrap;
}
.cl-filter-group {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.cl-search-input, .cl-select-input {
  height: 40px;
  padding: 0 14px;
  border: 1px solid #e2dce6;
  border-radius: 10px;
  font-size: 13.5px;
  background: #ffffff;
  color: #1e1b24;
  outline: none;
  transition: border-color .2s;
}
.cl-search-input:focus, .cl-select-input:focus {
  border-color: #ff77ff;
}
.cl-btn-primary {
  height: 40px;
  padding: 0 18px;
  background: #ff77ff;
  color: #ffffff;
  border: none;
  border-radius: 10px;
  font-size: 13.5px;
  font-weight: 700;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  box-shadow: 0 3px 10px rgba(255,119,255,0.22);
  transition: all .2s;
}
.cl-btn-primary:hover {
  background: #f05cf0;
  transform: translateY(-1px);
}
.cl-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
}
.cl-table th {
  background: #faf8fb;
  padding: 12px 18px;
  font-size: 11.5px;
  text-transform: uppercase;
  color: #6b7280;
  font-weight: 750;
  letter-spacing: 0.5px;
  border-bottom: 1px solid #eee8f0;
}
.cl-table td {
  padding: 15px 18px;
  font-size: 13.5px;
  color: #2b2733;
  border-bottom: 1px solid #f4eff6;
  vertical-align: middle;
}
.cl-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 11.5px;
  font-weight: 750;
  text-transform: capitalize;
}
.cl-badge.pending { background: #fef3c7; color: #92400e; border: 1px solid #fde68a; }
.cl-badge.confirmed { background: #d1fae5; color: #065f46; border: 1px solid #a7f3d0; }
.cl-badge.checked_in { background: #e0e7ff; color: #3730a3; border: 1px solid #c7d2fe; }
.cl-badge.completed { background: #d1fae5; color: #047857; border: 1px solid #a7f3d0; }
.cl-badge.cancelled { background: #fee2e2; color: #991b1b; border: 1px solid #fecaca; }
.cl-badge.no_show { background: #f3f4f6; color: #4b5563; border: 1px solid #e5e7eb; }

.cl-source-badge {
  font-size: 11px;
  padding: 2px 7px;
  border-radius: 6px;
  font-weight: 700;
  text-transform: uppercase;
}
.cl-source-badge.whatsapp_ai { background: #f3e8ff; color: #7e22ce; }
.cl-source-badge.dashboard { background: #f3f4f6; color: #4b5563; }

.cl-action-select {
  padding: 5px 8px;
  border-radius: 8px;
  border: 1px solid #d8d2dc;
  font-size: 12.5px;
  font-weight: 600;
  background: #ffffff;
  color: #1e1b24;
  outline: none;
  cursor: pointer;
}
.cl-action-select:focus {
  border-color: #ff77ff;
}
.cl-action-select:disabled {
  background: #f9f8fa;
  color: #9ca3af;
  cursor: not-allowed;
  border-color: #e5e7eb;
}

.cl-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(17,12,23,0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 999;
  padding: 16px;
}
.cl-modal {
  background: #ffffff;
  border-radius: 18px;
  width: 100%;
  max-width: 520px;
  padding: 24px;
  box-shadow: 0 10px 35px rgba(0,0,0,0.15);
}
.cl-modal-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 18px;
}
.cl-modal-head h3 {
  margin: 0;
  font-size: 19px;
  font-weight: 800;
  color: #1e1b24;
}
.cl-modal-close {
  background: none;
  border: none;
  font-size: 20px;
  cursor: pointer;
  color: #6b7280;
}
.cl-form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 14px;
}
.cl-form-group label {
  font-size: 12.5px;
  font-weight: 700;
  color: #4b5563;
}
.cl-form-input, .cl-form-textarea {
  border: 1px solid #e2dce6;
  border-radius: 9px;
  padding: 9px 12px;
  font-size: 13.5px;
  color: #1e1b24;
  outline: none;
}
.cl-form-input:focus, .cl-form-textarea:focus {
  border-color: #ff77ff;
}
.cl-alert-banner {
  padding: 11px 16px;
  border-radius: 10px;
  font-size: 13.5px;
  margin-bottom: 14px;
}
.cl-alert-banner.error {
  background: #fee2e2;
  color: #991b1b;
  border: 1px solid #fecaca;
}
.cl-alert-banner.success {
  background: #d1fae5;
  color: #065f46;
  border: 1px solid #a7f3d0;
}
`;

export default function ClinicAppointments({ staff = false }) {
  const [appointments, setAppointments] = useState([]);
  const [doctors, setDoctors] = useState([]);
  const [summary, setSummary] = useState({
    total: 0, pending: 0, confirmed: 0, checked_in: 0, completed: 0, cancelled: 0, no_show: 0
  });
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("all");
  const [doctorFilter, setDoctorFilter] = useState("");
  const [search, setSearch] = useState("");
  const [feedback, setFeedback] = useState(null);

  // Book appointment modal
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({
    patient_name: "",
    patient_phone: "",
    doctor_id: "",
    appointment_date: "",
    appointment_time: "",
    reason: "",
    staff_notes: "",
  });
  const [submitting, setSubmitting] = useState(false);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const params = {};
      if (statusFilter && statusFilter !== "all") params.status = statusFilter;
      if (doctorFilter) params.doctor_id = doctorFilter;
      if (search.trim()) params.search = search.trim();

      const [aptRes, docRes] = await Promise.all([
        clinicApi.getAppointments(params),
        clinicApi.getDoctors({ is_active: "true" }),
      ]);

      setAppointments(aptRes.data?.appointments || []);
      setSummary(aptRes.data?.summary || {});
      setDoctors(docRes.data?.doctors || []);
    } catch (err) {
      setFeedback({ type: "error", msg: errorText(err, "Failed to load clinic appointments.") });
    } finally {
      setLoading(false);
    }
  }, [statusFilter, doctorFilter, search]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleStatusChange = async (aptId, newStatus) => {
    try {
      await clinicApi.updateAppointmentStatus(aptId, { status: newStatus });
      setFeedback({ type: "success", msg: `Appointment status updated to '${newStatus}'.` });
      loadData();
    } catch (err) {
      setFeedback({ type: "error", msg: errorText(err, "Failed to update appointment status.") });
    }
  };

  const handleBookSubmit = async (e) => {
    e.preventDefault();
    if (!form.patient_name.trim() || !form.patient_phone.trim()) {
      setFeedback({ type: "error", msg: "Patient name and phone are required." });
      return;
    }
    try {
      setSubmitting(true);
      await clinicApi.createAppointment(form);
      setFeedback({ type: "success", msg: "Appointment booked successfully!" });
      setShowModal(false);
      setForm({
        patient_name: "",
        patient_phone: "",
        doctor_id: "",
        appointment_date: "",
        appointment_time: "",
        reason: "",
        staff_notes: "",
      });
      loadData();
    } catch (err) {
      setFeedback({ type: "error", msg: errorText(err, "Failed to book appointment.") });
    } finally {
      setSubmitting(false);
    }
  };

  const content = (
    <div className="cl-container">
      <style>{css}</style>

      {feedback && (
        <div className={`cl-alert-banner ${feedback.type}`}>
          {feedback.msg}
        </div>
      )}

      {/* KPI Cards */}
      <div className="cl-kpi-grid">
        <div className="cl-kpi-card">
          <div className="cl-kpi-label">Total Appointments</div>
          <div className="cl-kpi-val">{summary.total || 0}</div>
        </div>
        <div className="cl-kpi-card">
          <div className="cl-kpi-label" style={{ color: "#d97706" }}>Pending</div>
          <div className="cl-kpi-val" style={{ color: "#d97706" }}>{summary.pending || 0}</div>
        </div>
        <div className="cl-kpi-card">
          <div className="cl-kpi-label" style={{ color: "#059669" }}>Confirmed</div>
          <div className="cl-kpi-val" style={{ color: "#059669" }}>{summary.confirmed || 0}</div>
        </div>
        <div className="cl-kpi-card">
          <div className="cl-kpi-label" style={{ color: "#4f46e5" }}>Checked In</div>
          <div className="cl-kpi-val" style={{ color: "#4f46e5" }}>{summary.checked_in || 0}</div>
        </div>
        <div className="cl-kpi-card">
          <div className="cl-kpi-label" style={{ color: "#10b981" }}>Completed</div>
          <div className="cl-kpi-val" style={{ color: "#10b981" }}>{summary.completed || 0}</div>
        </div>
      </div>

      {/* Main Table Panel */}
      <div className="cl-panel">
        <div className="cl-toolbar">
          <div className="cl-filter-group">
            <input
              type="text"
              placeholder="Search APT#, patient, phone..."
              className="cl-search-input"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <select
              className="cl-select-input"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="all">All Statuses</option>
              <option value="pending">Pending</option>
              <option value="confirmed">Confirmed</option>
              <option value="checked_in">Checked In</option>
              <option value="completed">Completed</option>
              <option value="cancelled">Cancelled</option>
              <option value="no_show">No Show</option>
            </select>
            <select
              className="cl-select-input"
              value={doctorFilter}
              onChange={(e) => setDoctorFilter(e.target.value)}
            >
              <option value="">All Doctors</option>
              {doctors.map((d) => (
                <option key={d.id} value={d.id}>{d.name} ({d.specialty})</option>
              ))}
            </select>
          </div>

          <button className="cl-btn-primary" onClick={() => setShowModal(true)}>
            + Book Appointment
          </button>
        </div>

        <div style={{ overflowX: "auto" }}>
          <table className="cl-table">
            <thead>
              <tr>
                <th>Reference #</th>
                <th>Patient Details</th>
                <th>Doctor & Specialty</th>
                <th>Schedule</th>
                <th>Source</th>
                <th>Status</th>
                <th>Update Status</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="7" style={{ textAlign: "center", padding: "35px", color: "#6b7280" }}>
                    Loading appointments...
                  </td>
                </tr>
              ) : appointments.length === 0 ? (
                <tr>
                  <td colSpan="7" style={{ textAlign: "center", padding: "40px", color: "#6b7280" }}>
                    No appointments found matching current filters.
                  </td>
                </tr>
              ) : (
                appointments.map((apt) => {
                  const isTerminal = ["completed", "cancelled", "no_show"].includes(apt.status);
                  return (
                    <tr key={apt.id}>
                      <td>
                        <strong>{apt.appointment_number}</strong>
                        <div style={{ fontSize: "11px", color: "#8a8190" }}>{apt.formatted_date}</div>
                      </td>
                      <td>
                        <strong style={{ fontSize: "14px" }}>{apt.patient_name}</strong>
                        <div style={{ fontSize: "12px", color: "#6b7280" }}>📞 {apt.patient_phone}</div>
                        {apt.reason && <div style={{ fontSize: "11.5px", color: "#8a8190", marginTop: "2px" }}>Note: {apt.reason}</div>}
                      </td>
                      <td>
                        <strong>{apt.doctor_name}</strong>
                        {apt.doctor_specialty && (
                          <div style={{ fontSize: "12px", color: "#c026d3", fontWeight: "600" }}>
                            {apt.doctor_specialty} · Rs. {apt.doctor_fee}
                          </div>
                        )}
                      </td>
                      <td>
                        <div>📅 {apt.appointment_date || "Not set"}</div>
                        <div style={{ fontSize: "12px", color: "#6b7280" }}>⏰ {apt.appointment_time || "—"}</div>
                      </td>
                      <td>
                        <span className={`cl-source-badge ${apt.source}`}>
                          {apt.source === "whatsapp_ai" ? "WhatsApp AI" : apt.source}
                        </span>
                      </td>
                      <td>
                        <span className={`cl-badge ${apt.status}`}>{apt.status_display}</span>
                      </td>
                      <td>
                        <select
                          className="cl-action-select"
                          disabled={isTerminal}
                          value={apt.status}
                          onChange={(e) => handleStatusChange(apt.id, e.target.value)}
                        >
                          <option value={apt.status} disabled>{apt.status_display}</option>
                          {apt.status === "pending" && (
                            <>
                              <option value="confirmed">Confirm</option>
                              <option value="cancelled">Cancel</option>
                            </>
                          )}
                          {apt.status === "confirmed" && (
                            <>
                              <option value="checked_in">Mark Checked-In</option>
                              <option value="completed">Mark Completed</option>
                              <option value="cancelled">Cancel</option>
                              <option value="no_show">Mark No-Show</option>
                            </>
                          )}
                          {apt.status === "checked_in" && (
                            <>
                              <option value="completed">Mark Completed</option>
                              <option value="cancelled">Cancel</option>
                            </>
                          )}
                        </select>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Book Appointment Modal */}
      {showModal && (
        <div className="cl-modal-overlay" onClick={() => setShowModal(false)}>
          <div className="cl-modal" onClick={(e) => e.stopPropagation()}>
            <div className="cl-modal-head">
              <h3>Book New Appointment</h3>
              <button className="cl-modal-close" onClick={() => setShowModal(false)}>✕</button>
            </div>

            <form onSubmit={handleBookSubmit}>
              <div className="cl-form-group">
                <label>Patient Name *</label>
                <input
                  required
                  className="cl-form-input"
                  placeholder="e.g. Tariq Mehmood"
                  value={form.patient_name}
                  onChange={(e) => setForm({ ...form, patient_name: e.target.value })}
                />
              </div>

              <div className="cl-form-group">
                <label>Patient Phone Number *</label>
                <input
                  required
                  className="cl-form-input"
                  placeholder="e.g. 03001234567"
                  value={form.patient_phone}
                  onChange={(e) => setForm({ ...form, patient_phone: e.target.value })}
                />
              </div>

              <div className="cl-form-group">
                <label>Select Doctor</label>
                <select
                  className="cl-form-input"
                  value={form.doctor_id}
                  onChange={(e) => setForm({ ...form, doctor_id: e.target.value })}
                >
                  <option value="">Unassigned / Any available</option>
                  {doctors.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name} ({d.specialty}) — Fee: Rs. {d.consultation_fee}
                    </option>
                  ))}
                </select>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
                <div className="cl-form-group">
                  <label>Date</label>
                  <input
                    type="date"
                    className="cl-form-input"
                    value={form.appointment_date}
                    onChange={(e) => setForm({ ...form, appointment_date: e.target.value })}
                  />
                </div>
                <div className="cl-form-group">
                  <label>Time</label>
                  <input
                    type="text"
                    placeholder="e.g. 11:30 AM"
                    className="cl-form-input"
                    value={form.appointment_time}
                    onChange={(e) => setForm({ ...form, appointment_time: e.target.value })}
                  />
                </div>
              </div>

              <div className="cl-form-group">
                <label>Reason / Symptoms</label>
                <textarea
                  rows="2"
                  className="cl-form-textarea"
                  placeholder="e.g. Routine checkup, fever, chest discomfort"
                  value={form.reason}
                  onChange={(e) => setForm({ ...form, reason: e.target.value })}
                />
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "18px" }}>
                <button
                  type="button"
                  style={{ background: "#f3f4f6", border: "none", padding: "10px 18px", borderRadius: "9px", cursor: "pointer", fontWeight: "600" }}
                  onClick={() => setShowModal(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="cl-btn-primary"
                >
                  {submitting ? "Booking..." : "Book Appointment"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );

  return staff ? (
    <StaffLayout title="Appointments" subtitle="Review and update clinic patient appointments.">
      {content}
    </StaffLayout>
  ) : (
    <OwnerLayout title="Appointments" subtitle="Manage clinic doctors, patient bookings, and appointment schedules.">
      {content}
    </OwnerLayout>
  );
}
