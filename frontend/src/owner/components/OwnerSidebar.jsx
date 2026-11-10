
import { Link, NavLink } from "react-router-dom";
import logo from "../../assets/logo.webp";

const css = `
.ol-sidebar{
  width:270px;
  min-width:270px;
  height:100vh;
  position:sticky;
  top:0;
  z-index:50;
  display:flex;
  flex-direction:column;
  padding:20px 14px 14px;
  background:#fff;
  border-right:1px solid #eee8f0;
  overflow:hidden;
  transition:width .25s ease,min-width .25s ease,padding .25s ease;
}
.ol-sidebar.collapsed{
  width:72px;
  min-width:72px;
  padding:20px 10px 14px;
}
.ol-sidebar-head{
  display:flex;
  align-items:center;
  justify-content:space-between;
  min-height:42px;
  padding:0 5px;
  margin-bottom:28px;
}
.ol-brand{
  display:flex;
  align-items:center;
  gap:10px;
  min-width:0;
  text-decoration:none;
  overflow:hidden;
}
.ol-brand img{
  width:34px;
  height:34px;
  object-fit:contain;
  flex-shrink:0;
}
.ol-brand-text{
  display:flex;
  flex-direction:column;
  white-space:nowrap;
}
.ol-brand-text strong{
  font-size:16px;
  font-weight:800;
  letter-spacing:.5px;
  color:#302b38;
}
.ol-brand-text small{
  font-size:9px;
  letter-spacing:1.3px;
  color:#bd72bd;
  margin-top:2px;
}
.ol-collapse-btn{
  width:29px;
  height:29px;
  min-width:29px;
  display:grid;
  place-items:center;
  border:1px solid #f0e8f1;
  background:#fff;
  color:#918596;
  border-radius:8px;
  cursor:pointer;
  font-size:15px;
  transition:all .2s;
}
.ol-collapse-btn:hover{
  background:#fff0ff;
  border-color:#ffd0ff;
  color:#c026d3;
}
.ol-sidebar.collapsed .ol-sidebar-head{
  justify-content:center;
  padding:0;
}
.ol-sidebar.collapsed .ol-brand-text,
.ol-sidebar.collapsed .ol-collapse-btn{
  display:none;
}
.ol-sidebar.collapsed .ol-brand{
  justify-content:center;
}
.ol-nav-area{
  flex:1;
  min-height:0;
  overflow-y:auto;
  overflow-x:hidden;
  padding:0 1px 15px;
}
.ol-nav-area::-webkit-scrollbar{width:4px}
.ol-nav-area::-webkit-scrollbar-thumb{
  background:#eadbea;
  border-radius:10px;
}
.ol-group{margin-bottom:23px}
.ol-nav-title{
  display:block;
  padding:0 11px;
  margin-bottom:9px;
  font-size:10px;
  font-weight:750;
  letter-spacing:1.1px;
  text-transform:uppercase;
  color:#aaa1ae;
  white-space:nowrap;
}
.ol-nav{
  display:flex;
  flex-direction:column;
  gap:4px;
}
.ol-nav-item{
  min-height:40px;
  display:flex;
  align-items:center;
  gap:12px;
  padding:8px 11px;
  border-radius:10px;
  text-decoration:none;
  color:#625b69;
  font-size:13px;
  font-weight:500;
  white-space:nowrap;
  transition:all .18s ease;
  position:relative;
}
.ol-nav-item:hover{
  background:#fff5ff;
  color:#bd35bd;
}
.ol-nav-item.active{
  background:#fff0ff;
  color:#c026d3;
  font-weight:700;
}
.ol-nav-item.active::before{
  content:"";
  position:absolute;
  left:0;
  top:9px;
  bottom:9px;
  width:3px;
  border-radius:5px;
  background:#ff77ff;
}
.ol-nav-icon{
  width:20px;
  min-width:20px;
  display:grid;
  place-items:center;
  font-size:15px;
}
.ol-nav-label{
  overflow:hidden;
  text-overflow:ellipsis;
}
.ol-nav-item.locked{
  opacity:.45;
  cursor:not-allowed;
}
.ol-nav-item.locked:hover{background:transparent}
.ol-nav-item em{
  margin-left:auto;
  font-size:9px;
  font-style:normal;
  color:#a18ca5;
  background:#f7f2f8;
  padding:3px 6px;
  border-radius:5px;
}
.ol-sidebar.collapsed .ol-nav-title,
.ol-sidebar.collapsed .ol-nav-label,
.ol-sidebar.collapsed .ol-nav-item em{
  display:none;
}
.ol-sidebar.collapsed .ol-group{margin-bottom:13px}
.ol-sidebar.collapsed .ol-nav-item{
  justify-content:center;
  padding:0;
  width:44px;
  height:42px;
  margin:0 auto;
}
.ol-sidebar.collapsed .ol-nav-icon{
  width:auto;
  min-width:0;
  font-size:17px;
}
.ol-sidebar.collapsed .ol-nav-item.active::before{
  left:0;
}
.ol-sidebar-footer{
  display:flex;
  align-items:center;
  gap:10px;
  padding:12px 7px 2px;
  border-top:1px solid #f1ebf2;
  overflow:hidden;
}
.ol-footer-avatar{
  width:32px;
  height:32px;
  min-width:32px;
  border-radius:10px;
  display:grid;
  place-items:center;
  background:#ffe5ff;
  color:#c026d3;
  font-size:13px;
  font-weight:750;
}
.ol-footer-info{
  min-width:0;
  display:flex;
  flex-direction:column;
  gap:3px;
  white-space:nowrap;
}
.ol-footer-info strong{
  font-size:11px;
  color:#39313f;
  overflow:hidden;
  text-overflow:ellipsis;
}
.ol-footer-info small{
  font-size:10px;
  color:#a29aa7;
  overflow:hidden;
  text-overflow:ellipsis;
}
.ol-sidebar.collapsed .ol-sidebar-footer{
  justify-content:center;
  padding:12px 0 2px;
}
.ol-sidebar.collapsed .ol-footer-info{display:none}
.ol-overlay{display:none}
@media(max-width:900px){
  .ol-sidebar,
  .ol-sidebar.collapsed{
    position:fixed;
    left:0;
    top:0;
    width:270px;
    min-width:270px;
    height:100dvh;
    padding:20px 14px 14px;
    transform:translateX(-105%);
    box-shadow:8px 0 35px rgba(35,15,40,.10);
  }
  .ol-sidebar.open{transform:translateX(0)}
  .ol-sidebar.collapsed .ol-sidebar-head{
    justify-content:space-between;
    padding:0 5px;
  }
  .ol-sidebar.collapsed .ol-brand-text,
  .ol-sidebar.collapsed .ol-collapse-btn,
  .ol-sidebar.collapsed .ol-nav-title,
  .ol-sidebar.collapsed .ol-nav-label,
  .ol-sidebar.collapsed .ol-nav-item em,
  .ol-sidebar.collapsed .ol-footer-info{
    display:initial;
  }
  .ol-sidebar.collapsed .ol-brand-text{
    display:flex;
  }
  .ol-sidebar.collapsed .ol-nav-title{display:block}
  .ol-sidebar.collapsed .ol-nav-item em{display:block}
  .ol-sidebar.collapsed .ol-nav-item{
    justify-content:flex-start;
    width:auto;
    height:auto;
    padding:8px 11px;
    margin:0;
  }
  .ol-sidebar.collapsed .ol-nav-icon{
    width:20px;
    min-width:20px;
  }
  .ol-sidebar.collapsed .ol-sidebar-footer{
    justify-content:flex-start;
    padding:12px 7px 2px;
  }
  .ol-overlay{
    display:block;
    position:fixed;
    inset:0;
    background:rgba(35,20,40,.35);
    backdrop-filter:blur(2px);
    z-index:40;
  }
}
`;

