import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export const Loading = () => <div className="center">Loading...</div>;

const ROLE_HOME = {
  owner: "/owner/dashboard",
  manager: "/manager/dashboard",
  kitchen: "/kitchen/dashboard",
  rider: "/rider/dashboard",
  employee: "/employee/dashboard",
  superadmin: "/admin/dashboard",
};

export const isUserOverrideOrActive = (user) =>
  Boolean(
    user?.is_manual_override ||
    user?.subscription_status === "active" ||
    user?.company_details?.is_manual_override ||
    user?.company_details?.subscription_status === "active"
  );

export const homeFor = (user) => {
  if (user?.role === "kitchen" || user?.role_name?.toLowerCase?.().includes("kitchen")) {
    return "/kitchen/dashboard";
  }
  if (
    user?.role === "rider" ||
    user?.role_name?.toLowerCase?.().includes("rider") ||
    user?.role_name?.toLowerCase?.().includes("delivery boy")
  ) {
    return "/rider/dashboard";
  }
  if (user?.role === "owner" && isUserOverrideOrActive(user)) {
    return "/owner/dashboard";
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

  if (user.role !== "superadmin") {
    // Admin review has been removed. Keep billing suspension protection.
    if (!isUserOverrideOrActive(user) && user.access_state === "suspended")
      return <Navigate to="/billing" replace />;
  }

  if (roles) {
    const isOwner = user.role === "owner";
    const roleMatches =
      roles.includes(user.role) ||
      (roles.includes("kitchen") && (user.role === "kitchen" || user.role_name?.toLowerCase?.().includes("kitchen"))) ||
      (roles.includes("rider") && (user.role === "rider" || user.role_name?.toLowerCase?.().includes("rider") || user.role_name?.toLowerCase?.().includes("delivery")));

    if (!roleMatches && !isOwner) {
      const target = homeFor(user);
      return <Navigate to={target === "/login" ? "/login" : target} replace />;
    }
  }

  return children;
}