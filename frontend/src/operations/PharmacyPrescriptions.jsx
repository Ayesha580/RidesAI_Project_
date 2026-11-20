import { useCallback, useEffect, useState } from "react";
import OwnerLayout from "../owner/components/OwnerLayout";
import StaffLayout from "../staff/components/StaffLayout";
import { useAuth } from "../context/AuthContext";
import { pharmacyApi } from "../api/operationsApi";
import { errorText } from "../api/axiosClient";

const css = `
.rx-container {
  display: flex;
  flex-direction: column;
  gap: 18px;
  width: 100%;
}

.rx-kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 14px;
}

.rx-kpi-card {
  background: #ffffff;
  border: 1px solid #e8e3ec;
  border-radius: 14px;
  padding: 16px 18px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.02);
}

.rx-kpi-label {
  font-size: 12.5px;
  color: #6b7280;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.rx-kpi-val {
  font-size: 26px;
  font-weight: 800;
  margin-top: 4px;
  color: #1e1b24;
}

.rx-panel {
  background: #ffffff;
  border: 1px solid #e8e3ec;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 2px 10px rgba(0,0,0,0.03);
}

.rx-toolbar {
  padding: 16px 20px;
  border-bottom: 1px solid #f0ebf3;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.rx-search-input {
  padding: 9px 14px;
  background: #f8f6fa;
  border: 1px solid #e4dfe9;
  border-radius: 10px;
  font-size: 13.5px;
  outline: none;
  min-width: 260px;
}

.rx-search-input:focus {
  border-color: #ff77ff;
  background: #ffffff;
}

.rx-filter-tabs {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.rx-filter-btn {
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

.rx-filter-btn.active {
  background: #ff77ff;
  border-color: #ff77ff;
  color: #ffffff;
}

.rx-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  font-size: 13.5px;
}

.rx-table th {
  background: #faf8fb;
  padding: 12px 16px;
  font-size: 12px;
  font-weight: 700;
  color: #6b7280;
  border-bottom: 1px solid #eee9f2;
}

.rx-table td {
  padding: 14px 16px;
  border-bottom: 1px solid #f3eff6;
  color: #374151;
  vertical-align: middle;
}

.rx-badge {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 11.5px;
  font-weight: 700;
  text-transform: capitalize;
}

.rx-badge-pending { background: #fef3c7; color: #b45309; }
.rx-badge-approved { background: #dcfce7; color: #15803d; }
.rx-badge-rejected { background: #fee2e2; color: #b91c1c; }
.rx-badge-dispensed { background: #e0e7ff; color: #4338ca; }

.rx-btn {
  padding: 7px 14px;
  border-radius: 8px;
  font-size: 12.5px;
  font-weight: 700;
  cursor: pointer;
  border: none;
  transition: all 0.2s ease;
}

.rx-btn-primary {
  background: #ff77ff;
  color: #ffffff;
}
.rx-btn-primary:hover {
  background: #f060f0;
}

.rx-btn-danger {
  background: #fee2e2;
  color: #b91c1c;
}
.rx-btn-danger:hover {
  background: #fecaca;
}

.rx-btn-dispense {
  background: #10b981;
  color: #ffffff;
}
.rx-btn-dispense:hover {
  background: #059669;
}

.rx-modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.rx-modal-box {
  background: #ffffff;
  border-radius: 16px;
  padding: 24px;
  max-width: 480px;
  width: 90%;
  box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1);
}
`;

