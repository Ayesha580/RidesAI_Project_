import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import OwnerLayout from "../owner/components/OwnerLayout";
import StaffLayout from "../staff/components/StaffLayout";
import { hospitalApi } from "../api/operationsApi";

const ACCENT = "#ff77ff";
const BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", "unknown"];

const EMPTY_PATIENT = {
  full_name: "",
  phone: "",
  cnic: "",
  age: "",
  gender: "",
  blood_group: "unknown",
  allergies: "",
  chronic_conditions: "",
  emergency_contact_name: "",
  emergency_contact_phone: "",
  address: "",
};

function formatDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("en-PK", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return String(iso).slice(0, 10);
  }
}

export default function HospitalPatients({ staff = false }) {
  const Layout = staff ? StaffLayout : OwnerLayout;
  const navigate = useNavigate();

  const [patients, setPatients] = useState([]);
  const [summary, setSummary] = useState({ total_patients: 0, with_allergies: 0, blood_groups: {} });
  const [search, setSearch] = useState("");
  const [bloodFilter, setBloodFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState("");
  const [error, setError] = useState("");

  // Register / Edit modal
  const [showModal, setShowModal] = useState(false);
  const [editingPatient, setEditingPatient] = useState(null);
  const [form, setForm] = useState(EMPTY_PATIENT);

  // Patient 360° EMR Drawer / Modal
  const [emrPatient, setEmrPatient] = useState(null);
  const [emrLoading, setEmrLoading] = useState(false);
  const [emrTab, setEmrTab] = useState("prescriptions"); // "prescriptions" | "appointments" | "admissions"

  const showToast = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(""), 3500);
  };

  const loadPatients = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const params = {};
      if (search.trim()) params.search = search.trim();
      if (bloodFilter && bloodFilter !== "all") params.blood_group = bloodFilter;
      const { data } = await hospitalApi.listPatients(params);
      setPatients(data?.results || []);
      if (data?.summary) setSummary(data.summary);
    } catch (err) {
      setError(err?.response?.data?.detail || "Could not load patients directory.");
    } finally {
      if (!silent) setLoading(false);
    }
  }, [search, bloodFilter]);

  useEffect(() => {
    loadPatients();
  }, [loadPatients]);

  const openRegisterModal = () => {
    setEditingPatient(null);
    setForm(EMPTY_PATIENT);
    setShowModal(true);
  };

  const openEditModal = (p) => {
    setEditingPatient(p);
    setForm({
      full_name: p.full_name || "",
      phone: p.phone || "",
      cnic: p.cnic || "",
      age: p.age ?? "",
      gender: p.gender || "",
      blood_group: p.blood_group || "unknown",
      allergies: p.allergies || "",
      chronic_conditions: p.chronic_conditions || "",
      emergency_contact_name: p.emergency_contact_name || "",
      emergency_contact_phone: p.emergency_contact_phone || "",
      address: p.address || "",
    });
    setShowModal(true);
  };

  const openEmr = async (p) => {
    setEmrTab("prescriptions");
    setEmrLoading(true);
    setEmrPatient(p);
    try {
      const { data } = await hospitalApi.getPatient(p.id);
      setEmrPatient(data);
    } catch (err) {
      setError(err?.response?.data?.detail || "Could not load patient EMR.");
    } finally {
      setEmrLoading(false);
    }
  };

  const handleSavePatient = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      const payload = {
        ...form,
        age: form.age !== "" ? Number(form.age) : null,
      };
      if (editingPatient) {
        await hospitalApi.updatePatient(editingPatient.id, payload);
        showToast(`Updated ${form.full_name} (${editingPatient.mrn}).`);
      } else {
        const { data } = await hospitalApi.createPatient(payload);
        showToast(`Registered ${data.full_name} with ${data.mrn}.`);
      }
      setShowModal(false);
      setEditingPatient(null);
      await loadPatients(true);
    } catch (err) {
      const d = err?.response?.data;
      setError(d?.detail || d?.full_name || d?.phone || "Could not save patient.");
    } finally {
      setSaving(false);
    }
  };

  const handleDeletePatient = async (p) => {
    if (!window.confirm(`Delete patient ${p.full_name} (${p.mrn})? This also removes their prescriptions.`)) return;
    try {
      await hospitalApi.deletePatient(p.id);
      showToast(`Deleted ${p.full_name} (${p.mrn}).`);
      if (emrPatient?.id === p.id) setEmrPatient(null);
      await loadPatients(true);
    } catch (err) {
      setError(err?.response?.data?.detail || "Failed to delete patient.");
    }
  };

  const topBloodGroups = Object.entries(summary.blood_groups || {})
    .filter(([k]) => k !== "unknown")
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4);

  return (
    <Layout
      title="Patients Directory (EMR)"
      subtitle="Electronic Medical Records with auto-generated MRN, clinical alerts, prescriptions, OPD visits, and IPD admissions."
    >
      <div style={{ maxWidth: 1280, margin: "0 auto", padding: "4px 0 40px", display: "grid", gap: 16 }}>
        {/* KPI Strip */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
          <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 14, padding: "14px 16px" }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: "#64748b" }}>🧑‍⚕️ Total Registered Patients</div>
            <div style={{ fontSize: 24, fontWeight: 800, color: "#0f172a", marginTop: 6 }}>{summary.total_patients || 0}</div>
          </div>
          <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 14, padding: "14px 16px" }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: "#b91c1c" }}>⚠️ Patients with Allergy Alerts</div>
            <div style={{ fontSize: 24, fontWeight: 800, color: "#b91c1c", marginTop: 6 }}>{summary.with_allergies || 0}</div>
          </div>
          <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 14, padding: "14px 16px" }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: "#64748b" }}>🩸 Blood Group Distribution</div>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
              {topBloodGroups.length === 0 ? (
                <span style={{ fontSize: 12, color: "#94a3b8" }}>No blood groups recorded yet</span>
              ) : (
                topBloodGroups.map(([bg, cnt]) => (
                  <span key={bg} style={{ fontSize: 11.5, fontWeight: 800, background: "#fef2f2", color: "#991b1b", border: "1px solid #fecaca", borderRadius: 999, padding: "2px 9px" }}>
                    {bg}: {cnt}
                  </span>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Search & Filter Bar */}
        <div
          style={{
            background: "#fff",
            border: "1px solid #e2e8f0",
            borderRadius: 14,
            padding: "12px 16px",
            display: "flex",
            flexWrap: "wrap",
            gap: 10,
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", flex: "1 1 360px" }}>
            <input
              type="text"
              placeholder="Search by MRN (MRN-0001), Name, Phone, or CNIC..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ flex: "1 1 240px", padding: "8px 12px", borderRadius: 10, border: "1px solid #cbd5e1", fontSize: 13 }}
            />
            <select
              value={bloodFilter}
              onChange={(e) => setBloodFilter(e.target.value)}
              style={{ padding: "8px 12px", borderRadius: 10, border: "1px solid #cbd5e1", fontSize: 13, background: "#fff" }}
            >
              <option value="all">All Blood Groups</option>
              {BLOOD_GROUPS.map((bg) => (
                <option key={bg} value={bg}>{bg === "unknown" ? "Unknown" : bg}</option>
              ))}
            </select>
          </div>
          <button
            type="button"
            onClick={openRegisterModal}
            style={{
              border: "none",
              background: ACCENT,
              color: "#240729",
              borderRadius: 10,
              padding: "9px 16px",
              fontSize: 12.5,
              fontWeight: 800,
              cursor: "pointer",
            }}
          >
            + Register Patient
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

        {/* Patients Table */}
        <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 14, overflow: "hidden" }}>
          {loading ? (
            <div style={{ padding: 44, textAlign: "center", color: "#64748b", fontSize: 13 }}>Loading patients directory...</div>
          ) : patients.length === 0 ? (
            <div style={{ padding: 48, textAlign: "center", color: "#64748b", fontSize: 13 }}>
              No patients registered yet. Click <strong>+ Register Patient</strong> to issue the first MRN.
            </div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr style={{ background: "#f8fafc", textAlign: "left", color: "#475569" }}>
                    <th style={{ padding: "12px 14px", fontWeight: 700 }}>MRN</th>
                    <th style={{ padding: "12px 14px", fontWeight: 700 }}>Patient &amp; Phone</th>
                    <th style={{ padding: "12px 14px", fontWeight: 700 }}>Age / Gender</th>
                    <th style={{ padding: "12px 14px", fontWeight: 700 }}>Blood Group</th>
                    <th style={{ padding: "12px 14px", fontWeight: 700 }}>Clinical Alerts</th>
                    <th style={{ padding: "12px 14px", fontWeight: 700, textAlign: "right" }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {patients.map((p) => (
                    <tr key={p.id} style={{ borderTop: "1px solid #f1f5f9" }}>
                      <td style={{ padding: "12px 14px" }}>
                        <span style={{ background: "#0f172a", color: "#fff", borderRadius: 8, padding: "4px 9px", fontWeight: 800, fontSize: 12 }}>
                          {p.mrn}
                        </span>
                      </td>
                      <td style={{ padding: "12px 14px" }}>
                        <div style={{ fontWeight: 700, color: "#0f172a" }}>{p.full_name}</div>
                        <div style={{ fontSize: 11.5, color: "#64748b" }}>
                          {p.phone} {p.cnic ? `• CNIC: ${p.cnic}` : ""}
                        </div>
                      </td>
                      <td style={{ padding: "12px 14px", color: "#334155" }}>
                        {p.age ? `${p.age} yrs` : "—"} {p.gender_label ? `• ${p.gender_label}` : ""}
                      </td>
                      <td style={{ padding: "12px 14px" }}>
                        <span
                          style={{
                            fontSize: 11.5,
                            fontWeight: 800,
                            padding: "3px 9px",
                            borderRadius: 999,
                            background: p.blood_group && p.blood_group !== "unknown" ? "#fef2f2" : "#f1f5f9",
                            color: p.blood_group && p.blood_group !== "unknown" ? "#991b1b" : "#64748b",
                          }}
                        >
                          {p.blood_group === "unknown" ? "Unknown" : p.blood_group}
                        </span>
                      </td>
                      <td style={{ padding: "12px 14px" }}>
                        {p.allergies ? (
                          <span style={{ fontSize: 11, fontWeight: 700, background: "#fef2f2", color: "#b91c1c", border: "1px solid #fecaca", padding: "3px 8px", borderRadius: 999 }}>
                            ⚠ {p.allergies.slice(0, 32)}{p.allergies.length > 32 ? "..." : ""}
                          </span>
                        ) : (
                          <span style={{ fontSize: 11.5, color: "#94a3b8" }}>None recorded</span>
                        )}
                      </td>
                      <td style={{ padding: "12px 14px", textAlign: "right" }}>
                        <div style={{ display: "inline-flex", gap: 6 }}>
                          <button
                            type="button"
                            onClick={() => openEmr(p)}
                            style={{ border: `1px solid ${ACCENT}`, background: "#fdf4ff", color: "#86198f", borderRadius: 7, padding: "4px 10px", fontSize: 11.5, fontWeight: 700, cursor: "pointer" }}
                          >
                            View EMR
                          </button>
                          <button
                            type="button"
                            onClick={() => openEditModal(p)}
                            style={{ border: "1px solid #cbd5e1", background: "#fff", color: "#0f172a", borderRadius: 7, padding: "4px 9px", fontSize: 11.5, fontWeight: 700, cursor: "pointer" }}
                          >
                            Edit
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDeletePatient(p)}
                            style={{ border: "1px solid #fecaca", background: "#fff", color: "#b91c1c", borderRadius: 7, padding: "4px 9px", fontSize: 11.5, fontWeight: 700, cursor: "pointer" }}
                          >
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* REGISTER / EDIT PATIENT MODAL */}
      {showModal && (
        <div
          onClick={() => { setShowModal(false); setEditingPatient(null); }}
          style={{ position: "fixed", inset: 0, background: "rgba(15,23,42,0.48)", zIndex: 1000, display: "grid", placeItems: "center", padding: 16 }}
        >
          <form
            onClick={(e) => e.stopPropagation()}
            onSubmit={handleSavePatient}
            style={{ width: "100%", maxWidth: 520, maxHeight: "90vh", overflowY: "auto", background: "#fff", borderRadius: 16, padding: 22, display: "grid", gap: 12 }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h3 style={{ margin: 0, fontSize: 17, fontWeight: 800 }}>
                {editingPatient ? `✏️ Edit Patient (${editingPatient.mrn})` : "🧑‍⚕️ Register New Patient"}
              </h3>
              <button type="button" onClick={() => { setShowModal(false); setEditingPatient(null); }} style={{ border: "none", background: "transparent", fontSize: 18, cursor: "pointer" }}>
                ✕
              </button>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <input required placeholder="Full Name *" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }} />
              <input required placeholder="Phone Number *" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }} />
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10 }}>
              <input type="number" min="0" max="150" placeholder="Age (yrs)" value={form.age} onChange={(e) => setForm({ ...form, age: e.target.value })} style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }} />
              <select value={form.gender} onChange={(e) => setForm({ ...form, gender: e.target.value })} style={{ padding: "9px 10px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13, background: "#fff" }}>
                <option value="">Gender</option>
                <option value="male">Male</option>
                <option value="female">Female</option>
                <option value="other">Other</option>
              </select>
              <select value={form.blood_group} onChange={(e) => setForm({ ...form, blood_group: e.target.value })} style={{ padding: "9px 10px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13, background: "#fff" }}>
                {BLOOD_GROUPS.map((bg) => (
                  <option key={bg} value={bg}>{bg === "unknown" ? "Blood: Unknown" : `Blood: ${bg}`}</option>
                ))}
              </select>
            </div>

            <input placeholder="CNIC / National ID (optional)" value={form.cnic} onChange={(e) => setForm({ ...form, cnic: e.target.value })} style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }} />

            <textarea rows={2} placeholder="Known Allergies (e.g., Penicillin, Sulfa drugs, Peanuts)" value={form.allergies} onChange={(e) => setForm({ ...form, allergies: e.target.value })} style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }} />
            <textarea rows={2} placeholder="Chronic Conditions (e.g., Hypertension, Type-2 Diabetes, Asthma)" value={form.chronic_conditions} onChange={(e) => setForm({ ...form, chronic_conditions: e.target.value })} style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }} />

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <input placeholder="Emergency Contact Name" value={form.emergency_contact_name} onChange={(e) => setForm({ ...form, emergency_contact_name: e.target.value })} style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }} />
              <input placeholder="Emergency Contact Phone" value={form.emergency_contact_phone} onChange={(e) => setForm({ ...form, emergency_contact_phone: e.target.value })} style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }} />
            </div>

            <input placeholder="Residential Address" value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }} />

            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
              <button type="button" onClick={() => { setShowModal(false); setEditingPatient(null); }} style={{ border: "1px solid #cbd5e1", background: "#fff", borderRadius: 9, padding: "8px 14px", fontSize: 12.5, fontWeight: 700, cursor: "pointer" }}>
                Cancel
              </button>
              <button type="submit" disabled={saving} style={{ border: "none", background: ACCENT, color: "#240729", borderRadius: 9, padding: "8px 16px", fontSize: 13, fontWeight: 800, cursor: "pointer" }}>
                {saving ? "Saving..." : editingPatient ? "Save Changes" : "Register & Issue MRN"}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* PATIENT 360° EMR DRAWER / MODAL */}
      {emrPatient && (
        <div
          onClick={() => setEmrPatient(null)}
          style={{ position: "fixed", inset: 0, background: "rgba(15,23,42,0.48)", zIndex: 1000, display: "flex", justifyContent: "flex-end" }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{ width: "100%", maxWidth: 640, height: "100%", background: "#fff", padding: 22, overflowY: "auto", display: "grid", alignContent: "start", gap: 14, boxShadow: "-4px 0 24px rgba(15,23,42,0.12)" }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 10 }}>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ background: "#0f172a", color: "#fff", borderRadius: 8, padding: "3px 9px", fontWeight: 800, fontSize: 12 }}>
                    {emrPatient.mrn}
                  </span>
                  <h3 style={{ margin: 0, fontSize: 18, fontWeight: 800, color: "#0f172a" }}>{emrPatient.full_name}</h3>
                </div>
                <div style={{ fontSize: 12.5, color: "#64748b", marginTop: 4 }}>
                  {emrPatient.phone} {emrPatient.age ? `• ${emrPatient.age} yrs` : ""}{" "}
                  {emrPatient.gender_label ? `• ${emrPatient.gender_label}` : ""}{" "}
                  {emrPatient.blood_group && emrPatient.blood_group !== "unknown" ? `• Blood: ${emrPatient.blood_group}` : ""}
                </div>
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  type="button"
                  onClick={() => navigate(staff ? `/staff/prescriptions?patient_id=${emrPatient.id}` : `/owner/m/prescriptions?patient_id=${emrPatient.id}`)}
                  style={{ border: "none", background: ACCENT, color: "#240729", borderRadius: 9, padding: "7px 12px", fontSize: 12, fontWeight: 800, cursor: "pointer" }}
                >
                  + New Prescription
                </button>
                <button type="button" onClick={() => setEmrPatient(null)} style={{ border: "1px solid #e2e8f0", background: "#fff", borderRadius: 8, padding: "5px 10px", cursor: "pointer" }}>
                  ✕
                </button>
              </div>
            </div>

            {/* Clinical Alerts Banner */}
            {(emrPatient.allergies || emrPatient.chronic_conditions) && (
              <div style={{ background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 12, padding: 12, display: "grid", gap: 4, fontSize: 12.5, color: "#991b1b" }}>
                {emrPatient.allergies && <div><strong>⚠️ Allergies:</strong> {emrPatient.allergies}</div>}
                {emrPatient.chronic_conditions && <div><strong>🩺 Chronic Conditions:</strong> {emrPatient.chronic_conditions}</div>}
              </div>
            )}

            {/* Demographics Summary */}
            <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 12, padding: 12, fontSize: 12.5, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
              <div><strong>CNIC:</strong> {emrPatient.cnic || "—"}</div>
              <div><strong>Emergency Contact:</strong> {emrPatient.emergency_contact_name ? `${emrPatient.emergency_contact_name} (${emrPatient.emergency_contact_phone || "—"})` : "—"}</div>
              <div style={{ gridColumn: "1 / -1" }}><strong>Address:</strong> {emrPatient.address || "—"}</div>
            </div>

            {/* EMR Sub-Tabs */}
            <div style={{ display: "flex", gap: 8, borderBottom: "1px solid #e2e8f0", paddingBottom: 10 }}>
              {[
                { key: "prescriptions", label: `💊 Prescriptions (${(emrPatient.prescriptions || []).length})` },
                { key: "appointments", label: `📅 OPD Visits (${(emrPatient.appointments || []).length})` },
                { key: "admissions", label: `🛏️ IPD Admissions (${(emrPatient.admissions || []).length})` },
              ].map((t) => (
                <button
                  key={t.key}
                  type="button"
                  onClick={() => setEmrTab(t.key)}
                  style={{
                    border: emrTab === t.key ? `1.5px solid ${ACCENT}` : "1px solid #e2e8f0",
                    background: emrTab === t.key ? "#fdf4ff" : "#fff",
                    color: emrTab === t.key ? "#86198f" : "#475569",
                    borderRadius: 9,
                    padding: "6px 12px",
                    fontSize: 12,
                    fontWeight: 700,
                    cursor: "pointer",
                  }}
                >
                  {t.label}
                </button>
              ))}
            </div>

            {emrLoading ? (
              <div style={{ padding: 28, textAlign: "center", color: "#64748b", fontSize: 13 }}>Loading clinical history...</div>
            ) : emrTab === "prescriptions" ? (
              (emrPatient.prescriptions || []).length === 0 ? (
                <div style={{ padding: 24, textAlign: "center", color: "#94a3b8", fontSize: 13 }}>No prescriptions recorded for this patient yet.</div>
              ) : (
                <div style={{ display: "grid", gap: 10 }}>
                  {emrPatient.prescriptions.map((rx) => (
                    <div key={rx.id} style={{ border: "1px solid #e2e8f0", borderRadius: 12, padding: 12, display: "grid", gap: 6 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span style={{ fontWeight: 800, color: "#0f172a", fontSize: 13 }}>{rx.rx_number} — {rx.doctor_name || "Doctor"}</span>
                        <span style={{ fontSize: 11.5, color: "#64748b" }}>{formatDate(rx.created_at)}</span>
                      </div>
                      <div style={{ fontSize: 12.5, color: "#334155" }}><strong>Diagnosis:</strong> {rx.diagnosis}</div>
                      <div style={{ fontSize: 12, color: "#64748b" }}>
                        <strong>Medicines ({rx.medications_count}):</strong>{" "}
                        {(rx.medications || []).map((m) => `${m.name} (${m.frequency || m.dosage || ""})`).join(", ") || "—"}
                      </div>
                    </div>
                  ))}
                </div>
              )
            ) : emrTab === "appointments" ? (
              (emrPatient.appointments || []).length === 0 ? (
                <div style={{ padding: 24, textAlign: "center", color: "#94a3b8", fontSize: 13 }}>No OPD visits matched by phone.</div>
              ) : (
                <div style={{ display: "grid", gap: 8 }}>
                  {emrPatient.appointments.map((a) => (
                    <div key={a.id} style={{ border: "1px solid #e2e8f0", borderRadius: 10, padding: 10, display: "flex", justifyContent: "space-between", fontSize: 12.5 }}>
                      <div>
                        <strong>{a.token_display} — {a.doctor_name}</strong> ({a.department_name || "OPD"})
                        <div style={{ fontSize: 11.5, color: "#64748b" }}>{a.appointment_date} • {a.chief_complaint || a.visit_type_label}</div>
                      </div>
                      <span style={{ fontWeight: 700, color: "#475569" }}>{a.status_label}</span>
                    </div>
                  ))}
                </div>
              )
            ) : (emrPatient.admissions || []).length === 0 ? (
              <div style={{ padding: 24, textAlign: "center", color: "#94a3b8", fontSize: 13 }}>No IPD admissions matched by phone.</div>
            ) : (
              <div style={{ display: "grid", gap: 8 }}>
                {emrPatient.admissions.map((adm) => (
                  <div key={adm.id} style={{ border: "1px solid #e2e8f0", borderRadius: 10, padding: 10, fontSize: 12.5 }}>
                    <div style={{ fontWeight: 700 }}>{adm.ward_name} — Bed {adm.bed_number} ({adm.status})</div>
                    <div style={{ fontSize: 11.5, color: "#64748b" }}>
                      Admitted: {formatDate(adm.admitted_at)} {adm.attending_doctor ? `• Dr. ${adm.attending_doctor}` : ""}
                    </div>
                    {adm.diagnosis && <div style={{ fontSize: 12, marginTop: 4 }}>{adm.diagnosis}</div>}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </Layout>
  );
}
