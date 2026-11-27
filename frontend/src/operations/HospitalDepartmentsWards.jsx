import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import OwnerLayout from "../owner/components/OwnerLayout";
import StaffLayout from "../staff/components/StaffLayout";
import { hospitalApi } from "../api/operationsApi";

const ACCENT = "#ff77ff";

const WARD_TYPES = [
  { value: "icu", label: "ICU" },
  { value: "general", label: "General Ward" },
  { value: "private", label: "Private Suites" },
  { value: "semi_private", label: "Semi-Private" },
  { value: "emergency", label: "Emergency" },
  { value: "maternity", label: "Maternity" },
  { value: "pediatric", label: "Pediatric" },
];

const BED_STYLES = {
  available: {
    label: "Available",
    bg: "#ecfdf5",
    border: "#6ee7b7",
    color: "#047857",
    dot: "#10b981",
  },
  occupied: {
    label: "Occupied",
    bg: "#fdf2f8",
    border: "#f9a8d4",
    color: "#be185d",
    dot: "#ec4899",
  },
  cleaning: {
    label: "Cleaning",
    bg: "#fffbeb",
    border: "#fcd34d",
    color: "#b45309",
    dot: "#f59e0b",
  },
  maintenance: {
    label: "Maintenance",
    bg: "#f1f5f9",
    border: "#cbd5e1",
    color: "#475569",
    dot: "#64748b",
  },
};

