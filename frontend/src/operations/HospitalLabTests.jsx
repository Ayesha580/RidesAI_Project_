import { useCallback, useEffect, useState } from "react";
import OwnerLayout from "../owner/components/OwnerLayout";
import StaffLayout from "../staff/components/StaffLayout";
import { hospitalApi } from "../api/operationsApi";

const ACCENT = "#ff77ff";

const CATEGORIES = [
  { value: "hematology", label: "Hematology" },
  { value: "biochemistry", label: "Biochemistry" },
  { value: "radiology", label: "Radiology" },
  { value: "cardiology", label: "Cardiology" },
  { value: "microbiology", label: "Microbiology" },
  { value: "other", label: "Other" },
];

const ORDER_STATUS_STYLES = {
  ordered: { label: "Ordered", bg: "#eff6ff", color: "#1d4ed8", border: "#bfdbfe" },
  sample_collected: { label: "Sample Collected", bg: "#fefce8", color: "#a16207", border: "#fde047" },
  in_progress: { label: "In Progress", bg: "#fdf4ff", color: "#86198f", border: "#f0abfc" },
  completed: { label: "Completed", bg: "#ecfdf5", color: "#047857", border: "#a7f3d0" },
  cancelled: { label: "Cancelled", bg: "#fef2f2", color: "#b91c1c", border: "#fecaca" },
};

const FLAG_STYLES = {
  normal: { label: "Normal", bg: "#ecfdf5", color: "#047857" },
  abnormal: { label: "Abnormal", bg: "#fffbeb", color: "#b45309" },
  critical: { label: "Critical", bg: "#fef2f2", color: "#b91c1c" },
  pending: { label: "Pending", bg: "#f1f5f9", color: "#64748b" },
};

function formatMoney(v) {
  return `Rs. ${Number(v || 0).toLocaleString("en-PK", { maximumFractionDigits: 0 })}`;
}

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

const EMPTY_CATALOG = {
  test_code: "",
  name: "",
  category: "hematology",
  price: "",
  normal_range: "",
  unit: "",
  turnaround_hours: "24",
};

const EMPTY_ORDER = {
  patient_id: "",
  doctor_id: "",
  test_id: "",
  test_name: "",
  category: "hematology",
  fee: "",
  normal_range: "",
  payment_status: "unpaid",
  technician_notes: "",
};

