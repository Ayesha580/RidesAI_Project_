import { useState } from "react";
import { Link } from "react-router-dom";
import { authApi } from "../api/authApi";
import { errorText } from "../api/axiosClient";
import Footer from "../components/Footer";
import Navbar from "../components/Navbar";
import "../styles/landing.css";
import "../styles/auth.css";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [debugUrl, setDebugUrl] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccessMessage("");
    setDebugUrl("");
    setBusy(true);

    try {
      const { data } = await authApi.forgotPassword(email.trim());
      setSuccessMessage(data?.message || "If an account exists with this email, a password reset link has been sent.");
      if (data?.debug_reset_url) {
        setDebugUrl(data.debug_reset_url);
      }
    } catch (err) {
      setError(errorText(err) || "Failed to process your request. Please try again.");
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
            <span className="au-eyebrow">ACCOUNT RECOVERY</span>
            <h1>Forgot your password?</h1>
            <p>No worries! Enter your registered account email and we'll send you a secure link to reset your password.</p>

            <div className="au-vector au-vector-login">
              <svg viewBox="0 0 420 250" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="75" y="35" width="270" height="175" rx="16" fill="#fff" stroke="#f0d8f0" strokeWidth="2"/>
                <circle cx="210" cy="95" r="32" fill="#fff3ff" stroke="#ff77ff" strokeWidth="2"/>
                <path d="M202 95C202 90.58 205.58 87 210 87C214.42 87 218 90.58 218 95V102H202V95Z" fill="#ff77ff" opacity=".2"/>
                <rect x="198" y="102" width="24" height="20" rx="4" fill="#ff77ff"/>
                <circle cx="210" cy="111" r="2.5" fill="#fff"/>
                <rect x="125" y="145" width="170" height="12" rx="6" fill="#fce7f3"/>
                <rect x="155" y="167" width="110" height="8" rx="4" fill="#fbcfe8"/>
                <circle cx="65" cy="70" r="20" fill="#fff0ff"/>
                <circle cx="355" cy="165" r="22" fill="#f8edff"/>
              </svg>
            </div>

            <div className="au-intro-points">
              <div><span>✓</span> Fast, secure time-limited reset links</div>
              <div><span>✓</span> Account protection with standard token encryption</div>
              <div><span>✓</span> Restore access to your business dashboard instantly</div>
            </div>
          </section>

          <form className="au-card au-login-card" onSubmit={submit}>
            <div className="au-card-head">
              <span className="au-card-label">RIDES AI RECOVERY</span>
              <h2>Reset password</h2>
              <p>Enter the email address associated with your account.</p>
            </div>

            {error && <div className="au-alert" role="alert">{error}</div>}

            {successMessage && (
              <div
                style={{
                  background: "#fdf2f8",
                  border: "1px solid #f472b6",
                  color: "#9d174d",
                  padding: "12px 16px",
                  borderRadius: "10px",
                  fontSize: "13.5px",
                  lineHeight: "1.5",
                  marginBottom: "16px",
                }}
              >
                <strong>Check your email:</strong>
                <p style={{ margin: "4px 0 0 0" }}>{successMessage}</p>
                {debugUrl && (
                  <div style={{ marginTop: "10px", fontSize: "12px", borderTop: "1px solid #fbcfe8", paddingTop: "8px" }}>
                    <span>Local Test Link: </span>
                    <a href={debugUrl} style={{ color: "#c026d3", fontWeight: "600", wordBreak: "break-all" }}>
                      Click here to reset password directly
                    </a>
                  </div>
                )}
              </div>
            )}

            {!successMessage && (
              <div className="au-field">
                <label htmlFor="email">Email Address</label>
                <input
                  id="email"
                  type="email"
                  name="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="email"
                  placeholder="e.g. rubaisha1705@gmail.com"
                  required
                />
              </div>
            )}

            {!successMessage ? (
              <button className="lp-btn lp-btn-primary au-submit" disabled={busy}>
                {busy ? "Sending..." : "Send Reset Link"}
              </button>
            ) : (
              <Link
                to="/login"
                className="lp-btn lp-btn-primary au-submit"
                style={{ textAlign: "center", textDecoration: "none" }}
              >
                Back to Sign in
              </Link>
            )}

            <p className="au-switch" style={{ marginTop: "16px" }}>
              Remember your password? <Link to="/login">Sign in</Link>
            </p>
          </form>
        </div>
      </main>
      <Footer />
    </div>
  );
}
