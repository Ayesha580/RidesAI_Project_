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