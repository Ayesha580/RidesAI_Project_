import { useCallback, useEffect, useState } from "react";
import { billingApi } from "../../../api/billingApi";
import { errorText } from "../../../api/axiosClient";

const STATUS = {
  trialing: { label: "Plan", tone: "pink" },
  trial_expired: { label: "Trial ended", tone: "red" },
  active: { label: "Active", tone: "green" },
  canceling: { label: "Cancels at period end", tone: "amber" },
  past_due: { label: "Payment due", tone: "amber" },
  canceled: { label: "Canceled", tone: "red" },
  revoked: { label: "Ended", tone: "red" },
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

const cycleLabel = (c) => (c === "yearly" ? "year" : "month");

// status ke hisaab se "agli date" ka label
const dateLabel = (status) =>
  ({
    trialing: "Trial ends",
    active: "Renews on",
    canceling: "Access ends on",
    past_due: "Payment due since",
    trial_expired: "Trial ended on",
  }[status] || "Next date");


export default function BillingTab({ suspended }) {
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
  useEffect(() => { load(); }, [load]);

  // trial / ended: Polar checkout. Active: Polar customer portal (card, invoices)
  const payNow = async (portal = false) => {
  setBusy(true); setError("");
  try {
    const { data } = await billingApi.customerSession(portal);
    if (data.action === "new_subscription") {
      window.location.href = data.checkout_url;
      return;
    }
    const url = data.session?.customer_portal_url;
    if (url) window.open(url, "_blank");
    else setError("Customer portal link was not found.");
  } catch (e) {
    setError(errorText(e));
  } finally {
    setBusy(false);
  }
};

  const toggleCancel = async (fn) => {
    setBusy(true); setError("");
    try {
      await fn();
      await load();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  if (!info) {
    return error
      ? <div className="ad-alert" role="alert">{error}</div>
      : <div className="ad-skeleton" style={{ height: 360 }} />;
  }


  const st = STATUS[info.status] || { label: info.status, tone: "grey" };
  const trialPct =
    info.status === "trialing" && info.days_left != null
      ? Math.min(100, Math.max(0, (info.days_left / 30) * 100))
      : null;
  const hasPortal = !info.can_subscribe;

  return (
    <div className="se-stack">
      {suspended && (
        <div className="ow-banner warn">
          <span>⚠️</span>
          <div>
            <strong>Your access is paused</strong>
            <small>Your trial or subscription has ended. Pay to reopen your dashboard.</small>
          </div>
        </div>
      )}
      {info.status === "canceling" && (
        <div className="ow-banner warn">
          <span>ℹ️</span>
          <div>
            <strong>Your subscription will not renew</strong>
            <small>You keep access until {fmtDate(info.next_due_date)}. Resume anytime before then.</small>
          </div>
        </div>
      )}
      {info.status === "past_due" && (
        <div className="ow-banner warn">
          <span>💳</span>
          <div>
            <strong>Your last payment failed</strong>
            <small>Update your card to keep your account active.</small>
          </div>
        </div>
      )}
      {error && <div className="ad-alert" role="alert">{error}</div>}

      <div className="se-bill">
        {/* ---------- Current plan + renewal ---------- */}
        <section className="se-card">
          <div className="se-plan-top">
            <div>
              <span className="se-eyebrow">Current plan</span>
              <h2>{info.plan || "Standard"} plan</h2>
            </div>
            <span className={`se-badge ${st.tone}`}>{st.label}</span>
          </div>

          <div className="se-price">
            <strong>${info.amount_due ?? "-"}</strong>
            <small>/ {cycleLabel(info.billing_cycle)}</small>
          </div>

          {trialPct !== null && (
            <div className="se-trial">
              <div className="se-trial-top">
                <strong>{info.days_left} days left</strong>
              </div>
              <div className="se-bar"><i style={{ width: `${trialPct}%` }} /></div>
            </div>
          )}

          <dl className="se-rows">
            <div><dt>Status</dt><dd>{st.label}</dd></div>
            <div><dt>{dateLabel(info.status)}</dt><dd>{fmtDate(info.next_due_date)}</dd></div>
            <div><dt>Days left</dt><dd>{info.days_left ?? "-"}</dd></div>
            <div><dt>Billing cycle</dt><dd style={{ textTransform: "capitalize" }}>{info.billing_cycle || "-"}</dd></div>
            {info.status === "active" && (
              <div><dt>Next payment</dt><dd>${info.amount_due}</dd></div>
            )}
            {info.grace_ends_at && (
              <div className="warn"><dt>Grace period ends</dt><dd>{fmtDate(info.grace_ends_at)}</dd></div>
            )}
          </dl>

          <div className="se-actions">
            {info.can_subscribe && (
              <button className="ad-btn ad-btn-primary" onClick={payNow} disabled={busy}>
                {busy ? "Please wait..." : `Pay now ($${info.amount_due})`}
              </button>
            )}
            {info.status === "canceling" && (
              <button className="ad-btn ad-btn-primary" onClick={() => toggleCancel(billingApi.resume)} disabled={busy}>
                Resume subscription
              </button>
            )}
            {info.status === "active" && (
              <button
                className="ad-btn ad-btn-danger"
                disabled={busy}
                onClick={() => {
                  if (window.confirm("Cancel at the end of this billing period? You keep access until then.")) {
                    toggleCancel(billingApi.cancel);
                  }
                }}
              >
                Cancel at period end
              </button>
            )}
          </div>
        </section>

        {/* ---------- Payment method + included ---------- */}
        <div className="se-stack">
          <section className="se-card">
            <div className="se-pay">
              <span className="se-pay-ico">💳</span>
              <div>
                <h3>Payment method</h3>
                <p>
                  {hasPortal
                    ? "Change your card, download invoices and see payment history on Polar."
                    : "Add a payment method to start your subscription."}
                </p>
                <button
                  className="ad-btn ad-btn-ghost"
                  onClick={() => payNow(hasPortal)}
                  disabled={busy}
                >
                  {hasPortal ? "Change card / Manage payment ↗" : "Add payment method"}
                </button>
              </div>
            </div>
          </section>

          <section className="se-card">
            <h3>What's included</h3>
            <p className="se-sub">Everything in your plan</p>
            <ul className="se-incl">
              {INCLUDED.map((t) => <li key={t}><span>✓</span>{t}</li>)}
            </ul>
            <p className="se-note">
              Payments are handled securely by Polar. You can cancel anytime and keep access until the period ends.
            </p>
          </section>
        </div>
      </div>
      <section className="se-card" style={{ marginTop: 16 }}>
        <h3>Payment history</h3>
        {!info.payment_history?.length ? <p className="se-sub">No payments recorded yet.</p> : <div style={{ overflowX: "auto" }}><table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}><thead><tr><th style={{ textAlign: "left", padding: 10 }}>Date</th><th style={{ textAlign: "left", padding: 10 }}>Amount</th><th style={{ textAlign: "left", padding: 10 }}>Status</th></tr></thead><tbody>{info.payment_history.map((payment) => <tr key={payment.id}><td style={{ padding: 10, borderTop: "1px solid #eee" }}>{fmtDate(payment.created_at)}</td><td style={{ padding: 10, borderTop: "1px solid #eee" }}>{payment.amount ?? "-"} {payment.currency || ""}</td><td style={{ padding: 10, borderTop: "1px solid #eee", textTransform: "capitalize" }}>{payment.status}</td></tr>)}</tbody></table></div>}
      </section>
      {info.message_limit != null && <section className="se-card" style={{ marginTop: 16 }}><h3>AI message usage</h3><p className="se-sub">{info.messages_used || 0} used · {info.messages_remaining ?? info.message_limit} remaining of {info.message_limit} messages this period.</p></section>}
    </div>
  );
}