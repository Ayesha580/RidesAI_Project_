// src/pages/Billing.jsx
import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { billingApi } from "../api/billingApi";
import { errorText } from "../api/axiosClient";
import { Loading } from "../components/Guards";
import Footer from "../components/Footer";
import Navbar from "../components/Navbar";
import OwnerLayout from "../owner/components/OwnerLayout";
import { useAuth } from "../context/AuthContext";
import "../styles/Landing.css";
import "../styles/auth.css";

const STATUS = {
  trialing: { label: "Free trial", tone: "pink" },
  trial_expired: { label: "Trial ended", tone: "red" },
  active: { label: "Active", tone: "green" },
  canceling: { label: "Cancels at period end", tone: "amber" },
  past_due: { label: "Payment due", tone: "amber" },
  canceled: { label: "Canceled", tone: "red" },
  revoked: { label: "Ended", tone: "red" },
  pending_approval: { label: "Approval pending", tone: "grey" },
};

const INCLUDED = [
  "Your AI-powered business manager",
  "Products and services management",
  "Customer and operational automation",
  "Centralized business dashboard",
  "Employee and role management",
  "Business insights and notifications",
];

const fmtDate = (d) =>
  d ? new Date(d).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : "-";

export default function Billing() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const [info, setInfo] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const { data } = await billingApi.overview();
      setInfo(data);
    } catch (e) {
      setError(errorText(e));
    }
  }, []);

  useEffect(() => {
    if (user?.role === "owner") load();
  }, [user, load]);

  if (!user) return <Loading />;

  if (user.role !== "owner") {
    return (
      <div className="lp">
        <Navbar />
        <main className="au-main au-main-center">
          <div className="au-card au-pending">
            <div className="au-pending-icon"><span>🔒</span></div>
            <h2>Subscription problem</h2>
            <p className="au-pending-text">
              Your restaurant's subscription needs attention. Please contact your restaurant owner.
            </p>
            <div className="au-pending-actions">
              <button className="lp-btn ghost" onClick={() => { signOut(); navigate("/login"); }}>Logout</button>
            </div>
          </div>
        </main>
        <Footer />
      </div>
    );
  }

  const payNow = async () => {
    setBusy(true);
    setError("");
    try {
      const { data } = await billingApi.customerSession();
      if (data.action === "new_subscription") {
        window.location.href = data.checkout_url;
      } else {
        const url = data.session?.customer_portal_url;
        if (url) window.open(url, "_blank");
        else setError("Customer portal link was not found.");
      }
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const toggleCancel = async (fn) => {
    setBusy(true);
    setError("");
    try {
      await fn();
      await load();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const suspended = user.access_state === "suspended";
  const st = info ? STATUS[info.status] || { label: info.status, tone: "grey" } : null;
  const trialPct = info?.status === "trialing" && info.days_left != null ? Math.min(100, Math.max(0, (info.days_left / 30) * 100)) : null;

  return (
    <OwnerLayout
      title="Billing"
      subtitle="Your plan, trial and payment details."
      locked={suspended}
    >
      {suspended && (
        <div className="ow-banner warn">
          <span>⚠️</span>
          <div>
            <strong>Your access is paused</strong>
            <small>Your trial or subscription has ended. Pay to reopen your dashboard.</small>
          </div>
        </div>
      )}
      {error && <div className="ad-alert" role="alert">{error}</div>}

      {!info ? (
        !error && <div className="ad-skeleton" style={{ height: 320 }} />
      ) : (
        <div className="bl-grid">
          <section className="ad-card bl-plan">
            <div className="bl-plan-head">
              <div>
                <span className="bl-eyebrow">Current plan</span>
                <h3>{info.plan || "Standard"} plan</h3>
              </div>
              <span className={`bl-badge ${st.tone}`}>{st.label}</span>
            </div>

            <div className="bl-price">
              <strong>${info.amount_due ?? "-"}</strong>
              <small>/ {info.billing_cycle || "month"}</small>
            </div>

            {trialPct !== null && (
              <div className="bl-trial">
                <div className="bl-trial-top">
                  <span>Free trial</span>
                  <strong>{info.days_left} days left</strong>
                </div>
                <div className="bl-bar"><i style={{ width: `${trialPct}%` }} /></div>
              </div>
            )}

            <dl className="bl-rows">
              <div><dt>Status</dt><dd>{st.label}</dd></div>
              <div><dt>Next due / trial end</dt><dd>{fmtDate(info.next_due_date)}</dd></div>
              <div><dt>Days left</dt><dd>{info.days_left ?? "-"}</dd></div>
              {info.grace_ends_at && (
                <div className="warn"><dt>Grace period ends</dt><dd>{fmtDate(info.grace_ends_at)}</dd></div>
              )}
            </dl>

            <div className="ad-actions">
              {info.can_subscribe && (
                <button className="ad-btn ad-btn-primary" onClick={payNow} disabled={busy}>
                  {busy ? "Please wait..." : `Pay now ($${info.amount_due})`}
                </button>
              )}
              {!info.can_subscribe && info.status !== "pending_approval" && (
                <button className="ad-btn ad-btn-ghost" onClick={payNow} disabled={busy}>
                  Manage subscription ↗
                </button>
              )}
              {info.status === "active" && (
                <button className="ad-btn ad-btn-danger" onClick={() => toggleCancel(billingApi.cancel)} disabled={busy}>
                  Cancel at period end
                </button>
              )}
              {info.status === "canceling" && (
                <button className="ad-btn ad-btn-primary" onClick={() => toggleCancel(billingApi.resume)} disabled={busy}>
                  Resume subscription
                </button>
              )}
            </div>
          </section>

          <aside className="ad-card bl-side">
            <h3>What's included</h3>
            <ul>
              {INCLUDED.map((t) => (
                <li key={t}><span>✓</span>{t}</li>
              ))}
            </ul>
            <p>Payments are handled securely by Polar. You can cancel anytime and keep access until the period ends.</p>
          </aside>
        </div>
      )}
    </OwnerLayout>
  );
}