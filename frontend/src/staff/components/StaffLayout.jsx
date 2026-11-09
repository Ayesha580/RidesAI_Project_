// src/staff/components/StaffLayout.jsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import StaffSidebar from "./StaffSidebar";
import StaffTopbar from "./StaffTopbar";
import "../../styles/landing.css";
import "../../styles/admin.css";

const css = `
.sl-shell{display:flex;min-height:100vh;background:var(--sl-bg,#f9fafb)}
.sl-main{flex:1;min-width:0;display:flex;flex-direction:column}
.sl-content{padding:24px}

/* dashboard cards */
.sl-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:14px}
.sl-card{
  display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px;
  padding:26px 14px;border-radius:16px;text-align:center;text-decoration:none;color:inherit;
  background:var(--sl-surface,#fff);border:1px solid var(--sl-border,#e5e7eb);
  transition:transform .15s,box-shadow .15s;
}
.sl-card:hover{transform:translateY(-2px);box-shadow:0 8px 22px rgba(0,0,0,.08)}
.sl-card span{font-size:30px}
.sl-card strong{font-size:14px}

@media (max-width:900px){.sl-content{padding:16px}}
`;

export default function StaffLayout({ title, subtitle, action, children }) {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const [menu, setMenu] = useState(false);

  const modules = user?.modules || [];
  const first = (user?.first_name || user?.username || "there").split(" ")[0];

  const logout = () => {
    signOut();
    navigate("/login");
  };

  return (
    <>
      <style>{css}</style>
      <div className="sl-shell">
        <StaffSidebar
          modules={modules}
          open={menu}
          onClose={() => setMenu(false)}
          user={user}
          onLogout={logout}
        />
        <main className="sl-main">
          <StaffTopbar
            title={title || `Welcome, ${first}`}
            subtitle={subtitle ?? [user?.role_name, user?.company_name].filter(Boolean).join(" · ")}
            action={action}
            onMenu={() => setMenu(true)}
          />
          <div className="sl-content">{children}</div>
        </main>
      </div>
    </>
  );
}