import { useCallback, useEffect, useState } from "react";
import OwnerLayout from "../owner/components/OwnerLayout";
import StaffLayout from "../staff/components/StaffLayout";
import { retailApi } from "../api/operationsApi";
import { errorText } from "../api/axiosClient";

const css = `
.rr-container {
  display: flex;
  flex-direction: column;
  gap: 18px;
  width: 100%;
}
.rr-kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 14px;
}
.rr-kpi-card {
  background: #ffffff;
  border: 1px solid #e8e3ec;
  border-radius: 14px;
  padding: 16px 18px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.02);
}
.rr-kpi-label {
  font-size: 11.5px;
  color: #6b7280;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.rr-kpi-val {
  font-size: 26px;
  font-weight: 800;
  margin-top: 4px;
  color: #1e1b24;
}
.rr-panel {
  background: #ffffff;
  border: 1px solid #e8e3ec;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 2px 10px rgba(0,0,0,0.03);
}
.rr-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 16px 20px;
  border-bottom: 1px solid #f1ebf4;
  flex-wrap: wrap;
}
.rr-tabs {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.rr-tab-btn {
  padding: 8px 14px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid #e2dce6;
  background: #ffffff;
  color: #555;
  transition: all .2s;
}
.rr-tab-btn.active {
  background: #ff77ff;
  color: #ffffff;
  border-color: #ff77ff;
  box-shadow: 0 3px 8px rgba(255,119,255,0.25);
}
.rr-filter-group {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.rr-search-input, .rr-select-input {
  height: 38px;
  padding: 0 14px;
  border: 1px solid #e2dce6;
  border-radius: 10px;
  font-size: 13.5px;
  outline: none;
  background: #ffffff;
  color: #1e1b24;
  transition: border-color .2s;
}
.rr-search-input:focus, .rr-select-input:focus {
  border-color: #ff77ff;
}
.rr-btn-primary {
  height: 38px;
  padding: 0 16px;
  background: #ff77ff;
  color: #ffffff;
  border: none;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  box-shadow: 0 3px 8px rgba(255,119,255,0.22);
  transition: all .2s;
}
.rr-btn-primary:hover {
  background: #f05cf0;
  transform: translateY(-1px);
}
.rr-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
}
.rr-table th {
  background: #faf8fb;
  padding: 12px 16px;
  font-size: 12px;
  font-weight: 700;
  color: #6b7280;
  text-transform: uppercase;
  border-bottom: 1px solid #e8e3ec;
}
.rr-table td {
  padding: 14px 16px;
  font-size: 13px;
  color: #374151;
  border-bottom: 1px solid #f1ebf4;
  vertical-align: top;
}
.rr-table tr:hover {
  background: #fdfcfe;
}
.rr-badge {
  display: inline-block;
  padding: 3px 9px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.4px;
}
.rr-badge-pending { background: #fef3c7; color: #b45309; }
.rr-badge-approved { background: #fdf2f8; color: #db2777; }
.rr-badge-completed { background: #dcfce7; color: #15803d; }
.rr-badge-rejected { background: #fee2e2; color: #b91c1c; }
.rr-type-badge {
  display: inline-block;
  padding: 2px 7px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  background: #f3f4f6;
  color: #4b5563;
  margin-left: 6px;
}
.rr-swap-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: rgba(255, 119, 255, 0.12);
  color: #c026d3;
  border: 1px solid rgba(255, 119, 255, 0.35);
  border-radius: 20px;
  padding: 2px 8px;
  font-size: 11px;
  font-weight: 700;
  margin-top: 4px;
}
.rr-actions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.rr-btn-action {
  padding: 5px 10px;
  border-radius: 7px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all .2s;
}
.rr-btn-approve {
  background: #fdf2f8;
  border-color: #fbcfe8;
  color: #db2777;
}
.rr-btn-approve:hover {
  background: #fce7f3;
}
.rr-btn-complete {
  background: #dcfce7;
  border-color: #bbf7d0;
  color: #15803d;
}
.rr-btn-complete:hover {
  background: #bbf7d0;
}
.rr-btn-reject {
  background: #fee2e2;
  border-color: #fecaca;
  color: #b91c1c;
}
.rr-btn-reject:hover {
  background: #fecaca;
}
.rr-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 16px;
}
.rr-modal {
  background: #ffffff;
  border-radius: 16px;
  width: 100%;
  max-width: 500px;
  padding: 24px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.12);
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.rr-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.rr-modal-title {
  font-size: 17px;
  font-weight: 800;
  color: #1e1b24;
}
.rr-modal-close {
  background: none;
  border: none;
  font-size: 20px;
  color: #9ca3af;
  cursor: pointer;
}
.rr-form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.rr-label {
  font-size: 12.5px;
  font-weight: 700;
  color: #374151;
}
.rr-input, .rr-textarea, .rr-select {
  padding: 9px 12px;
  border: 1px solid #e2dce6;
  border-radius: 9px;
  font-size: 13.5px;
  outline: none;
  background: #ffffff;
  color: #1e1b24;
  font-family: inherit;
}
.rr-input:focus, .rr-textarea:focus, .rr-select:focus {
  border-color: #ff77ff;
}
.rr-modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 8px;
}
.rr-btn-cancel {
  padding: 9px 16px;
  border: 1px solid #e2dce6;
  background: #ffffff;
  color: #4b5563;
  border-radius: 9px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.rr-toast {
  background: #dcfce7;
  border: 1px solid #86efac;
  color: #15803d;
  padding: 12px 18px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 12px;
}
.rr-empty {
  padding: 40px;
  text-align: center;
  color: #888;
}
`;

