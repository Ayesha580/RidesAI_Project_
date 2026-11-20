import { useCallback, useEffect, useState } from "react";
import OwnerLayout from "../owner/components/OwnerLayout";
import StaffLayout from "../staff/components/StaffLayout";
import { useAuth } from "../context/AuthContext";
import { pharmacyApi, operationsApi } from "../api/operationsApi";
import { errorText } from "../api/axiosClient";

const css = `
.batch-container {
  display: flex;
  flex-direction: column;
  gap: 18px;
  width: 100%;
}

.batch-kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 14px;
}

.batch-kpi-card {
  background: #ffffff;
  border: 1px solid #e8e3ec;
  border-radius: 14px;
  padding: 16px 18px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.02);
}

.batch-kpi-label {
  font-size: 12.5px;
  color: #6b7280;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.batch-kpi-val {
  font-size: 26px;
  font-weight: 800;
  margin-top: 4px;
  color: #1e1b24;
}

.batch-panel {
  background: #ffffff;
  border: 1px solid #e8e3ec;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 2px 10px rgba(0,0,0,0.03);
}

.batch-toolbar {
  padding: 16px 20px;
  border-bottom: 1px solid #f0ebf3;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.batch-search-input {
  padding: 9px 14px;
  background: #f8f6fa;
  border: 1px solid #e4dfe9;
  border-radius: 10px;
  font-size: 13.5px;
  outline: none;
  min-width: 260px;
}

.batch-search-input:focus {
  border-color: #ff77ff;
  background: #ffffff;
}

.batch-filter-tabs {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.batch-filter-btn {
  padding: 6px 14px;
  border-radius: 20px;
  border: 1px solid #e4dfe9;
  background: #ffffff;
  font-size: 13px;
  font-weight: 600;
  color: #6b7280;
  cursor: pointer;
  transition: all 0.2s ease;
}

.batch-filter-btn.active {
  background: #ff77ff;
  border-color: #ff77ff;
  color: #ffffff;
}

.batch-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  font-size: 13.5px;
}

.batch-table th {
  background: #faf8fb;
  padding: 12px 16px;
  font-size: 12px;
  font-weight: 700;
  color: #6b7280;
  border-bottom: 1px solid #eee9f2;
}

.batch-table td {
  padding: 14px 16px;
  border-bottom: 1px solid #f3eff6;
  color: #374151;
  vertical-align: middle;
}

.batch-badge {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 11.5px;
  font-weight: 700;
  text-transform: capitalize;
}

.batch-badge-safe { background: #dcfce7; color: #15803d; }
.batch-badge-expiring_soon { background: #fef3c7; color: #b45309; }
.batch-badge-expired { background: #fee2e2; color: #b91c1c; }

.batch-btn {
  padding: 7px 14px;
  border-radius: 8px;
  font-size: 12.5px;
  font-weight: 700;
  cursor: pointer;
  border: none;
  transition: all 0.2s ease;
}

.batch-btn-primary {
  background: #ff77ff;
  color: #ffffff;
}
.batch-btn-primary:hover {
  background: #f060f0;
}

.batch-btn-ghost {
  background: transparent;
  color: #4b5563;
  border: 1px solid #d1d5db;
}
.batch-btn-ghost:hover {
  background: #f3f4f6;
}

.batch-modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.batch-modal-box {
  background: #ffffff;
  border-radius: 16px;
  padding: 24px;
  max-width: 520px;
  width: 90%;
  box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1);
}
`;

