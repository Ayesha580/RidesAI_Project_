// src/App.jsx
import { Navigate, Route, Routes, useParams } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import { AuthOnly, Guard, Loading, homeFor } from "./components/Guards";
import Catalog from "./components/catalog/Catalog";
// public / shared
import AccountSuspended from "./pages/AccountSuspended";
import AdminCompanies from "./pages/AdminCompanies";
import AdminLogin from "./pages/AdminLogin";
import Billing from "./pages/Billing";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import PaymentSuccess from "./pages/PaymentSuccess";
import PendingApproval from "./pages/PendingApproval";
import Register from "./pages/Register";
import VerifyEmail from "./pages/VerifyEmail";
import OwnerPlaceholder from "./owner/pages/OwnerPlaceholder";
import OwnerSettings from "./owner/pages/OwnerSettings";

// owner
import OwnerDashboard from "./owner/pages/OwnerDashboard";
import OwnerRoles from "./owner/pages/OwnerRoles";
import OwnerStaff from "./owner/pages/OwnerStaff";

// staff
import StaffDashboard from "./staff/pages/StaffDashboard";
import StaffLayout from "./staff/components/StaffLayout";
import SelectPlan from "./pages/SelectPlan";
import Checkout from "./pages/Checkout";
import Features from "./pages/Features";
import How from "./pages/Howitworks";
import Industries from "./pages/Industries";
import Businesses from "./pages/Businesses";
import Pricing from "./pages/Plans";
function Home() {
  const { user, loading } = useAuth();
  if (loading) return <Loading />;
  if (!user) return <Landing />;
  return <Navigate to={homeFor(user)} replace />;
}
function OwnerModulePage() {
  const { moduleKey } = useParams();
  return <Catalog moduleKey={moduleKey} />;
}
function ModuleGuard({ children }) {
  const { user } = useAuth();
  const { moduleKey } = useParams();
  return user?.modules?.includes(moduleKey) ? children : <Navigate to="/staff/dashboard" replace />;
}

function StaffModulePage() {
  const { moduleKey } = useParams();
  return (
    <StaffLayout title={moduleLabel(moduleKey)}>
      <div className="ad-empty">
        <span>{moduleIcon(moduleKey)}</span>
        <h3>{moduleLabel(moduleKey)}</h3>
        <p>This page is coming soon.</p>
      </div>
    </StaffLayout>
  );
}
export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/verify-email" element={<VerifyEmail />} />
      <Route path="/admin-login" element={<AdminLogin />} />
      <Route path="/select-plan" element={<SelectPlan />} />
      <Route path="/checkout" element={<Checkout />} />
      {/* <Route path="/select-plan" element={<AuthOnly><SelectPlan /></AuthOnly>} />
      <Route path="/checkout" element={<AuthOnly><Checkout /></AuthOnly>} /> */}
      <Route path="/pending-approval" element={<AuthOnly><PendingApproval /></AuthOnly>} />
      <Route path="/account-suspended" element={<AuthOnly><AccountSuspended /></AuthOnly>} />
      <Route path="/payment-success" element={<AuthOnly><PaymentSuccess /></AuthOnly>} />
      <Route path="/billing" element={<AuthOnly><Billing /></AuthOnly>} />
      <Route path="/features" element={<Features />} />
      <Route path="/how" element={<How />} />
      <Route path="/industries" element={<Industries />} />
      <Route path="/businesses" element={<Businesses />} />
      <Route path="/pricing" element={<Pricing />} />
      <Route path="/admin/dashboard" element={<Guard roles={["superadmin"]}><AdminCompanies /></Guard>} />

      <Route path="/owner/dashboard" element={<Guard roles={["owner"]}><OwnerDashboard /></Guard>} />
      <Route path="/owner/staff" element={<Guard roles={["owner"]}><OwnerStaff /></Guard>} />
      <Route path="/owner/roles" element={<Guard roles={["owner"]}><OwnerRoles /></Guard>} />

      <Route
        path="/owner/m/:moduleKey"
        element={
          <Guard roles={["owner"]}>
            <OwnerModulePage />
          </Guard>
        }
      />

      {["ai-agent", "conversations", "knowledge", "channels"].map((p) => (
        <Route
          key={p}
          path={`/owner/${p}`}
          element={
            <Guard roles={["owner"]}>
              <OwnerPlaceholder />
            </Guard>
          }
        />
      ))}

      <Route path="/owner/catalog" element={<Guard roles={["owner"]}><Catalog /></Guard>} />
      <Route path="/owner/settings" element={<AuthOnly><OwnerSettings /></AuthOnly>} />
      <Route path="/owner/billing" element={<Navigate to="/owner/settings?tab=billing" replace />} />

      <Route path="/staff/dashboard" element={<Guard roles={["staff"]}><StaffDashboard /></Guard>} />
      <Route
        path="/staff/:moduleKey"
        element={
          <Guard roles={["staff"]}>
            <ModuleGuard><StaffModulePage /></ModuleGuard>
          </Guard>
        }
      />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}