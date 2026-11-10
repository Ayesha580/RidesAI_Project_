
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { moduleIcon } from "../../constants/modules";
import OwnerSidebar from "./OwnerSidebar";
import OwnerTopbar from "./OwnerTopbar";
import "../../styles/landing.css";
import "../../styles/admin.css";
import "../styles/owner.css";
import "../../styles/roles.css";

const BILLING = "/owner/settings";

const css = `
.ol-shell{
  --ol-brand:#ff77ff;
  --ol-brand-ink:#fff;
  --ol-brand-soft:#fff0ff;
  --ol-bg:#faf9fc;
  --ol-surface:#fff;
  --ol-border:#f0eaf2;
  --ol-muted:#898493;
  --ol-text:#302b38;
  min-height:100vh;
  display:flex;
  background:var(--ol-bg);
  color:var(--ol-text);
}
.ol-main{
  flex:1;
  min-width:0;
  display:flex;
  flex-direction:column;
}
.ol-content{
  width:100%;
  max-width:1700px;
  margin:0 auto;
  padding:28px 30px 45px;
  box-sizing:border-box;
}
.ol-page-head{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:18px;
  flex-wrap:wrap;
  margin-bottom:25px;
}
.ol-page-head h1{
  margin:0;
  font-size:25px;
  line-height:1.3;
  font-weight:750;
  letter-spacing:-.5px;
  color:#302b38;
}
.ol-page-head p{
  margin:6px 0 0;
  font-size:13.5px;
  line-height:1.6;
  color:#898493;
}
.ol-page-action{
  display:flex;
  align-items:center;
  gap:10px;
  flex-wrap:wrap;
}
.ol-shell .ad-btn-primary{
  background:#ff77ff;
  color:#fff;
  border:1px solid #ff77ff;
  border-radius:10px;
  font-weight:650;
  box-shadow:0 3px 10px rgba(255,119,255,.16);
  transition:all .2s ease;
}
.ol-shell .ad-btn-primary:hover{
  background:#f05cf0;
  border-color:#f05cf0;
  box-shadow:0 5px 14px rgba(255,119,255,.22);
  transform:translateY(-1px);
}
@media(max-width:1100px){
  .ol-content{padding:24px 20px 35px}
}
@media(max-width:900px){
  .ol-content{padding:20px 15px 30px}
  .ol-page-head{margin-bottom:20px}
  .ol-page-head h1{font-size:22px}
}
@media(max-width:480px){
  .ol-content{padding:17px 12px 25px}
  .ol-page-head{gap:13px}
  .ol-page-head h1{font-size:20px}
  .ol-page-head p{font-size:12.5px}
  .ol-page-action{width:100%}
}
`;

export default function OwnerLayout({ title, subtitle, action, locked = false, children }) {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const [menu, setMenu] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  const groups = useMemo(() => {
    const business = (user?.owner_nav || []).map((m) => ({
      to: `/owner/m/${m.key}`,
      icon: moduleIcon(m.key),
      label: m.label,
    }));

    return [
      {
        title: "General",
        items: [{ to: "/owner/dashboard", icon: "🏠", label: "Dashboard" }],
      },
      ...(business.length
        ? [{ title: user?.business_label || "Business", items: business }]
        : []),
      {
        title: "AI Agent",
        items: [
          { to: "/owner/ai-agent", icon: "🤖", label: "AI agent" },
          { to: "/owner/conversations", icon: "💬", label: "Conversations" },
          { to: "/owner/knowledge", icon: "📚", label: "Knowledge base" },
          { to: "/owner/channels", icon: "🔗", label: "Channels & links" },
        ],
      },
      {
        title: "Team",
        items: [
          { to: "/owner/staff", icon: "👥", label: "Employee" },
          { to: "/owner/roles", icon: "🛡️", label: "Employee Role and Access" },
        ],
      },
      {
        title: "Account",
        items: [{ to: BILLING, icon: "💳", label: "Setting" }],
      },
    ];
  }, [user]);

  const logout = () => {
    signOut();
    navigate("/login");
  };

  return (
    <>
      <style>{css}</style>

      <div className="ol-shell">
        <OwnerSidebar
          groups={groups}
          locked={locked}
          billingPath={BILLING}
          open={menu}
          collapsed={collapsed}
          onToggleCollapse={() => setCollapsed((value) => !value)}
          onClose={() => setMenu(false)}
          user={user}
        />

        <main className="ol-main">
          <OwnerTopbar
            groups={groups}
            locked={locked}
            billingPath={BILLING}
            user={user}
            onMenu={() => setMenu(true)}
            onLogout={logout}
          />

          <div className="ol-content">
            {(title || action) && (
              <div className="ol-page-head">
                <div>
                  {title && <h1>{title}</h1>}
                  {subtitle && <p>{subtitle}</p>}
                </div>
                {action && <div className="ol-page-action">{action}</div>}
              </div>
            )}

            {children}
          </div>
        </main>
      </div>
    </>
  );
}
