
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { restaurantDashboardApi } from "../../api/operationsApi";

const css = `
.ol-topbar{
  display:flex;align-items:center;gap:16px;padding:13px 26px;
  background:var(--ol-surface,#fff);border-bottom:1px solid #f0eaf2;
  position:sticky;top:0;z-index:30;min-height:66px;
}
.ol-burger{
  display:none;border:1px solid #eee5f0;background:#fff;border-radius:12px;
  width:40px;height:40px;font-size:18px;cursor:pointer;color:#555;
}
.ol-search{position:relative;flex:1;max-width:400px}
.ol-search input{
  width:100%;height:42px;padding:0 42px;border:1px solid #eee9f0;
  border-radius:13px;background:#faf9fb;font-size:13px;outline:none;
  color:#292331;transition:all .2s;
}
.ol-search input:focus{
  border-color:#ff77ff;background:#fff;
  box-shadow:0 0 0 4px rgba(255,119,255,.10);
}
.ol-search-ico{
  position:absolute;left:15px;top:50%;transform:translateY(-50%);
  font-size:14px;color:#aaa;pointer-events:none;
}
.ol-search kbd{
  position:absolute;right:12px;top:50%;transform:translateY(-50%);
  font-size:11px;color:#999;border:1px solid #eee5f0;
  border-radius:6px;padding:2px 7px;background:#fff;
}
.ol-results{
  position:absolute;top:50px;left:0;right:0;background:#fff;
  border:1px solid #f0eaf2;border-radius:14px;
  box-shadow:0 14px 35px rgba(40,20,50,.10);padding:7px;z-index:60;
}
.ol-result{
  display:flex;align-items:center;gap:11px;width:100%;padding:11px 12px;
  border:0;background:transparent;border-radius:10px;cursor:pointer;
  font-size:13px;text-align:left;color:#38313e;transition:background .15s;
}
.ol-result:hover{background:#fff1ff}
.ol-result small{margin-left:auto;color:#aaa;font-size:11px}
.ol-noresult{padding:14px;font-size:13px;color:#999}
.ol-top-right{margin-left:auto;display:flex;align-items:center;gap:13px}
.ol-icon-btn{
  position:relative;
  width:41px;height:41px;border:1px solid #eee9f0;background:#fff;
  border-radius:12px;cursor:pointer;font-size:16px;
  display:grid;place-items:center;transition:all .2s;color:#777;
}
.ol-icon-btn:hover{background:#fff1ff;border-color:#ffd6ff;color:#d946ef}
.ol-bell-wrap{position:relative}
.ol-bell-badge{
  position:absolute;top:-5px;right:-5px;min-width:19px;height:19px;padding:0 5px;
  border-radius:999px;background:linear-gradient(135deg,#ef4444,#ec4899);
  color:#fff;font-size:10.5px;font-weight:800;display:grid;place-items:center;
  border:2px solid #fff;box-shadow:0 2px 8px rgba(239,68,68,.35);line-height:1;
}
.ol-bell-menu{
  position:absolute;right:0;top:52px;width:300px;background:#fff;
  border:1px solid #f0e2f4;border-radius:16px;
  box-shadow:0 16px 38px rgba(40,20,50,.14);padding:10px;z-index:70;
  animation:ol-dropdown .16s ease-out;
}
.ol-bell-head{
  display:flex;align-items:center;justify-content:space-between;
  padding:6px 8px 10px;border-bottom:1px solid #f3eaf5;margin-bottom:8px;
}
.ol-bell-head strong{font-size:13.5px;color:#24142b}
.ol-bell-head span{
  font-size:11px;font-weight:700;padding:2px 8px;border-radius:999px;
  background:#fdf2ff;color:#b822b8;
}
.ol-bell-item{
  display:flex;align-items:center;justify-content:space-between;gap:10px;
  width:100%;padding:10px 11px;border:1px solid transparent;border-radius:11px;
  background:transparent;cursor:pointer;text-align:left;transition:all .15s;
  margin-bottom:4px;
}
.ol-bell-item:hover{background:#fdf6fe;border-color:#f3d6f7}
.ol-bell-item-left{display:flex;align-items:center;gap:10px;min-width:0}
.ol-bell-ico{
  width:32px;height:32px;border-radius:9px;display:grid;place-items:center;
  font-size:15px;flex-shrink:0;
}
.ol-bell-count{
  font-size:12px;font-weight:800;padding:3px 9px;border-radius:999px;flex-shrink:0;
}
.ol-user-wrap{position:relative}
.ol-user-btn{
  display:flex;align-items:center;gap:10px;height:42px;padding:0 12px 0 5px;
  border:1px solid #eee9f0;background:#fff;border-radius:13px;
  cursor:pointer;transition:all .2s;
}
.ol-user-btn:hover{border-color:#ffd6ff;background:#fffaff}
.ol-avatar{
  width:32px;height:32px;border-radius:10px;
  background:linear-gradient(135deg,#ff77ff,#e9a5f5);
  color:#fff;display:grid;place-items:center;font-weight:700;font-size:14px;
  flex-shrink:0;
}
.ol-user-name{
  max-width:130px;overflow:hidden;text-overflow:ellipsis;
  white-space:nowrap;font-size:13px;font-weight:600;color:#39313f;
}
.ol-chevron{font-size:11px;color:#999;transition:transform .2s}
.ol-user-btn[aria-expanded="true"] .ol-chevron{transform:rotate(180deg)}
.ol-menu{
  position:absolute;right:0;top:52px;width:210px;background:#fff;
  border:1px solid #f0eaf2;border-radius:15px;
  box-shadow:0 14px 35px rgba(40,20,50,.12);padding:7px;z-index:60;
  animation:ol-dropdown .16s ease-out;
}
@keyframes ol-dropdown{
  from{opacity:0;transform:translateY(-5px)}
  to{opacity:1;transform:translateY(0)}
}
.ol-menu-head{
  padding:11px 10px 13px;border-bottom:1px solid #f2edf3;
  margin-bottom:6px;display:flex;flex-direction:column;gap:4px;
}
.ol-menu-head strong{font-size:13px;color:#332b38}
.ol-menu-head small{color:#999;font-size:11px}
.ol-menu button{
  display:flex;align-items:center;gap:10px;width:100%;padding:10px;
  border:0;background:transparent;border-radius:9px;cursor:pointer;
  font-size:13px;color:#dc2626;text-align:left;transition:background .15s;
}
.ol-menu button:hover{background:#fff1f1}
@media(max-width:900px){
  .ol-topbar{padding:11px 15px;gap:11px}
  .ol-burger{display:block}
  .ol-search kbd{display:none}
  .ol-user-name{display:none}
  .ol-user-btn{padding:0 5px}
}
@media(max-width:480px){
  .ol-topbar{gap:9px}
  .ol-search{max-width:none}
  .ol-search input{height:40px;padding:0 12px 0 36px;font-size:12px}
  .ol-top-right{gap:7px}
  .ol-icon-btn{width:38px;height:38px}
}
`;

