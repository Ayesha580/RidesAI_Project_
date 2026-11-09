import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { authApi } from "../api/authApi";
import { clearTokens, errorText } from "../api/axiosClient";
import { useAuth } from "../context/AuthContext";
import Footer from "../components/Footer";
import Navbar from "../components/Navbar";
import "../styles/landing.css";
import "../styles/auth.css";

export default function Login() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ username: "", password: "" });
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});
  const [busy, setBusy] = useState(false);
  const [verificationEmail, setVerificationEmail] = useState("");

  const change = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
    setFieldErrors({ ...fieldErrors, [e.target.name]: "" });
  };

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setFieldErrors({});
    setVerificationEmail("");
    setBusy(true);
    clearTokens();

    try {
      const { data } = await authApi.login(form);
      await signIn(data);
      navigate(data.redirect, { replace: true });
    } catch (err) {
      const responseData = err?.response?.data;
      setError(errorText(err));
      if (responseData?.verification_required) {
        setVerificationEmail(responseData.email || "");
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="lp">
      <Navbar />
      <main className="au-main">
        <div className="au-login-layout">
          <section className="au-intro">
            <span className="au-eyebrow">RIDES AI BUSINESS PLATFORM</span>
            <h1>Welcome back.</h1>
            <p>Manage your business, customers and daily operations from one intelligent workspace.</p>

            <div className="au-vector au-vector-login">
              <svg viewBox="0 0 420 250" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="75" y="35" width="270" height="175" rx="16" fill="#fff" stroke="#f0d8f0" strokeWidth="2"/>
                <rect x="95" y="55" width="230" height="28" rx="7" fill="#fff3ff"/>
                <circle cx="111" cy="69" r="5" fill="#ff77ff"/>
                <rect x="125" y="65" width="85" height="7" rx="3.5" fill="#e8c8e8"/>
                <rect x="95" y="98" width="105" height="90" rx="9" fill="#fff8ff"/>
                <rect x="110" y="155" width="12" height="22" rx="3" fill="#ffb5ff"/>
                <rect x="130" y="137" width="12" height="40" rx="3" fill="#ff77ff"/>
                <rect x="150" y="120" width="12" height="57" rx="3" fill="#dca0ed"/>
                <rect x="170" y="145" width="12" height="32" rx="3" fill="#ffb5ff"/>
                <rect x="215" y="98" width="110" height="40" rx="8" fill="#fff5ff"/>
                <circle cx="235" cy="118" r="9" fill="#ff77ff" opacity=".2"/>
                <path d="M231 118L234 121L240 114" stroke="#d94bd9" strokeWidth="2" strokeLinecap="round"/>
                <rect x="250" y="113" width="58" height="7" rx="3.5" fill="#e8c8e8"/>
                <rect x="215" y="148" width="110" height="40" rx="8" fill="#f9f4ff"/>
                <circle cx="235" cy="168" r="9" fill="#dca0ed" opacity=".25"/>
                <path d="M231 168L234 171L240 164" stroke="#b66bd1" strokeWidth="2" strokeLinecap="round"/>
                <rect x="250" y="163" width="58" height="7" rx="3.5" fill="#e8c8e8"/>
                <circle cx="65" cy="70" r="22" fill="#fff0ff"/>
                <path d="M58 70H72M65 63V77" stroke="#e85de8" strokeWidth="2.5" strokeLinecap="round"/>
                <circle cx="355" cy="165" r="24" fill="#f8edff"/>
                <path d="M355 151L359 161L369 165L359 169L355 179L351 169L341 165L351 161L355 151Z" fill="#d28ce8"/>
                <circle cx="335" cy="35" r="5" fill="#ff77ff"/>
                <circle cx="55" cy="190" r="5" fill="#dca0ed"/>
              </svg>
            </div>

            <div className="au-intro-points">
              <div><span>✓</span> Manage orders and customer requests</div>
              <div><span>✓</span> Keep your team and operations organized</div>
              <div><span>✓</span> Let your AI agent handle routine inquiries</div>
            </div>
            <div className="au-intro-note">
              <span className="au-note-dot"/>
              Your business workspace, all in one place.
            </div>
          </section>

          <form className="au-card au-login-card" onSubmit={submit}>
            <div className="au-card-head">
              <span className="au-card-label">YOUR WORKSPACE</span>
              <h2>Sign in to your account</h2>
              <p>Enter your credentials to continue.</p>
            </div>

            {error && <div className="au-alert" role="alert">{error}</div>}

            {verificationEmail && (
              <button
                type="button"
                className="au-resend"
                onClick={async () => {
                  try {
                    await authApi.resendVerification(verificationEmail);
                    setError("If this account is still unverified, a fresh verification email has been sent.");
                  } catch {
                    setError("Could not resend the verification email. Please try again later.");
                  }
                }}
              >
                Resend verification email
              </button>
            )}

            <div className="au-field">
              <label htmlFor="username">Username</label>
              <input
                id="username"
                name="username"
                value={form.username}
                onChange={change}
                autoComplete="username"
                placeholder="Enter your username"
                required
              />
              {fieldErrors.username && <small className="au-field-error">{fieldErrors.username}</small>}
            </div>

            <div className="au-field">
              <label htmlFor="password">Password</label>
              <input
                id="password"
                type="password"
                name="password"
                value={form.password}
                onChange={change}
                autoComplete="current-password"
                placeholder="Enter your password"
                required
              />
              {fieldErrors.password && <small className="au-field-error">{fieldErrors.password}</small>}
            </div>

            <button className="lp-btn lp-btn-primary au-submit" disabled={busy}>
              {busy ? "Please wait..." : "Sign in"}
            </button>

            <p className="au-switch">
              Don't have an account? <Link to="/register">Register your business</Link>
            </p>
          </form>
        </div>
      </main>
      <Footer />
    </div>
  );
}