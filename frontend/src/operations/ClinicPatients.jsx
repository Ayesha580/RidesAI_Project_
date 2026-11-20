import { useCallback, useEffect, useState } from "react";
import OwnerLayout from "../owner/components/OwnerLayout";
import StaffLayout from "../staff/components/StaffLayout";
import { clinicApi } from "../api/operationsApi";
import { errorText } from "../api/axiosClient";

const css = `
.pt-container {
  display: flex;
  flex-direction: column;
  gap: 18px;
  width: 100%;
}
.pt-panel {
  background: #ffffff;
  border: 1px solid #e8e3ec;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 2px 10px rgba(0,0,0,0.03);
}
.pt-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 16px 20px;
  border-bottom: 1px solid #f1ebf4;
  flex-wrap: wrap;
}
.pt-search-input {
  height: 40px;
  padding: 0 14px;
  border: 1px solid #e2dce6;
  border-radius: 10px;
  font-size: 13.5px;
  background: #ffffff;
  color: #1e1b24;
  outline: none;
  min-width: 280px;
}
.pt-search-input:focus {
  border-color: #ff77ff;
}
.pt-btn-primary {
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
.pt-btn-primary:hover {
  background: #f05cf0;
  transform: translateY(-1px);
}
.pt-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
}
.pt-table th {
  background: #faf8fb;
  padding: 12px 18px;
  font-size: 11.5px;
  text-transform: uppercase;
  color: #6b7280;
  font-weight: 750;
  letter-spacing: 0.5px;
  border-bottom: 1px solid #eee8f0;
}
.pt-table td {
  padding: 15px 18px;
  font-size: 13.5px;
  color: #2b2733;
  border-bottom: 1px solid #f4eff6;
  vertical-align: middle;
}
.pt-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(17,12,23,0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 999;
  padding: 16px;
}
.pt-modal {
  background: #ffffff;
  border-radius: 18px;
  width: 100%;
  max-width: 480px;
  padding: 24px;
  box-shadow: 0 10px 35px rgba(0,0,0,0.15);
}
.pt-form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 14px;
}
.pt-form-group label {
  font-size: 12.5px;
  font-weight: 700;
  color: #4b5563;
}
.pt-form-input, .pt-form-textarea {
  border: 1px solid #e2dce6;
  border-radius: 9px;
  padding: 9px 12px;
  font-size: 13.5px;
  color: #1e1b24;
  outline: none;
}
.pt-form-input:focus, .pt-form-textarea:focus {
  border-color: #ff77ff;
}
.pt-alert-banner {
  padding: 11px 16px;
  border-radius: 10px;
  font-size: 13.5px;
  margin-bottom: 14px;
}
.pt-alert-banner.error { background: #fee2e2; color: #991b1b; }
.pt-alert-banner.success { background: #d1fae5; color: #065f46; }
`;

