import { Link, NavLink } from "react-router-dom";
import logo from "../../assets/logo.webp";
import { moduleIcon, moduleLabel } from "../../constants/modules";

const css = `
.sl-sidebar{
  width:250px;flex-shrink:0;display:flex;flex-direction:column;
  background:var(--sl-surface,#fff);border-right:1px solid var(--sl-border,#e5e7eb);
  padding:18px 14px;position:sticky;top:0;height:100vh;overflow-y:auto;z-index:50;
}
.sl-brand{display:block;padding:4px 8px 16px}
.sl-brand img{height:34px;width:auto;display:block}
.sl-company{background:var(--sl-soft,#f3f4f6);border-radius:12px;padding:10px 12px;margin-bottom:18px;display:flex;flex-direction:column;gap:2px}
.sl-company span{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--sl-muted,#6b7280)}
.sl-company strong{font-size:14px;word-break:break-word}
.sl-nav-title{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--sl-muted,#6b7280);padding:0 10px;margin-bottom:6px}
.sl-nav{display:flex;flex-direction:column;gap:4px}
.sl-nav-item{
  display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:10px;
  color:inherit;text-decoration:none;font-size:14px;transition:background .15s;
}
.sl-nav-item:hover{background:var(--sl-soft,#f3f4f6)}
.sl-nav-item.active{background:var(--sl-active-bg,#eef2ff);color:var(--sl-active,#4338ca);font-weight:600}
.sl-nav-icon{width:22px;text-align:center}
.sl-side-bottom{margin-top:auto;padding-top:16px;border-top:1px solid var(--sl-border,#e5e7eb);display:flex;flex-direction:column;gap:10px}
.sl-user{display:flex;align-items:center;gap:10px}
.sl-avatar{width:36px;height:36px;border-radius:50%;background:var(--sl-active-bg,#eef2ff);color:var(--sl-active,#4338ca);display:grid;place-items:center;font-weight:700;flex-shrink:0}
.sl-user div{display:flex;flex-direction:column;min-width:0}
.sl-user strong{font-size:14px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.sl-user small{color:var(--sl-muted,#6b7280)}
.sl-overlay{display:none}

@media (max-width:900px){
  .sl-sidebar{position:fixed;left:0;top:0;transform:translateX(-100%);transition:transform .25s;box-shadow:0 0 30px rgba(0,0,0,.15)}
  .sl-sidebar.open{transform:translateX(0)}
  .sl-overlay{display:block;position:fixed;inset:0;background:rgba(0,0,0,.4);z-index:40}
}
`;

export default function StaffSidebar({ modules, open, onClose, user, onLogout }) {
  const name = user?.full_name || user?.first_name || user?.username || "Staff";

  return (
    <>
      <style>{css}</style>

      <aside className={`sl-sidebar ${open ? "open" : ""}`}>
        <Link to="/staff/dashboard" className="sl-brand" onClick={onClose}>
          <img src={logo} alt="Rides AI" />
        </Link>

        <div className="sl-company">
          <span>Business</span>
          <strong>{user?.company_name || "Your business"}</strong>
        </div>

        <span className="sl-nav-title">Menu</span>
        <nav className="sl-nav">
          <NavLink
            to="/staff/dashboard"
            end
            className={({ isActive }) => `sl-nav-item ${isActive ? "active" : ""}`}
            onClick={onClose}
          >
            <span className="sl-nav-icon">🏠</span>
            Dashboard
          </NavLink>

          {modules.map((m) => (
            <NavLink
              key={m}
              to={`/staff/${m}`}
              className={({ isActive }) => `sl-nav-item ${isActive ? "active" : ""}`}
              onClick={onClose}
            >
              <span className="sl-nav-icon">{moduleIcon(m)}</span>
              {moduleLabel(m)}
            </NavLink>
          ))}
        </nav>

        <div className="sl-side-bottom">
          <div className="sl-user">
            <span className="sl-avatar">{name.charAt(0).toUpperCase()}</span>
            <div>
              <strong>{name}</strong>
              <small>{user?.role_name || "Staff"}</small>
            </div>
          </div>
          <button className="ad-btn ad-btn-ghost" onClick={onLogout}>Logout</button>
        </div>
      </aside>

      {open && <div className="sl-overlay" onClick={onClose} />}
    </>
  );
}