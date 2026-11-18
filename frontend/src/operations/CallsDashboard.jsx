import { useCallback, useEffect, useState } from "react";
import OwnerLayout from "../owner/components/OwnerLayout";
import { dashboardApi } from "../api/operationsApi";
import { errorText } from "../api/axiosClient";
import { useAuth } from "../context/AuthContext";

const css = `
.cd-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
  width: 100%;
}

/* Informational Banner */
.cd-banner {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 18px;
  background: #fdf4ff;
  border: 1px solid #f0abfc;
  border-radius: 14px;
  color: #86198f;
  font-size: 13.5px;
}
.cd-banner-icon {
  font-size: 22px;
  flex-shrink: 0;
}
.cd-banner-text strong {
  display: block;
  font-weight: 700;
  margin-bottom: 2px;
}

/* KPI Summary Cards */
.cd-kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
}
.cd-kpi-card {
  background: #ffffff;
  border: 1px solid #e8e3ec;
  border-radius: 16px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.02);
  position: relative;
  overflow: hidden;
}
.cd-kpi-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #797182;
  font-size: 12px;
  font-weight: 750;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.cd-kpi-value {
  font-size: 30px;
  font-weight: 800;
  color: #302b38;
  letter-spacing: -0.5px;
  display: flex;
  align-items: center;
  gap: 10px;
}
.cd-kpi-sub {
  font-size: 11.5px;
  color: #98909e;
}
.cd-pulse-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #22c55e;
  box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.7);
  animation: cdPulse 1.8s infinite;
  display: inline-block;
}
@keyframes cdPulse {
  0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.7); }
  70% { transform: scale(1); box-shadow: 0 0 0 8px rgba(34, 197, 94, 0); }
  100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }
}

/* Panel & Controls */
.cd-panel {
  background: #ffffff;
  border: 1px solid #e8e3ec;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 2px 10px rgba(0,0,0,0.03);
}

.cd-toolbar {
  padding: 16px 20px;
  border-bottom: 1px solid #f0ebf3;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
  background: #ffffff;
}

.cd-filters-group {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  flex: 1;
}

.cd-search-box {
  position: relative;
  display: flex;
  align-items: center;
  min-width: 240px;
  max-width: 320px;
  flex: 1;
}
.cd-search-input {
  width: 100%;
  padding: 9px 12px 9px 34px;
  background: #f8f6fa;
  border: 1px solid #e4dfe9;
  border-radius: 10px;
  font-size: 13.5px;
  outline: none;
  transition: border-color 0.2s ease;
}
.cd-search-input:focus {
  border-color: #c026d3;
  background: #ffffff;
}
.cd-search-icon {
  position: absolute;
  left: 10px;
  color: #9891a0;
  font-size: 14px;
}

.cd-select {
  padding: 9px 14px;
  background: #f8f6fa;
  border: 1px solid #e4dfe9;
  border-radius: 10px;
  font-size: 13.5px;
  color: #312b39;
  outline: none;
  cursor: pointer;
  transition: border-color 0.2s ease;
}
.cd-select:focus {
  border-color: #c026d3;
  background: #ffffff;
}

.cd-actions-group {
  display: flex;
  align-items: center;
  gap: 10px;
}

.cd-live-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border-radius: 10px;
  border: 1px solid #e4dfe9;
  background: #ffffff;
  font-size: 12.5px;
  font-weight: 700;
  cursor: pointer;
  color: #645f6d;
  transition: all 0.15s ease;
}
.cd-live-toggle.active {
  background: #f0fdf4;
  color: #15803d;
  border-color: #86efac;
}

.cd-refresh-btn {
  padding: 8px 14px;
  border-radius: 10px;
  border: 1px solid #dbd4e0;
  background: #ffffff;
  color: #4b4454;
  font-size: 12.5px;
  font-weight: 650;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: all 0.15s ease;
}
.cd-refresh-btn:hover {
  background: #f6f3f8;
}

/* Table */
.cd-table-wrap {
  overflow-x: auto;
  width: 100%;
}
.cd-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
}
.cd-table th {
  padding: 13px 18px;
  font-size: 11.5px;
  font-weight: 750;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #797182;
  background: #faf8fc;
  border-bottom: 1px solid #ede8f2;
  white-space: nowrap;
}
.cd-table td {
  padding: 14px 18px;
  font-size: 13.5px;
  color: #312b39;
  border-bottom: 1px solid #f4f0f6;
  vertical-align: middle;
}
.cd-table tr:hover td {
  background: #fdfbfe;
  cursor: pointer;
}

/* Badges */
.cd-call-id {
  font-family: monospace;
  font-weight: 750;
  color: #7e22ce;
  background: #faf5ff;
  padding: 3px 8px;
  border-radius: 6px;
  font-size: 12px;
  border: 1px solid #f3e8ff;
  display: inline-block;
}

.cd-dir-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11.5px;
  font-weight: 650;
  padding: 3px 8px;
  border-radius: 6px;
  background: #f3f4f6;
  color: #4b5563;
}
.cd-dir-inbound { background: #eff6ff; color: #1d4ed8; }
.cd-dir-outbound { background: #faf5ff; color: #7e22ce; }

.cd-status-badge {
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 750;
  text-transform: uppercase;
  letter-spacing: 0.3px;
  display: inline-block;
}
.status-initiated { background: #dbeafe; color: #1e40af; }
.status-ringing { background: #fae8ff; color: #86198f; }
.status-accepted { background: #dcfce7; color: #166534; }
.status-terminated { background: #f3f4f6; color: #4b5563; }
.status-rejected { background: #ffedd5; color: #9a3412; }
.status-failed { background: #fee2e2; color: #991b1b; }

.cd-duration-pill {
  font-family: monospace;
  font-size: 12px;
  font-weight: 600;
  color: #4b5563;
}

.cd-view-btn {
  padding: 5px 10px;
  border-radius: 8px;
  border: 1px solid #d8b4fe;
  background: #faf5ff;
  color: #7e22ce;
  font-size: 12px;
  font-weight: 650;
  cursor: pointer;
  transition: all 0.15s ease;
}
.cd-view-btn:hover {
  background: #f3e8ff;
}

/* Empty State */
.cd-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
  color: #8c8594;
}
.cd-empty-icon {
  font-size: 42px;
  margin-bottom: 12px;
}
.cd-empty h4 {
  margin: 0;
  color: #312b39;
  font-size: 16px;
  font-weight: 750;
}
.cd-empty p {
  margin: 5px 0 0;
  font-size: 13px;
}

/* Event Timeline Modal / Drawer */
.cd-drawer-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.45);
  display: flex;
  justify-content: flex-end;
  z-index: 9999;
  backdrop-filter: blur(2px);
}
.cd-drawer {
  width: 100%;
  max-width: 520px;
  height: 100%;
  background: #ffffff;
  display: flex;
  flex-direction: column;
  box-shadow: -4px 0 25px rgba(0,0,0,0.15);
  animation: cdSlideIn 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}
@keyframes cdSlideIn {
  from { transform: translateX(100%); }
  to { transform: translateX(0); }
}
.cd-drawer-head {
  padding: 18px 22px;
  border-bottom: 1px solid #f0ebf3;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #faf8fc;
}
.cd-drawer-head h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 750;
  color: #27222d;
}
.cd-drawer-close {
  background: transparent;
  border: none;
  font-size: 20px;
  color: #797182;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 6px;
}
.cd-drawer-close:hover {
  background: #ece7f0;
}
.cd-drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: 22px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.cd-drawer-card {
  background: #faf8fc;
  border: 1px solid #eee8f2;
  border-radius: 12px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 13px;
}
.cd-drawer-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.cd-drawer-row span {
  color: #797182;
}
.cd-drawer-row strong {
  color: #27222d;
}

/* Timeline */
.cd-timeline {
  display: flex;
  flex-direction: column;
  gap: 14px;
  position: relative;
  padding-left: 20px;
}
.cd-timeline::before {
  content: "";
  position: absolute;
  top: 8px;
  bottom: 8px;
  left: 6px;
  width: 2px;
  background: #e9e4ee;
}
.cd-timeline-item {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.cd-timeline-dot {
  position: absolute;
  left: -20px;
  top: 5px;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #c026d3;
  border: 3px solid #ffffff;
  box-shadow: 0 0 0 1px #d8b4fe;
}
.cd-timeline-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12.5px;
}
.cd-timeline-type {
  font-weight: 750;
  text-transform: uppercase;
  color: #3b0764;
  background: #f5d0fe;
  padding: 2px 7px;
  border-radius: 5px;
  font-size: 11px;
}
.cd-timeline-time {
  font-size: 11px;
  color: #98909e;
}
.cd-timeline-raw {
  margin-top: 6px;
  background: #1e1b24;
  color: #a7f3d0;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 11px;
  font-family: monospace;
  max-height: 140px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
`;

