import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { authApi } from "../api/authApi";
import { errorText } from "../api/axiosClient";
import Footer from "../components/Footer";
import Navbar from "../components/Navbar";
import "../styles/landing.css";
import "../styles/auth.css";

export default function ResetPassword() {
  const { uid, token } = useParams();
  const navigate = useNavigate();

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");

    if (!password || password.length < 8) {
      setError("Password must be at least 8 characters long.");
      return;
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setBusy(true);
    try {
      await authApi.resetPassword(uid, token, password);
      setSuccess(true);
    } catch (err) {
      setError(errorText(err) || "Failed to reset password. The link may have expired.");
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
            <span className="au-eyebrow">SECURITY & ACCESS</span>
            <h1>Choose a new password.</h1>
            <p>Set a strong password for your RidesAI business account to regain access.</p>

            <div className="au-vector au-vector-login">
              <svg viewBox="0 0 420 250" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="75" y="35" width="270" height="175" rx="16" fill="#fff" stroke="#f0d8f0" strokeWidth="2"/>
                <rect x="110" y="70" width="200" height="35" rx="8" fill="#fdf2f8"/>
                <circle cx="130" cy="87" r="4" fill="#ff77ff"/>
                <circle cx="145" cy="87" r="4" fill="#ff77ff"/>
                <circle cx="160" cy="87" r="4" fill="#ff77ff"/>
                <circle cx="175" cy="87" r="4" fill="#ff77ff"/>
                <circle cx="190" cy="87" r="4" fill="#ff77ff"/>
                <circle cx="205" cy="87" r="4" fill="#ff77ff"/>
                <rect x="110" y="125" width="200" height="35" rx="8" fill="#fdf2f8"/>
                <circle cx="130" cy="142" r="4" fill="#ec4899"/>
                <circle cx="145" cy="142" r="4" fill="#ec4899"/>
                <circle cx="160" cy="142" r="4" fill="#ec4899"/>
                <circle cx="175" cy="142" r="4" fill="#ec4899"/>
                <circle cx="190" cy="142" r="4" fill="#ec4899"/>
                <circle cx="205" cy="142" r="4" fill="#ec4899"/>
                <circle cx="355" cy="165" r="22" fill="#f8edff"/>
              </svg>
            </div>

            <div className="au-intro-points">
              <div><span>✓</span> Minimum 8 characters</div>
              <div><span>✓</span> Instant activation upon submission</div>
              <div><span>✓</span> Automatic sign-in ready</div>
            </div>
          </section>

          <form className="au-card au-login-card" onSubmit={submit}>
            <div className="au-card-head">
              <span className="au-card-label">RIDES AI RECOVERY</span>
              <h2>Set new password</h2>
              <p>Please enter your new password below.</p>
            </div>

            {error && <div className="au-alert" role="alert">{error}</div>}

            {success ? (
              <div>
                <div
                  style={{
                    background: "#f0fdf4",
                    border: "1px solid #86efac",
                    color: "#166534",
                    padding: "16px",
                    borderRadius: "10px",
                    fontSize: "14px",
                    lineHeight: "1.5",
                    marginBottom: "20px",
                    textAlign: "center",
                  }}
                >
                  <div style={{ fontSize: "24px", marginBottom: "6px" }}>🎉</div>
                  <strong>Password Reset Successful!</strong>
                  <p style={{ margin: "6px 0 0 0" }}>
                    Your password has been securely updated. You can now log in with your new credentials.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => navigate("/login")}
                  className="lp-btn lp-btn-primary au-submit"
                  style={{ width: "100%" }}
                >
                  Go to Sign in
                </button>
              </div>
            ) : (
              <>
                <div className="au-field">
                  <label htmlFor="new_password">New Password</label>
                  <input
                    id="new_password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="At least 8 characters"
                    autoComplete="new-password"
                    required
                  />
                </div>

                <div className="au-field">
                  <label htmlFor="confirm_password">Confirm New Password</label>
                  <input
                    id="confirm_password"
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Re-enter your new password"
                    autoComplete="new-password"
                    required
                  />
                </div>

                <button className="lp-btn lp-btn-primary au-submit" disabled={busy}>
                  {busy ? "Updating..." : "Reset Password"}
                </button>

                <p className="au-switch" style={{ marginTop: "16px" }}>
                  Remember your old password? <Link to="/login">Sign in</Link>
                </p>
              </>
            )}
          </form>
        </div>
      </main>
      <Footer />
    </div>
  );
}
