import { useCallback, useEffect, useState } from "react";
import OwnerLayout from "../owner/components/OwnerLayout";
import StaffLayout from "../staff/components/StaffLayout";
import { clinicApi } from "../api/operationsApi";
import { errorText } from "../api/axiosClient";

const css = `
.dr-container {
  display: flex;
  flex-direction: column;
  gap: 18px;
  width: 100%;
}
.dr-kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 14px;
}
.dr-kpi-card {
  background: #ffffff;
  border: 1px solid #e8e3ec;
  border-radius: 14px;
  padding: 16px 18px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.02);
}
.dr-kpi-label {
  font-size: 12px;
  color: #6b7280;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.dr-kpi-val {
  font-size: 26px;
  font-weight: 800;
  margin-top: 4px;
  color: #1e1b24;
}
.dr-panel {
  background: #ffffff;
  border: 1px solid #e8e3ec;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 2px 10px rgba(0,0,0,0.03);
}
.dr-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 16px 20px;
  border-bottom: 1px solid #f1ebf4;
  flex-wrap: wrap;
}
.dr-search-input {
  height: 40px;
  padding: 0 14px;
  border: 1px solid #e2dce6;
  border-radius: 10px;
  font-size: 13.5px;
  background: #ffffff;
  color: #1e1b24;
  outline: none;
  min-width: 260px;
}
.dr-search-input:focus {
  border-color: #ff77ff;
}
.dr-btn-primary {
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
.dr-btn-primary:hover {
  background: #f05cf0;
  transform: translateY(-1px);
}
.dr-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
  padding: 20px;
}
.dr-card {
  background: #ffffff;
  border: 1px solid #e8e3ec;
  border-radius: 14px;
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  transition: all .2s;
}
.dr-card:hover {
  box-shadow: 0 4px 16px rgba(0,0,0,0.05);
  border-color: #dcc8e2;
}
.dr-card-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}
.dr-card-name {
  font-size: 16px;
  font-weight: 800;
  color: #1e1b24;
}
.dr-card-specialty {
  font-size: 13px;
  color: #c026d3;
  font-weight: 700;
  margin-top: 2px;
}
.dr-card-qual {
  font-size: 12px;
  color: #6b7280;
  margin-top: 2px;
}
.dr-card-fee {
  display: flex;
  align-items: baseline;
  gap: 6px;
  font-size: 13px;
  color: #4b5563;
}
.dr-card-fee strong {
  font-size: 18px;
  color: #1e1b24;
  font-weight: 800;
}
.dr-card-timings {
  font-size: 12.5px;
  color: #4b5563;
  background: #faf8fb;
  padding: 8px 12px;
  border-radius: 8px;
}
.dr-card-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 6px;
  border-top: 1px solid #f4eff6;
  padding-top: 12px;
}
.dr-btn-sm {
  padding: 6px 12px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid #e2dce6;
  background: #ffffff;
}
.dr-btn-sm:hover {
  border-color: #ff77ff;
  color: #c026d3;
}
.dr-badge-active {
  padding: 3px 8px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 700;
}
.dr-badge-active.active { background: #d1fae5; color: #065f46; }
.dr-badge-active.inactive { background: #fee2e2; color: #991b1b; }

.dr-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(17,12,23,0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 999;
  padding: 16px;
}
.dr-modal {
  background: #ffffff;
  border-radius: 18px;
  width: 100%;
  max-width: 520px;
  padding: 24px;
  box-shadow: 0 10px 35px rgba(0,0,0,0.15);
}
.dr-form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 14px;
}
.dr-form-group label {
  font-size: 12.5px;
  font-weight: 700;
  color: #4b5563;
}
.dr-form-input {
  border: 1px solid #e2dce6;
  border-radius: 9px;
  padding: 9px 12px;
  font-size: 13.5px;
  color: #1e1b24;
  outline: none;
}
.dr-form-input:focus {
  border-color: #ff77ff;
}
.dr-alert-banner {
  padding: 11px 16px;
  border-radius: 10px;
  font-size: 13.5px;
  margin-bottom: 14px;
}
.dr-alert-banner.error { background: #fee2e2; color: #991b1b; }
.dr-alert-banner.success { background: #d1fae5; color: #065f46; }
`;

