import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { authApi } from "../api/authApi";
import { clearTokens, errorText } from "../api/axiosClient";
import { useAuth } from "../context/AuthContext";

export default function AdminLogin() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ username: "", password: "" });
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    clearTokens();
    try {
      const { data } = await authApi.adminLogin(form);
      await signIn(data);
      navigate("/admin/dashboard", { replace: true });
    } catch (err) {
      setError(errorText(err));
    }
  };

  return (
    <div className="auth-wrap">
      <form className="card" onSubmit={submit}>
        <h2>Super Admin Login</h2>
        {error && <div className="alert">{error}</div>}
        <label>Username</label>
        <input
          value={form.username}
          onChange={(e) => setForm({ ...form, username: e.target.value })}
          required
        />
        <label>Password</label>
        <input
          type="password"
          value={form.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })}
          required
        />
        <button className="btn">Login</button>
      </form>
    </div>
  );
}