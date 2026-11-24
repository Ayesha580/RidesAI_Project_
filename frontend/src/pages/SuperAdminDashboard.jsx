import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { superAdminApi } from "../api/operationsApi";
import { errorText } from "../api/axiosClient";
import logo from "../assets/logo.webp";

function formatRs(val) {
  const num = Number(val || 0);
  return `Rs. ${num.toLocaleString("en-PK", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;
}

export default function SuperAdminDashboard() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState("tenants"); // "tenants" | "audit"
  const [overview, setOverview] = useState(null);
  const [companies, setCompanies] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [search, setSearch] = useState("");
  const [vertical, setVertical] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const loadAll = useCallback(async () => {
    setError("");
    try {
      const params = {};
      if (search.trim()) params.search = search.trim();
      if (vertical !== "all") params.vertical = vertical;
      if (statusFilter !== "all") params.status = statusFilter;

      const [ovRes, compRes, logRes] = await Promise.all([
        superAdminApi.getOverview(),
        superAdminApi.listCompanies(params),
        superAdminApi.listAuditLogs(),
      ]);
      setOverview(ovRes.data);
      setCompanies(Array.isArray(compRes.data) ? compRes.data : []);
      setAuditLogs(Array.isArray(logRes.data) ? logRes.data : []);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setLoading(false);
    }
  }, [search, vertical, statusFilter]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const handleToggleStatus = async (comp) => {
    const nextActive = !comp.is_active;
    const actionLabel = nextActive ? "Activate" : "Suspend";
    if (!window.confirm(`${actionLabel} "${comp.name}"? This action will be recorded in the platform audit log.`)) {
      return;
    }
    setBusyId(comp.id);
    setError("");
    try {
      await superAdminApi.updateCompanyStatus(comp.id, nextActive, `${actionLabel}d via Super Admin Dashboard`);
      setNotice(`${comp.name} has been ${nextActive ? "activated" : "suspended"}.`);
      setTimeout(() => setNotice(""), 3500);
      await loadAll();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusyId(null);
    }
  };

  const kpis = overview?.kpis || {};
  const verticals = overview?.vertical_breakdown || [];

  return (
    <div style={{ minHeight: "100vh", background: "#fbf9fc", color: "#0f172a", fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" }}>
      {/* Top Header */}
      <header
        style={{
          background: "#ffffff",
          borderBottom: "1px solid #f0e8f4",
          padding: "14px 28px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 12,
          position: "sticky",
          top: 0,
          zIndex: 30,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <img src={logo} alt="RidesAI" style={{ width: 34, height: 34, objectFit: "contain" }} />
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <strong style={{ fontSize: 17 }}>RidesAI Platform Owner</strong>
              <span style={{ fontSize: 10.5, fontWeight: 800, textTransform: "uppercase", padding: "2px 8px", borderRadius: 999, background: "#fdf4ff", color: "#a21caf", border: "1px solid #f0abfc" }}>
                Super Admin
              </span>
            </div>
            <div style={{ fontSize: 11.5, color: "#64748b" }}>Owned by Rides Technologies · Multi-Tenant Control Plane</div>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <span style={{ fontSize: 12.5, color: "#64748b" }}>{user?.email || user?.username}</span>
          {user?.role === "owner" && (
            <Link
              to="/owner/dashboard"
              style={{ padding: "7px 12px", borderRadius: 10, border: "1px solid #e2e8f0", background: "#fff", color: "#334155", fontSize: 12.5, fontWeight: 600, textDecoration: "none" }}
            >
              Business Dashboard
            </Link>
          )}
          <button
            type="button"
            onClick={() => {
              signOut?.();
              navigate("/login");
            }}
            style={{ padding: "7px 12px", borderRadius: 10, border: "1px solid #f0abfc", background: "#fdf4ff", color: "#a21caf", fontSize: 12.5, fontWeight: 700, cursor: "pointer" }}
          >
            Sign Out
          </button>
        </div>
      </header>

      <main style={{ maxWidth: 1220, margin: "0 auto", padding: "24px 20px 48px", display: "grid", gap: 20 }}>
        {error && (
          <div style={{ background: "#fef2f2", border: "1px solid #fecaca", color: "#991b1b", padding: "12px 16px", borderRadius: 12, fontSize: 13.5 }}>
            {error}
          </div>
        )}
        {notice && (
          <div style={{ background: "#fdf4ff", border: "1px solid #f0abfc", color: "#86198f", padding: "12px 16px", borderRadius: 12, fontSize: 13.5, fontWeight: 600 }}>
            ✅ {notice}
          </div>
        )}

        {/* Platform KPI Cards */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 14 }}>
          {[
            {
              icon: "🏢",
              label: "Total Businesses",
              value: kpis.total_businesses ?? 0,
              sub: `${kpis.active_businesses ?? 0} active · ${kpis.suspended_businesses ?? 0} suspended`,
            },
            {
              icon: "👥",
              label: "Platform Users",
              value: kpis.total_users ?? 0,
              sub: `${kpis.total_owners ?? 0} owners · ${kpis.total_staff ?? 0} staff`,
            },
            {
              icon: "📦",
              label: "Orders & Bookings",
              value: kpis.total_bookings_and_orders ?? 0,
              sub: `${kpis.total_orders ?? 0} orders · ${kpis.total_appointments ?? 0} OPD · ${kpis.total_lab_bookings ?? 0} labs`,
            },
            {
              icon: "🎙️",
              label: "AI Conversations",
              value: kpis.total_ai_conversations ?? 0,
              sub: `${kpis.total_voice_messages_used ?? 0} voice turns used`,
            },
            {
              icon: "💰",
              label: "Platform GMV",
              value: formatRs(kpis.platform_gmv_rs),
              sub: "Non-cancelled gross volume",
            },
          ].map((c) => (
            <div key={c.label} style={{ background: "#fff", border: "1px solid #f0abfc", borderRadius: 16, padding: "16px 18px", boxShadow: "0 4px 14px rgba(255,119,255,0.06)" }}>
              <div style={{ fontSize: 12, color: "#64748b", fontWeight: 700 }}>{c.icon} {c.label}</div>
              <div style={{ fontSize: 24, fontWeight: 800, color: "#0f172a", marginTop: 4 }}>{c.value}</div>
              <div style={{ fontSize: 11.5, color: "#94a3b8", marginTop: 4 }}>{c.sub}</div>
            </div>
          ))}
        </div>

        {/* Vertical Distribution Chips */}
        <section style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 16, padding: "16px 20px" }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 10 }}>
            Businesses by Vertical
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {verticals.map((v) => (
              <button
                key={v.key}
                type="button"
                onClick={() => {
                  setActiveTab("tenants");
                  setVertical(vertical === v.key ? "all" : v.key);
                }}
                style={{
                  padding: "7px 14px",
                  borderRadius: 999,
                  border: vertical === v.key ? "1px solid #ff77ff" : "1px solid #e2e8f0",
                  background: vertical === v.key ? "#fdf4ff" : "#f8fafc",
                  color: vertical === v.key ? "#a21caf" : "#334155",
                  fontWeight: 700,
                  fontSize: 12.5,
                  cursor: "pointer",
                }}
              >
                {v.label}: <span style={{ color: "#c026d3" }}>{v.count}</span>
              </button>
            ))}
          </div>
        </section>

        {/* Tabs: Tenants Management vs Platform Audit Logs */}
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <button
            type="button"
            onClick={() => setActiveTab("tenants")}
            style={{
              padding: "10px 18px",
              borderRadius: 12,
              border: activeTab === "tenants" ? "1px solid #ff77ff" : "1px solid #e2e8f0",
              background: activeTab === "tenants" ? "#ff77ff" : "#fff",
              color: activeTab === "tenants" ? "#fff" : "#475569",
              fontWeight: 700,
              fontSize: 13.5,
              cursor: "pointer",
              boxShadow: activeTab === "tenants" ? "0 4px 12px rgba(255,119,255,0.35)" : "none",
            }}
          >
            🏢 Tenant Businesses ({companies.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("audit")}
            style={{
              padding: "10px 18px",
              borderRadius: 12,
              border: activeTab === "audit" ? "1px solid #ff77ff" : "1px solid #e2e8f0",
              background: activeTab === "audit" ? "#ff77ff" : "#fff",
              color: activeTab === "audit" ? "#fff" : "#475569",
              fontWeight: 700,
              fontSize: 13.5,
              cursor: "pointer",
              boxShadow: activeTab === "audit" ? "0 4px 12px rgba(255,119,255,0.35)" : "none",
            }}
          >
            📜 Platform Audit Logs ({auditLogs.length})
          </button>
        </div>

        {loading ? (
          <div style={{ background: "#fff", borderRadius: 16, padding: 32, textAlign: "center", color: "#64748b" }}>
            Loading platform metrics...
          </div>
        ) : activeTab === "tenants" ? (
          <section style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 16, padding: 20 }}>
            {/* Search & Filter Controls */}
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 16 }}>
              <input
                placeholder="Search business name, email, or phone..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                style={{ flex: 1, minWidth: 220, padding: "9px 12px", borderRadius: 10, border: "1px solid #d1d5db", fontSize: 13.5 }}
              />
              <select
                value={vertical}
                onChange={(e) => setVertical(e.target.value)}
                style={{ padding: "9px 12px", borderRadius: 10, border: "1px solid #d1d5db", fontSize: 13 }}
              >
                <option value="all">All Verticals</option>
                <option value="restaurant">Restaurant</option>
                <option value="pharmacy">Pharmacy</option>
                <option value="clinic">Clinic</option>
                <option value="hospital">Hospital</option>
                <option value="retail">Retail</option>
                <option value="grocery">Grocery</option>
              </select>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                style={{ padding: "9px 12px", borderRadius: 10, border: "1px solid #d1d5db", fontSize: 13 }}
              >
                <option value="all">All Statuses</option>
                <option value="active">Active</option>
                <option value="suspended">Suspended</option>
              </select>
            </div>

            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid #e2e8f0", color: "#64748b", textAlign: "left" }}>
                    <th style={{ padding: "10px 8px" }}>Business</th>
                    <th style={{ padding: "10px 8px" }}>Vertical</th>
                    <th style={{ padding: "10px 8px" }}>Status</th>
                    <th style={{ padding: "10px 8px", textAlign: "right" }}>Orders</th>
                    <th style={{ padding: "10px 8px", textAlign: "right" }}>AI Chats</th>
                    <th style={{ padding: "10px 8px", textAlign: "right" }}>Voice Quota</th>
                    <th style={{ padding: "10px 8px", textAlign: "right" }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {companies.length === 0 ? (
                    <tr>
                      <td colSpan={7} style={{ padding: 24, textAlign: "center", color: "#94a3b8" }}>
                        No businesses match your current filters.
                      </td>
                    </tr>
                  ) : (
                    companies.map((c) => (
                      <tr key={c.id} style={{ borderBottom: "1px solid #f1f5f9" }}>
                        <td style={{ padding: "11px 8px" }}>
                          <div style={{ fontWeight: 700, color: "#0f172a" }}>{c.name}</div>
                          <div style={{ fontSize: 11.5, color: "#64748b" }}>{c.owner_email || "No owner email"}</div>
                        </td>
                        <td style={{ padding: "11px 8px" }}>
                          <span style={{ fontSize: 11.5, fontWeight: 600, padding: "3px 9px", borderRadius: 999, background: "#f8fafc", border: "1px solid #e2e8f0" }}>
                            {c.vertical_label}
                          </span>
                        </td>
                        <td style={{ padding: "11px 8px" }}>
                          <span
                            style={{
                              fontSize: 11,
                              fontWeight: 700,
                              padding: "3px 9px",
                              borderRadius: 999,
                              background: c.is_active ? "#ecfdf5" : "#fef2f2",
                              color: c.is_active ? "#047857" : "#b91c1c",
                            }}
                          >
                            {c.is_active ? "Active" : "Suspended"}
                          </span>
                        </td>
                        <td style={{ padding: "11px 8px", textAlign: "right", fontWeight: 600 }}>{c.orders_count}</td>
                        <td style={{ padding: "11px 8px", textAlign: "right", fontWeight: 600 }}>{c.conversations_count}</td>
                        <td style={{ padding: "11px 8px", textAlign: "right", color: "#475569" }}>
                          {c.messages_used} / {c.message_limit}
                        </td>
                        <td style={{ padding: "11px 8px", textAlign: "right" }}>
                          <button
                            type="button"
                            disabled={busyId === c.id}
                            onClick={() => handleToggleStatus(c)}
                            style={{
                              padding: "6px 12px",
                              borderRadius: 8,
                              border: "none",
                              fontWeight: 700,
                              fontSize: 12,
                              cursor: busyId === c.id ? "not-allowed" : "pointer",
                              background: c.is_active ? "#fee2e2" : "#ff77ff",
                              color: c.is_active ? "#b91c1c" : "#ffffff",
                            }}
                          >
                            {busyId === c.id ? "..." : c.is_active ? "Suspend" : "Activate"}
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </section>
        ) : (
          <section style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 16, padding: 20 }}>
            <h3 style={{ margin: "0 0 14px", fontSize: 16 }}>Recent Platform Administrative Actions</h3>
            {auditLogs.length === 0 ? (
              <p style={{ margin: 0, color: "#94a3b8", fontSize: 13 }}>No platform administrative actions recorded yet.</p>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid #e2e8f0", color: "#64748b", textAlign: "left" }}>
                      <th style={{ padding: "9px 8px" }}>Action</th>
                      <th style={{ padding: "9px 8px" }}>Target Business</th>
                      <th style={{ padding: "9px 8px" }}>Super Admin</th>
                      <th style={{ padding: "9px 8px" }}>Timestamp</th>
                    </tr>
                  </thead>
                  <tbody>
                    {auditLogs.map((log) => (
                      <tr key={log.id} style={{ borderBottom: "1px solid #f1f5f9" }}>
                        <td style={{ padding: "10px 8px" }}>
                          <span style={{ fontSize: 11.5, fontWeight: 700, padding: "3px 9px", borderRadius: 999, background: "#fdf4ff", color: "#a21caf" }}>
                            {log.action.replace(/_/g, " ")}
                          </span>
                        </td>
                        <td style={{ padding: "10px 8px", fontWeight: 600 }}>{log.target_company_name || "—"}</td>
                        <td style={{ padding: "10px 8px", color: "#475569" }}>{log.actor_email || "System"}</td>
                        <td style={{ padding: "10px 8px", color: "#64748b", fontSize: 12 }}>
                          {log.created_at ? new Date(log.created_at).toLocaleString() : ""}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}
      </main>
    </div>
  );
}
