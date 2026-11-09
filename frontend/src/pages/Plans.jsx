import { Link } from "react-router-dom";
import Navbar from "../components/Navbar";
import Footer from "../components/Footer";
import { PageHero, PageCta } from "../components/PageHero";
import { PLAN_FEATURES, FAQS } from "../data/siteContent";
import "../styles/plans.css";

export default function Plans() {
  return (
    <div className="lp pl-page">
      <Navbar />
      <main>
        <PageHero
          label="SIMPLE PRICING"
          title="One plan."
          highlight="More possibilities."
          text="Everything your business needs to work smarter with AI."
        />

        <section className="pl-pricing">
          <div className="pl-container">
            <div className="pl-card">
              <div className="pl-card-top">
                <span className="pl-badge">ALL-IN-ONE PLAN</span>
                <h2>Rides AI Standard</h2>
                <p>Complete AI-powered business management.</p>
              </div>

              <div className="pl-price">
                <strong>$90.86</strong>
                <span>/ month</span>
              </div>

              <div className="pl-trial">
                <span>✓</span> First month free after business approval
              </div>

              <div className="pl-divider" />

              <h3>Everything included</h3>
              <ul className="pl-features">
                {PLAN_FEATURES.map((feature) => (
                  <li key={feature}>
                    <span>✓</span>{feature}
                  </li>
                ))}
              </ul>

              <Link to="/register" className="pl-button">
                Start Your Free Month <span>→</span>
              </Link>

              <p className="pl-note">
                No credit card required for the trial. Cancel anytime.
              </p>
            </div>
          </div>
        </section>

        <section className="pl-faq-section">
          <div className="pl-container">
            <div className="pl-faq-heading">
              <span>FAQ</span>
              <h2>Common questions</h2>
            </div>

            <div className="pl-faq">
              {FAQS.map((item) => (
                <details className="pl-faq-item" key={item.q}>
                  <summary>{item.q}<span>+</span></summary>
                  <p>{item.a}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        <PageCta />
      </main>
      <Footer />
    </div>
  );
}
