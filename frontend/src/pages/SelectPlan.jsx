import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { billingApi } from "../api/billingApi";
import { errorText } from "../api/axiosClient";
import Navbar from "../components/Navbar";
import Footer from "../components/Footer";
import "../styles/landing.css";
import "../styles/select-plan.css";

const FEATURES = [
  "Your AI-powered business manager",
  "Business products and services management",
  "Customer and operational automation",
  "Centralized business dashboard",
  "Employee and role management",
];

export default function SelectPlan() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    billingApi.getPlanPage()
      .then(({ data }) => {
        if (data.already_active) {
          window.location.replace(data.redirect);
          return;
        }
        setData(data);
        setSelected(data.selected_plan_id || data.plans[0]?.id || null);
      })
      .catch((e) => setError(errorText(e)));
  }, []);

  async function proceed() {
    if (!selected || busy) return;
    setBusy(true);
    setError("");
    try {
      await billingApi.selectPlan(selected);
      navigate("/checkout");
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  const reg = data?.registration;

  return (
    <div className="sp-page">
      <Navbar />
      <main className="sp-main">
        <section className="sp-heading">
          <span className="sp-eyebrow">WELCOME TO RIDES AI</span>
          <h1>Choose the right plan for your business</h1>
          <p>Start managing your business smarter with AI-powered tools and automation.</p>
          <div className="sp-verified">
            <span>✓</span> Your email has been verified
          </div>
        </section>

        {reg && (
          <section className="sp-account">
            <div className="sp-account-icon">✓</div>
            <div className="sp-account-info">
              <span>ACCOUNT CREATED</span>
              <strong>{reg.business_name}</strong>
              <p>{reg.owner_name} · {reg.email}</p>
            </div>
            <div className="sp-account-status">Verified</div>
          </section>
        )}

        {error && <div className="sp-error" role="alert">{error}</div>}

        {!data && !error && (
          <div className="sp-loading">
            <div className="sp-loader" />
            <p>Loading available plans...</p>
          </div>
        )}

        {data && data.plans.length === 0 && (
          <div className="sp-empty">
            <h3>No plans available</h3>
            <p>There are currently no active plans. Please contact support.</p>
          </div>
        )}

        {data?.plans.length > 0 && (
          <>
            <div className="sp-plans">
              {data.plans.map((p) => {
                const active = selected === p.id;
                return (
                  <div
                    key={p.id}
                    className={`sp-card ${active ? "sp-card-selected" : ""}`}
                    onClick={() => setSelected(p.id)}
                  >
                    {active && <span className="sp-selected-label">SELECTED PLAN</span>}
                    <div className="sp-card-top">
                      <h2>{p.name}</h2>
                      <p>Everything you need to run your business smarter.</p>
                    </div>
                    <div className="sp-price">
                      <strong>${p.price}</strong>
                      <span>/{p.billing_cycle === "yearly" ? "year" : "month"}</span>
                    </div>
                    <div className="sp-cycle">
                      Billed {p.billing_cycle === "yearly" ? "annually" : "monthly"}
                    </div>
                    <div className="sp-divider" />
                    <h4>What's included</h4>
                    <ul className="sp-features">
                      {FEATURES.map((f) => (
                        <li key={f}>
                          <span>✓</span>{f}
                        </li>
                      ))}
                    </ul>
                    <button
                      type="button"
                      className={`sp-select-btn ${active ? "sp-select-btn-active" : ""}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelected(p.id);
                      }}
                    >
                      {active ? "Selected" : "Choose plan"}
                      <span>{active ? "✓" : "→"}</span>
                    </button>
                  </div>
                );
              })}
            </div>

            <div className="sp-continue">
              <p>You can review your selection before completing payment.</p>
              <button
                className="sp-continue-btn"
                onClick={proceed}
                disabled={busy || !selected}
              >
                {busy ? "Please wait..." : <>Continue to checkout <span>→</span></>}
              </button>
            </div>
          </>
        )}
      </main>
      <Footer />
    </div>
  );
}