export default function OwnerTopbar({ groups = [], locked, billingPath, user, onMenu, onLogout }) {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const [userOpen, setUserOpen] = useState(false);
  const [bellOpen, setBellOpen] = useState(false);
  const [alerts, setAlerts] = useState({
    unassigned_orders_count: 0,
    pending_faq_suggestions_count: 0,
    low_stock_items_count: 0,
  });
  const inputRef = useRef(null);
  const searchRef = useRef(null);
  const userRef = useRef(null);
  const bellRef = useRef(null);

  useEffect(() => {
    if (locked) return;
    let mounted = true;
    const loadAlerts = async () => {
      try {
        const res = await restaurantDashboardApi.getSummary("today");
        if (mounted && res?.data?.alerts) {
          setAlerts(res.data.alerts);
        }
      } catch {
        // Silent fallback so topbar never disrupts navigation
      }
    };
    loadAlerts();
    const timer = setInterval(loadAlerts, 60000);
    return () => {
      mounted = false;
      clearInterval(timer);
    };
  }, [locked]);

  const totalAlerts =
    Number(alerts.unassigned_orders_count || 0) +
    Number(alerts.pending_faq_suggestions_count || 0) +
    Number(alerts.low_stock_items_count || 0);

  const name = user?.full_name || user?.first_name || user?.username || "Owner";

  const all = useMemo(
    () => groups.flatMap((g) => g.items.map((i) => ({ ...i, group: g.title })))
      .filter((i) => !locked || i.to === billingPath),
    [groups, locked, billingPath]
  );

  const results = useMemo(() => {
    const t = q.trim().toLowerCase();
    return t ? all.filter((i) => i.label.toLowerCase().includes(t)).slice(0, 6) : [];
  }, [q, all]);

  useEffect(() => {
    const onClick = (e) => {
      if (searchRef.current && !searchRef.current.contains(e.target)) setSearchOpen(false);
      if (userRef.current && !userRef.current.contains(e.target)) setUserOpen(false);
      if (bellRef.current && !bellRef.current.contains(e.target)) setBellOpen(false);
    };
    const onKey = (e) => {
      const tag = (e.target.tagName || "").toLowerCase();
      if (e.key === "/" && !["input", "textarea", "select"].includes(tag)) {
        e.preventDefault();
        inputRef.current?.focus();
      }
      if (e.key === "Escape") {
        setSearchOpen(false);
        setUserOpen(false);
        setBellOpen(false);
      }
    };
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, []);

  const go = (to) => {
    setQ("");
    setSearchOpen(false);
    setUserOpen(false);
    setBellOpen(false);
    navigate(to);
  };

  return (
    <>
      <style>{css}</style>
      <header className="ol-topbar">
        <button className="ol-burger" onClick={onMenu} aria-label="Open menu">☰</button>

        <div className="ol-search" ref={searchRef}>
          <span className="ol-search-ico">⌕</span>
          <input
            ref={inputRef}
            value={q}
            placeholder="Search pages..."
            aria-label="Search pages"
            onChange={(e) => { setQ(e.target.value); setSearchOpen(true); }}
            onFocus={() => setSearchOpen(true)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && results[0]) go(results[0].to);
            }}
          />
          <kbd>/</kbd>
          {searchOpen && q.trim() && (
            <div className="ol-results">
              {results.length === 0 && <div className="ol-noresult">No page found</div>}
              {results.map((r) => (
                <button key={r.to} className="ol-result" onClick={() => go(r.to)}>
                  <span>{r.icon}</span>
                  {r.label}
                  <small>{r.group}</small>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="ol-top-right">
          {user?.is_superuser && (
            <button
              type="button"
              onClick={() => navigate("/superadmin")}
              style={{
                padding: "7px 12px",
                borderRadius: 10,
                border: "1px solid #f0abfc",
                background: "#fdf4ff",
                color: "#a21caf",
                fontWeight: 700,
                fontSize: 12,
                cursor: "pointer",
                whiteSpace: "nowrap",
              }}
              title="Open Platform Super Admin Dashboard"
            >
              👑 Super Admin
            </button>
          )}
          <div className="ol-bell-wrap" ref={bellRef}>
            <button
              type="button"
              className="ol-icon-btn"
              title={totalAlerts > 0 ? `${totalAlerts} Action Required Alerts` : "Notifications"}
              aria-label="Notifications"
              aria-expanded={bellOpen}
              disabled={locked}
              onClick={() => setBellOpen((v) => !v)}
              style={totalAlerts > 0 ? { borderColor: "#f5b8f5", background: "#fff6ff", color: "#c026d3" } : undefined}
            >
              <span>🔔</span>
              {totalAlerts > 0 && (
                <span className="ol-bell-badge">{totalAlerts > 99 ? "99+" : totalAlerts}</span>
              )}
            </button>

            {bellOpen && (
              <div className="ol-bell-menu" role="menu">
                <div className="ol-bell-head">
                  <strong>Action Alerts</strong>
                  <span>{totalAlerts > 0 ? `${totalAlerts} Pending` : "All Clear"}</span>
                </div>

                {totalAlerts === 0 ? (
                  <div style={{ padding: "14px 8px", textAlign: "center", fontSize: 12.5, color: "#8c7d96" }}>
                    ✅ You’re all caught up! No pending operational alerts.
                  </div>
                ) : (
                  <>
                    {(alerts.unassigned_orders_count || 0) > 0 && (
                      <button type="button" className="ol-bell-item" onClick={() => go("/owner/m/orders")}>
                        <div className="ol-bell-item-left">
                          <span className="ol-bell-ico" style={{ background: "#fdf2ff", color: "#b822b8" }}>🔔</span>
                          <div>
                            <div style={{ fontSize: 13, fontWeight: 700, color: "#24142b" }}>New / Unassigned Orders</div>
                            <div style={{ fontSize: 11.5, color: "#7f7288" }}>Review & dispatch incoming orders</div>
                          </div>
                        </div>
                        <span className="ol-bell-count" style={{ background: "#fdf2ff", color: "#b822b8" }}>
                          {alerts.unassigned_orders_count}
                        </span>
                      </button>
                    )}

                    {(alerts.pending_faq_suggestions_count || 0) > 0 && (
                      <button type="button" className="ol-bell-item" onClick={() => go("/owner/knowledge")}>
                        <div className="ol-bell-item-left">
                          <span className="ol-bell-ico" style={{ background: "#f5f3ff", color: "#6d28d9" }}>✨</span>
                          <div>
                            <div style={{ fontSize: 13, fontWeight: 700, color: "#24142b" }}>Pending AI FAQs</div>
                            <div style={{ fontSize: 11.5, color: "#7f7288" }}>Approve customer questions for AI</div>
                          </div>
                        </div>
                        <span className="ol-bell-count" style={{ background: "#f5f3ff", color: "#6d28d9" }}>
                          {alerts.pending_faq_suggestions_count}
                        </span>
                      </button>
                    )}

                    {(alerts.low_stock_items_count || 0) > 0 && (
                      <button type="button" className="ol-bell-item" onClick={() => go("/owner/m/inventory")}>
                        <div className="ol-bell-item-left">
                          <span className="ol-bell-ico" style={{ background: "#fff7ed", color: "#c2410c" }}>⚠️</span>
                          <div>
                            <div style={{ fontSize: 13, fontWeight: 700, color: "#24142b" }}>Low Stock Items</div>
                            <div style={{ fontSize: 11.5, color: "#7f7288" }}>Restock items below threshold</div>
                          </div>
                        </div>
                        <span className="ol-bell-count" style={{ background: "#fff7ed", color: "#c2410c" }}>
                          {alerts.low_stock_items_count}
                        </span>
                      </button>
                    )}
                  </>
                )}
              </div>
            )}
          </div>

          <button
            className="ol-icon-btn"
            title="Conversations"
            aria-label="Conversations"
            disabled={locked}
            onClick={() => go("/owner/conversations")}
          >♧</button>

          <div className="ol-user-wrap" ref={userRef}>
            <button
              className="ol-user-btn"
              onClick={() => setUserOpen((v) => !v)}
              aria-haspopup="menu"
              aria-expanded={userOpen}
            >
              <span className="ol-avatar">{name.charAt(0).toUpperCase()}</span>
              <span className="ol-user-name">{name}</span>
              <span className="ol-chevron">▾</span>
            </button>

            {userOpen && (
              <div className="ol-menu" role="menu">
                <div className="ol-menu-head">
                  <strong>{name}</strong>
                  <small>Owner · {user?.company_name || "Your business"}</small>
                </div>
                <button role="menuitem" onClick={onLogout}>
                  <span>↪</span> Logout
                </button>
              </div>
            )}
          </div>
        </div>
      </header>
    </>
  );
}