function formatDuration(seconds) {
  const sec = parseInt(seconds) || 0;
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}

export default function CallsDashboard() {
  const { user } = useAuth();

  const [calls, setCalls] = useState([]);
  const [stats, setStats] = useState({
    active_calls: 0,
    total_calls: 0,
    missed_or_failed: 0,
    avg_duration_seconds: 0,
  });
  const [isCallingEnabled, setIsCallingEnabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Filters
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [directionFilter, setDirectionFilter] = useState("");

  // Live Auto-Refresh Toggle (10 seconds)
  const [isLiveFeed, setIsLiveFeed] = useState(false);

  // Selected Call for Events Timeline Drawer
  const [selectedCallId, setSelectedCallId] = useState(null);
  const [selectedCallData, setSelectedCallData] = useState(null);
  const [eventsLoading, setEventsLoading] = useState(false);

  const fetchCalls = useCallback(async () => {
    setError("");
    try {
      const params = {};
      const companyId = user?.company_id || user?.company;
      if (companyId) params.company_id = companyId;
      if (search.trim()) params.search = search.trim();
      if (statusFilter) params.status = statusFilter;
      if (directionFilter) params.direction = directionFilter;

      const { data } = await dashboardApi.getCalls(params);
      setCalls(data.calls || []);
      setStats(data.stats || {
        active_calls: 0,
        total_calls: 0,
        missed_or_failed: 0,
        avg_duration_seconds: 0,
      });
      setIsCallingEnabled(Boolean(data.is_calling_enabled));
    } catch (err) {
      setError(errorText(err));
    } finally {
      setLoading(false);
    }
  }, [user, search, statusFilter, directionFilter]);

  useEffect(() => {
    fetchCalls();
  }, [fetchCalls]);

  // Live Feed auto-refresh
  useEffect(() => {
    if (!isLiveFeed) return;
    const timer = setInterval(() => {
      fetchCalls();
    }, 10000);
    return () => clearInterval(timer);
  }, [isLiveFeed, fetchCalls]);

  // Fetch events when drawer opens
  const openCallEvents = async (callId) => {
    setSelectedCallId(callId);
    setEventsLoading(true);
    try {
      const { data } = await dashboardApi.getCallEvents(callId);
      setSelectedCallData(data);
    } catch (err) {
      alert("Failed to load call events: " + errorText(err));
      setSelectedCallId(null);
    } finally {
      setEventsLoading(false);
    }
  };

  const closeDrawer = () => {
    setSelectedCallId(null);
    setSelectedCallData(null);
  };

  return (
    <OwnerLayout
      title="WhatsApp Calls"
      subtitle={`Live voice call monitoring and lifecycle audit for ${user?.company_name || "your business"}.`}
    >
      <div className="cd-container">
        <style>{css}</style>

        {/* Informational Banner if Calling Disabled */}
        {!isCallingEnabled && (
          <div className="cd-banner">
            <span className="cd-banner-icon">ℹ️</span>
            <div className="cd-banner-text">
              <strong>WhatsApp Live Calling is Pending Activation</strong>
              WhatsApp Calling is currently in preview for this store. Incoming and outbound live voice agent calls will initiate once verified by Meta WABA.
            </div>
          </div>
        )}

        {error && (
          <div style={{ padding: "12px 16px", background: "#fee2e2", color: "#991b1b", borderRadius: 10, fontSize: 13, fontWeight: 600 }}>
            {error}
          </div>
        )}

        {/* 4 KPI Summary Cards */}
        <section className="cd-kpi-grid">
          <article className="cd-kpi-card">
            <div className="cd-kpi-head">
              <span>Active Calls</span>
              {stats.active_calls > 0 && <span className="cd-pulse-dot" title="Live calls in progress" />}
            </div>
            <div className="cd-kpi-value">
              {stats.active_calls}
              {stats.active_calls > 0 && <span style={{ fontSize: 13, color: "#16a34a", fontWeight: 700 }}>LIVE</span>}
            </div>
            <span className="cd-kpi-sub">Currently ringing or connected</span>
          </article>

          <article className="cd-kpi-card">
            <div className="cd-kpi-head">
              <span>Total Calls</span>
              <span>📞</span>
            </div>
            <div className="cd-kpi-value">{stats.total_calls}</div>
            <span className="cd-kpi-sub">All-time voice agent interactions</span>
          </article>

          <article className="cd-kpi-card">
            <div className="cd-kpi-head">
              <span>Missed / Failed</span>
              <span>⚠️</span>
            </div>
            <div className="cd-kpi-value" style={{ color: stats.missed_or_failed > 0 ? "#b91c1c" : "inherit" }}>
              {stats.missed_or_failed}
            </div>
            <span className="cd-kpi-sub">Declined or network dropouts</span>
          </article>

          <article className="cd-kpi-card">
            <div className="cd-kpi-head">
              <span>Avg. Duration</span>
              <span>⏱️</span>
            </div>
            <div className="cd-kpi-value">{formatDuration(stats.avg_duration_seconds)}</div>
            <span className="cd-kpi-sub">Across completed calls</span>
          </article>
        </section>

        {/* Calls Feed Table Panel */}
        <section className="cd-panel">
          {/* Toolbar */}
          <div className="cd-toolbar">
            <div className="cd-filters-group">
              <div className="cd-search-box">
                <span className="cd-search-icon">🔍</span>
                <input
                  type="text"
                  className="cd-search-input"
                  placeholder="Search phone or Call ID..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>

              <select
                className="cd-select"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
              >
                <option value="">All Statuses</option>
                <option value="initiated">Initiated</option>
                <option value="ringing">Ringing</option>
                <option value="accepted">Accepted</option>
                <option value="terminated">Terminated</option>
                <option value="rejected">Rejected</option>
                <option value="failed">Failed</option>
              </select>

              <select
                className="cd-select"
                value={directionFilter}
                onChange={(e) => setDirectionFilter(e.target.value)}
              >
                <option value="">All Directions</option>
                <option value="inbound">📥 Inbound</option>
                <option value="outbound">📤 Outbound</option>
              </select>
            </div>

            <div className="cd-actions-group">
              <button
                className={`cd-live-toggle ${isLiveFeed ? "active" : ""}`}
                onClick={() => setIsLiveFeed((prev) => !prev)}
                title="Automatically refresh every 10 seconds"
              >
                <span className={isLiveFeed ? "cd-pulse-dot" : ""} style={{ width: 8, height: 8 }} />
                Live Feed: {isLiveFeed ? "ON" : "OFF"}
              </button>

              <button className="cd-refresh-btn" onClick={fetchCalls}>
                <span>↻</span> Refresh
              </button>
            </div>
          </div>

          {/* Table */}
          <div className="cd-table-wrap">
            {loading && calls.length === 0 ? (
              <div className="cd-empty">
                <div className="cd-empty-icon">⏳</div>
                <p>Loading WhatsApp calls...</p>
              </div>
            ) : calls.length === 0 ? (
              <div className="cd-empty">
                <div className="cd-empty-icon">📞</div>
                <h4>No voice calls found</h4>
                <p>Customer WhatsApp calls to your business number will appear here in real time.</p>
              </div>
            ) : (
              <table className="cd-table">
                <thead>
                  <tr>
                    <th>Call Reference</th>
                    <th>Direction</th>
                    <th>Customer Phone</th>
                    <th>Status</th>
                    <th>Duration</th>
                    <th>Timestamp</th>
                    <th>Lifecycle Events</th>
                  </tr>
                </thead>
                <tbody>
                  {calls.map((c) => {
                    const statusClass = `status-${c.status || "initiated"}`;
                    const dirClass = c.direction === "inbound" ? "cd-dir-inbound" : "cd-dir-outbound";

                    return (
                      <tr key={c.id} onClick={() => openCallEvents(c.id)}>
                        <td>
                          <span className="cd-call-id">{c.call_id}</span>
                        </td>
                        <td>
                          <span className={`cd-dir-badge ${dirClass}`}>
                            {c.direction === "inbound" ? "📥 Inbound" : "📤 Outbound"}
                          </span>
                        </td>
                        <td>
                          <strong style={{ fontFamily: "monospace", fontSize: 13 }}>
                            {c.customer_phone || "Unknown Phone"}
                          </strong>
                        </td>
                        <td>
                          <span className={`cd-status-badge ${statusClass}`}>
                            {c.status_display || c.status}
                          </span>
                        </td>
                        <td>
                          <span className="cd-duration-pill">
                            {c.duration_seconds > 0 ? formatDuration(c.duration_seconds) : "–"}
                          </span>
                        </td>
                        <td style={{ fontSize: 12.5, color: "#787081", whiteSpace: "nowrap" }}>
                          {c.formatted_date || c.created_at}
                        </td>
                        <td>
                          <button
                            className="cd-view-btn"
                            onClick={(e) => {
                              e.stopPropagation();
                              openCallEvents(c.id);
                            }}
                          >
                            Timeline ➔
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </section>

        {/* Call Lifecycle Timeline Drawer */}
        {selectedCallId && (
          <div className="cd-drawer-overlay" onClick={closeDrawer}>
            <div className="cd-drawer" onClick={(e) => e.stopPropagation()}>
              <div className="cd-drawer-head">
                <div>
                  <h3>Call Lifecycle Audit</h3>
                  <span style={{ fontSize: 11.5, color: "#98909e", fontFamily: "monospace" }}>
                    ID: {selectedCallData?.call?.call_id || selectedCallId}
                  </span>
                </div>
                <button className="cd-drawer-close" onClick={closeDrawer}>✕</button>
              </div>

              <div className="cd-drawer-body">
                {eventsLoading && !selectedCallData ? (
                  <div className="cd-empty">
                    <div className="cd-empty-icon">⏳</div>
                    <p>Loading lifecycle events...</p>
                  </div>
                ) : (
                  <>
                    {/* Call Summary Card */}
                    <div className="cd-drawer-card">
                      <div className="cd-drawer-row">
                        <span>Customer Phone</span>
                        <strong>{selectedCallData?.call?.customer_phone}</strong>
                      </div>
                      <div className="cd-drawer-row">
                        <span>Direction</span>
                        <strong style={{ textTransform: "capitalize" }}>{selectedCallData?.call?.direction}</strong>
                      </div>
                      <div className="cd-drawer-row">
                        <span>Status</span>
                        <span className={`cd-status-badge status-${selectedCallData?.call?.status}`}>
                          {selectedCallData?.call?.status_display || selectedCallData?.call?.status}
                        </span>
                      </div>
                      <div className="cd-drawer-row">
                        <span>Session Duration</span>
                        <strong>{formatDuration(selectedCallData?.call?.duration_seconds)}</strong>
                      </div>
                      {selectedCallData?.call?.error_code && (
                        <div style={{ marginTop: 8, padding: 8, background: "#fee2e2", borderRadius: 8, color: "#991b1b", fontSize: 12 }}>
                          <strong>Meta Error ({selectedCallData.call.error_code}):</strong> {selectedCallData.call.error_message}
                        </div>
                      )}
                    </div>

                    {/* Timeline */}
                    <h4 style={{ margin: "10px 0 0", fontSize: 13, color: "#6b6474", textTransform: "uppercase", letterSpacing: 0.5 }}>
                      Chronological Events ({selectedCallData?.events?.length || 0})
                    </h4>

                    {(!selectedCallData?.events || selectedCallData.events.length === 0) ? (
                      <p style={{ fontSize: 13, color: "#98909e" }}>No raw events logged for this call yet.</p>
                    ) : (
                      <div className="cd-timeline">
                        {selectedCallData.events.map((ev, idx) => (
                          <div key={ev.id || idx} className="cd-timeline-item">
                            <span className="cd-timeline-dot" />
                            <div className="cd-timeline-head">
                              <span className="cd-timeline-type">{ev.event_type}</span>
                              <span className="cd-timeline-time">{ev.formatted_date || ev.created_at}</span>
                            </div>
                            {ev.raw_payload && Object.keys(ev.raw_payload).length > 0 && (
                              <details style={{ marginTop: 4, cursor: "pointer" }}>
                                <summary style={{ fontSize: 11, color: "#7e22ce", fontWeight: 600 }}>
                                  View Meta Webhook Payload
                                </summary>
                                <pre className="cd-timeline-raw">
                                  {JSON.stringify(ev.raw_payload, null, 2)}
                                </pre>
                              </details>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </OwnerLayout>
  );
}