function formatMoney(val) {
  const num = Number(val || 0);
  return `Rs. ${num.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

export default function HospitalDepartmentsWards({ staff = false }) {
  const Layout = staff ? StaffLayout : OwnerLayout;
  const [searchParams] = useSearchParams();
  const [tab, setTab] = useState(
    searchParams.get("tab") === "departments" ? "departments" : "wards"
  );

  const [wards, setWards] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [selectedWardFilter, setSelectedWardFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");

  // Modals
  const [admitBedModal, setAdmitBedModal] = useState(null);
  const [admitForm, setAdmitForm] = useState({
    patient_name: "",
    patient_phone: "",
    attending_doctor: "",
    diagnosis: "",
    notes: "",
  });

  const [dischargeBedModal, setDischargeBedModal] = useState(null);
  const [dischargeNotes, setDischargeNotes] = useState("");

  const [showWardModal, setShowWardModal] = useState(false);
  const [editingWard, setEditingWard] = useState(null);
  const [wardForm, setWardForm] = useState({
    name: "",
    department_id: "",
    ward_type: "general",
    daily_bed_rate: "2500",
    floor: "",
    auto_create_beds: "6",
    bed_prefix: "GW",
  });

  const [showDeptModal, setShowDeptModal] = useState(false);
  const [editingDept, setEditingDept] = useState(null);
  const [deptForm, setDeptForm] = useState({
    name: "",
    code: "",
    head_of_department: "",
    floor_location: "",
    phone_ext: "",
    is_24_7: false,
  });

  const showToast = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(""), 3500);
  };

  const loadAll = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    setError("");
    try {
      const [wRes, dRes] = await Promise.all([
        hospitalApi.listWards(),
        hospitalApi.listDepartments(),
      ]);
      setWards(Array.isArray(wRes.data) ? wRes.data : []);
      setDepartments(Array.isArray(dRes.data) ? dRes.data : []);
    } catch (err) {
      setError(err?.response?.data?.detail || "Could not load wards & departments.");
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll(false);
  }, [loadAll]);

  const handleAdmit = async (e) => {
    e.preventDefault();
    if (!admitBedModal || !admitForm.patient_name.trim()) return;
    setSaving(true);
    setError("");
    try {
      await hospitalApi.admitBed(admitBedModal.id, admitForm);
      showToast(`Admitted ${admitForm.patient_name} to Bed ${admitBedModal.bed_number}.`);
      setAdmitBedModal(null);
      setAdmitForm({ patient_name: "", patient_phone: "", attending_doctor: "", diagnosis: "", notes: "" });
      await loadAll(true);
    } catch (err) {
      setError(err?.response?.data?.detail || "Could not admit patient.");
    } finally {
      setSaving(false);
    }
  };

  const handleDischarge = async () => {
    if (!dischargeBedModal) return;
    setSaving(true);
    setError("");
    try {
      const res = await hospitalApi.dischargeBed(dischargeBedModal.id, { notes: dischargeNotes });
      const total = res.data?.total_bed_charges ?? 0;
      const days = res.data?.stay_days ?? 1;
      showToast(
        `Discharged patient from Bed ${dischargeBedModal.bed_number} (${days} day(s) • ${formatMoney(total)}). Bed marked Cleaning.`
      );
      setDischargeBedModal(null);
      setDischargeNotes("");
      await loadAll(true);
    } catch (err) {
      setError(err?.response?.data?.detail || "Could not discharge patient.");
    } finally {
      setSaving(false);
    }
  };

  const handleBedStatusChange = async (bed, nextStatus) => {
    setError("");
    try {
      await hospitalApi.updateBedStatus(bed.id, nextStatus);
      showToast(`Bed ${bed.bed_number} marked ${nextStatus}.`);
      await loadAll(true);
    } catch (err) {
      setError(err?.response?.data?.detail || "Failed to update bed status.");
    }
  };

  const handleSaveWard = async (e) => {
    e.preventDefault();
    if (!wardForm.name.trim()) return;
    setSaving(true);
    setError("");
    try {
      const payload = {
        name: wardForm.name.trim(),
        department_id: wardForm.department_id ? Number(wardForm.department_id) : null,
        ward_type: wardForm.ward_type,
        daily_bed_rate: Number(wardForm.daily_bed_rate || 0),
        floor: wardForm.floor.trim(),
      };
      if (editingWard) {
        await hospitalApi.updateWard(editingWard.id, payload);
        showToast(`Updated ward "${payload.name}".`);
      } else {
        await hospitalApi.createWard({
          ...payload,
          auto_create_beds: Number(wardForm.auto_create_beds || 0),
          bed_prefix: wardForm.bed_prefix.trim(),
        });
        showToast("Ward and beds created.");
      }
      setShowWardModal(false);
      setEditingWard(null);
      setWardForm({
        name: "",
        department_id: "",
        ward_type: "general",
        daily_bed_rate: "2500",
        floor: "",
        auto_create_beds: "6",
        bed_prefix: "GW",
      });
      await loadAll(true);
    } catch (err) {
      setError(err?.response?.data?.detail || "Could not save ward.");
    } finally {
      setSaving(false);
    }
  };

  const handleSaveDept = async (e) => {
    e.preventDefault();
    if (!deptForm.name.trim()) return;
    setSaving(true);
    setError("");
    try {
      if (editingDept) {
        await hospitalApi.updateDepartment(editingDept.id, deptForm);
        showToast(`Updated department "${deptForm.name}".`);
      } else {
        await hospitalApi.createDepartment(deptForm);
        showToast("Department created.");
      }
      setShowDeptModal(false);
      setEditingDept(null);
      setDeptForm({ name: "", code: "", head_of_department: "", floor_location: "", phone_ext: "", is_24_7: false });
      await loadAll(true);
    } catch (err) {
      setError(err?.response?.data?.detail || err?.response?.data?.name || "Could not save department.");
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteDept = async (dept) => {
    if (!window.confirm(`Delete department "${dept.name}"?`)) return;
    try {
      await hospitalApi.deleteDepartment(dept.id);
      showToast(`Deleted "${dept.name}".`);
      await loadAll(true);
    } catch (err) {
      setError(err?.response?.data?.detail || "Failed to delete department.");
    }
  };

  const visibleWards =
    selectedWardFilter === "all"
      ? wards
      : wards.filter((w) => String(w.id) === String(selectedWardFilter));

  return (
    <Layout
      title="Departments, Wards & Live Bed Map"
      subtitle="Manage clinical departments, ward bed capacity, and atomic IPD admissions & discharges."
    >
      <div style={{ maxWidth: 1280, margin: "0 auto", padding: "4px 0 36px", display: "grid", gap: 16 }}>
        {/* Header Tab Bar & Primary Actions */}
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
              onClick={() => setTab("wards")}
              style={{
                border: tab === "wards" ? `1.5px solid ${ACCENT}` : "1px solid #e2e8f0",
                background: tab === "wards" ? "#fdf4ff" : "#fff",
                color: tab === "wards" ? "#86198f" : "#475569",
                borderRadius: 10,
                padding: "8px 16px",
                fontSize: 13,
                fontWeight: 700,
                cursor: "pointer",
              }}
            >
              🛏️ Live Wards &amp; Bed Map ({wards.length})
            </button>
            <button
              type="button"
              onClick={() => setTab("departments")}
              style={{
                border: tab === "departments" ? `1.5px solid ${ACCENT}` : "1px solid #e2e8f0",
                background: tab === "departments" ? "#fdf4ff" : "#fff",
                color: tab === "departments" ? "#86198f" : "#475569",
                borderRadius: 10,
                padding: "8px 16px",
                fontSize: 13,
                fontWeight: 700,
                cursor: "pointer",
              }}
            >
              🏥 Departments Directory ({departments.length})
            </button>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              type="button"
              onClick={() => {
                setEditingDept(null);
                setDeptForm({ name: "", code: "", head_of_department: "", floor_location: "", phone_ext: "", is_24_7: false });
                setShowDeptModal(true);
              }}
              style={{
                border: "1px solid #cbd5e1",
                background: "#fff",
                color: "#0f172a",
                borderRadius: 10,
                padding: "8px 14px",
                fontSize: 12.5,
                fontWeight: 700,
                cursor: "pointer",
              }}
            >
              + Add Department
            </button>
            <button
              type="button"
              onClick={() => {
                setEditingWard(null);
                setWardForm({ name: "", department_id: "", ward_type: "general", daily_bed_rate: "5000", floor: "", auto_create_beds: "6", bed_prefix: "BED" });
                setShowWardModal(true);
              }}
              style={{
                border: "none",
                background: ACCENT,
                color: "#240729",
                borderRadius: 10,
                padding: "8px 14px",
                fontSize: 12.5,
                fontWeight: 800,
                cursor: "pointer",
              }}
            >
              + Create Ward &amp; Beds
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

        {/* TAB 1: LIVE WARDS & BED MAP */}
        {tab === "wards" && (
          <div style={{ display: "grid", gap: 14 }}>
            {/* Ward Filter Pills + Legend */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 10 }}>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                <button
                  type="button"
                  onClick={() => setSelectedWardFilter("all")}
                  style={{
                    border: selectedWardFilter === "all" ? `1.5px solid ${ACCENT}` : "1px solid #e2e8f0",
                    background: selectedWardFilter === "all" ? "#0f172a" : "#fff",
                    color: selectedWardFilter === "all" ? "#fff" : "#475569",
                    borderRadius: 999,
                    padding: "6px 13px",
                    fontSize: 12,
                    fontWeight: 700,
                    cursor: "pointer",
                  }}
                >
                  All Wards
                </button>
                {wards.map((w) => (
                  <button
                    key={w.id}
                    type="button"
                    onClick={() => setSelectedWardFilter(String(w.id))}
                    style={{
                      border: selectedWardFilter === String(w.id) ? `1.5px solid ${ACCENT}` : "1px solid #e2e8f0",
                      background: selectedWardFilter === String(w.id) ? "#0f172a" : "#fff",
                      color: selectedWardFilter === String(w.id) ? "#fff" : "#475569",
                      borderRadius: 999,
                      padding: "6px 13px",
                      fontSize: 12,
                      fontWeight: 700,
                      cursor: "pointer",
                    }}
                  >
                    {w.name} ({w.available_beds}/{w.total_beds} free)
                  </button>
                ))}
              </div>
              <div style={{ display: "flex", gap: 10, fontSize: 11.5, fontWeight: 700 }}>
                {Object.entries(BED_STYLES).map(([k, st]) => (
                  <span key={k} style={{ display: "inline-flex", alignItems: "center", gap: 5, color: st.color }}>
                    <span style={{ width: 9, height: 9, borderRadius: 999, background: st.dot }} />
                    {st.label}
                  </span>
                ))}
              </div>
            </div>

            {loading ? (
              <div style={{ background: "#fff", borderRadius: 14, border: "1px solid #e2e8f0", padding: 44, textAlign: "center", color: "#64748b" }}>
                Loading wards and bed map...
              </div>
            ) : visibleWards.length === 0 ? (
              <div style={{ background: "#fff", borderRadius: 14, border: "1px dashed #cbd5e1", padding: 48, textAlign: "center", color: "#64748b" }}>
                <div style={{ fontSize: 32, marginBottom: 8 }}>🛏️</div>
                <div style={{ fontSize: 15, fontWeight: 700, color: "#0f172a", marginBottom: 4 }}>
                  No wards configured yet
                </div>
                <div style={{ fontSize: 13 }}>
                  Click <strong>+ Create Ward &amp; Beds</strong> to set up ICU, General, or Private wards with auto-numbered beds.
                </div>
              </div>
            ) : (
              visibleWards.map((ward) => (
                <div
                  key={ward.id}
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
                      flexWrap: "wrap",
                      gap: 8,
                      marginBottom: 14,
                      paddingBottom: 10,
                      borderBottom: "1px solid #f1f5f9",
                    }}
                  >
                    <div>
                      <div style={{ fontSize: 16, fontWeight: 800, color: "#0f172a" }}>
                        {ward.name}{" "}
                        <span style={{ fontSize: 12, fontWeight: 600, color: "#64748b" }}>
                          • {ward.ward_type_label}
                          {ward.department_name ? ` • ${ward.department_name}` : ""}
                          {ward.floor ? ` • ${ward.floor}` : ""}
                        </span>
                      </div>
                      <div style={{ fontSize: 12, color: "#64748b", marginTop: 2 }}>
                        Daily Rate: <strong>{formatMoney(ward.daily_bed_rate)}/day</strong> •{" "}
                        {ward.available_beds} available / {ward.occupied_beds} occupied / {ward.cleaning_beds} cleaning
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        setEditingWard(ward);
                        setWardForm({
                          name: ward.name || "",
                          department_id: ward.department_id ? String(ward.department_id) : "",
                          ward_type: ward.ward_type || "general",
                          daily_bed_rate: String(ward.daily_bed_rate ?? ""),
                          floor: ward.floor || "",
                          auto_create_beds: "0",
                          bed_prefix: "BED",
                        });
                        setShowWardModal(true);
                      }}
                      style={{
                        border: "1px solid #cbd5e1",
                        background: "#fff",
                        color: "#334155",
                        borderRadius: 8,
                        padding: "5px 11px",
                        fontSize: 12,
                        fontWeight: 700,
                        cursor: "pointer",
                      }}
                    >
                      Edit Ward
                    </button>
                  </div>

                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "repeat(auto-fill, minmax(195px, 1fr))",
                      gap: 10,
                    }}
                  >
                    {(ward.beds || []).map((bed) => {
                      const st = BED_STYLES[bed.status] || BED_STYLES.available;
                      return (
                        <div
                          key={bed.id}
                          onClick={() => {
                            if (bed.status === "available") {
                              setAdmitBedModal(bed);
                            } else if (bed.status === "occupied") {
                              setDischargeBedModal(bed);
                            }
                          }}
                          style={{
                            background: st.bg,
                            border: `1.5px solid ${st.border}`,
                            borderRadius: 12,
                            padding: 12,
                            cursor:
                              bed.status === "available" || bed.status === "occupied"
                                ? "pointer"
                                : "default",
                            display: "flex",
                            flexDirection: "column",
                            gap: 6,
                          }}
                        >
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                            <span style={{ fontWeight: 800, fontSize: 14, color: "#0f172a" }}>
                              🛏️ {bed.bed_number}
                            </span>
                            <span
                              style={{
                                fontSize: 10.5,
                                fontWeight: 800,
                                color: st.color,
                                textTransform: "uppercase",
                              }}
                            >
                              {st.label}
                            </span>
                          </div>

                          {bed.status === "occupied" ? (
                            <>
                              <div style={{ fontSize: 13, fontWeight: 700, color: "#831843" }}>
                                {bed.current_patient_name}
                              </div>
                              {bed.attending_doctor && (
                                <div style={{ fontSize: 11.5, color: "#9d174d" }}>
                                  Dr. {bed.attending_doctor}
                                </div>
                              )}
                              <div style={{ fontSize: 11, color: "#be185d", marginTop: 2, fontWeight: 600 }}>
                                Click to Discharge &amp; Bill →
                              </div>
                            </>
                          ) : bed.status === "available" ? (
                            <div style={{ fontSize: 12, color: "#047857", fontWeight: 600 }}>
                              Click to Admit Patient →
                            </div>
                          ) : bed.status === "cleaning" ? (
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleBedStatusChange(bed, "available");
                              }}
                              style={{
                                marginTop: 4,
                                border: "none",
                                background: "#059669",
                                color: "#fff",
                                borderRadius: 8,
                                padding: "6px 10px",
                                fontSize: 11.5,
                                fontWeight: 700,
                                cursor: "pointer",
                              }}
                            >
                              ✓ Mark Ready
                            </button>
                          ) : (
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleBedStatusChange(bed, "available");
                              }}
                              style={{
                                marginTop: 4,
                                border: "1px solid #cbd5e1",
                                background: "#fff",
                                color: "#334155",
                                borderRadius: 8,
                                padding: "5px 9px",
                                fontSize: 11.5,
                                fontWeight: 700,
                                cursor: "pointer",
                              }}
                            >
                              Set Available
                            </button>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* TAB 2: DEPARTMENTS DIRECTORY */}
        {tab === "departments" && (
          <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 14, overflow: "hidden" }}>
            <div style={{ padding: "14px 18px", borderBottom: "1px solid #e2e8f0" }}>
              <div style={{ fontSize: 15, fontWeight: 800, color: "#0f172a" }}>
                🏥 Clinical Departments Directory
              </div>
              <div style={{ fontSize: 12, color: "#64748b" }}>
                Cardiology, Emergency, Pediatrics, Orthopedics, General Medicine &amp; specialty units
              </div>
            </div>
            {departments.length === 0 ? (
              <div style={{ padding: 40, textAlign: "center", color: "#64748b", fontSize: 13 }}>
                No departments added yet. Click <strong>+ Add Department</strong> to create one.
              </div>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                  <thead>
                    <tr style={{ background: "#f8fafc", textAlign: "left", color: "#475569" }}>
                      <th style={{ padding: "12px 16px", fontWeight: 700 }}>Department</th>
                      <th style={{ padding: "12px 14px", fontWeight: 700 }}>Code</th>
                      <th style={{ padding: "12px 14px", fontWeight: 700 }}>Head of Dept</th>
                      <th style={{ padding: "12px 14px", fontWeight: 700 }}>Floor / Ext</th>
                      <th style={{ padding: "12px 16px", fontWeight: 700, textAlign: "right" }}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {departments.map((d) => (
                      <tr key={d.id} style={{ borderTop: "1px solid #f1f5f9" }}>
                        <td style={{ padding: "12px 16px", fontWeight: 700, color: "#0f172a" }}>
                          {d.name}{" "}
                          {d.is_24_7 && (
                            <span style={{ fontSize: 10.5, fontWeight: 800, padding: "2px 7px", borderRadius: 999, background: "#fef2f2", color: "#b91c1c" }}>
                              24/7
                            </span>
                          )}
                        </td>
                        <td style={{ padding: "12px 14px", fontWeight: 700, color: "#64748b" }}>
                          {d.code || "—"}
                        </td>
                        <td style={{ padding: "12px 14px" }}>
                          {d.head_of_department || d.head_doctor_name || "—"}
                        </td>
                        <td style={{ padding: "12px 14px", color: "#64748b" }}>
                          {d.floor_location || d.floor_or_location || "—"}
                          {d.phone_ext || d.phone_extension ? ` • Ext ${d.phone_ext || d.phone_extension}` : ""}
                        </td>
                        <td style={{ padding: "12px 16px", textAlign: "right" }}>
                          <div style={{ display: "inline-flex", gap: 6 }}>
                            <button
                              type="button"
                              onClick={() => {
                                setEditingDept(d);
                                setDeptForm({
                                  name: d.name || "",
                                  code: d.code || "",
                                  head_of_department: d.head_of_department || d.head_doctor_name || "",
                                  floor_location: d.floor_location || d.floor_or_location || "",
                                  phone_ext: d.phone_ext || d.phone_extension || "",
                                  is_24_7: Boolean(d.is_24_7),
                                });
                                setShowDeptModal(true);
                              }}
                              style={{ border: "1px solid #cbd5e1", background: "#fff", color: "#0f172a", borderRadius: 7, padding: "4px 9px", fontSize: 11.5, fontWeight: 700, cursor: "pointer" }}
                            >
                              Edit
                            </button>
                            <button
                              type="button"
                              onClick={() => handleDeleteDept(d)}
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
        )}
      </div>

      {/* ADMIT PATIENT MODAL */}
      {admitBedModal && (
        <div
          onClick={() => setAdmitBedModal(null)}
          style={{ position: "fixed", inset: 0, background: "rgba(15,23,42,0.48)", zIndex: 1000, display: "grid", placeItems: "center", padding: 16 }}
        >
          <form
            onClick={(e) => e.stopPropagation()}
            onSubmit={handleAdmit}
            style={{ width: "100%", maxWidth: 460, background: "#fff", borderRadius: 16, padding: 22, display: "grid", gap: 12 }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h3 style={{ margin: 0, fontSize: 17, fontWeight: 800 }}>
                🛏️ Admit Patient — Bed {admitBedModal.bed_number}
              </h3>
              <button type="button" onClick={() => setAdmitBedModal(null)} style={{ border: "none", background: "transparent", fontSize: 18, cursor: "pointer" }}>
                ✕
              </button>
            </div>
            <div style={{ fontSize: 12, color: "#64748b" }}>
              {admitBedModal.ward_name} • {formatMoney(admitBedModal.daily_bed_rate)}/day
            </div>
            <input
              required
              placeholder="Patient Full Name *"
              value={admitForm.patient_name}
              onChange={(e) => setAdmitForm({ ...admitForm, patient_name: e.target.value })}
              style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }}
            />
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <input
                placeholder="Patient Phone"
                value={admitForm.patient_phone}
                onChange={(e) => setAdmitForm({ ...admitForm, patient_phone: e.target.value })}
                style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }}
              />
              <input
                placeholder="Attending Doctor"
                value={admitForm.attending_doctor}
                onChange={(e) => setAdmitForm({ ...admitForm, attending_doctor: e.target.value })}
                style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }}
              />
            </div>
            <input
              placeholder="Primary Diagnosis / Reason for Admission"
              value={admitForm.diagnosis}
              onChange={(e) => setAdmitForm({ ...admitForm, diagnosis: e.target.value })}
              style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }}
            />
            <textarea
              rows={2}
              placeholder="Admission Notes (allergies, monitoring instructions...)"
              value={admitForm.notes}
              onChange={(e) => setAdmitForm({ ...admitForm, notes: e.target.value })}
              style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }}
            />
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
              <button type="button" onClick={() => setAdmitBedModal(null)} style={{ border: "1px solid #cbd5e1", background: "#fff", borderRadius: 9, padding: "8px 14px", fontSize: 12.5, fontWeight: 700, cursor: "pointer" }}>
                Cancel
              </button>
              <button type="submit" disabled={saving} style={{ border: "none", background: ACCENT, color: "#240729", borderRadius: 9, padding: "8px 16px", fontSize: 13, fontWeight: 800, cursor: "pointer" }}>
                {saving ? "Admitting..." : "Confirm Admission"}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* DISCHARGE & BILL SUMMARY MODAL */}
      {dischargeBedModal && (
        <div
          onClick={() => setDischargeBedModal(null)}
          style={{ position: "fixed", inset: 0, background: "rgba(15,23,42,0.48)", zIndex: 1000, display: "grid", placeItems: "center", padding: 16 }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{ width: "100%", maxWidth: 440, background: "#fff", borderRadius: 16, padding: 22, display: "grid", gap: 12 }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h3 style={{ margin: 0, fontSize: 17, fontWeight: 800 }}>
                📋 Discharge Patient — Bed {dischargeBedModal.bed_number}
              </h3>
              <button type="button" onClick={() => setDischargeBedModal(null)} style={{ border: "none", background: "transparent", fontSize: 18, cursor: "pointer" }}>
                ✕
              </button>
            </div>
            <div style={{ background: "#fdf4ff", border: `1px solid ${ACCENT}`, borderRadius: 10, padding: 12, fontSize: 13, display: "grid", gap: 4 }}>
              <div><strong>Patient:</strong> {dischargeBedModal.current_patient_name}</div>
              <div><strong>Phone:</strong> {dischargeBedModal.current_patient_phone || "—"}</div>
              <div><strong>Doctor:</strong> {dischargeBedModal.attending_doctor || "—"}</div>
              <div><strong>Daily Rate:</strong> {formatMoney(dischargeBedModal.daily_bed_rate)} / day (min 1 day billed)</div>
            </div>
            <textarea
              rows={2}
              placeholder="Discharge summary / follow-up notes (optional)"
              value={dischargeNotes}
              onChange={(e) => setDischargeNotes(e.target.value)}
              style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }}
            />
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
              <button type="button" onClick={() => setDischargeBedModal(null)} style={{ border: "1px solid #cbd5e1", background: "#fff", borderRadius: 9, padding: "8px 14px", fontSize: 12.5, fontWeight: 700, cursor: "pointer" }}>
                Cancel
              </button>
              <button type="button" disabled={saving} onClick={handleDischarge} style={{ border: "none", background: "#0f172a", color: "#fff", borderRadius: 9, padding: "8px 16px", fontSize: 13, fontWeight: 700, cursor: "pointer" }}>
                {saving ? "Processing..." : "Discharge & Calculate Bill"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* CREATE / EDIT WARD MODAL */}
      {showWardModal && (
        <div
          onClick={() => {
            setShowWardModal(false);
            setEditingWard(null);
          }}
          style={{ position: "fixed", inset: 0, background: "rgba(15,23,42,0.48)", zIndex: 1000, display: "grid", placeItems: "center", padding: 16 }}
        >
          <form
            onClick={(e) => e.stopPropagation()}
            onSubmit={handleSaveWard}
            style={{ width: "100%", maxWidth: 460, background: "#fff", borderRadius: 16, padding: 22, display: "grid", gap: 12 }}
          >
            <h3 style={{ margin: 0, fontSize: 17, fontWeight: 800 }}>
              {editingWard ? "🛏️ Edit Ward" : "🛏️ Create Ward & Auto-Generate Beds"}
            </h3>
            <input
              required
              placeholder="Ward Name * (e.g., ICU Ward A, General Ward)"
              value={wardForm.name}
              onChange={(e) => setWardForm({ ...wardForm, name: e.target.value })}
              style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }}
            />
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <select
                value={wardForm.ward_type}
                onChange={(e) => setWardForm({ ...wardForm, ward_type: e.target.value })}
                style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13, background: "#fff" }}
              >
                {WARD_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
              <select
                value={wardForm.department_id}
                onChange={(e) => setWardForm({ ...wardForm, department_id: e.target.value })}
                style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13, background: "#fff" }}
              >
                <option value="">— Optional Department —</option>
                {departments.map((d) => (
                  <option key={d.id} value={d.id}>{d.name}</option>
                ))}
              </select>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <input
                type="number"
                min="0"
                step="100"
                placeholder="Daily Bed Rate (Rs.)"
                value={wardForm.daily_bed_rate}
                onChange={(e) => setWardForm({ ...wardForm, daily_bed_rate: e.target.value })}
                style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }}
              />
              <input
                placeholder="Floor (e.g. 2nd Floor)"
                value={wardForm.floor}
                onChange={(e) => setWardForm({ ...wardForm, floor: e.target.value })}
                style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }}
              />
            </div>
            {!editingWard && (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                <input
                  type="number"
                  min="0"
                  max="100"
                  placeholder="Auto-create beds (e.g. 10)"
                  value={wardForm.auto_create_beds}
                  onChange={(e) => setWardForm({ ...wardForm, auto_create_beds: e.target.value })}
                  style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }}
                />
                <input
                  placeholder="Bed Prefix (e.g. ICU, GW)"
                  value={wardForm.bed_prefix}
                  onChange={(e) => setWardForm({ ...wardForm, bed_prefix: e.target.value })}
                  style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }}
                />
              </div>
            )}
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
              <button
                type="button"
                onClick={() => {
                  setShowWardModal(false);
                  setEditingWard(null);
                }}
                style={{ border: "1px solid #cbd5e1", background: "#fff", borderRadius: 9, padding: "8px 14px", fontSize: 12.5, fontWeight: 700, cursor: "pointer" }}
              >
                Cancel
              </button>
              <button type="submit" disabled={saving} style={{ border: "none", background: ACCENT, color: "#240729", borderRadius: 9, padding: "8px 16px", fontSize: 13, fontWeight: 800, cursor: "pointer" }}>
                {saving ? "Saving..." : editingWard ? "Save Changes" : "Create Ward"}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* CREATE / EDIT DEPARTMENT MODAL */}
      {showDeptModal && (
        <div
          onClick={() => {
            setShowDeptModal(false);
            setEditingDept(null);
          }}
          style={{ position: "fixed", inset: 0, background: "rgba(15,23,42,0.48)", zIndex: 1000, display: "grid", placeItems: "center", padding: 16 }}
        >
          <form
            onClick={(e) => e.stopPropagation()}
            onSubmit={handleSaveDept}
            style={{ width: "100%", maxWidth: 440, background: "#fff", borderRadius: 16, padding: 22, display: "grid", gap: 12 }}
          >
            <h3 style={{ margin: 0, fontSize: 17, fontWeight: 800 }}>
              {editingDept ? "🏥 Edit Department" : "🏥 Add Hospital Department"}
            </h3>
            <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 10 }}>
              <input
                required
                placeholder="Department Name * (e.g. Cardiology)"
                value={deptForm.name}
                onChange={(e) => setDeptForm({ ...deptForm, name: e.target.value })}
                style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }}
              />
              <input
                placeholder="Code (CARD)"
                value={deptForm.code}
                onChange={(e) => setDeptForm({ ...deptForm, code: e.target.value })}
                style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }}
              />
            </div>
            <input
              placeholder="Head of Department (e.g. Dr. Ahmed)"
              value={deptForm.head_of_department}
              onChange={(e) => setDeptForm({ ...deptForm, head_of_department: e.target.value })}
              style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }}
            />
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <input
                placeholder="Floor / Wing"
                value={deptForm.floor_location}
                onChange={(e) => setDeptForm({ ...deptForm, floor_location: e.target.value })}
                style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }}
              />
              <input
                placeholder="Phone Ext."
                value={deptForm.phone_ext}
                onChange={(e) => setDeptForm({ ...deptForm, phone_ext: e.target.value })}
                style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }}
              />
            </div>
            <label style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 13, fontWeight: 600 }}>
              <input
                type="checkbox"
                checked={deptForm.is_24_7}
                onChange={(e) => setDeptForm({ ...deptForm, is_24_7: e.target.checked })}
              />
              24/7 Emergency / Critical Care Department
            </label>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
              <button
                type="button"
                onClick={() => {
                  setShowDeptModal(false);
                  setEditingDept(null);
                }}
                style={{ border: "1px solid #cbd5e1", background: "#fff", borderRadius: 9, padding: "8px 14px", fontSize: 12.5, fontWeight: 700, cursor: "pointer" }}
              >
                Cancel
              </button>
              <button type="submit" disabled={saving} style={{ border: "none", background: ACCENT, color: "#240729", borderRadius: 9, padding: "8px 16px", fontSize: 13, fontWeight: 800, cursor: "pointer" }}>
                {saving ? "Saving..." : editingDept ? "Save Changes" : "Save Department"}
              </button>
            </div>
          </form>
        </div>
      )}
    </Layout>
  );
}