export default function PharmacyBatches({ staff = false }) {
  const { user } = useAuth();
  const [batches, setBatches] = useState([]);
  const [summary, setSummary] = useState({ total_batches: 0, expiring_soon_count: 0, expired_count: 0, low_stock_count: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [showAddModal, setShowAddModal] = useState(false);
  const [catalogItems, setCatalogItems] = useState([]);

  const [form, setForm] = useState({
    item_id: "",
    batch_number: "",
    expiry_date: "",
    quantity: "50",
    supplier_name: "",
  });

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError("");
      const params = {};
      if (search.trim()) params.search = search.trim();
      if (statusFilter) params.status = statusFilter;
      const res = await pharmacyApi.getBatches(params);
      setBatches(res.data.results || []);
      setSummary(res.data.summary || {});
    } catch (e) {
      setError(errorText(e));
    } finally {
      setLoading(false);
    }
  }, [search, statusFilter]);

  useEffect(() => {
    loadData();
    operationsApi.orderCatalog().then(({ data }) => setCatalogItems(data || [])).catch(() => {});
  }, [loadData]);

  const handleAddBatch = async (e) => {
    e.preventDefault();
    try {
      await pharmacyApi.createBatch({
        item_id: form.item_id,
        batch_number: form.batch_number.trim(),
        expiry_date: form.expiry_date,
        quantity: Number(form.quantity),
        supplier_name: form.supplier_name.trim(),
      });
      setShowAddModal(false);
      setForm({ item_id: "", batch_number: "", expiry_date: "", quantity: "50", supplier_name: "" });
      loadData();
    } catch (err) {
      alert("Failed to save batch: " + errorText(err));
    }
  };

  const handleDeleteBatch = async (batchId) => {
    if (!window.confirm("Are you sure you want to delete this medicine batch?")) return;
    try {
      await pharmacyApi.deleteBatch(batchId);
      loadData();
    } catch (err) {
      alert("Failed to delete batch: " + errorText(err));
    }
  };

  const content = (
    <div className="batch-container">
      <style>{css}</style>

      {error && (
        <div style={{ background: "#fee2e2", color: "#991b1b", padding: "12px 18px", borderRadius: 10, fontSize: 13.5 }}>
          {error}
        </div>
      )}

      {/* KPI Stats */}
      <div className="batch-kpi-grid">
        <div className="batch-kpi-card" style={{ borderLeft: "4px solid #3b82f6" }}>
          <div className="batch-kpi-label">Total Batches</div>
          <div className="batch-kpi-val" style={{ color: "#1e40af" }}>{summary.total_batches || 0}</div>
        </div>
        <div className="batch-kpi-card" style={{ borderLeft: "4px solid #f59e0b" }}>
          <div className="batch-kpi-label">Expiring Soon (≤30 Days)</div>
          <div className="batch-kpi-val" style={{ color: "#d97706" }}>{summary.expiring_soon_count || 0}</div>
        </div>
        <div className="batch-kpi-card" style={{ borderLeft: "4px solid #ef4444" }}>
          <div className="batch-kpi-label">Expired Batches</div>
          <div className="batch-kpi-val" style={{ color: "#dc2626" }}>{summary.expired_count || 0}</div>
        </div>
        <div className="batch-kpi-card" style={{ borderLeft: "4px solid #8b5cf6" }}>
          <div className="batch-kpi-label">Low Stock (≤10 Units)</div>
          <div className="batch-kpi-val" style={{ color: "#6d28d9" }}>{summary.low_stock_count || 0}</div>
        </div>
      </div>

      {/* Main Panel */}
      <div className="batch-panel">
        <div className="batch-toolbar">
          <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
            <input
              className="batch-search-input"
              placeholder="Search batch #, medicine, supplier..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <div className="batch-filter-tabs">
              {["", "expiring_soon", "expired", "safe"].map((st) => (
                <button
                  key={st}
                  className={`batch-filter-btn ${statusFilter === st ? "active" : ""}`}
                  onClick={() => setStatusFilter(st)}
                >
                  {st === "" ? "All Batches" : st.replace("_", " ").toUpperCase()}
                </button>
              ))}
            </div>
          </div>
          <button
            className="batch-btn batch-btn-primary"
            onClick={() => setShowAddModal(true)}
          >
            + Add Medicine Batch
          </button>
        </div>

        {loading ? (
          <div style={{ padding: 40, textAlign: "center", color: "#6b7280" }}>Loading medicine batches...</div>
        ) : batches.length === 0 ? (
          <div style={{ padding: 60, textAlign: "center", color: "#9ca3af" }}>
            <span style={{ fontSize: 36 }}>💊</span>
            <h3 style={{ marginTop: 12, color: "#4b5563" }}>No Batches Recorded</h3>
            <p style={{ fontSize: 13.5 }}>Add medicine batches with manufacturing numbers and expiry dates to track your stock.</p>
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="batch-table">
              <thead>
                <tr>
                  <th>Batch Number</th>
                  <th>Medicine</th>
                  <th>Expiry Date</th>
                  <th>Status</th>
                  <th>Quantity</th>
                  <th>Supplier</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {batches.map((b) => (
                  <tr key={b.id}>
                    <td>
                      <strong style={{ color: "#1e1b24" }}>{b.batch_number}</strong>
                    </td>
                    <td>
                      <div><strong>{b.item_name}</strong></div>
                      {b.generic_name && (
                        <div style={{ fontSize: 12, color: "#6b7280" }}>Generic: {b.generic_name}</div>
                      )}
                      {b.requires_prescription && (
                        <span style={{ fontSize: 11, background: "#fdf2f8", color: "#db2777", padding: "2px 6px", borderRadius: 4, fontWeight: 700 }}>
                          Rx Required
                        </span>
                      )}
                    </td>
                    <td>
                      <div style={{ fontWeight: 600 }}>{b.expiry_date}</div>
                    </td>
                    <td>
                      <span className={`batch-badge batch-badge-${b.status}`}>
                        {b.status === "expiring_soon" ? "Expiring Soon" : b.status}
                      </span>
                    </td>
                    <td>
                      <strong style={{ color: b.quantity <= 10 ? "#dc2626" : "#111827" }}>
                        {b.quantity} units
                      </strong>
                    </td>
                    <td style={{ color: "#6b7280" }}>
                      {b.supplier_name || "Direct / Local"}
                    </td>
                    <td>
                      <button
                        className="batch-btn batch-btn-ghost"
                        style={{ color: "#dc2626", borderColor: "#fecaca" }}
                        onClick={() => handleDeleteBatch(b.id)}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Add Batch Modal */}
      {showAddModal && (
        <div className="batch-modal-backdrop">
          <div className="batch-modal-box">
            <h3 style={{ margin: "0 0 16px", fontSize: 18, color: "#111827" }}>
              Add Medicine Batch
            </h3>
            <form onSubmit={handleAddBatch} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <div>
                <label style={{ display: "block", fontSize: 12.5, fontWeight: 700, color: "#374151", marginBottom: 4 }}>
                  Select Medicine *
                </label>
                <select
                  required
                  style={{ width: "100%", padding: 9, borderRadius: 8, border: "1px solid #d1d5db", fontSize: 13.5 }}
                  value={form.item_id}
                  onChange={(e) => setForm({ ...form, item_id: e.target.value })}
                >
                  <option value="">-- Choose Medicine --</option>
                  {catalogItems.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name} {item.unit ? `(${item.unit})` : ""}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ display: "block", fontSize: 12.5, fontWeight: 700, color: "#374151", marginBottom: 4 }}>
                  Batch Number *
                </label>
                <input
                  required
                  placeholder="e.g. BATCH-2026-X01"
                  style={{ width: "100%", padding: 9, borderRadius: 8, border: "1px solid #d1d5db", fontSize: 13.5 }}
                  value={form.batch_number}
                  onChange={(e) => setForm({ ...form, batch_number: e.target.value })}
                />
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div>
                  <label style={{ display: "block", fontSize: 12.5, fontWeight: 700, color: "#374151", marginBottom: 4 }}>
                    Expiry Date *
                  </label>
                  <input
                    required
                    type="date"
                    style={{ width: "100%", padding: 9, borderRadius: 8, border: "1px solid #d1d5db", fontSize: 13.5 }}
                    value={form.expiry_date}
                    onChange={(e) => setForm({ ...form, expiry_date: e.target.value })}
                  />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: 12.5, fontWeight: 700, color: "#374151", marginBottom: 4 }}>
                    Quantity (Units) *
                  </label>
                  <input
                    required
                    type="number"
                    min="0"
                    style={{ width: "100%", padding: 9, borderRadius: 8, border: "1px solid #d1d5db", fontSize: 13.5 }}
                    value={form.quantity}
                    onChange={(e) => setForm({ ...form, quantity: e.target.value })}
                  />
                </div>
              </div>

              <div>
                <label style={{ display: "block", fontSize: 12.5, fontWeight: 700, color: "#374151", marginBottom: 4 }}>
                  Supplier / Distributor Name
                </label>
                <input
                  placeholder="e.g. Pfizer Pakistan / OBS Healthcare"
                  style={{ width: "100%", padding: 9, borderRadius: 8, border: "1px solid #d1d5db", fontSize: 13.5 }}
                  value={form.supplier_name}
                  onChange={(e) => setForm({ ...form, supplier_name: e.target.value })}
                />
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 12 }}>
                <button
                  type="button"
                  className="batch-btn batch-btn-ghost"
                  onClick={() => setShowAddModal(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="batch-btn batch-btn-primary"
                >
                  Save Batch
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );

  if (staff) {
    return <StaffLayout title="Medicine Expiry Tracking">{content}</StaffLayout>;
  }

  return (
    <OwnerLayout
      title="Medicine Expiry Tracking"
      subtitle={`Monitor medicine batches, expiry alerts, and stock quantities for ${user?.company_name || "your pharmacy"}.`}
    >
      {content}
    </OwnerLayout>
  );
}
