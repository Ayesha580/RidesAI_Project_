import { useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { homeFor } from "../components/Guards";
import Footer from "../components/Footer";
import Navbar from "../components/Navbar";
import "../styles/landing.css";
import "../styles/auth.css";

const STEPS = [
  { title: "Account created", text: "Your details and documents are submitted.", state: "done" },
  { title: "Admin review", text: "We are checking your documents.", state: "active" },
  { title: "Free trial starts", text: "30 days free once you are approved.", state: "todo" },
];

export default function PendingApproval() {
  const { user, loadMe, signOut } = useAuth();
  const navigate = useNavigate();
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    const id = setInterval(loadMe, 15000);
    return () => clearInterval(id);
  }, [loadMe]);

  if (user && user.access_state !== "pending_approval") {
    return <Navigate to={homeFor(user)} replace />;
  }

  const check = async () => {
    setChecking(true);
    try {
      await loadMe();
    } finally {
      setChecking(false);
    }
  };

  return (
    <div className="lp">
      <Navbar />

      <main className="au-main au-main-center">
        <div className="au-card au-pending">
          <div className="au-pending-icon">
            <span className="au-pending-ring" />
            <span>⏳</span>
          </div>

          <h2>Waiting for approval</h2>
          <p className="au-pending-text">
            Your account has been created. An admin will review your documents and
            approve it, then your <strong>30-day free trial</strong> will start.
          </p>

          <ol className="au-timeline">
            {STEPS.map((s, i) => (
              <li key={s.title} className={`au-tl-item ${s.state}`}>
                <span className="au-tl-dot">{s.state === "done" ? "✓" : i + 1}</span>
                <div>
                  <strong>{s.title}</strong>
                  <small>{s.text}</small>
                </div>
              </li>
            ))}
          </ol>

          <p className="au-pending-note">
            <span className="lp-live-dot" /> As soon as you are approved, this page will take you to your dashboard.
          </p>

          <div className="au-pending-actions">
            <button className="lp-btn" onClick={check} disabled={checking}>
              {checking ? "Checking..." : "Check status"}
            </button>
            <button
              className="lp-btn ghost"
              onClick={() => {
                signOut();
                navigate("/login");
              }}
            >
              Logout
            </button>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}