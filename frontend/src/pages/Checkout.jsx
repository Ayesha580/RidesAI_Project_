import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { billingApi } from "../api/billingApi";
import { errorText } from "../api/axiosClient";
import Footer from "../components/Footer";
import Navbar from "../components/Navbar";
import "../styles/landing.css";
import "../styles/checkout.css";

export default function Checkout() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    billingApi.getPlanPage()
      .then(({ data }) => {
        if (data.already_active) {
          window.location.replace(data.redirect);
          return;
        }
        if (!data.selected_plan_id) {
          navigate("/select-plan", { replace: true });
          return;
        }
        setData(data);
      })
      .catch((e) => setError(errorText(e)));
  }, [navigate]);

  const plan = data?.plans.find((p) => p.id === data.selected_plan_id);
  const reg = data?.registration;

  async function pay() {
    if (busy || !plan) return;
    setBusy(true);
    setError("");
    try {
      const { data: res } = await billingApi.startCheckout();
      if (!res.checkout_url) {
        setError("Could not start checkout. Please try again.");
        setBusy(false);
        return;
      }
      window.location.href = res.checkout_url;
    } catch (e) {
      setError(errorText(e));
      setBusy(false);
    }
  }

  return (
    <div className="co-page">
      <Navbar />
      <main className="co-main">
        <div className="co-heading">
          <span className="co-eyebrow">SECURE CHECKOUT</span>
          <h1>Review your order</h1>
          <p>You're one step away from activating your Rides AI business workspace.</p>
        </div>

        {error && <div className="co-error" role="alert">{error}</div>}

        {!data && !error && (
          <div className="co-loading">
            <div className="co-loader" />
            <p>Preparing your checkout...</p>
          </div>
        )}

        {data && !plan && (
          <div className="co-error">
            Your selected plan could not be found. Please select a plan again.
            <Link to="/select-plan">Choose a plan</Link>
          </div>
        )}

        {data && plan && (
          <div className="co-layout">
            <section className="co-left">
              <div className="co-section">
                <div className="co-section-heading">
                  <div className="co-step">01</div>
                  <div>
                    <h2>Business information</h2>
                    <p>Details associated with your account</p>
                  </div>
                </div>

                <div className="co-business-card">
                  <div className="co-business-icon">B</div>
                  <div className="co-business-main">
                    <span>BUSINESS NAME</span>
                    <strong>{reg?.business_name || "Your business"}</strong>
                    <p>{reg?.business_type || "Business account"}</p>
                  </div>
                  <span className="co-verified">Verified</span>
                </div>

                <div className="co-details">
                  <div className="co-detail">
                    <span>Account owner</span>
                    <strong>{reg?.owner_name || "—"}</strong>
                  </div>
                  <div className="co-detail">
                    <span>Email address</span>
                    <strong>{reg?.email || "—"}</strong>
                  </div>
                  <div className="co-detail">
                    <span>Phone number</span>
                    <strong>{reg?.phone || "—"}</strong>
                  </div>
                </div>
              </div>

              <div className="co-section co-payment-info">
                <div className="co-section-heading">
                  <div className="co-step">02</div>
                  <div>
                    <h2>Secure payment</h2>
                    <p>Complete your payment through our trusted payment partner</p>
                  </div>
                </div>

                <div className="co-secure-card">
                  <div className="co-lock">⌑</div>
                  <div>
                    <strong>Protected checkout</strong>
                    <p>Your payment will be processed securely by our payment partner. Rides AI does not store your card details.</p>
                  </div>
                </div>

                <div className="co-payment-note">
                  <span>ⓘ</span>
                  You'll be redirected to the payment provider to enter your payment details and confirm the transaction.
                </div>
              </div>
            </section>

            <aside className="co-summary">
              <div className="co-summary-header">
                <span>ORDER SUMMARY</span>
                <h2>Your selected plan</h2>
              </div>

              <div className="co-plan">
                <div className="co-plan-top">
                  <div>
                    <span className="co-plan-label">RIDES AI SUBSCRIPTION</span>
                    <h3>{plan.name}</h3>
                  </div>
                  <div className="co-plan-mark">✦</div>
                </div>
                <div className="co-plan-price">
                  <strong>${plan.price}</strong>
                  <span>/{plan.billing_cycle === "yearly" ? "year" : "month"}</span>
                </div>
                <p className="co-billing-cycle">
                  Billed {plan.billing_cycle === "yearly" ? "annually" : "monthly"}
                </p>
                <div className="co-summary-divider" />
                <div className="co-included">
                  <strong>Included in your plan</strong>
                  <ul>
                    <li><span>✓</span> AI-powered business management</li>
                    <li><span>✓</span> Customer interaction automation</li>
                    <li><span>✓</span> Products and services management</li>
                    <li><span>✓</span> Centralized business dashboard</li>
                    <li><span>✓</span> Employee and role management</li>
                  </ul>
                </div>
              </div>

              <div className="co-total">
                <span>Total due today</span>
                <strong>${plan.price}</strong>
              </div>
              <p className="co-tax-note">Final taxes or charges, if applicable, will be shown by the payment provider.</p>

              <button
                className="co-pay-btn"
                onClick={pay}
                disabled={busy}
              >
                {busy ? "Redirecting to secure checkout..." : <>Continue to secure payment <span>→</span></>}
              </button>

              <div className="co-security">
                <span>♢</span>
                <p>Secure payment processing</p>
              </div>

              <Link to="/select-plan" className="co-change-plan">
                ← Change selected plan
              </Link>
            </aside>
          </div>
        )}
      </main>
      <Footer />
    </div>
  );
}