export default function HospitalLabTests({ staff = false }) {
  const Layout = staff ? StaffLayout : OwnerLayout;
  const [tab, setTab] = useState("orders"); // "orders" | "catalog"

  const [orders, setOrders] = useState([]);
  const [summary, setSummary] = useState({
    total_orders: 0,
    pending_orders: 0,
    completed_today: 0,
    abnormal_alerts: 0,
    lab_revenue: 0,
  });
  const [catalog, setCatalog] = useState([]);
  const [patients, setPatients] = useState([]);
  const [doctors, setDoctors] = useState([]);

  // Filters
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [catFilter, setCatFilter] = useState("all");

  // UI states
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState("");
  const [error, setError] = useState("");

  // Modals
  const [showOrderModal, setShowOrderModal] = useState(false);
  const [orderForm, setOrderForm] = useState(EMPTY_ORDER);

  const [showCatalogModal, setShowCatalogModal] = useState(false);
  const [editingCatalog, setEditingCatalog] = useState(null);
  const [catalogForm, setCatalogForm] = useState(EMPTY_CATALOG);

  const [resultModalOrder, setResultModalOrder] = useState(null);
  const [resultForm, setResultForm] = useState({
    status: "completed",
    result_value: "",
    normal_range: "",
    result_flag: "normal",
    payment_status: "paid",
    technician_notes: "",
  });

  const [printOrder, setPrintOrder] = useState(null);

  const showToast = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(""), 3500);
  };

  const loadMeta = useCallback(async () => {
    try {
      const [patRes, docRes, catRes] = await Promise.all([
        hospitalApi.listPatients(),
        hospitalApi.listDoctors(),
        hospitalApi.listLabCatalog(),
      ]);
      setPatients(patRes.data?.results || []);
      setDoctors(docRes.data?.results || docRes.data || []);
      setCatalog(catRes.data?.results || []);
    } catch {
      // non-blocking
    }
  }, []);

  const loadOrders = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const params = {};
      if (search.trim()) params.search = search.trim();
      if (statusFilter && statusFilter !== "all") params.status = statusFilter;
      const { data } = await hospitalApi.listLabOrders(params);
      setOrders(data?.results || []);
      if (data?.summary) setSummary(data.summary);
    } catch (err) {
      setError(err?.response?.data?.detail || "Could not load lab orders.");
    } finally {
      if (!silent) setLoading(false);
    }
  }, [search, statusFilter]);

  const loadCatalog = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const params = {};
      if (search.trim()) params.search = search.trim();
      if (catFilter && catFilter !== "all") params.category = catFilter;
      const { data } = await hospitalApi.listLabCatalog(params);
      setCatalog(data?.results || []);
    } catch (err) {
      setError(err?.response?.data?.detail || "Could not load lab test catalog.");
    } finally {
      if (!silent) setLoading(false);
    }
  }, [search, catFilter]);

  useEffect(() => {
    loadMeta();
  }, [loadMeta]);

  useEffect(() => {
    if (tab === "orders") loadOrders();
    else loadCatalog();
  }, [tab, loadOrders, loadCatalog]);

  const handleSelectCatalogTest = (testId) => {
    const t = catalog.find((c) => String(c.id) === String(testId));
    if (!t) {
      setOrderForm((prev) => ({ ...prev, test_id: testId }));
      return;
    }
    setOrderForm((prev) => ({
      ...prev,
      test_id: testId,
      test_name: t.name,
      category: t.category,
      fee: String(t.price ?? ""),
      normal_range: t.normal_range || "",
    }));
  };

  const handleCreateOrder = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      const payload = {
        ...orderForm,
        patient_id: Number(orderForm.patient_id),
        doctor_id: orderForm.doctor_id ? Number(orderForm.doctor_id) : null,
        test_id: orderForm.test_id ? Number(orderForm.test_id) : null,
        fee: orderForm.fee !== "" ? Number(orderForm.fee) : undefined,
      };
      const { data } = await hospitalApi.createLabOrder(payload);
      showToast(`Created ${data.order_number} (${data.test_name}) for ${data.patient_name}.`);
      setShowOrderModal(false);
      setOrderForm(EMPTY_ORDER);
      await loadOrders(true);
    } catch (err) {
      const d = err?.response?.data;
      setError(d?.detail || d?.patient_id || d?.test_name || "Could not create lab order.");
    } finally {
      setSaving(false);
    }
  };

  const openResultModal = (order) => {
    setResultModalOrder(order);
    setResultForm({
      status: order.status === "ordered" ? "completed" : order.status,
      result_value: order.result_value || "",
      normal_range: order.normal_range || "",
      result_flag: order.result_flag === "pending" ? "normal" : order.result_flag,
      payment_status: order.payment_status || "unpaid",
      technician_notes: order.technician_notes || "",
    });
  };

  const handleSubmitResult = async (e) => {
    e.preventDefault();
    if (!resultModalOrder) return;
    setSaving(true);
    setError("");
    try {
      const { data } = await hospitalApi.submitLabResult(resultModalOrder.id, resultForm);
      showToast(`Saved diagnostic result for ${data.order_number}.`);
      setResultModalOrder(null);
      await loadOrders(true);
      if (data.status === "completed") setPrintOrder(data);
    } catch (err) {
      setError(err?.response?.data?.detail || "Could not save lab result.");
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteOrder = async (order) => {
    if (!window.confirm(`Delete lab order ${order.order_number} (${order.test_name})?`)) return;
    try {
      await hospitalApi.deleteLabOrder(order.id);
      showToast(`Deleted ${order.order_number}.`);
      await loadOrders(true);
    } catch (err) {
      setError(err?.response?.data?.detail || "Failed to delete lab order.");
    }
  };

  const handleSaveCatalog = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      const payload = {
        ...catalogForm,
        price: Number(catalogForm.price || 0),
        turnaround_hours: Number(catalogForm.turnaround_hours || 24),
      };
      if (editingCatalog) {
        await hospitalApi.updateLabCatalogItem(editingCatalog.id, payload);
        showToast(`Updated ${catalogForm.test_code}.`);
      } else {
        await hospitalApi.createLabCatalogItem(payload);
        showToast(`Added ${catalogForm.test_code} to lab catalog.`);
      }
      setShowCatalogModal(false);
      setEditingCatalog(null);
      setCatalogForm(EMPTY_CATALOG);
      await loadCatalog(true);
    } catch (err) {
      const d = err?.response?.data;
      setError(d?.detail || d?.test_code || d?.name || "Could not save lab test.");
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteCatalog = async (item) => {
    if (!window.confirm(`Delete test "${item.name}" (${item.test_code}) from catalog?`)) return;
    try {
      await hospitalApi.deleteLabCatalogItem(item.id);
      showToast(`Removed ${item.test_code}.`);
      await loadCatalog(true);
    } catch (err) {
      setError(err?.response?.data?.detail || "Failed to delete catalog test.");
    }
  };

  return (
    <Layout
      title="Lab Tests & Diagnostic Reports"
      subtitle="Manage hospital test catalog, patient lab orders, structured diagnostic results, and 1-click printable lab reports."
    >
      <style>{`
        @media print {
          body * { visibility: hidden !important; }
          #lab-report-sheet, #lab-report-sheet * { visibility: visible !important; }
          #lab-report-sheet {
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
        {/* KPI Strip */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(195px, 1fr))", gap: 12 }}>
          {[
            { label: "Total Lab Orders", value: summary.total_orders || 0, color: "#0f172a", icon: "🧪" },
            { label: "Pending / In Progress", value: summary.pending_orders || 0, color: "#a16207", icon: "⏳" },
            { label: "Completed Today", value: summary.completed_today || 0, color: "#047857", icon: "✅" },
            { label: "Abnormal / Critical", value: summary.abnormal_alerts || 0, color: "#b91c1c", icon: "⚠️" },
            { label: "Lab Revenue", value: formatMoney(summary.lab_revenue), color: "#86198f", icon: "💳" },
          ].map((k) => (
            <div key={k.label} style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 14, padding: "14px 16px" }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: "#64748b" }}>{k.icon} {k.label}</div>
              <div style={{ fontSize: 22, fontWeight: 800, color: k.color, marginTop: 6 }}>{k.value}</div>
            </div>
          ))}
        </div>

        {/* Tab Bar + Primary CTA */}
        <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 14, padding: "12px 16px", display: "flex", flexWrap: "wrap", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              type="button"
              onClick={() => setTab("orders")}
              style={{
                border: tab === "orders" ? `1.5px solid ${ACCENT}` : "1px solid #e2e8f0",
                background: tab === "orders" ? "#fdf4ff" : "#fff",
                color: tab === "orders" ? "#86198f" : "#475569",
                borderRadius: 10,
                padding: "8px 16px",
                fontSize: 13,
                fontWeight: 700,
                cursor: "pointer",
              }}
            >
              🧪 Lab Orders &amp; Results ({orders.length})
            </button>
            <button
              type="button"
              onClick={() => setTab("catalog")}
              style={{
                border: tab === "catalog" ? `1.5px solid ${ACCENT}` : "1px solid #e2e8f0",
                background: tab === "catalog" ? "#fdf4ff" : "#fff",
                color: tab === "catalog" ? "#86198f" : "#475569",
                borderRadius: 10,
                padding: "8px 16px",
                fontSize: 13,
                fontWeight: 700,
                cursor: "pointer",
              }}
            >
              📋 Test Catalog &amp; Pricing ({catalog.length})
            </button>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              type="button"
              onClick={() => { setEditingCatalog(null); setCatalogForm(EMPTY_CATALOG); setShowCatalogModal(true); }}
              style={{ border: "1px solid #cbd5e1", background: "#fff", color: "#0f172a", borderRadius: 10, padding: "8px 14px", fontSize: 12.5, fontWeight: 700, cursor: "pointer" }}
            >
              + Add Lab Test
            </button>
            <button
              type="button"
              onClick={() => { setOrderForm(EMPTY_ORDER); setShowOrderModal(true); }}
              style={{ border: "none", background: ACCENT, color: "#240729", borderRadius: 10, padding: "8px 16px", fontSize: 12.5, fontWeight: 800, cursor: "pointer" }}
            >
              + New Lab Order
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

        {/* TAB 1: LAB ORDERS */}
        {tab === "orders" && (
          <div style={{ display: "grid", gap: 12 }}>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              <input
                type="text"
                placeholder="Search LAB#, Patient Name, MRN, or Test..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                style={{ flex: "1 1 240px", padding: "8px 12px", borderRadius: 10, border: "1px solid #cbd5e1", fontSize: 13 }}
              />
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                style={{ padding: "8px 12px", borderRadius: 10, border: "1px solid #cbd5e1", fontSize: 13, background: "#fff" }}
              >
                <option value="all">All Statuses</option>
                {Object.entries(ORDER_STATUS_STYLES).map(([k, v]) => (
                  <option key={k} value={k}>{v.label}</option>
                ))}
              </select>
            </div>

            <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 14, overflow: "hidden" }}>
              {loading ? (
                <div style={{ padding: 44, textAlign: "center", color: "#64748b", fontSize: 13 }}>Loading lab orders...</div>
              ) : orders.length === 0 ? (
                <div style={{ padding: 48, textAlign: "center", color: "#64748b", fontSize: 13 }}>
                  No lab orders yet. Click <strong>+ New Lab Order</strong> to order a diagnostic test.
                </div>
              ) : (
                <div style={{ overflowX: "auto" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                    <thead>
                      <tr style={{ background: "#f8fafc", textAlign: "left", color: "#475569" }}>
                        <th style={{ padding: "12px 14px", fontWeight: 700 }}>Order #</th>
                        <th style={{ padding: "12px 14px", fontWeight: 700 }}>Patient</th>
                        <th style={{ padding: "12px 14px", fontWeight: 700 }}>Test &amp; Category</th>
                        <th style={{ padding: "12px 14px", fontWeight: 700 }}>Fee / Payment</th>
                        <th style={{ padding: "12px 14px", fontWeight: 700 }}>Status</th>
                        <th style={{ padding: "12px 14px", fontWeight: 700 }}>Result Flag</th>
                        <th style={{ padding: "12px 14px", fontWeight: 700, textAlign: "right" }}>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {orders.map((o) => {
                        const st = ORDER_STATUS_STYLES[o.status] || ORDER_STATUS_STYLES.ordered;
                        const fl = FLAG_STYLES[o.result_flag] || FLAG_STYLES.pending;
                        return (
                          <tr key={o.id} style={{ borderTop: "1px solid #f1f5f9" }}>
                            <td style={{ padding: "12px 14px" }}>
                              <span style={{ background: "#0f172a", color: "#fff", borderRadius: 8, padding: "4px 9px", fontWeight: 800, fontSize: 12 }}>
                                {o.order_number}
                              </span>
                            </td>
                            <td style={{ padding: "12px 14px" }}>
                              <div style={{ fontWeight: 700, color: "#0f172a" }}>{o.patient_name}</div>
                              <div style={{ fontSize: 11.5, color: "#64748b" }}>{o.patient_mrn}</div>
                            </td>
                            <td style={{ padding: "12px 14px" }}>
                              <div style={{ fontWeight: 700, color: "#0f172a" }}>{o.test_name}</div>
                              <div style={{ fontSize: 11.5, color: "#64748b", textTransform: "capitalize" }}>{o.category}</div>
                            </td>
                            <td style={{ padding: "12px 14px" }}>
                              <div style={{ fontWeight: 700 }}>{formatMoney(o.fee)}</div>
                              <span style={{ fontSize: 10.5, fontWeight: 700, padding: "1px 7px", borderRadius: 999, background: o.payment_status === "paid" ? "#ecfdf5" : "#fffbeb", color: o.payment_status === "paid" ? "#047857" : "#b45309" }}>
                                {o.payment_status === "paid" ? "Paid" : "Unpaid"}
                              </span>
                            </td>
                            <td style={{ padding: "12px 14px" }}>
                              <span style={{ fontSize: 11, fontWeight: 700, background: st.bg, color: st.color, border: `1px solid ${st.border}`, padding: "3px 9px", borderRadius: 999 }}>
                                {st.label}
                              </span>
                            </td>
                            <td style={{ padding: "12px 14px" }}>
                              <span style={{ fontSize: 11, fontWeight: 800, background: fl.bg, color: fl.color, padding: "3px 9px", borderRadius: 999 }}>
                                {fl.label}
                              </span>
                            </td>
                            <td style={{ padding: "12px 14px", textAlign: "right" }}>
                              <div style={{ display: "inline-flex", gap: 6 }}>
                                <button
                                  type="button"
                                  onClick={() => openResultModal(o)}
                                  style={{ border: `1px solid ${ACCENT}`, background: "#fdf4ff", color: "#86198f", borderRadius: 7, padding: "4px 9px", fontSize: 11.5, fontWeight: 700, cursor: "pointer" }}
                                >
                                  Enter Result
                                </button>
                                <button
                                  type="button"
                                  onClick={() => setPrintOrder(o)}
                                  style={{ border: "1px solid #cbd5e1", background: "#fff", color: "#0f172a", borderRadius: 7, padding: "4px 9px", fontSize: 11.5, fontWeight: 700, cursor: "pointer" }}
                                >
                                  🖨️ Report
                                </button>
                                <button
                                  type="button"
                                  onClick={() => handleDeleteOrder(o)}
                                  style={{ border: "1px solid #fecaca", background: "#fff", color: "#b91c1c", borderRadius: 7, padding: "4px 9px", fontSize: 11.5, fontWeight: 700, cursor: "pointer" }}
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

        {/* TAB 2: TEST CATALOG */}
        {tab === "catalog" && (
          <div style={{ display: "grid", gap: 12 }}>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              <input
                type="text"
                placeholder="Search test code (CBC, LFT) or name..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                style={{ flex: "1 1 240px", padding: "8px 12px", borderRadius: 10, border: "1px solid #cbd5e1", fontSize: 13 }}
              />
              <select
                value={catFilter}
                onChange={(e) => setCatFilter(e.target.value)}
                style={{ padding: "8px 12px", borderRadius: 10, border: "1px solid #cbd5e1", fontSize: 13, background: "#fff" }}
              >
                <option value="all">All Categories</option>
                {CATEGORIES.map((c) => (
                  <option key={c.value} value={c.value}>{c.label}</option>
                ))}
              </select>
            </div>

            <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 14, overflow: "hidden" }}>
              {catalog.length === 0 ? (
                <div style={{ padding: 48, textAlign: "center", color: "#64748b", fontSize: 13 }}>
                  No tests in catalog yet. Click <strong>+ Add Lab Test</strong> to configure pricing and normal ranges.
                </div>
              ) : (
                <div style={{ overflowX: "auto" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                    <thead>
                      <tr style={{ background: "#f8fafc", textAlign: "left", color: "#475569" }}>
                        <th style={{ padding: "12px 14px", fontWeight: 700 }}>Code</th>
                        <th style={{ padding: "12px 14px", fontWeight: 700 }}>Test Name</th>
                        <th style={{ padding: "12px 14px", fontWeight: 700 }}>Category</th>
                        <th style={{ padding: "12px 14px", fontWeight: 700 }}>Normal Range</th>
                        <th style={{ padding: "12px 14px", fontWeight: 700 }}>TAT</th>
                        <th style={{ padding: "12px 14px", fontWeight: 700 }}>Price</th>
                        <th style={{ padding: "12px 14px", fontWeight: 700, textAlign: "right" }}>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {catalog.map((t) => (
                        <tr key={t.id} style={{ borderTop: "1px solid #f1f5f9" }}>
                          <td style={{ padding: "12px 14px", fontWeight: 800, color: "#0f172a" }}>{t.test_code}</td>
                          <td style={{ padding: "12px 14px", fontWeight: 700 }}>{t.name}</td>
                          <td style={{ padding: "12px 14px", color: "#475569" }}>{t.category_label}</td>
                          <td style={{ padding: "12px 14px", color: "#64748b" }}>
                            {t.normal_range || "—"} {t.unit ? `(${t.unit})` : ""}
                          </td>
                          <td style={{ padding: "12px 14px" }}>{t.turnaround_hours} hrs</td>
                          <td style={{ padding: "12px 14px", fontWeight: 700 }}>{formatMoney(t.price)}</td>
                          <td style={{ padding: "12px 14px", textAlign: "right" }}>
                            <div style={{ display: "inline-flex", gap: 6 }}>
                              <button
                                type="button"
                                onClick={() => {
                                  setEditingCatalog(t);
                                  setCatalogForm({
                                    test_code: t.test_code || "",
                                    name: t.name || "",
                                    category: t.category || "hematology",
                                    price: String(t.price ?? ""),
                                    normal_range: t.normal_range || "",
                                    unit: t.unit || "",
                                    turnaround_hours: String(t.turnaround_hours ?? 24),
                                  });
                                  setShowCatalogModal(true);
                                }}
                                style={{ border: "1px solid #cbd5e1", background: "#fff", color: "#0f172a", borderRadius: 7, padding: "4px 9px", fontSize: 11.5, fontWeight: 700, cursor: "pointer" }}
                              >
                                Edit
                              </button>
                              <button
                                type="button"
                                onClick={() => handleDeleteCatalog(t)}
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
        )}
      </div>

      {/* NEW LAB ORDER MODAL */}
      {showOrderModal && (
        <div onClick={() => setShowOrderModal(false)} style={{ position: "fixed", inset: 0, background: "rgba(15,23,42,0.48)", zIndex: 1000, display: "grid", placeItems: "center", padding: 16 }}>
          <form onClick={(e) => e.stopPropagation()} onSubmit={handleCreateOrder} style={{ width: "100%", maxWidth: 500, background: "#fff", borderRadius: 16, padding: 22, display: "grid", gap: 12 }}>
            <h3 style={{ margin: 0, fontSize: 17, fontWeight: 800 }}>🧪 New Diagnostic Lab Order</h3>
            <select required value={orderForm.patient_id} onChange={(e) => setOrderForm({ ...orderForm, patient_id: e.target.value })} style={{ padding: "9px 10px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13, background: "#fff" }}>
              <option value="">— Select Patient * —</option>
              {patients.map((p) => (
                <option key={p.id} value={p.id}>{p.full_name} ({p.mrn})</option>
              ))}
            </select>
            <select value={orderForm.doctor_id} onChange={(e) => setOrderForm({ ...orderForm, doctor_id: e.target.value })} style={{ padding: "9px 10px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13, background: "#fff" }}>
              <option value="">— Optional Referring Doctor —</option>
              {doctors.map((d) => (
                <option key={d.id} value={d.id}>{d.full_name}</option>
              ))}
            </select>
            <select value={orderForm.test_id} onChange={(e) => handleSelectCatalogTest(e.target.value)} style={{ padding: "9px 10px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13, background: "#fff" }}>
              <option value="">— Select from Test Catalog (or type custom below) —</option>
              {catalog.map((t) => (
                <option key={t.id} value={t.id}>{t.test_code} — {t.name} ({formatMoney(t.price)})</option>
              ))}
            </select>
            <input required placeholder="Test Name *" value={orderForm.test_name} onChange={(e) => setOrderForm({ ...orderForm, test_name: e.target.value })} style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }} />
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <input type="number" min="0" step="50" placeholder="Fee (Rs.)" value={orderForm.fee} onChange={(e) => setOrderForm({ ...orderForm, fee: e.target.value })} style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }} />
              <select value={orderForm.payment_status} onChange={(e) => setOrderForm({ ...orderForm, payment_status: e.target.value })} style={{ padding: "9px 10px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13, background: "#fff" }}>
                <option value="unpaid">Payment: Unpaid</option>
                <option value="paid">Payment: Paid</option>
              </select>
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
              <button type="button" onClick={() => setShowOrderModal(false)} style={{ border: "1px solid #cbd5e1", background: "#fff", borderRadius: 9, padding: "8px 14px", fontSize: 12.5, fontWeight: 700, cursor: "pointer" }}>Cancel</button>
              <button type="submit" disabled={saving} style={{ border: "none", background: ACCENT, color: "#240729", borderRadius: 9, padding: "8px 16px", fontSize: 13, fontWeight: 800, cursor: "pointer" }}>
                {saving ? "Creating..." : "Create Lab Order"}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* ADD / EDIT CATALOG TEST MODAL */}
      {showCatalogModal && (
        <div onClick={() => { setShowCatalogModal(false); setEditingCatalog(null); }} style={{ position: "fixed", inset: 0, background: "rgba(15,23,42,0.48)", zIndex: 1000, display: "grid", placeItems: "center", padding: 16 }}>
          <form onClick={(e) => e.stopPropagation()} onSubmit={handleSaveCatalog} style={{ width: "100%", maxWidth: 480, background: "#fff", borderRadius: 16, padding: 22, display: "grid", gap: 12 }}>
            <h3 style={{ margin: 0, fontSize: 17, fontWeight: 800 }}>
              {editingCatalog ? "✏️ Edit Lab Test" : "📋 Add Lab Test to Catalog"}
            </h3>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: 10 }}>
              <input required placeholder="Code * (CBC)" value={catalogForm.test_code} onChange={(e) => setCatalogForm({ ...catalogForm, test_code: e.target.value })} style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }} />
              <input required placeholder="Test Name *" value={catalogForm.name} onChange={(e) => setCatalogForm({ ...catalogForm, name: e.target.value })} style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }} />
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10 }}>
              <select value={catalogForm.category} onChange={(e) => setCatalogForm({ ...catalogForm, category: e.target.value })} style={{ padding: "9px 10px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13, background: "#fff" }}>
                {CATEGORIES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
              </select>
              <input type="number" min="0" step="50" placeholder="Price (Rs.)" value={catalogForm.price} onChange={(e) => setCatalogForm({ ...catalogForm, price: e.target.value })} style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }} />
              <input type="number" min="1" placeholder="TAT (hrs)" value={catalogForm.turnaround_hours} onChange={(e) => setCatalogForm({ ...catalogForm, turnaround_hours: e.target.value })} style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }} />
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 10 }}>
              <input placeholder="Normal Range (e.g. 4.5 - 11.0)" value={catalogForm.normal_range} onChange={(e) => setCatalogForm({ ...catalogForm, normal_range: e.target.value })} style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }} />
              <input placeholder="Unit (g/dL)" value={catalogForm.unit} onChange={(e) => setCatalogForm({ ...catalogForm, unit: e.target.value })} style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }} />
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
              <button type="button" onClick={() => { setShowCatalogModal(false); setEditingCatalog(null); }} style={{ border: "1px solid #cbd5e1", background: "#fff", borderRadius: 9, padding: "8px 14px", fontSize: 12.5, fontWeight: 700, cursor: "pointer" }}>Cancel</button>
              <button type="submit" disabled={saving} style={{ border: "none", background: ACCENT, color: "#240729", borderRadius: 9, padding: "8px 16px", fontSize: 13, fontWeight: 800, cursor: "pointer" }}>
                {saving ? "Saving..." : editingCatalog ? "Save Changes" : "Add Test"}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* ENTER RESULT MODAL */}
      {resultModalOrder && (
        <div onClick={() => setResultModalOrder(null)} style={{ position: "fixed", inset: 0, background: "rgba(15,23,42,0.48)", zIndex: 1000, display: "grid", placeItems: "center", padding: 16 }}>
          <form onClick={(e) => e.stopPropagation()} onSubmit={handleSubmitResult} style={{ width: "100%", maxWidth: 480, background: "#fff", borderRadius: 16, padding: 22, display: "grid", gap: 12 }}>
            <h3 style={{ margin: 0, fontSize: 17, fontWeight: 800 }}>🔬 Enter Result — {resultModalOrder.order_number}</h3>
            <div style={{ fontSize: 12.5, color: "#64748b" }}>
              {resultModalOrder.patient_name} ({resultModalOrder.patient_mrn}) • <strong>{resultModalOrder.test_name}</strong>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <select value={resultForm.status} onChange={(e) => setResultForm({ ...resultForm, status: e.target.value })} style={{ padding: "9px 10px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13, background: "#fff" }}>
                <option value="sample_collected">Sample Collected</option>
                <option value="in_progress">In Progress</option>
                <option value="completed">Completed</option>
                <option value="cancelled">Cancelled</option>
              </select>
              <select value={resultForm.result_flag} onChange={(e) => setResultForm({ ...resultForm, result_flag: e.target.value })} style={{ padding: "9px 10px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13, background: "#fff" }}>
                <option value="normal">Flag: Normal</option>
                <option value="abnormal">Flag: Abnormal</option>
                <option value="critical">Flag: Critical</option>
                <option value="pending">Flag: Pending</option>
              </select>
            </div>
            <textarea rows={2} placeholder="Observed Result Value (e.g. Hemoglobin 13.8 g/dL)" value={resultForm.result_value} onChange={(e) => setResultForm({ ...resultForm, result_value: e.target.value })} style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }} />
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <input placeholder="Normal Reference Range" value={resultForm.normal_range} onChange={(e) => setResultForm({ ...resultForm, normal_range: e.target.value })} style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }} />
              <select value={resultForm.payment_status} onChange={(e) => setResultForm({ ...resultForm, payment_status: e.target.value })} style={{ padding: "9px 10px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13, background: "#fff" }}>
                <option value="paid">Payment: Paid</option>
                <option value="unpaid">Payment: Unpaid</option>
              </select>
            </div>
            <textarea rows={2} placeholder="Pathologist / Technician Notes" value={resultForm.technician_notes} onChange={(e) => setResultForm({ ...resultForm, technician_notes: e.target.value })} style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #cbd5e1", fontSize: 13 }} />
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
              <button type="button" onClick={() => setResultModalOrder(null)} style={{ border: "1px solid #cbd5e1", background: "#fff", borderRadius: 9, padding: "8px 14px", fontSize: 12.5, fontWeight: 700, cursor: "pointer" }}>Cancel</button>
              <button type="submit" disabled={saving} style={{ border: "none", background: ACCENT, color: "#240729", borderRadius: 9, padding: "8px 16px", fontSize: 13, fontWeight: 800, cursor: "pointer" }}>
                {saving ? "Saving..." : "Save Result"}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* 1-CLICK PRINTABLE LAB REPORT MODAL */}
      {printOrder && (
        <div onClick={() => setPrintOrder(null)} style={{ position: "fixed", inset: 0, background: "rgba(15,23,42,0.55)", zIndex: 1100, display: "grid", placeItems: "center", padding: 16 }}>
          <div id="lab-report-sheet" onClick={(e) => e.stopPropagation()} style={{ width: "100%", maxWidth: 720, maxHeight: "92vh", overflowY: "auto", background: "#fff", borderRadius: 16, padding: 28, display: "grid", gap: 16 }}>
            <div className="no-print" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid #e2e8f0", paddingBottom: 10 }}>
              <span style={{ fontSize: 13, fontWeight: 700, color: "#64748b" }}>Diagnostic Lab Report — {printOrder.order_number}</span>
              <div style={{ display: "flex", gap: 8 }}>
                <button type="button" onClick={() => window.print()} style={{ border: "none", background: ACCENT, color: "#240729", borderRadius: 9, padding: "7px 14px", fontSize: 12.5, fontWeight: 800, cursor: "pointer" }}>
                  🖨️ Print Report
                </button>
                <button type="button" onClick={() => setPrintOrder(null)} style={{ border: "1px solid #cbd5e1", background: "#fff", borderRadius: 9, padding: "7px 12px", fontSize: 12.5, fontWeight: 700, cursor: "pointer" }}>
                  Close
                </button>
              </div>
            </div>

            <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "2px solid #0f172a", paddingBottom: 12 }}>
              <div>
                <div style={{ fontSize: 21, fontWeight: 900, color: "#0f172a" }}>{printOrder.hospital?.name || "HospitalCare Diagnostics"}</div>
                {printOrder.hospital?.address && <div style={{ fontSize: 12, color: "#475569" }}>{printOrder.hospital.address}</div>}
                {printOrder.hospital?.phone && <div style={{ fontSize: 12, color: "#475569" }}>Tel: {printOrder.hospital.phone}</div>}
              </div>
              <div style={{ textAlign: "right", fontSize: 12.5 }}>
                <div style={{ fontWeight: 800, fontSize: 15 }}>DIAGNOSTIC LAB REPORT</div>
                <div><strong>Order #:</strong> {printOrder.order_number}</div>
                <div><strong>Date:</strong> {formatDate(printOrder.completed_at || printOrder.created_at)}</div>
              </div>
            </div>

            <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 10, padding: 12, display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8, fontSize: 12.5 }}>
              <div><strong>Patient:</strong> {printOrder.patient_name}</div>
              <div><strong>MRN:</strong> {printOrder.patient_mrn}</div>
              <div><strong>Age/Gender:</strong> {printOrder.patient_age ? `${printOrder.patient_age}y` : "—"} {printOrder.patient_gender ? `/ ${printOrder.patient_gender}` : ""}</div>
              <div><strong>Ref. Doctor:</strong> {printOrder.doctor_name || "Self"}</div>
            </div>

            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13, border: "1px solid #e2e8f0" }}>
              <thead>
                <tr style={{ background: "#f8fafc", textAlign: "left" }}>
                  <th style={{ padding: "10px 12px", borderBottom: "1px solid #e2e8f0" }}>Test Name</th>
                  <th style={{ padding: "10px 12px", borderBottom: "1px solid #e2e8f0" }}>Result</th>
                  <th style={{ padding: "10px 12px", borderBottom: "1px solid #e2e8f0" }}>Normal Range</th>
                  <th style={{ padding: "10px 12px", borderBottom: "1px solid #e2e8f0" }}>Status Flag</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td style={{ padding: "12px", fontWeight: 700 }}>{printOrder.test_name}</td>
                  <td style={{ padding: "12px", fontWeight: 800 }}>{printOrder.result_value || "Pending"}</td>
                  <td style={{ padding: "12px", color: "#475569" }}>{printOrder.normal_range || "—"} {printOrder.unit || ""}</td>
                  <td style={{ padding: "12px", fontWeight: 800, textTransform: "uppercase" }}>{printOrder.result_flag_label}</td>
                </tr>
              </tbody>
            </table>

            {printOrder.technician_notes && (
              <div style={{ fontSize: 13 }}>
                <strong>Pathologist / Technician Notes:</strong> {printOrder.technician_notes}
              </div>
            )}

            <div style={{ display: "flex", justifyContent: "space-between", borderTop: "1px solid #e2e8f0", paddingTop: 14, marginTop: 12, fontSize: 12 }}>
              <div style={{ color: "#64748b" }}>Electronically verified diagnostic report.</div>
              <div style={{ borderTop: "1px solid #334155", paddingTop: 4, minWidth: 180, textAlign: "center", fontWeight: 700 }}>
                Lab Pathologist / Technologist
              </div>
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
}
