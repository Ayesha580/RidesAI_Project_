import { useCallback, useEffect, useState } from "react";
import { billingApi } from "../../../api/billingApi";
import { errorText } from "../../../api/axiosClient";
import { useEffect as useReactEffect, useState as useReactState } from "react";

const STATUS = {
  trialing: { label: "Plan", tone: "pink" },
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


function ManualClientPanel({ info, suspended }) {
  const [payment, setPayment] = useReactState({ amount: "", currency: "USD", payment_reference: "", notes: "" });
  const [proof, setProof] = useReactState(null);
  const [email, setEmail] = useReactState({ email_address: "", domain: "", status: "not_started" });
  const [busy, setBusy] = useReactState(false);
  const [notice, setNotice] = useReactState("");
  const [error, setError] = useReactState("");
  useReactEffect(() => { billingApi.businessEmail().then(({ data }) => setEmail({ email_address: data.email_address || "", domain: data.domain || "", status: data.status || "not_started" })).catch(() => {}); }, []);
  const submitPayment = async (e) => {
    e.preventDefault(); setBusy(true); setError(""); setNotice("");
    const fd = new FormData(); Object.entries(payment).forEach(([k,v]) => fd.append(k,v)); if (proof) fd.append("proof", proof);
    try { await billingApi.submitManualPayment(fd); setNotice("Your payment details have been submitted for administrator review."); } catch (e2) { setError(errorText(e2)); } finally { setBusy(false); }
  };
  const saveEmail = async (e) => {
    e.preventDefault(); setBusy(true); setError(""); setNotice("");
    try { await billingApi.saveBusinessEmail(email); setNotice("Business email setup details saved."); } catch (e2) { setError(errorText(e2)); } finally { setBusy(false); }
  };
  const fmt = (v) => v ? new Date(v).toLocaleDateString(undefined,{day:"numeric",month:"short",year:"numeric"}) : "Not set";
  const pct = info.message_limit ? Math.min(100, (info.messages_used / info.message_limit) * 100) : 0;
  return <div className="se-stack">
    {error && <div className="ad-alert" role="alert">{error}</div>}
    {notice && <div className="se-ok" role="status">{notice}</div>}
    <section className="se-card">
      <div className="se-plan-top"><div><span className="se-eyebrow">Client access</span><h2>Initial access & renewal</h2></div><span className={`se-badge ${suspended ? "red" : info.status === "past_due" ? "amber" : "green"}`}>{suspended ? "Suspended" : info.status === "past_due" ? "Payment due" : info.status === "pending_approval" ? "Pending approval" : "Access active"}</span></div>
      <dl className="se-rows">
        <div><dt>Access expires</dt><dd>{fmt(info.access_expires_at)}</dd></div>
        <div><dt>Renewal due</dt><dd>{fmt(info.next_due_date)}</dd></div>
        <div><dt>Days remaining</dt><dd>{info.days_left ?? "—"}</dd></div>
        <div><dt>Grace period ends</dt><dd>{fmt(info.grace_ends_at)}</dd></div>
      </dl>
      <div style={{marginTop:16}}><div style={{display:"flex",justifyContent:"space-between",fontSize:13,marginBottom:7}}><strong>Message usage</strong><span>{info.messages_used} / {info.message_limit}</span></div><div style={{height:9,background:"#eee",borderRadius:99,overflow:"hidden"}}><div style={{height:"100%",width:`${pct}%`,background:"#c026d3",borderRadius:99}} /></div><small style={{display:"block",marginTop:7,color:"#777"}}>{info.messages_remaining} messages remaining in this usage period. The limit is set by the administrator.</small></div>
    </section>
    <section className="se-card">
      <h3>Manual payment</h3><p className="se-sub">There are no subscription plans or automatic online checkout for this client. Submit your transfer details for admin confirmation.</p>
      <div className="se-ok">{info.payment_instructions || "Please contact the RidesAI administrator for current payment details."}</div>
      {info.latest_payment?.status === "pending" && <div className="se-ok">Your latest payment is awaiting administrator review.</div>}
      {info.status === "payment_rejected" && <div className="ad-alert">Your last payment submission was not approved. Please contact the administrator or submit corrected details.</div>}
      {info.status === "past_due" && <div className="ad-alert">Your renewal is overdue. You have a three-day grace period before dashboard access is suspended.</div>}
      <form onSubmit={submitPayment} className="se-stack">
        <div className="se-two"><div className="se-field"><label>Amount paid (optional)</label><input type="number" min="0" step="0.01" value={payment.amount} onChange={e=>setPayment({...payment,amount:e.target.value})} /></div><div className="se-field"><label>Currency</label><input value={payment.currency} onChange={e=>setPayment({...payment,currency:e.target.value.toUpperCase()})} maxLength={10}/></div></div>
        <div className="se-field"><label>Transaction/reference number</label><input value={payment.payment_reference} onChange={e=>setPayment({...payment,payment_reference:e.target.value})} /></div>
        <div className="se-field"><label>Payment proof (optional)</label><input type="file" accept="image/*,.pdf" onChange={e=>setProof(e.target.files?.[0] || null)} /></div>
        <div className="se-field"><label>Additional notes</label><input value={payment.notes} onChange={e=>setPayment({...payment,notes:e.target.value})} /></div>
        <div className="se-actions"><button className="ad-btn ad-btn-primary" disabled={busy || info.latest_payment?.status === "pending"}>{busy ? "Submitting..." : "Submit payment for review"}</button></div>
      </form>
    </section>
    <section className="se-card">
      <h3>Business Gmail setup</h3><p className="se-sub">Set up or connect the email account your business will use. RidesAI does not ask for or store your Google password.</p>
      <div className="se-actions" style={{marginBottom:14}}><a className="ad-btn ad-btn-ghost" href="https://accounts.google.com/signup" target="_blank" rel="noreferrer">Create a Gmail account ↗</a><a className="ad-btn ad-btn-ghost" href="https://workspace.google.com/" target="_blank" rel="noreferrer">Google Workspace ↗</a></div>
      <form onSubmit={saveEmail} className="se-stack">
        <div className="se-field"><label>Business email address</label><input type="email" placeholder="yourbusiness@gmail.com or info@yourdomain.com" value={email.email_address} onChange={e=>setEmail({...email,email_address:e.target.value})}/></div>
        <div className="se-two"><div className="se-field"><label>Business domain (if applicable)</label><input placeholder="yourbusiness.com" value={email.domain} onChange={e=>setEmail({...email,domain:e.target.value})}/></div><div className="se-field"><label>Setup status</label><select value={email.status} onChange={e=>setEmail({...email,status:e.target.value})}><option value="not_started">Not started</option><option value="in_progress">In progress</option><option value="completed">Completed</option></select></div></div>
        <div className="se-actions"><button className="ad-btn ad-btn-primary" disabled={busy}>{busy ? "Saving..." : "Save business email details"}</button></div>
      </form>
      <p className="se-note">A custom address such as info@yourdomain.com requires a domain and Google Workspace. A free @gmail.com address can be created through Google directly.</p>
    </section>
  </div>;
}

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

  if (info.mode === "manual") return <ManualClientPanel info={info} suspended={suspended || info.status === "suspended"} />;

  const st = STATUS[info.status] || { label: info.status, tone: "grey" };
  const trialPct =
    info.status === "trialing" && info.days_left != null
      ? Math.min(100, Math.max(0, (info.days_left / 30) * 100))
      : null;
  const hasPortal = !info.can_subscribe && info.status !== "pending_approval";

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
                  disabled={busy || info.status === "pending_approval"}
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
    </div>
  );
}