import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { authApi } from "../api/authApi";
import { errorText, saveTokens } from "../api/axiosClient";
import Navbar from "../components/Navbar";
import Footer from "../components/Footer";
import "../styles/landing.css";
import "../styles/verify-email.css";

export default function VerifyEmail() {
  const [params] = useSearchParams();
  const [email, setEmail] = useState(params.get("email") || "");
  const [otp, setOtp] = useState("");
  const [message, setMessage] = useState(
    params.get("sent") === "0"
      ? "Your account was created, but the verification email could not be delivered. Configure Gmail SMTP, then use Resend code."
      : ""
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function verify(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const { data } = await authApi.verifyEmail(otp, email);
      saveTokens(data);
      setMessage(data.message || "Email verified successfully.");
      window.location.replace(data.redirect || "/owner/dashboard");
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  async function resend() {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const { data } = await authApi.resendVerification(email);
      setMessage(data?.verification_email_sent === false
        ? "We couldn't send the email. Please check the backend SMTP configuration and try again."
        : "If the account is unverified, a new six-digit code has been sent.");
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="ve-page">
      <Navbar />
      <main className="ve-main">
        <div className="ve-decoration ve-decoration-one" />
        <div className="ve-decoration ve-decoration-two" />

        <form className="ve-card" onSubmit={verify}>
          <div className="ve-icon">
            <svg viewBox="0 0 64 64" fill="none">
              <rect x="8" y="15" width="48" height="35" rx="9" stroke="currentColor" strokeWidth="2.5" />
              <path d="M11 20L32 36L53 20" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
              <circle cx="49" cy="46" r="10" fill="#fff" stroke="#D94FD9" strokeWidth="2.5" />
              <path d="M45 46L48 49L53 43" stroke="#D94FD9" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>

          <span className="ve-eyebrow">EMAIL VERIFICATION</span>
          <h1>Verify your email address</h1>
          <p className="ve-description">
Enter the six-digit code sent to your business email. If you haven't received it, check Spam or use Resend code below.
          </p>

          <div className="ve-email">
            <span className="ve-email-icon">✉</span>
            <div>
              <span>VERIFICATION EMAIL</span>
              <strong>{email || "Enter your email address below"}</strong>
            </div>
          </div>

          {message && <div className="ve-success" role="status">{message}</div>}
          {error && <div className="ve-error" role="alert">{error}</div>}

          <div className="ve-field">
            <label htmlFor="ve-email">Email address</label>
            <input
              id="ve-email"
              name="email"
              type="email"
              autoComplete="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div className="ve-field">
            <label htmlFor="ve-otp">Enter verification code</label>
            <input
              id="ve-otp"
              name="otp"
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              pattern="[0-9]{6}"
              maxLength={6}
              placeholder="000000"
              value={otp}
              onChange={(e) => setOtp(e.target.value.replace(/\D/g, "").slice(0, 6))}
              required
              autoFocus
            />
            <span className="ve-hint">The code expires in five minutes.</span>
          </div>

          <button
            type="submit"
            className="ve-verify-btn"
            disabled={busy || otp.length !== 6 || !email}
          >
            {busy ? "Verifying..." : <>Verify email address <span>→</span></>}
          </button>

          <div className="ve-resend">
            <span>Didn't receive the code?</span>
            <button type="button" onClick={resend} disabled={busy || !email}>
              Resend code
            </button>
          </div>

          <div className="ve-divider" />

          <Link to="/login" className="ve-login-link">
            <span>←</span> Back to login
          </Link>

          
        </form>
      </main>
      <Footer />
    </div>
  );
}