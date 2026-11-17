import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export const Loading = () => <div className="center">Loading...</div>;

const ROLE_HOME = {
  owner: "/owner/dashboard",
  manager: "/manager/dashboard",
  kitchen: "/kitchen/dashboard",
  employee: "/employee/dashboard",
};

export const isUserOverrideOrActive = (user) =>
  Boolean(
    user?.is_manual_override === true ||
    user?.company_details?.is_manual_override === true ||
    user?.subscription_status === "active" ||
    user?.company_details?.subscription_status === "active"
  );

export const homeFor = (user) => {
  if (isUserOverrideOrActive(user)) {
    return ROLE_HOME[user?.role] || "/owner/dashboard";
  }
  if (user?.redirect === "/select-plan" && isUserOverrideOrActive(user)) {
    return ROLE_HOME[user?.role] || "/owner/dashboard";
  }
  return user?.redirect || ROLE_HOME[user?.role] || "/login";
};

export function AuthOnly({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <Loading />;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

export function Guard({ roles, children }) {
  const { user, loading } = useAuth();
  if (loading) return <Loading />;
  if (!user) return <Navigate to="/login" replace />;
  const normalizedRole = user.role === "Employee" ? "staff" : user.role;

  const overrideActive = isUserOverrideOrActive(user);

  if (user.access_state === "suspended" && !overrideActive)
    return <Navigate to={normalizedRole === "owner" ? "/billing" : "/account-suspended"} replace />;

  if (roles && !roles.includes(normalizedRole)) {
    const target = homeFor(user);
    return <Navigate to={target === "/login" ? "/login" : target} replace />;
  }

  return children;
}