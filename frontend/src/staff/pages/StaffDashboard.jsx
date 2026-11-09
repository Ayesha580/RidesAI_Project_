import { Link } from "react-router-dom";
import StaffLayout from "../components/StaffLayout";
import { useAuth } from "../../context/AuthContext";
import { moduleIcon, moduleLabel } from "../../constants/modules";

export default function StaffDashboard() {
  const { user } = useAuth();
  const modules = user?.modules || [];

  return (
    <StaffLayout>
      {modules.length === 0 ? (
        <div className="ad-empty">
          <span>🔒</span>
          <h3>No access assigned yet</h3>
          <p>Your owner has not given this role any dashboard items. Please ask them to update your role.</p>
        </div>
      ) : (
        <div className="sl-grid">
          {modules.map((m) => (
            <Link className="sl-card" key={m} to={`/staff/${m}`}>
              <span>{moduleIcon(m)}</span>
              <strong>{moduleLabel(m)}</strong>
            </Link>
          ))}
        </div>
      )}
    </StaffLayout>
  );
}