export default function PharmacyPrescriptions({ staff = false }) {
  const { user } = useAuth();
  const [prescriptions, setPrescriptions] = useState([]);
  const [summary, setSummary] = useState({ total: 0, pending: 0, approved: 0, rejected: 0, dispensed: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [rejectModalRx, setRejectModalRx] = useState(null);
  const [rejectReason, setRejectReason] = useState("");
  const [toast, setToast] = useState("");

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError("");
      const params = {};
      if (search.trim()) params.search = search.trim();
      if (statusFilter) params.status = statusFilter;
      const res = await pharmacyApi.getPrescriptions(params);
      setPrescriptions(res.data.results || []);
      setSummary(res.data.summary || {});
    } catch (e) {
      setError(errorText(e));
    } finally {
      setLoading(false);
    }
  }, [search, statusFilter]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const showToast = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(""), 4000);
  };

  const handleUpdateStatus = async (rxId, newStatus, reason = "") => {
    try {
      await pharmacyApi.updatePrescriptionStatus(rxId, {
        status: newStatus,
        pharmacist_notes: reason,
        reason: reason,
      });
      showToast(`Prescription status updated to ${newStatus}. WhatsApp notification dispatched.`);
      if (rejectModalRx) {
        setRejectModalRx(null);
        setRejectReason("");
      }
      loadData();
    } catch (e) {
      alert("Failed to update status: " + errorText(e));
    }
  };

  const content = (
    <div className="rx-container">
      <style>{css}</style>

      {toast && (
        <div style={{ background: "#dcfce7", color: "#166534", padding: "12px 18px", borderRadius: 10, fontSize: 13.5, fontWeight: 600 }}>
          💬 {toast}
        </div>
      )}

      {error && (
        <div style={{ background: "#fee2e2", color: "#991b1b", padding: "12px 18px", borderRadius: 10, fontSize: 13.5 }}>
          {error}
        </div>
      )}

      {/* KPI Stats */}
      <div className="rx-kpi-grid">
        <div className="rx-kpi-card" style={{ borderLeft: "4px solid #f59e0b" }}>
          <div className="rx-kpi-label">Pending Review</div>
          <div className="rx-kpi-val" style={{ color: "#d97706" }}>{summary.pending || 0}</div>
        </div>
        <div className="rx-kpi-card" style={{ borderLeft: "4px solid #10b981" }}>
          <div className="rx-kpi-label">Approved</div>
          <div className="rx-kpi-val" style={{ color: "#059669" }}>{summary.approved || 0}</div>
        </div>
        <div className="rx-kpi-card" style={{ borderLeft: "4px solid #6366f1" }}>
          <div className="rx-kpi-label">Dispensed</div>
          <div className="rx-kpi-val" style={{ color: "#4f46e5" }}>{summary.dispensed || 0}</div>
        </div>
        <div className="rx-kpi-card" style={{ borderLeft: "4px solid #ef4444" }}>
          <div className="rx-kpi-label">Rejected</div>
          <div className="rx-kpi-val" style={{ color: "#dc2626" }}>{summary.rejected || 0}</div>
        </div>
      </div>

      {/* Main Panel */}
      <div className="rx-panel">
        <div className="rx-toolbar">
          <input
            className="rx-search-input"
            placeholder="Search by RX#, customer name, phone, medicine..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <div className="rx-filter-tabs">
            {["", "pending", "approved", "dispensed", "rejected"].map((st) => (
              <button
                key={st}
                className={`rx-filter-btn ${statusFilter === st ? "active" : ""}`}
                onClick={() => setStatusFilter(st)}
              >
                {st === "" ? "All Prescriptions" : st.charAt(0).toUpperCase() + st.slice(1)}
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div style={{ padding: 40, textAlign: "center", color: "#6b7280" }}>Loading prescriptions...</div>
        ) : prescriptions.length === 0 ? (
          <div style={{ padding: 60, textAlign: "center", color: "#9ca3af" }}>
            <span style={{ fontSize: 36 }}>📋</span>
            <h3 style={{ marginTop: 12, color: "#4b5563" }}>No Prescriptions Found</h3>
            <p style={{ fontSize: 13.5 }}>Prescription requests submitted via WhatsApp AI or dashboard will appear here.</p>
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="rx-table">
              <thead>
                <tr>
                  <th>Prescription #</th>
                  <th>Customer</th>
                  <th>Requested Medicines</th>
                  <th>Status</th>
                  <th>Date</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {prescriptions.map((rx) => (
                  <tr key={rx.id}>
                    <td>
                      <strong style={{ color: "#1e1b24" }}>{rx.prescription_number}</strong>
                    </td>
                    <td>
                      <div><strong>{rx.customer_name}</strong></div>
                      <div style={{ fontSize: 12, color: "#6b7280" }}>{rx.customer_phone}</div>
                    </td>
                    <td style={{ maxWidth: 280 }}>
                      <div style={{ whiteSpace: "pre-wrap", color: "#1f2937", fontSize: 13 }}>
                        {rx.requested_items_text || "Prescription uploaded as document/photo"}
                      </div>
                      {rx.notes && (
                        <div style={{ fontSize: 12, color: "#6b7280", fontStyle: "italic", marginTop: 4 }}>
                          Notes: {rx.notes}
                        </div>
                      )}
                      {rx.pharmacist_notes && (
                        <div style={{ fontSize: 12, color: "#b91c1c", marginTop: 4 }}>
                          Pharmacist: {rx.pharmacist_notes}
                        </div>
                      )}
                    </td>
                    <td>
                      <span className={`rx-badge rx-badge-${rx.status}`}>
                        {rx.status_display}
                      </span>
                    </td>
                    <td style={{ fontSize: 12, color: "#6b7280", whiteSpace: "nowrap" }}>
                      {rx.formatted_date}
                    </td>
                    <td>
                      <div style={{ display: "flex", gap: 6 }}>
                        {rx.status === "pending" && (
                          <>
                            <button
                              className="rx-btn rx-btn-primary"
                              onClick={() => handleUpdateStatus(rx.id, "approved")}
                            >
                              Approve
                            </button>
                            <button
                              className="rx-btn rx-btn-danger"
                              onClick={() => {
                                setRejectModalRx(rx);
                                setRejectReason("");
                              }}
                            >
                              Reject
                            </button>
                          </>
                        )}
                        {rx.status === "approved" && (
                          <button
                            className="rx-btn rx-btn-dispense"
                            onClick={() => handleUpdateStatus(rx.id, "dispensed")}
                          >
                            Mark Dispensed
                          </button>
                        )}
                        {rx.status === "dispensed" && (
                          <span style={{ fontSize: 12, color: "#10b981", fontWeight: 700 }}>✓ Completed</span>
                        )}
                        {rx.status === "rejected" && (
                          <span style={{ fontSize: 12, color: "#ef4444", fontWeight: 700 }}>✗ Rejected</span>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Reject Reason Modal */}
      {rejectModalRx && (
        <div className="rx-modal-backdrop">
          <div className="rx-modal-box">
            <h3 style={{ margin: "0 0 10px", fontSize: 18, color: "#111827" }}>
              Reject Prescription {rejectModalRx.prescription_number}
            </h3>
            <p style={{ fontSize: 13.5, color: "#4b5563", marginBottom: 14 }}>
              Provide a clear reason for rejecting this prescription. This reason will be automatically sent to the customer on WhatsApp.
            </p>
            <textarea
              style={{ width: "100%", height: 90, padding: 10, borderRadius: 8, border: "1px solid #d1d5db", fontSize: 13.5, marginBottom: 16 }}
              placeholder="e.g. Expired doctor's slip, medicine out of stock, unreadable photo..."
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
            />
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
              <button
                className="rx-btn"
                style={{ background: "#e5e7eb", color: "#374151" }}
                onClick={() => setRejectModalRx(null)}
              >
                Cancel
              </button>
              <button
                className="rx-btn rx-btn-danger"
                disabled={!rejectReason.trim()}
                onClick={() => handleUpdateStatus(rejectModalRx.id, "rejected", rejectReason)}
              >
                Confirm Rejection & Send Alert
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );

  if (staff) {
    return <StaffLayout title="Prescriptions">{content}</StaffLayout>;
  }

  return (
    <OwnerLayout
      title="Prescriptions"
      subtitle={`Review, approve, and dispense customer prescriptions for ${user?.company_name || "your pharmacy"}.`}
    >
      {content}
    </OwnerLayout>
  );
}
