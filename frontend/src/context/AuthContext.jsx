import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { authApi } from "../api/authApi";
import { clearTokens, saveTokens } from "../api/axiosClient";

const Ctx = createContext(null);
export const useAuth = () => useContext(Ctx);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(!!localStorage.getItem("access"));

  const loadMe = useCallback(async () => {
    try {
      const { data } = await authApi.me();
      if (data) {
        const isOverrideOrActive =
          data.is_manual_override === true ||
          data.company_details?.is_manual_override === true ||
          data.subscription_status === "active" ||
          data.company_details?.subscription_status === "active";

        if (isOverrideOrActive) {
          if (data.redirect === "/select-plan" || data.redirect === "/billing") {
            data.redirect = "/owner/dashboard";
          }
          if (data.access_state === "payment_required" || data.access_state === "suspended") {
            data.access_state = "ok";
          }
        }
      }
      setUser(data);
      return data;
    } catch {
      clearTokens();
      setUser(null);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (localStorage.getItem("access")) loadMe();
    else setLoading(false);
  }, [loadMe]);

  const signIn = async (tokens) => {
    saveTokens(tokens);
    return loadMe();
  };

  const signOut = () => {
    clearTokens();
    setUser(null);
  };

  return (
    <Ctx.Provider value={{ user, loading, loadMe, signIn, signOut }}>
      {children}
    </Ctx.Provider>
  );
}