export default function ClinicPatients({ staff = false }) {
  const [patients, setPatients] = useState([]);
  const [summary, setSummary] = useState({ total_patients: 0 });
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [feedback, setFeedback] = useState(null);

  // Add / Edit Modal
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState({
    name: "",
    phone: "",
    age: "",
    gender: "",
    notes: "",
  });
  const [submitting, setSubmitting] = useState(false);

  const loadPatients = useCallback(async () => {
    try {
      setLoading(true);
      const params = {};
      if (search.trim()) params.search = search.trim();
      const res = await clinicApi.getPatients(params);
      setPatients(res.data?.patients || []);
      setSummary(res.data?.summary || {});
    } catch (err) {
      setFeedback({ type: "error", msg: errorText(err, "Failed to load clinic patients.") });
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => {
    loadPatients();
  }, [loadPatients]);

  const openCreate = () => {
    setEditingId(null);
    setForm({ name: "", phone: "", age: "", gender: "", notes: "" });
    setShowModal(true);
  };

  const openEdit = (p) => {
    setEditingId(p.id);
    setForm({
      name: p.name,
      phone: p.phone,
      age: p.age ?? "",
      gender: p.gender || "",
      notes: p.notes || "",
    });
    setShowModal(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.name.trim() || !form.phone.trim()) {
      setFeedback({ type: "error", msg: "Patient name and phone number are required." });
      return;
    }
    try {
      setSubmitting(true);
      if (editingId) {
        await clinicApi.updatePatient(editingId, form);
        setFeedback({ type: "success", msg: "Patient details updated successfully!" });
      } else {
        await clinicApi.createPatient(form);
        setFeedback({ type: "success", msg: "Patient registered successfully!" });
      }
      setShowModal(false);
      loadPatients();
    } catch (err) {
      setFeedback({ type: "error", msg: errorText(err, "Failed to save patient.") });
    } finally {
      setSubmitting(false);
    }
  };

  const content = (
    <div className="pt-container">
      <style>{css}</style>

      {feedback && (
        <div className={`pt-alert-banner ${feedback.type}`}>
          {feedback.msg}
        </div>
      )}

      {/* Main Patients Directory Panel */}
      <div className="pt-panel">
        <div className="pt-toolbar">
          <input
            type="text"
            placeholder="Search patients by name, phone, or medical notes..."
            className="pt-search-input"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />

          <button className="pt-btn-primary" onClick={openCreate}>
            + Add Patient
          </button>
        </div>

        <div style={{ overflowX: "auto" }}>
          <table className="pt-table">
            <thead>
              <tr>
                <th>Patient Name</th>
                <th>Phone Number</th>
                <th>Age / Gender</th>
                <th>Notes / History</th>
                <th>Total Appointments</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="6" style={{ textAlign: "center", padding: "40px", color: "#6b7280" }}>
                    Loading patient records...
                  </td>
                </tr>
              ) : patients.length === 0 ? (
                <tr>
                  <td colSpan="6" style={{ textAlign: "center", padding: "40px", color: "#6b7280" }}>
                    No patient records found. Click "+ Add Patient" to register a patient.
                  </td>
                </tr>
              ) : (
                patients.map((p) => (
                  <tr key={p.id}>
                    <td>
                      <strong style={{ fontSize: "14px" }}>{p.name}</strong>
                    </td>
                    <td>
                      <span style={{ fontFamily: "monospace", fontSize: "13px" }}>📞 {p.phone}</span>
                    </td>
                    <td>
                      {p.age ? `${p.age} yrs` : "—"} {p.gender ? `· ${p.gender}` : ""}
                    </td>
                    <td>
                      <span style={{ color: p.notes ? "#374151" : "#9ca3af" }}>
                        {p.notes || "No notes"}
                      </span>
                    </td>
                    <td>
                      <span style={{ background: "#f3e8ff", color: "#7e22ce", padding: "3px 9px", borderRadius: "12px", fontWeight: "700", fontSize: "12px" }}>
                        {p.total_appointments} visits
                      </span>
                    </td>
                    <td>
                      <button
                        style={{ padding: "5px 12px", borderRadius: "8px", border: "1px solid #e2dce6", background: "#ffffff", fontSize: "12px", fontWeight: "600", cursor: "pointer" }}
                        onClick={() => openEdit(p)}
                      >
                        Edit
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Add / Edit Patient Modal */}
      {showModal && (
        <div className="pt-modal-overlay" onClick={() => setShowModal(false)}>
          <div className="pt-modal" onClick={(e) => e.stopPropagation()}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "18px" }}>
              <h3 style={{ margin: 0, fontSize: "19px", fontWeight: "800", color: "#1e1b24" }}>
                {editingId ? "Edit Patient Details" : "Register New Patient"}
              </h3>
              <button style={{ background: "none", border: "none", fontSize: "20px", cursor: "pointer", color: "#6b7280" }} onClick={() => setShowModal(false)}>
                ✕
              </button>
            </div>

            <form onSubmit={handleSubmit}>
              <div className="pt-form-group">
                <label>Patient Full Name *</label>
                <input
                  required
                  className="pt-form-input"
                  placeholder="e.g. Usman Ali"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                />
              </div>

              <div className="pt-form-group">
                <label>Phone Number *</label>
                <input
                  required
                  className="pt-form-input"
                  placeholder="e.g. 03001234567"
                  value={form.phone}
                  onChange={(e) => setForm({ ...form, phone: e.target.value })}
                />
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
                <div className="pt-form-group">
                  <label>Age</label>
                  <input
                    type="number"
                    min="0"
                    max="130"
                    className="pt-form-input"
                    placeholder="e.g. 35"
                    value={form.age}
                    onChange={(e) => setForm({ ...form, age: e.target.value })}
                  />
                </div>
                <div className="pt-form-group">
                  <label>Gender</label>
                  <select
                    className="pt-form-input"
                    value={form.gender}
                    onChange={(e) => setForm({ ...form, gender: e.target.value })}
                  >
                    <option value="">Select gender</option>
                    <option value="Male">Male</option>
                    <option value="Female">Female</option>
                    <option value="Other">Other</option>
                  </select>
                </div>
              </div>

              <div className="pt-form-group">
                <label>Medical Notes / Chronic Conditions</label>
                <textarea
                  rows="3"
                  className="pt-form-textarea"
                  placeholder="e.g. Diabetic, hypertensive, allergic to penicillin"
                  value={form.notes}
                  onChange={(e) => setForm({ ...form, notes: e.target.value })}
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
                  className="pt-btn-primary"
                >
                  {submitting ? "Saving..." : editingId ? "Update Patient" : "Register Patient"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );

  return staff ? (
    <StaffLayout title="Patients Directory" subtitle="View and search registered clinic patient files.">
      {content}
    </StaffLayout>
  ) : (
    <OwnerLayout title="Patients Directory" subtitle="Manage registered patients, contact details, and medical records.">
      {content}
    </OwnerLayout>
  );
}
