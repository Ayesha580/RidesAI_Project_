// src/App.jsx
import { Navigate, Route, Routes, useParams } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import { AuthOnly, Guard, Loading, homeFor } from "./components/Guards";
import Catalog from "./components/catalog/Catalog";
import { moduleIcon, moduleLabel } from "./constants/modules";
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
import ForgotPassword from "./pages/ForgotPassword";
import ResetPassword from "./pages/ResetPassword";
import OwnerSettings from "./owner/pages/OwnerSettings";

// owner
import OwnerDashboard from "./owner/pages/OwnerDashboard";
import OwnerRoles from "./owner/pages/OwnerRoles";
import OwnerStaff from "./owner/pages/OwnerStaff";
import OwnerLayout from "./owner/components/OwnerLayout";

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

import OrdersDashboard from "./operations/OrdersDashboard";
import RiderDeliveries from "./operations/RiderDeliveries";
import AgentConsole from "./operations/AgentConsole";
import AgentConversations from "./operations/AgentConversations";
import CallsDashboard from "./operations/CallsDashboard";
import PublicAgentPage from "./operations/PublicAgentPage";
import DeliveriesDashboard from "./operations/DeliveriesDashboard";
import WhatsAppSettings from "./operations/components/agent-settings/WhatsAppSettings";
import KnowledgeBaseForm from "./operations/components/agent-settings/KnowledgeBaseForm";
import KitchenDashboard from "./operations/KitchenDashboard";
import RiderDashboard from "./operations/RiderDashboard";
import PharmacyPrescriptions from "./operations/PharmacyPrescriptions";
import PharmacyBatches from "./operations/PharmacyBatches";
import ClinicAppointments from "./operations/ClinicAppointments";
import ClinicDoctors from "./operations/ClinicDoctors";
import ClinicPatients from "./operations/ClinicPatients";
import HospitalDashboard from "./operations/HospitalDashboard";
import AnalyticsReports from "./operations/AnalyticsReports";
import RetailFulfillment from "./operations/RetailFulfillment";
import RetailReturns from "./operations/RetailReturns";

function Home() {
  const { user, loading } = useAuth();
  if (loading) return <Loading />;
  if (!user) return <Landing />;
  return <Navigate to={homeFor(user)} replace />;
}
function OwnerModulePage() {
  const { moduleKey } = useParams();
  if (moduleKey === "orders" || moduleKey === "deliveries") return <OrdersDashboard />;
  if (moduleKey === "calls") return <CallsDashboard />;
  if (moduleKey === "prescriptions") return <PharmacyPrescriptions />;
  if (moduleKey === "expiry_tracking") return <PharmacyBatches />;
  if (moduleKey === "departments") return <HospitalDashboard defaultTab="departments" />;
  if (moduleKey === "lab_tests") return <HospitalDashboard defaultTab="lab_tests" />;
  if (moduleKey === "reports") return <AnalyticsReports />;
  if (moduleKey === "appointments") return <ClinicAppointments />;
  if (moduleKey === "doctors") return <ClinicDoctors />;
  if (moduleKey === "patients") return <ClinicPatients />;
  if (moduleKey === "fulfillment") return <RetailFulfillment />;
  if (moduleKey === "returns") return <RetailReturns />;
  return (
    <OwnerLayout title={moduleLabel(moduleKey)}>
      <Catalog moduleKey={moduleKey} />
    </OwnerLayout>
  );
}
function ModuleGuard({ children }) {
  const { user, loading } = useAuth();
  const { moduleKey } = useParams();
  if (loading) return <Loading />;
  if (!user) return <Navigate to="/login" replace />;
  const roleNameLower = String(user?.role_name || "").toLowerCase();
  const isPacker = roleNameLower.includes("packer");
  if (isPacker && ["fulfillment", "orders"].includes(moduleKey)) {
    return children;
  }
  return user?.modules?.includes(moduleKey) ? children : <Navigate to="/staff/dashboard" replace />;
}

function StaffModulePage() {
  const { moduleKey } = useParams();
  if (moduleKey === "orders") return <OrdersDashboard staff />;
  if (moduleKey === "deliveries") return <DeliveriesDashboard />;
  if (moduleKey === "my_deliveries") return <RiderDeliveries />;
  if (moduleKey === "prescriptions") return <PharmacyPrescriptions staff />;
  if (moduleKey === "expiry_tracking") return <PharmacyBatches staff />;
  if (moduleKey === "departments") return <HospitalDashboard staff defaultTab="departments" />;
  if (moduleKey === "lab_tests") return <HospitalDashboard staff defaultTab="lab_tests" />;
  if (moduleKey === "reports") return <AnalyticsReports staff />;
  if (moduleKey === "appointments") return <ClinicAppointments staff />;
  if (moduleKey === "doctors") return <ClinicDoctors staff />;
  if (moduleKey === "patients") return <ClinicPatients staff />;
  if (moduleKey === "fulfillment") return <RetailFulfillment staff />;
  if (moduleKey === "returns") return <RetailReturns staff />;
  if (["products", "menu", "medicines", "services"].includes(moduleKey)) return <StaffLayout title={moduleLabel(moduleKey)}><Catalog moduleKey={moduleKey} /></StaffLayout>;
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
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password/:uid/:token" element={<ResetPassword />} />
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

      <Route path="/agent/:publicId" element={<PublicAgentPage />} />

      {["ai-agent", "conversations", "calls", "knowledge", "channels", "whatsapp"].map((p) => (
        <Route
          key={p}
          path={`/owner/${p}`}
          element={
            <Guard roles={["owner"]}>
              {p === "ai-agent" ? (
                <AgentConsole />
              ) : p === "conversations" ? (
                <AgentConversations />
              ) : p === "calls" ? (
                <CallsDashboard />
              ) : p === "knowledge" ? (
                <KnowledgeBaseForm />
              ) : (
                <WhatsAppSettings />
              )}
            </Guard>
          }
        />
      ))}

      <Route
        path="/owner/catalog"
        element={
          <Guard roles={["owner"]}>
            <OwnerLayout title="Catalog">
              <Catalog />
            </OwnerLayout>
          </Guard>
        }
      />
      <Route path="/owner/settings" element={<AuthOnly><OwnerSettings /></AuthOnly>} />
      <Route path="/owner/analytics" element={<Guard roles={["owner"]}><AnalyticsReports /></Guard>} />
      <Route path="/owner/reports" element={<Guard roles={["owner"]}><AnalyticsReports /></Guard>} />
      <Route path="/owner/billing" element={<Navigate to="/owner/settings?tab=billing" replace />} />
      <Route path="/owner/tables" element={<Navigate to="/owner/m/tables" replace />} />
      <Route path="/owner/reservations" element={<Navigate to="/owner/m/reservations" replace />} />

      <Route path="/staff/dashboard" element={<Guard roles={["staff"]}><StaffDashboard /></Guard>} />
      <Route path="/kitchen/dashboard" element={<Guard roles={["kitchen", "owner"]}><KitchenDashboard /></Guard>} />
      <Route path="/rider/dashboard" element={<Guard roles={["rider", "owner"]}><RiderDashboard /></Guard>} />
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