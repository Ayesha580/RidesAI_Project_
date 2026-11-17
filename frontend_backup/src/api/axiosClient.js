import axios from "axios";

export const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api";

// ---------------- Tokens ----------------
export const saveTokens = ({ access, refresh }) => {
  if (access) localStorage.setItem("access", access);
  if (refresh) localStorage.setItem("refresh", refresh);
};

export const clearTokens = () => {
  localStorage.removeItem("access");
  localStorage.removeItem("refresh");
};

// ---------------- Axios instance ----------------
const axiosClient = axios.create({
  baseURL: API,
  timeout: 30000,
});

axiosClient.interceptors.request.use((config) => {
  const token = localStorage.getItem("access");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

let refreshing = null;

axiosClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    const refresh = localStorage.getItem("refresh");

    if (error.response?.status === 401 && refresh && !original._retry) {
      original._retry = true;

      try {
        refreshing =
          refreshing ||
          axios
            .post(`${API}/accounts/token/refresh/`, { refresh })
            .finally(() => (refreshing = null));

        const { data } = await refreshing;
        saveTokens(data);

        original.headers.Authorization = `Bearer ${data.access}`;
        return axiosClient(original);
      } catch {
        clearTokens();
        window.location.href = "/login";
      }
    }

    return Promise.reject(error);
  }
);

export function errorText(err) {
  const d = err?.response?.data;
  if (!d) return err?.message || "Something went wrong.";
  if (typeof d === "string") return d;
  if (d.error) return d.error;
  if (d.detail) return d.detail;
  return Object.entries(d)
    .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(" ") : v}`)
    .join(" | ");
}

export default axiosClient;