export default function OwnerSidebar({
  groups = [],
  locked,
  billingPath,
  open,
  collapsed = false,
  onToggleCollapse,
  onClose,
  user
}) {
  const name =
    [user?.first_name, user?.last_name].filter(Boolean).join(" ") ||
    user?.full_name ||
    user?.username ||
    "Owner";

  return (
    <>
      <style>{css}</style>

      <aside className={`ol-sidebar ${collapsed ? "collapsed" : ""} ${open ? "open" : ""}`}>
        <div className="ol-sidebar-head">
          <Link to="/owner/dashboard" className="ol-brand" onClick={onClose}>
            <img src={logo} alt="RidesAI" />
            <div className="ol-brand-text">
              <strong>RIDES AI</strong>
              <small>BUSINESS PLATFORM</small>
            </div>
          </Link>

          <button
            className="ol-collapse-btn"
            onClick={onToggleCollapse}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? "›" : "‹"}
          </button>
        </div>

        <div className="ol-nav-area">
          {groups.map((group) => (
            <div className="ol-group" key={group.title}>
              <span className="ol-nav-title">{group.title}</span>

              <nav className="ol-nav">
                {group.items.map((item) =>
                  locked && item.to !== billingPath ? (
                    <span
                      key={item.to}
                      className="ol-nav-item locked"
                      aria-disabled="true"
                      title={collapsed ? `${item.label} - Locked` : ""}
                    >
                      <span className="ol-nav-icon">{item.icon}</span>
                      <span className="ol-nav-label">{item.label}</span>
                      <em>Locked</em>
                    </span>
                  ) : (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      end={item.to === "/owner/dashboard"}
                      onClick={onClose}
                      title={collapsed ? item.label : ""}
                      className={({ isActive }) =>
                        `ol-nav-item ${isActive ? "active" : ""}`
                      }
                    >
                      <span className="ol-nav-icon">{item.icon}</span>
                      <span className="ol-nav-label">{item.label}</span>
                    </NavLink>
                  )
                )}
              </nav>
            </div>
          ))}
        </div>

        <div className="ol-sidebar-footer" title={name}>
          <div className="ol-footer-avatar">{name.charAt(0).toUpperCase()}</div>
          <div className="ol-footer-info">
            <strong>{name}</strong>
            <small>{user?.company_name || "Business Owner"}</small>
          </div>
        </div>
      </aside>

      {open && <div className="ol-overlay" onClick={onClose} />}
    </>
  );
}