export default function RetailReturns({ staff = false }) {
  const [requests, setRequests] = useState([]);
  const [kpis, setKpis] = useState({
    total: 0,
    pending: 0,
    approved: 0,
    rejected: 0,
    completed: 0,
  });
  const [selectedStatus, setSelectedStatus] = useState("all");
  const [selectedType, setSelectedType] = useState("all");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [toastMsg, setToastMsg] = useState("");
  const [errorMsg, setErrorMsg] = useState("");

  // Create Modal
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [formData, setFormData] = useState({
    request_type: "return",
    customer_phone: "",
    customer_name: "",
    order_number: "",
    item_summary: "",
    reason: "",
    staff_notes: "",
  });
  const [createLoading, setCreateLoading] = useState(false);

  // Status Modal (Approve / Reject)
  const [statusModal, setStatusModal] = useState({
    isOpen: false,
    req: null,
    targetStatus: "",
    staffNotes: "",
    loading: false,
  });

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setErrorMsg("");
      const params = {};
      if (selectedStatus !== "all") params.status = selectedStatus;
      if (selectedType !== "all") params.request_type = selectedType;
      if (search.trim()) params.search = search.trim();

      const res = await retailApi.getReturns(params);
      setRequests(res.data?.results || []);
      if (res.data?.kpis) {
        setKpis(res.data.kpis);
      }
    } catch (err) {
      setErrorMsg(errorText(err) || "Failed to load returns and exchanges.");
    } finally {
      setLoading(false);
    }
  }, [selectedStatus, selectedType, search]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleCreateSubmit = async (e) => {
    e.preventDefault();
    if (!formData.customer_phone.trim() || !formData.reason.trim()) {
      alert("Customer Phone and Reason are required.");
      return;
    }
    try {
      setCreateLoading(true);
      const res = await retailApi.createReturn(formData);
      setShowCreateModal(false);
      setFormData({
        request_type: "return",
        customer_phone: "",
        customer_name: "",
        order_number: "",
        item_summary: "",
        reason: "",
        staff_notes: "",
      });
      setToastMsg(`Request ${res.data?.return_request?.return_number} created successfully.`);
      setTimeout(() => setToastMsg(""), 4500);
      loadData();
    } catch (err) {
      alert(errorText(err) || "Failed to create request.");
    } finally {
      setCreateLoading(false);
    }
  };

  const openStatusModal = (req, targetStatus) => {
    setStatusModal({
      isOpen: true,
      req,
      targetStatus,
      staffNotes: req.staff_notes || "",
      loading: false,
    });
  };

  const handleStatusSubmit = async () => {
    const { req, targetStatus, staffNotes } = statusModal;
    if (!req) return;
    try {
      setStatusModal((prev) => ({ ...prev, loading: true }));
      await retailApi.updateReturnStatus(req.id, {
        status: targetStatus,
        staff_notes: staffNotes,
      });
      setStatusModal({ isOpen: false, req: null, targetStatus: "", staffNotes: "", loading: false });
      setToastMsg(`Request ${req.return_number} marked as ${targetStatus}. WhatsApp notification sent!`);
      setTimeout(() => setToastMsg(""), 4500);
      loadData();
    } catch (err) {
      alert(errorText(err) || "Failed to update return status.");
      setStatusModal((prev) => ({ ...prev, loading: false }));
    }
  };

  const content = (
    <div className="rr-container">
      <style>{css}</style>

      {toastMsg && <div className="rr-toast">{toastMsg}</div>}
      {errorMsg && <div className="rr-toast" style={{ background: "#fee2e2", borderColor: "#fca5a5", color: "#b91c1c" }}>{errorMsg}</div>}

      {/* KPI Cards */}
      <div className="rr-kpi-grid">
        <div className="rr-kpi-card">
          <div className="rr-kpi-label">Total Requests</div>
          <div className="rr-kpi-val">{kpis.total || 0}</div>
        </div>
        <div className="rr-kpi-card" style={{ borderLeft: "4px solid #b45309" }}>
          <div className="rr-kpi-label">Pending Review</div>
          <div className="rr-kpi-val" style={{ color: "#b45309" }}>{kpis.pending || 0}</div>
        </div>
        <div className="rr-kpi-card" style={{ borderLeft: "4px solid #db2777" }}>
          <div className="rr-kpi-label">Approved</div>
          <div className="rr-kpi-val" style={{ color: "#db2777" }}>{kpis.approved || 0}</div>
        </div>
        <div className="rr-kpi-card" style={{ borderLeft: "4px solid #15803d" }}>
          <div className="rr-kpi-label">Completed</div>
          <div className="rr-kpi-val" style={{ color: "#15803d" }}>{kpis.completed || 0}</div>
        </div>
        <div className="rr-kpi-card" style={{ borderLeft: "4px solid #b91c1c" }}>
          <div className="rr-kpi-label">Rejected</div>
          <div className="rr-kpi-val" style={{ color: "#b91c1c" }}>{kpis.rejected || 0}</div>
        </div>
      </div>

      {/* Main Panel */}
      <div className="rr-panel">
        <div className="rr-toolbar">
          <div className="rr-tabs">
            {[
              { id: "all", label: "All Requests" },
              { id: "pending", label: "Pending" },
              { id: "approved", label: "Approved" },
              { id: "completed", label: "Completed" },
              { id: "rejected", label: "Rejected" },
            ].map((tab) => (
              <button
                key={tab.id}
                className={`rr-tab-btn ${selectedStatus === tab.id ? "active" : ""}`}
                onClick={() => setSelectedStatus(tab.id)}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div className="rr-filter-group">
            <select
              className="rr-select-input"
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value)}
            >
              <option value="all">All Types</option>
              <option value="return">Returns Only</option>
              <option value="exchange">Exchanges Only</option>
            </select>

            <input
              type="text"
              className="rr-search-input"
              placeholder="Search return #, order #, customer..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />

            <button className="rr-btn-primary" onClick={() => setShowCreateModal(true)}>
              + New Request
            </button>
          </div>
        </div>

        {loading && requests.length === 0 ? (
          <div className="rr-empty">Loading return & exchange requests...</div>
        ) : requests.length === 0 ? (
          <div className="rr-empty">No return or exchange requests found.</div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="rr-table">
              <thead>
                <tr>
                  <th>Request #</th>
                  <th>Order Ref</th>
                  <th>Customer</th>
                  <th>Items & Reason</th>
                  <th>Status</th>
                  <th>Staff Notes</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {requests.map((r) => (
                  <tr key={r.id}>
                    <td>
                      <strong>{r.return_number}</strong>
                      <span className="rr-type-badge">{r.request_type}</span>
                      {r.replacement_order_number && (
                        <div>
                          <span className="rr-swap-badge" title="Doorstep Replacement Order">
                            🔄 Replacement: #{r.replacement_order_number}
                          </span>
                        </div>
                      )}
                      <div style={{ fontSize: "11px", color: "#888", marginTop: "2px" }}>
                        {new Date(r.created_at).toLocaleDateString()} {new Date(r.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      </div>
                    </td>
                    <td>
                      {r.order_number ? (
                        <span style={{ fontWeight: "600", color: "#1e1b24" }}>{r.order_number}</span>
                      ) : (
                        <span style={{ color: "#9ca3af", fontStyle: "italic" }}>None linked</span>
                      )}
                    </td>
                    <td>
                      <div><strong>{r.customer_name || "Valued Customer"}</strong></div>
                      <div style={{ color: "#6b7280", fontSize: "12px" }}>{r.customer_phone}</div>
                    </td>
                    <td>
                      {r.item_summary && (
                        <div style={{ fontWeight: "600", color: "#1e1b24", marginBottom: "2px" }}>
                          📦 {r.item_summary}
                        </div>
                      )}
                      <div style={{ color: "#4b5563", fontSize: "12.5px" }}>
                        {r.reason}
                      </div>
                    </td>
                    <td>
                      <span className={`rr-badge rr-badge-${r.status}`}>
                        {r.status}
                      </span>
                    </td>
                    <td>
                      <span style={{ color: "#4b5563", fontSize: "12.5px" }}>
                        {r.staff_notes || "—"}
                      </span>
                    </td>
                    <td>
                      <div className="rr-actions">
                        {r.status === "pending" && (
                          <>
                            <button
                              className="rr-btn-action rr-btn-approve"
                              onClick={() => openStatusModal(r, "approved")}
                            >
                              ✓ Approve
                            </button>
                            <button
                              className="rr-btn-action rr-btn-reject"
                              onClick={() => openStatusModal(r, "rejected")}
                            >
                              ✕ Reject
                            </button>
                          </>
                        )}
                        {r.status === "approved" && (
                          <button
                            className="rr-btn-action rr-btn-complete"
                            onClick={() => openStatusModal(r, "completed")}
                          >
                            🎉 Mark Completed
                          </button>
                        )}
                        {(r.status === "completed" || r.status === "rejected") && (
                          <span style={{ fontSize: "11.5px", color: "#9ca3af" }}>Closed</span>
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

      {/* Create Modal */}
      {showCreateModal && (
        <div className="rr-modal-overlay">
          <div className="rr-modal">
            <div className="rr-modal-header">
              <div className="rr-modal-title">New Return / Exchange Request</div>
              <button className="rr-modal-close" onClick={() => setShowCreateModal(false)}>✕</button>
            </div>
            <form onSubmit={handleCreateSubmit} style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              <div className="rr-form-group">
                <label className="rr-label">Request Type</label>
                <select
                  className="rr-select"
                  value={formData.request_type}
                  onChange={(e) => setFormData({ ...formData, request_type: e.target.value })}
                >
                  <option value="return">Return (Refund / Store Credit)</option>
                  <option value="exchange">Exchange (Replacement Item)</option>
                </select>
              </div>

              <div className="rr-form-group">
                <label className="rr-label">Customer Phone *</label>
                <input
                  type="text"
                  className="rr-input"
                  placeholder="+923001234567"
                  required
                  value={formData.customer_phone}
                  onChange={(e) => setFormData({ ...formData, customer_phone: e.target.value })}
                />
              </div>

              <div className="rr-form-group">
                <label className="rr-label">Customer Name</label>
                <input
                  type="text"
                  className="rr-input"
                  placeholder="e.g. Bilal Ahmed"
                  value={formData.customer_name}
                  onChange={(e) => setFormData({ ...formData, customer_name: e.target.value })}
                />
              </div>

              <div className="rr-form-group">
                <label className="rr-label">Original Order Number (Optional)</label>
                <input
                  type="text"
                  className="rr-input"
                  placeholder="e.g. RA-261120-XXXX"
                  value={formData.order_number}
                  onChange={(e) => setFormData({ ...formData, order_number: e.target.value })}
                />
              </div>

              <div className="rr-form-group">
                <label className="rr-label">Items Summary</label>
                <input
                  type="text"
                  className="rr-input"
                  placeholder="e.g. 1x Wireless Earbuds Pro (Black)"
                  value={formData.item_summary}
                  onChange={(e) => setFormData({ ...formData, item_summary: e.target.value })}
                />
              </div>

              <div className="rr-form-group">
                <label className="rr-label">Reason *</label>
                <textarea
                  className="rr-textarea"
                  rows="2"
                  placeholder="Reason for return/exchange (e.g. defective audio, wrong color)..."
                  required
                  value={formData.reason}
                  onChange={(e) => setFormData({ ...formData, reason: e.target.value })}
                />
              </div>

              <div className="rr-form-group">
                <label className="rr-label">Internal Staff Notes</label>
                <textarea
                  className="rr-textarea"
                  rows="2"
                  placeholder="Notes for inspection or warehouse team..."
                  value={formData.staff_notes}
                  onChange={(e) => setFormData({ ...formData, staff_notes: e.target.value })}
                />
              </div>

              <div className="rr-modal-actions">
                <button type="button" className="rr-btn-cancel" onClick={() => setShowCreateModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="rr-btn-primary" disabled={createLoading}>
                  {createLoading ? "Creating..." : "Submit Request"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Status Modal */}
      {statusModal.isOpen && (
        <div className="rr-modal-overlay">
          <div className="rr-modal">
            <div className="rr-modal-header">
              <div className="rr-modal-title">
                {statusModal.targetStatus === "approved"
                  ? "Approve Request"
                  : statusModal.targetStatus === "rejected"
                  ? "Reject Request"
                  : "Mark Completed"}
              </div>
              <button
                className="rr-modal-close"
                onClick={() => setStatusModal({ isOpen: false, req: null, targetStatus: "", staffNotes: "", loading: false })}
              >
                ✕
              </button>
            </div>

            <p style={{ fontSize: "13px", color: "#4b5563", margin: 0 }}>
              Updating <strong>{statusModal.req?.return_number}</strong> for <strong>{statusModal.req?.customer_name}</strong> to <strong>{statusModal.targetStatus}</strong>.
              A WhatsApp notification will be automatically sent to {statusModal.req?.customer_phone}.
            </p>

            <div className="rr-form-group">
              <label className="rr-label">
                {statusModal.targetStatus === "rejected" ? "Rejection Reason (Sent to Customer) *" : "Staff Notes (Optional)"}
              </label>
              <textarea
                className="rr-textarea"
                rows="3"
                placeholder={statusModal.targetStatus === "rejected" ? "Explain why this request cannot be approved..." : "Additional notes or instructions..."}
                value={statusModal.staffNotes}
                onChange={(e) => setStatusModal((prev) => ({ ...prev, staffNotes: e.target.value }))}
              />
            </div>

            <div className="rr-modal-actions">
              <button
                type="button"
                className="rr-btn-cancel"
                onClick={() => setStatusModal({ isOpen: false, req: null, targetStatus: "", staffNotes: "", loading: false })}
              >
                Cancel
              </button>
              <button
                type="button"
                className="rr-btn-primary"
                disabled={statusModal.loading}
                onClick={handleStatusSubmit}
              >
                {statusModal.loading ? "Updating..." : `Confirm ${statusModal.targetStatus}`}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );

  return staff ? (
    <StaffLayout title="Returns & Exchanges">{content}</StaffLayout>
  ) : (
    <OwnerLayout title="Returns & Exchanges">{content}</OwnerLayout>
  );
}
