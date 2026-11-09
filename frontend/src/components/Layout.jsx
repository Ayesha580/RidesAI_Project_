import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { billingApi } from "../api/billingApi";
import { useAuth } from "../context/AuthContext";

function TrialBanner() {
  const [info, setInfo] = useState(null);

  useEffect(() => {
    billingApi.overview().then((r) => setInfo(r.data)).catch(() => {});
  }, []);

  if (!info || info.status !== "trialing") return null;

  return (
    <div className="banner">
      Free trial: {info.days_left} din baqi hain.{" "}
      <Link to="/billing">Abhi subscribe karo</Link>
    </div>
  );
}

export default function Layout({ title, children }) {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();

  const logout = () => {
    const isAdmin = user?.role === "superadmin";
    signOut();
    navigate(isAdmin ? "/admin-login" : "/login");
  };

  return (
    <div>
      <header className="nav">
        <strong>{title}</strong>
        <div className="nav-right">
          <span>
            {user?.full_name} ({user?.role})
          </span>
          {user?.role === "owner" && <Link to="/billing">Billing</Link>}
          <button className="btn small ghost" onClick={logout}>
            Logout
          </button>
        </div>
      </header>
      {user?.role === "owner" && user?.access_state === "ok" && <TrialBanner />}
      <main className="container">{children}</main>
    </div>
  );
}