export default function ClinicDoctors({ staff = false }) {
  const [doctors, setDoctors] = useState([]);
  const [summary, setSummary] = useState({ total_doctors: 0, active_doctors: 0, specialties_count: 0 });
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [feedback, setFeedback] = useState(null);

  // Add / Edit Modal
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState({
    name: "",
    specialty: "",
    qualification: "",
    consultation_fee: "",
    available_days: "Mon-Sat",
    available_hours: "10:00 AM - 06:00 PM",
    is_active: true,
  });
  const [submitting, setSubmitting] = useState(false);

  const loadDoctors = useCallback(async () => {
    try {
      setLoading(true);
      const params = {};
      if (search.trim()) params.search = search.trim();
      const res = await clinicApi.getDoctors(params);
      setDoctors(res.data?.doctors || []);
      setSummary(res.data?.summary || {});
    } catch (err) {
      setFeedback({ type: "error", msg: errorText(err, "Failed to load clinic doctors.") });
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => {
    loadDoctors();
  }, [loadDoctors]);

  const openCreate = () => {
    setEditingId(null);
    setForm({
      name: "",
      specialty: "",
      qualification: "",
      consultation_fee: "",
      available_days: "Mon-Sat",
      available_hours: "10:00 AM - 06:00 PM",
      is_active: true,
    });
    setShowModal(true);
  };

  const openEdit = (doc) => {
    setEditingId(doc.id);
    setForm({
      name: doc.name,
      specialty: doc.specialty,
      qualification: doc.qualification || "",
      consultation_fee: doc.consultation_fee || "",
      available_days: doc.available_days || "Mon-Sat",
      available_hours: doc.available_hours || "10:00 AM - 06:00 PM",
      is_active: doc.is_active,
    });
    setShowModal(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.name.trim() || !form.specialty.trim()) {
      setFeedback({ type: "error", msg: "Doctor name and specialty are required." });
      return;
    }
    try {
      setSubmitting(true);
      if (editingId) {
        await clinicApi.updateDoctor(editingId, form);
        setFeedback({ type: "success", msg: "Doctor updated successfully!" });
      } else {
        await clinicApi.createDoctor(form);
        setFeedback({ type: "success", msg: "Doctor added successfully!" });
      }
      setShowModal(false);
      loadDoctors();
    } catch (err) {
      setFeedback({ type: "error", msg: errorText(err, "Failed to save doctor.") });
    } finally {
      setSubmitting(false);
    }
  };

  const toggleActive = async (doc) => {
    try {
      await clinicApi.updateDoctor(doc.id, { is_active: !doc.is_active });
      loadDoctors();
    } catch (err) {
      setFeedback({ type: "error", msg: errorText(err, "Failed to update doctor status.") });
    }
  };

  const content = (
    <div className="dr-container">
      <style>{css}</style>

      {feedback && (
        <div className={`dr-alert-banner ${feedback.type}`}>
          {feedback.msg}
        </div>
      )}

      {/* KPI Cards */}
      <div className="dr-kpi-grid">
        <div className="dr-kpi-card">
          <div className="dr-kpi-label">Total Doctors</div>
          <div className="dr-kpi-val">{summary.total_doctors || 0}</div>
        </div>
        <div className="dr-kpi-card">
          <div className="dr-kpi-label" style={{ color: "#059669" }}>Active Practicing</div>
          <div className="dr-kpi-val" style={{ color: "#059669" }}>{summary.active_doctors || 0}</div>
        </div>
        <div className="dr-kpi-card">
          <div className="dr-kpi-label" style={{ color: "#c026d3" }}>Specialties Count</div>
          <div className="dr-kpi-val" style={{ color: "#c026d3" }}>{summary.specialties_count || 0}</div>
        </div>
      </div>

      {/* Main Doctors Directory Panel */}
      <div className="dr-panel">
        <div className="dr-toolbar">
          <input
            type="text"
            placeholder="Search doctors by name, specialty, qualification..."
            className="dr-search-input"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />

          {!staff && (
            <button className="dr-btn-primary" onClick={openCreate}>
              + Add Doctor
            </button>
          )}
        </div>

        {loading ? (
          <div style={{ textAlign: "center", padding: "40px", color: "#6b7280" }}>Loading doctors...</div>
        ) : doctors.length === 0 ? (
          <div style={{ textAlign: "center", padding: "40px", color: "#6b7280" }}>
            No doctors found. Click "+ Add Doctor" to register your medical staff.
          </div>
        ) : (
          <div className="dr-grid">
            {doctors.map((doc) => (
              <div className="dr-card" key={doc.id}>
                <div className="dr-card-head">
                  <div>
                    <div className="dr-card-name">{doc.name}</div>
                    <div className="dr-card-specialty">{doc.specialty}</div>
                    {doc.qualification && <div className="dr-card-qual">{doc.qualification}</div>}
                  </div>
                  <span className={`dr-badge-active ${doc.is_active ? "active" : "inactive"}`}>
                    {doc.is_active ? "Active" : "Inactive"}
                  </span>
                </div>

                <div className="dr-card-fee">
                  <span>Fee:</span>
                  <strong>Rs. {doc.consultation_fee}</strong>
                </div>

                <div className="dr-card-timings">
                  <div>📅 {doc.available_days}</div>
                  <div>⏰ {doc.available_hours}</div>
                </div>

                {!staff && (
                  <div className="dr-card-actions">
                    <button className="dr-btn-sm" onClick={() => toggleActive(doc)}>
                      {doc.is_active ? "Deactivate" : "Activate"}
                    </button>
                    <button className="dr-btn-sm" onClick={() => openEdit(doc)}>
                      Edit Details
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Add / Edit Doctor Modal */}
      {showModal && (
        <div className="dr-modal-overlay" onClick={() => setShowModal(false)}>
          <div className="dr-modal" onClick={(e) => e.stopPropagation()}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "18px" }}>
              <h3 style={{ margin: 0, fontSize: "19px", fontWeight: "800", color: "#1e1b24" }}>
                {editingId ? "Edit Doctor Profile" : "Register New Doctor"}
              </h3>
              <button style={{ background: "none", border: "none", fontSize: "20px", cursor: "pointer", color: "#6b7280" }} onClick={() => setShowModal(false)}>
                ✕
              </button>
            </div>

            <form onSubmit={handleSubmit}>
              <div className="dr-form-group">
                <label>Doctor Full Name *</label>
                <input
                  required
                  className="dr-form-input"
                  placeholder="e.g. Dr. Ayesha Tariq"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                />
              </div>

              <div className="dr-form-group">
                <label>Medical Specialty *</label>
                <input
                  required
                  className="dr-form-input"
                  placeholder="e.g. General Physician, Cardiologist, Dermatologist"
                  value={form.specialty}
                  onChange={(e) => setForm({ ...form, specialty: e.target.value })}
                />
              </div>

              <div className="dr-form-group">
                <label>Qualifications</label>
                <input
                  className="dr-form-input"
                  placeholder="e.g. MBBS, FCPS, MD"
                  value={form.qualification}
                  onChange={(e) => setForm({ ...form, qualification: e.target.value })}
                />
              </div>

              <div className="dr-form-group">
                <label>Consultation Fee (Rs.)</label>
                <input
                  type="number"
                  min="0"
                  step="1"
                  className="dr-form-input"
                  placeholder="e.g. 1500"
                  value={form.consultation_fee}
                  onChange={(e) => setForm({ ...form, consultation_fee: e.target.value })}
                />
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
                <div className="dr-form-group">
                  <label>Available Days</label>
                  <input
                    className="dr-form-input"
                    placeholder="e.g. Mon-Sat"
                    value={form.available_days}
                    onChange={(e) => setForm({ ...form, available_days: e.target.value })}
                  />
                </div>
                <div className="dr-form-group">
                  <label>Available Hours</label>
                  <input
                    className="dr-form-input"
                    placeholder="e.g. 10:00 AM - 04:00 PM"
                    value={form.available_hours}
                    onChange={(e) => setForm({ ...form, available_hours: e.target.value })}
                  />
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "10px", margin: "14px 0" }}>
                <input
                  type="checkbox"
                  id="dr_active_toggle"
                  style={{ width: "18px", height: "18px", accentColor: "#ff77ff" }}
                  checked={form.is_active}
                  onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                />
                <label htmlFor="dr_active_toggle" style={{ fontSize: "13.5px", fontWeight: "600", cursor: "pointer", margin: 0 }}>
                  Active Practicing Doctor
                </label>
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
                  className="dr-btn-primary"
                >
                  {submitting ? "Saving..." : editingId ? "Update Doctor" : "Add Doctor"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );

  return staff ? (
    <StaffLayout title="Doctors Directory" subtitle="View active clinic doctors, specialties and consultation timings.">
      {content}
    </StaffLayout>
  ) : (
    <OwnerLayout title="Doctors Directory" subtitle="Manage clinic medical specialists, consultation fees, and available hours.">
      {content}
    </OwnerLayout>
  );
}
