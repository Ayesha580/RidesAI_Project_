import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import "../styles/landing.css";
import "../styles/admin.css";
import "../styles/owner.css";
import "../styles/roles.css";

export default function AccountSuspended() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="sd-wrap">
      <div className="ad-empty">
        <span>⏸️</span>
        <h3>Access is paused</h3>
        <p>
          {user?.company_name ? `${user.company_name}'s` : "Your company's"} subscription has ended.
          Please ask your business owner to renew it. Your access will return as soon as they do.
        </p>
        <button
          className="ad-btn ad-btn-ghost"
          style={{ marginTop: 18 }}
          onClick={() => {
            signOut();
            navigate("/login");
          }}
        >
          Logout
        </button>
      </div>
    </div>
  );
}