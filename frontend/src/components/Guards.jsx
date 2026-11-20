import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export const Loading = () => <div className="center">Loading...</div>;

const ROLE_HOME = {
  owner: "/owner/dashboard",
  manager: "/manager/dashboard",
  kitchen: "/kitchen/dashboard",
  rider: "/rider/dashboard",
  employee: "/staff/dashboard",
  Employee: "/staff/dashboard",
  staff: "/staff/dashboard",
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
  const roleLower = String(user?.role || "").toLowerCase();
  const roleNameLower = String(user?.role_name || "").toLowerCase();
  const modules = Array.isArray(user?.modules) ? user.modules : [];

  if (roleLower === "kitchen" || roleNameLower.includes("kitchen")) {
    return "/kitchen/dashboard";
  }
  if (
    roleLower === "rider" ||
    roleNameLower.includes("rider") ||
    roleNameLower.includes("delivery boy") ||
    roleNameLower.includes("delivery")
  ) {
    return "/rider/dashboard";
  }
  if (roleLower === "owner" && isUserOverrideOrActive(user)) {
    return "/owner/dashboard";
  }

  if (roleNameLower.includes("packer") || modules.includes("fulfillment")) {
    return "/staff/fulfillment";
  }

  if (roleLower === "staff" || roleLower === "employee") {
    return user?.redirect || (modules.length === 1 ? `/staff/${modules[0]}` : "/staff/dashboard");
  }

  return user?.redirect || ROLE_HOME[roleLower] || ROLE_HOME[user?.role] || "/login";
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
    const roleLower = String(user.role || "").toLowerCase();
    const isOwner = roleLower === "owner";
    const isStaff = roleLower === "staff" || roleLower === "employee";
    const roleMatches =
      roles.map((r) => r.toLowerCase()).includes(roleLower) ||
      (roles.includes("staff") && isStaff) ||
      (roles.includes("employee") && isStaff) ||
      (roles.includes("kitchen") && (roleLower === "kitchen" || user.role_name?.toLowerCase?.().includes("kitchen"))) ||
      (roles.includes("rider") && (roleLower === "rider" || user.role_name?.toLowerCase?.().includes("rider") || user.role_name?.toLowerCase?.().includes("delivery")));

    if (!roleMatches && !isOwner) {
      const target = homeFor(user);
      if (typeof window !== "undefined" && target === window.location.pathname) {
        return children;
      }
      return <Navigate to={target === "/login" ? "/login" : target} replace />;
    }
  }

  return children;
}