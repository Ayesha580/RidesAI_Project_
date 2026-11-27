import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import OwnerLayout from "../owner/components/OwnerLayout";
import StaffLayout from "../staff/components/StaffLayout";
import { hospitalApi } from "../api/operationsApi";

const ACCENT = "#ff77ff";

const EMPTY_MED = { name: "", dosage: "", frequency: "1+0+1", duration: "5 days", instructions: "After meal" };

const EMPTY_RX_FORM = {
  patient_id: "",
  doctor_id: "",
  vitals: { bp: "", pulse: "", temp: "", weight: "" },
  diagnosis: "",
  medications: [{ ...EMPTY_MED }],
  lab_tests_advised: "",
  clinical_notes: "",
  follow_up_date: "",
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

export default function HospitalPrescriptions({ staff = false }) {
  const Layout = staff ? StaffLayout : OwnerLayout;
  const [searchParams, setSearchParams] = useSearchParams();

  const [prescriptions, setPrescriptions] = useState([]);
  const [patients, setPatients] = useState([]);
  const [doctors, setDoctors] = useState([]);
  const [search, setSearch] = useState("");
  const [doctorFilter, setDoctorFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState("");
  const [error, setError] = useState("");

  // Write Rx Modal
  const [showWriteModal, setShowWriteModal] = useState(false);
  const [form, setForm] = useState(EMPTY_RX_FORM);

  // Print / View Rx Modal
  const [printRx, setPrintRx] = useState(null);

  const showToast = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(""), 3500);
  };

  const loadMeta = useCallback(async () => {
    try {
      const [patRes, docRes] = await Promise.all([
        hospitalApi.listPatients(),
        hospitalApi.listDoctors(),
      ]);
      setPatients(patRes.data?.results || []);
      setDoctors(docRes.data?.results || docRes.data || []);
    } catch {
      // non-blocking
    }
  }, []);

  const loadPrescriptions = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const params = {};
      if (search.trim()) params.search = search.trim();
      if (doctorFilter) params.doctor_id = doctorFilter;
      const { data } = await hospitalApi.listPrescriptions(params);
      setPrescriptions(data?.results || []);
    } catch (err) {
      setError(err?.response?.data?.detail || "Could not load prescriptions.");
    } finally {
      if (!silent) setLoading(false);
    }
  }, [search, doctorFilter]);

  useEffect(() => {
    loadMeta();
  }, [loadMeta]);

  useEffect(() => {
    loadPrescriptions();
  }, [loadPrescriptions]);

  // If navigated from Patient 360° EMR with ?patient_id=...
  useEffect(() => {
    const prePatId = searchParams.get("patient_id");
    if (prePatId) {
      setForm({
        ...EMPTY_RX_FORM,
        patient_id: String(prePatId),
        medications: [{ ...EMPTY_MED }],
      });
      setShowWriteModal(true);
      setSearchParams({}, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  const updateMedRow = (idx, key, val) => {
    setForm((prev) => {
      const next = prev.medications.map((m, i) => (i === idx ? { ...m, [key]: val } : m));
      return { ...prev, medications: next };
    });
  };

  const addMedRow = () => {
    setForm((prev) => ({
      ...prev,
      medications: [...prev.medications, { ...EMPTY_MED }],
    }));
  };

  const removeMedRow = (idx) => {
    setForm((prev) => {
      const next = prev.medications.filter((_, i) => i !== idx);
      return { ...prev, medications: next.length ? next : [{ ...EMPTY_MED }] };
    });
  };

  const handleSaveRx = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      const cleanedMeds = form.medications.filter((m) => m.name && m.name.trim());
      const payload = {
        patient_id: Number(form.patient_id),
        doctor_id: form.doctor_id ? Number(form.doctor_id) : null,
        vitals: form.vitals,
        diagnosis: form.diagnosis,
        medications: cleanedMeds,
        lab_tests_advised: form.lab_tests_advised,
        clinical_notes: form.clinical_notes,
        follow_up_date: form.follow_up_date || null,
      };
      const { data } = await hospitalApi.createPrescription(payload);
      showToast(`Created ${data.rx_number} for ${data.patient_name}.`);
      setShowWriteModal(false);
      setForm({ ...EMPTY_RX_FORM, medications: [{ ...EMPTY_MED }] });
      await loadPrescriptions(true);
      setPrintRx(data);
    } catch (err) {
      const d = err?.response?.data;
      setError(d?.detail || d?.patient_id || d?.diagnosis || "Could not create prescription.");
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteRx = async (rx) => {
    if (!window.confirm(`Delete prescription ${rx.rx_number} for ${rx.patient_name}?`)) return;
    try {
      await hospitalApi.deletePrescription(rx.id);
      showToast(`Deleted ${rx.rx_number}.`);
      await loadPrescriptions(true);
    } catch (err) {
      setError(err?.response?.data?.detail || "Failed to delete prescription.");
    }
  };

  return (
    <Layout
      title="Digital Prescriptions (Rx)"
      subtitle="Structured clinical prescriptions with vitals, dynamic medication schedules, lab tests, and 1-click printable Rx sheets."
    >
      <style>{`
        @media print {
          body * { visibility: hidden !important; }
          #rx-print-sheet, #rx-print-sheet * { visibility: visible !important; }
          #rx-print-sheet {
            position: fixed !important;
            inset: 0 !important;
            width: 100% !important;
            max-width: 100% !important;
            margin: 0 !important;
            padding: 24px !important;
            background: #fff !important;
            box-shadow: none !important;
            border: none !important;
          }
          .no-print { display: none !important; }
        }
      `}</style>

      <div style={{ maxWidth: 1280, margin: "0 auto", padding: "4px 0 40px", display: "grid", gap: 16 }}>
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
              placeholder="Search by RX# (RX-0001), Patient Name, MRN, or Diagnosis..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ flex: "1 1 240px", padding: "8px 12px", borderRadius: 10, border: "1px solid #cbd5e1", fontSize: 13 }}
            />
            <select
              value={doctorFilter}
              onChange={(e) => setDoctorFilter(e.target.value)}
              style={{ padding: "8px 12px", borderRadius: 10, border: "1px solid #cbd5e1", fontSize: 13, background: "#fff" }}
            >
              <option value="">All Doctors</option>
              {doctors.map((d) => (
                <option key={d.id} value={d.id}>{d.full_name}</option>
              ))}
            </select>
          </div>
          <button
            type="button"
            onClick={() => {
              setForm({ ...EMPTY_RX_FORM, medications: [{ ...EMPTY_MED }] });
              setShowWriteModal(true);
            }}
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
            + Write Prescription
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

        {/* Prescriptions Table */}
        <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 14, overflow: "hidden" }}>
          {loading ? (
            <div style={{ padding: 44, textAlign: "center", color: "#64748b", fontSize: 13 }}>Loading prescriptions...</div>
          ) : prescriptions.length === 0 ? (
            <div style={{ padding: 48, textAlign: "center", color: "#64748b", fontSize: 13 }}>
              No digital prescriptions yet. Click <strong>+ Write Prescription</strong> to create one.
            </div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr style={{ background: "#f8fafc", textAlign: "left", color: "#475569" }}>
                    <th style={{ padding: "12px 14px", fontWeight: 700 }}>RX #</th>
                    <th style={{ padding: "12px 14px", fontWeight: 700 }}>Date</th>
                    <th style={{ padding: "12px 14px", fontWeight: 700 }}>Patient</th>
                    <th style={{ padding: "12px 14px", fontWeight: 700 }}>Doctor &amp; Dept</th>
                    <th style={{ padding: "12px 14px", fontWeight: 700 }}>Diagnosis</th>
                    <th style={{ padding: "12px 14px", fontWeight: 700 }}>Medicines</th>
                    <th style={{ padding: "12px 14px", fontWeight: 700 }}>Follow-up</th>
                    <th style={{ padding: "12px 14px", fontWeight: 700, textAlign: "right" }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {prescriptions.map((rx) => (
                    <tr key={rx.id} style={{ borderTop: "1px solid #f1f5f9" }}>
                      <td style={{ padding: "12px 14px" }}>
                        <span style={{ background: "#0f172a", color: "#fff", borderRadius: 8, padding: "4px 9px", fontWeight: 800, fontSize: 12 }}>
                          {rx.rx_number}
                        </span>
                      </td>
                      <td style={{ padding: "12px 14px", color: "#334155" }}>{formatDate(rx.created_at)}</td>
                      <td style={{ padding: "12px 14px" }}>
                        <div style={{ fontWeight: 700, color: "#0f172a" }}>{rx.patient_name}</div>
                        <div style={{ fontSize: 11.5, color: "#64748b" }}>{rx.patient_mrn}</div>
                      </td>
                      <td style={{ padding: "12px 14px" }}>
                        <div style={{ fontWeight: 700, color: "#0f172a" }}>{rx.doctor_name || "—"}</div>
                        <div style={{ fontSize: 11.5, color: "#64748b" }}>{rx.doctor_department || rx.doctor_specialization || ""}</div>
                      </td>
                      <td style={{ padding: "12px 14px", maxWidth: 220, color: "#334155" }}>
                        {rx.diagnosis.length > 60 ? `${rx.diagnosis.slice(0, 60)}...` : rx.diagnosis}
                      </td>
                      <td style={{ padding: "12px 14px" }}>
                        <span style={{ fontSize: 11.5, fontWeight: 700, background: "#fdf4ff", color: "#86198f", border: `1px solid ${ACCENT}`, borderRadius: 999, padding: "2px 9px" }}>
                          {rx.medications_count} med{rx.medications_count === 1 ? "" : "s"}
                        </span>
                      </td>
                      <td style={{ padding: "12px 14px", color: "#334155" }}>
                        {rx.follow_up_date || "—"}
                      </td>
                      <td style={{ padding: "12px 14px", textAlign: "right" }}>
                        <div style={{ display: "inline-flex", gap: 6 }}>
                          <button
                            type="button"
                            onClick={() => setPrintRx(rx)}
                            style={{ border: `1px solid ${ACCENT}`, background: "#fdf4ff", color: "#86198f", borderRadius: 7, padding: "4px 10px", fontSize: 11.5, fontWeight: 700, cursor: "pointer" }}
                          >
                            🖨️ Print / View Rx
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDeleteRx(rx)}
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

      {/* WRITE PRESCRIPTION MODAL */}
      {showWriteModal && (
        <div
          onClick={() => setShowWriteModal(false)}
          style={{ position: "fixed", inset: 0, background: "rgba(15,23,42,0.48)", zIndex: 1000, display: "grid", placeItems: "center", padding: 16 }}
        >
          <form
            onClick={(e) => e.stopPropagation()}
            onSubmit={handleSaveRx}
            style={{ width: "100%", maxWidth: 720, maxHeight: "92vh", overflowY: "auto", background: "#fff", borderRadius: 16, padding: 22, display: "grid", gap: 14 }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h3 style={{ margin: 0, fontSize: 17, fontWeight: 800 }}>💊 Write Digital Prescription</h3>
              <button type="button" onClick={() => setShowWriteModal(false)} style={{ border: "none", background: "transparent", fontSize: 18, cursor: "pointer" }}>
                ✕
              </button>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <div>
                <label style={{ fontSize: 11.5, fontWeight: 700, color: "#475569", display: "block", marginBottom: 4 }}>Patient *</label>
                <select
                  required
                  value={form.patient_id}
                  onChange={(e) => setForm({ ...form, patient_id: e.target.value })}
                  style={{ width: "100%", padding: "9px 10px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13, background: "#fff" }}
                >
                  <option value="">— Select Registered Patient —</option>
                  {patients.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.full_name} ({p.mrn})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label style={{ fontSize: 11.5, fontWeight: 700, color: "#475569", display: "block", marginBottom: 4 }}>Prescribing Doctor</label>
                <select
                  value={form.doctor_id}
                  onChange={(e) => setForm({ ...form, doctor_id: e.target.value })}
                  style={{ width: "100%", padding: "9px 10px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13, background: "#fff" }}
                >
                  <option value="">— Select Doctor —</option>
                  {doctors.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.full_name} {d.department_name ? `(${d.department_name})` : ""}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Vitals Strip */}
            <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 12, padding: 12 }}>
              <div style={{ fontSize: 11.5, fontWeight: 800, color: "#475569", marginBottom: 8, textTransform: "uppercase" }}>Patient Vitals</div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8 }}>
                <input placeholder="BP (120/80)" value={form.vitals.bp} onChange={(e) => setForm({ ...form, vitals: { ...form.vitals, bp: e.target.value } })} style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid #cbd5e1", fontSize: 12.5 }} />
                <input placeholder="Pulse (76 bpm)" value={form.vitals.pulse} onChange={(e) => setForm({ ...form, vitals: { ...form.vitals, pulse: e.target.value } })} style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid #cbd5e1", fontSize: 12.5 }} />
                <input placeholder="Temp (98.6 F)" value={form.vitals.temp} onChange={(e) => setForm({ ...form, vitals: { ...form.vitals, temp: e.target.value } })} style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid #cbd5e1", fontSize: 12.5 }} />
                <input placeholder="Weight (70 kg)" value={form.vitals.weight} onChange={(e) => setForm({ ...form, vitals: { ...form.vitals, weight: e.target.value } })} style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid #cbd5e1", fontSize: 12.5 }} />
              </div>
            </div>

            <textarea
              required
              rows={2}
              placeholder="Primary Diagnosis / Clinical Assessment *"
              value={form.diagnosis}
              onChange={(e) => setForm({ ...form, diagnosis: e.target.value })}
              style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }}
            />

            {/* Dynamic Medications Builder */}
            <div style={{ border: "1px solid #e2e8f0", borderRadius: 12, padding: 12, display: "grid", gap: 8 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div style={{ fontSize: 12, fontWeight: 800, color: "#0f172a" }}>℞ Medications</div>
                <button
                  type="button"
                  onClick={addMedRow}
                  style={{ border: `1px solid ${ACCENT}`, background: "#fdf4ff", color: "#86198f", borderRadius: 8, padding: "4px 10px", fontSize: 11.5, fontWeight: 700, cursor: "pointer" }}
                >
                  + Add Medicine
                </button>
              </div>
              {form.medications.map((m, idx) => (
                <div key={idx} style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr 1.5fr auto", gap: 6, alignItems: "center" }}>
                  <input placeholder="Medicine (e.g. Panadol 500mg)" value={m.name} onChange={(e) => updateMedRow(idx, "name", e.target.value)} style={{ padding: "7px 9px", borderRadius: 8, border: "1px solid #cbd5e1", fontSize: 12 }} />
                  <input placeholder="Dosage (1 tab)" value={m.dosage} onChange={(e) => updateMedRow(idx, "dosage", e.target.value)} style={{ padding: "7px 9px", borderRadius: 8, border: "1px solid #cbd5e1", fontSize: 12 }} />
                  <input placeholder="1+0+1" value={m.frequency} onChange={(e) => updateMedRow(idx, "frequency", e.target.value)} style={{ padding: "7px 9px", borderRadius: 8, border: "1px solid #cbd5e1", fontSize: 12 }} />
                  <input placeholder="5 days" value={m.duration} onChange={(e) => updateMedRow(idx, "duration", e.target.value)} style={{ padding: "7px 9px", borderRadius: 8, border: "1px solid #cbd5e1", fontSize: 12 }} />
                  <input placeholder="Instructions" value={m.instructions} onChange={(e) => updateMedRow(idx, "instructions", e.target.value)} style={{ padding: "7px 9px", borderRadius: 8, border: "1px solid #cbd5e1", fontSize: 12 }} />
                  <button type="button" onClick={() => removeMedRow(idx)} style={{ border: "1px solid #fecaca", background: "#fff", color: "#b91c1c", borderRadius: 7, padding: "5px 8px", fontSize: 11, fontWeight: 700, cursor: "pointer" }}>
                    ✕
                  </button>
                </div>
              ))}
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 10 }}>
              <input placeholder="Lab Tests Advised (e.g., CBC, ECG, Lipid Profile)" value={form.lab_tests_advised} onChange={(e) => setForm({ ...form, lab_tests_advised: e.target.value })} style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }} />
              <input type="date" title="Follow-up Date" value={form.follow_up_date} onChange={(e) => setForm({ ...form, follow_up_date: e.target.value })} style={{ padding: "8px 10px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }} />
            </div>

            <textarea rows={2} placeholder="Clinical Notes / Lifestyle Advice" value={form.clinical_notes} onChange={(e) => setForm({ ...form, clinical_notes: e.target.value })} style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }} />

            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
              <button type="button" onClick={() => setShowWriteModal(false)} style={{ border: "1px solid #cbd5e1", background: "#fff", borderRadius: 9, padding: "8px 14px", fontSize: 12.5, fontWeight: 700, cursor: "pointer" }}>
                Cancel
              </button>
              <button type="submit" disabled={saving} style={{ border: "none", background: ACCENT, color: "#240729", borderRadius: 9, padding: "8px 16px", fontSize: 13, fontWeight: 800, cursor: "pointer" }}>
                {saving ? "Saving..." : "Save & Open Printable Rx"}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* 1-CLICK PRINTABLE PRESCRIPTION MODAL */}
      {printRx && (
        <div
          onClick={() => setPrintRx(null)}
          style={{ position: "fixed", inset: 0, background: "rgba(15,23,42,0.55)", zIndex: 1100, display: "grid", placeItems: "center", padding: 16 }}
        >
          <div
            id="rx-print-sheet"
            onClick={(e) => e.stopPropagation()}
            style={{ width: "100%", maxWidth: 740, maxHeight: "92vh", overflowY: "auto", background: "#fff", borderRadius: 16, padding: 28, display: "grid", gap: 16, boxShadow: "0 12px 36px rgba(15,23,42,0.2)" }}
          >
            {/* Top Action Bar (hidden when printing) */}
            <div className="no-print" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid #e2e8f0", paddingBottom: 10 }}>
              <span style={{ fontSize: 13, fontWeight: 700, color: "#64748b" }}>Clinical Prescription Sheet — {printRx.rx_number}</span>
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  type="button"
                  onClick={() => window.print()}
                  style={{ border: "none", background: ACCENT, color: "#240729", borderRadius: 9, padding: "7px 14px", fontSize: 12.5, fontWeight: 800, cursor: "pointer" }}
                >
                  🖨️ Print Prescription
                </button>
                <button type="button" onClick={() => setPrintRx(null)} style={{ border: "1px solid #cbd5e1", background: "#fff", borderRadius: 9, padding: "7px 12px", fontSize: 12.5, fontWeight: 700, cursor: "pointer" }}>
                  Close
                </button>
              </div>
            </div>

            {/* Hospital & Doctor Header */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", borderBottom: "2px solid #0f172a", paddingBottom: 12 }}>
              <div>
                <div style={{ fontSize: 21, fontWeight: 900, color: "#0f172a" }}>{printRx.hospital?.name || "HospitalCare"}</div>
                {printRx.hospital?.address && <div style={{ fontSize: 12, color: "#475569" }}>{printRx.hospital.address}</div>}
                {printRx.hospital?.phone && <div style={{ fontSize: 12, color: "#475569" }}>Tel: {printRx.hospital.phone}</div>}
              </div>
              <div style={{ textAlign: "right" }}>
                <div style={{ fontSize: 15, fontWeight: 800, color: "#0f172a" }}>{printRx.doctor_name || "Attending Physician"}</div>
                <div style={{ fontSize: 12, color: "#475569" }}>
                  {[printRx.doctor_qualification, printRx.doctor_specialization, printRx.doctor_department].filter(Boolean).join(" • ")}
                </div>
                <div style={{ fontSize: 12, fontWeight: 700, color: "#0f172a", marginTop: 4 }}>
                  {printRx.rx_number} • {formatDate(printRx.created_at)}
                </div>
              </div>
            </div>

            {/* Patient Strip */}
            <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 10, padding: 12, display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8, fontSize: 12.5 }}>
              <div><strong>Patient:</strong> {printRx.patient_name}</div>
              <div><strong>MRN:</strong> {printRx.patient_mrn}</div>
              <div><strong>Age / Gender:</strong> {printRx.patient_age ? `${printRx.patient_age}y` : "—"} {printRx.patient_gender ? `/ ${printRx.patient_gender}` : ""}</div>
              <div><strong>Blood Group:</strong> {printRx.patient_blood_group && printRx.patient_blood_group !== "unknown" ? printRx.patient_blood_group : "—"}</div>
            </div>

            {/* Vitals Strip */}
            {printRx.vitals && Object.keys(printRx.vitals).length > 0 && (
              <div style={{ display: "flex", gap: 16, flexWrap: "wrap", fontSize: 12.5, padding: "8px 12px", border: "1px dashed #cbd5e1", borderRadius: 10 }}>
                <strong>Vitals:</strong>
                {printRx.vitals.bp && <span>BP: <strong>{printRx.vitals.bp}</strong></span>}
                {printRx.vitals.pulse && <span>Pulse: <strong>{printRx.vitals.pulse}</strong></span>}
                {printRx.vitals.temp && <span>Temp: <strong>{printRx.vitals.temp}</strong></span>}
                {printRx.vitals.weight && <span>Weight: <strong>{printRx.vitals.weight}</strong></span>}
              </div>
            )}

            {/* Diagnosis */}
            <div style={{ fontSize: 13.5 }}>
              <strong>Diagnosis:</strong> {printRx.diagnosis}
            </div>

            {/* Rx Medications Table */}
            <div>
              <div style={{ fontSize: 18, fontWeight: 900, color: "#0f172a", marginBottom: 6 }}>℞ Medications</div>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5, border: "1px solid #e2e8f0" }}>
                <thead>
                  <tr style={{ background: "#f8fafc", textAlign: "left" }}>
                    <th style={{ padding: "8px 10px", borderBottom: "1px solid #e2e8f0" }}>Medicine</th>
                    <th style={{ padding: "8px 10px", borderBottom: "1px solid #e2e8f0" }}>Dosage</th>
                    <th style={{ padding: "8px 10px", borderBottom: "1px solid #e2e8f0" }}>Frequency</th>
                    <th style={{ padding: "8px 10px", borderBottom: "1px solid #e2e8f0" }}>Duration</th>
                    <th style={{ padding: "8px 10px", borderBottom: "1px solid #e2e8f0" }}>Instructions</th>
                  </tr>
                </thead>
                <tbody>
                  {(printRx.medications || []).map((m, idx) => (
                    <tr key={idx} style={{ borderTop: "1px solid #f1f5f9" }}>
                      <td style={{ padding: "8px 10px", fontWeight: 700 }}>{m.name}</td>
                      <td style={{ padding: "8px 10px" }}>{m.dosage || "—"}</td>
                      <td style={{ padding: "8px 10px", fontWeight: 700 }}>{m.frequency || "—"}</td>
                      <td style={{ padding: "8px 10px" }}>{m.duration || "—"}</td>
                      <td style={{ padding: "8px 10px", color: "#475569" }}>{m.instructions || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {printRx.lab_tests_advised && (
              <div style={{ fontSize: 13 }}>
                <strong>Lab Tests Advised:</strong> {printRx.lab_tests_advised}
              </div>
            )}
            {printRx.clinical_notes && (
              <div style={{ fontSize: 13 }}>
                <strong>Clinical Notes:</strong> {printRx.clinical_notes}
              </div>
            )}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", borderTop: "1px solid #e2e8f0", paddingTop: 14, marginTop: 8, fontSize: 12.5 }}>
              <div>
                <strong>Follow-up Date:</strong> {printRx.follow_up_date || "As advised"}
              </div>
              <div style={{ textAlign: "right" }}>
                <div style={{ borderTop: "1px solid #334155", paddingTop: 4, minWidth: 180, fontWeight: 700 }}>
                  {printRx.doctor_name || "Doctor Signature"}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
}
