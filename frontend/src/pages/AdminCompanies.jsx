import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { authApi } from "../api/authApi";
import { errorText } from "../api/axiosClient";
import { useAuth } from "../context/AuthContext";
import logo from "../assets/logo.webp";
import "../styles/landing.css";
import "../styles/admin.css";

const DOCS = [
  ["cnic_front_url", "CNIC front"],
  ["cnic_back_url", "CNIC back"],
  ["passport_size_photo_url", "Photo"],
  ["business_registration_document_url", "Business doc"],
];

const NAV = [
  { to: "/admin/companies", icon: "🕒", label: "Pending Approvals", active: true },
];

export default function AdminCompanies() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();

  const [companies, setCompanies] = useState([]);
  const [payments, setPayments] = useState([]);
  const [view, setView] = useState("approvals");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState(null);
  const [query, setQuery] = useState("");
  const [menu, setMenu] = useState(false);

  const load = useCallback(async () => {
    setError("");
    try {
      const [companyResult, paymentResult] = await Promise.all([authApi.pendingCompanies(), authApi.manualPayments()]);
      setCompanies(companyResult.data);
      setPayments(paymentResult.data);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const paymentAct = async (id, action) => {
    if (action === "reject" && !window.confirm("Reject this payment submission?")) return;
    setBusyId(id); setError("");
    try { await authApi.manualPaymentAction(id, action); await load(); }
    catch (e) { setError(errorText(e)); }
    finally { setBusyId(null); }
  };

  const act = async (id, action) => {
    if (action === "reject" && !window.confirm("Do you want to reject this company?")) return;
    setBusyId(id);
    setError("");
    try {
      await authApi.companyAction(id, action);
      setCompanies((list) => list.filter((c) => c.id !== id));
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusyId(null);
    }
  };

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return companies;
    return companies.filter((c) =>
      [c.name, c.email, c.phone, c.cnic, c.business_type]
        .filter(Boolean)
        .some((v) => String(v).toLowerCase().includes(q))
    );
  }, [companies, query]);

  const logout = () => {
    signOut();
    navigate("/login");
  };

  const name = user?.first_name || user?.username || "Admin";

  return (
    <div className="ad-shell">
      {/* ---------- SIDEBAR ---------- */}
      <aside className={`ad-sidebar ${menu ? "open" : ""}`}>
        <Link to="/" className="ad-brand">
          <img src={logo} alt="Rides AI" />
        </Link>

        <span className="ad-nav-title">Admin</span>
        <nav className="ad-nav">
          {NAV.map((item) => (
            <Link
              key={item.label}
              to={item.to}
              className={`ad-nav-item ${item.active ? "active" : ""}`}
              onClick={() => setMenu(false)}
            >
              <span className="ad-nav-icon">{item.icon}</span>
              {item.label}
              {item.active && companies.length > 0 && <em>{companies.length}</em>}
            </Link>
          ))}
        </nav>

        <div className="ad-sidebar-bottom">
          <div className="ad-user">
            <span className="ad-avatar">{name.charAt(0).toUpperCase()}</span>
            <div>
              <strong>{name}</strong>
              <small>Administrator</small>
            </div>
          </div>
          <button className="ad-btn ad-btn-ghost ad-logout" onClick={logout}>
            Logout
          </button>
        </div>
      </aside>

      {menu && <div className="ad-overlay" onClick={() => setMenu(false)} />}

      {/* ---------- MAIN ---------- */}
      <main className="ad-main">
        <header className="ad-topbar">
          <button className="ad-burger" onClick={() => setMenu(true)} aria-label="Open menu">☰</button>
          <div className="ad-title">
            <h1>{view === "approvals" ? "Pending Approvals" : "Manual Payments"}</h1>
            <p>{view === "approvals" ? "Review documents and approve businesses to start their one-month initial access." : "Review submitted transfer details and confirm client payments."}</p>
          </div>
          <div style={{display:"flex",gap:8,flexWrap:"wrap"}}>
            <button className={`ad-btn ${view === "approvals" ? "ad-btn-primary" : "ad-btn-ghost"}`} onClick={() => setView("approvals")}>Approvals ({companies.length})</button>
            <button className={`ad-btn ${view === "payments" ? "ad-btn-primary" : "ad-btn-ghost"}`} onClick={() => setView("payments")}>Payments ({payments.filter(p => p.status === "pending").length})</button>
          </div>
          <button className="ad-btn ad-btn-ghost" onClick={load}>↻ Refresh</button>
        </header>

        <section className="ad-toolbar">
          <div className="ad-stat">
            <span>{view === "approvals" ? "🕒" : "💳"}</span>
            <div>
              <strong>{view === "approvals" ? companies.length : payments.filter(p => p.status === "pending").length}</strong>
              <small>{view === "approvals" ? "Waiting for review" : "Payments awaiting review"}</small>
            </div>
          </div>
          <input
            className="ad-search"
            type="search"
            placeholder={view === "approvals" ? "Search by name, email, phone or CNIC" : "Search by company, email or reference"}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Search companies"
          />
        </section>

        {error && <div className="ad-alert" role="alert">{error}</div>}

        {loading && (
          <div className="ad-list">
            {[1, 2].map((n) => <div className="ad-skeleton" key={n} />)}
          </div>
        )}

        {view === "approvals" && !loading && companies.length === 0 && !error && (
          <div className="ad-empty">
            <span>🎉</span>
            <h3>All caught up</h3>
            <p>There are no companies waiting for approval right now.</p>
          </div>
        )}

        {view === "approvals" && !loading && companies.length > 0 && filtered.length === 0 && (
          <div className="ad-empty">
            <span>🔍</span>
            <h3>No matches</h3>
            <p>No pending company matches “{query}”.</p>
          </div>
        )}

        {view === "approvals" && <div className="ad-list">
          {filtered.map((c) => (
            <article className="ad-card" key={c.id}>
              <div className="ad-card-head">
                <span className="ad-company-avatar">{(c.name || "C").charAt(0).toUpperCase()}</span>
                <div className="ad-card-title">
                  <h3>{c.name}</h3>
                  <span className="ad-chip">{c.business_type || "Business"}</span>
                </div>
                <span className="ad-badge">Pending</span>
              </div>

              <dl className="ad-details">
                <div><dt>Email</dt><dd>{c.email || "-"}</dd></div>
                <div><dt>Phone</dt><dd>{c.phone || "-"}</dd></div>
                <div><dt>CNIC</dt><dd>{c.cnic || "-"}</dd></div>
                <div><dt>Registration #</dt><dd>{c.registration_number || "-"}</dd></div>
                <div><dt>Plan</dt><dd>{c.plan || "-"}</dd></div>
              </dl>

              <div className="ad-docs">
                <span>Documents</span>
                {DOCS.some(([key]) => c[key]) ? (
                  DOCS.map(([key, label]) =>
                    c[key] ? (
                      <a key={key} href={c[key]} target="_blank" rel="noreferrer">
                        📄 {label} <i>↗</i>
                      </a>
                    ) : null
                  )
                ) : (
                  <em>No documents uploaded</em>
                )}
              </div>

              <div className="ad-actions">
                <button
                  className="ad-btn ad-btn-primary"
                  disabled={busyId === c.id}
                  onClick={() => act(c.id, "approve")}
                >
                  {busyId === c.id ? "Please wait..." : "Approve & start one-month access"}
                </button>
                <button
                  className="ad-btn ad-btn-danger"
                  disabled={busyId === c.id}
                  onClick={() => act(c.id, "reject")}
                >
                  Reject
                </button>
              </div>
            </article>
          ))}
        </div>}
        {view === "payments" && <div className="ad-list">
          {payments.filter(p => !query || [p.company,p.submitted_by,p.reference,p.status].filter(Boolean).some(v => String(v).toLowerCase().includes(query.toLowerCase()))).map(p => (
            <article className="ad-card" key={p.id}>
              <div className="ad-card-head"><span className="ad-company-avatar">💳</span><div className="ad-card-title"><h3>{p.company}</h3><span className="ad-chip">{p.status}</span></div><span className="ad-badge">{p.currency} {p.amount || "Amount not provided"}</span></div>
              <dl className="ad-details"><div><dt>Submitted by</dt><dd>{p.submitted_by}</dd></div><div><dt>Reference</dt><dd>{p.reference || "—"}</dd></div><div><dt>Submitted</dt><dd>{new Date(p.created_at).toLocaleString()}</dd></div></dl>
              {p.notes && <p>{p.notes}</p>}
              {p.proof_url && <p><a href={p.proof_url} target="_blank" rel="noreferrer">View payment proof ↗</a></p>}
              {p.status === "pending" && <div className="ad-actions"><button className="ad-btn ad-btn-primary" disabled={busyId === p.id} onClick={() => paymentAct(p.id,"approve")}>Approve & renew 30 days</button><button className="ad-btn ad-btn-danger" disabled={busyId === p.id} onClick={() => paymentAct(p.id,"reject")}>Reject</button></div>}
            </article>
          ))}
          {!loading && payments.length === 0 && <div className="ad-empty"><span>💳</span><h3>No payments yet</h3><p>Manual payment submissions will appear here.</p></div>}
        </div>}
      </main>
    </div>
  );
}