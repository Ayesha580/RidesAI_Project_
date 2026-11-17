import { useEffect } from "react";
import { Link } from "react-router-dom";
import Navbar from "../components/Navbar";
import Footer from "../components/Footer";
import { PLAN_FEATURES, FAQS } from "../data/siteContent";
import "../styles/Landing.css"; // Navbar + Footer styles live here
import "../styles/plans.css";

const STAR = "M12 0C13 8 16 11 24 12C16 13 13 16 12 24C11 16 8 13 0 12C8 11 11 8 12 0Z";
const BLOB = "M44.7,-58.3C57.6,-49.5,67.4,-35.6,71.6,-20.1C75.8,-4.6,74.4,12.5,66.6,25.6C58.8,38.7,44.6,47.8,30.1,56.2C15.6,64.6,0.8,72.3,-14.5,71.1C-29.8,69.9,-45.6,59.8,-56.3,46.2C-67,32.6,-72.6,15.5,-70.8,-0.9C-69,-17.3,-59.8,-33,-47.2,-42C-34.6,-51,-17.3,-53.3,-0.9,-52.2C15.5,-51.1,31.8,-67.1,44.7,-58.3Z";

function Blob({ className = "" }) {
  return (
    <svg className={`pl-blob ${className}`} viewBox="0 0 200 200" aria-hidden="true">
      <path d={BLOB} transform="translate(100 100)" fill="currentColor" />
    </svg>
  );
}

function Sparkle({ className = "" }) {
  return (
    <svg className={`pl-spark ${className}`} viewBox="0 0 24 24" aria-hidden="true">
      <path d={STAR} fill="currentColor" />
    </svg>
  );
}

function useReveal() {
  useEffect(() => {
    const els = document.querySelectorAll(".pl-reveal");
    if (!("IntersectionObserver" in window)) { els.forEach((e) => e.classList.add("in")); return; }
    const io = new IntersectionObserver((entries) => {
      entries.forEach((en) => { if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); } });
    }, { threshold: 0.12 });
    els.forEach((e) => io.observe(e));
    return () => io.disconnect();
  }, []);
}

const NOT_FREE = /\b(free|trial|no credit card)\b/i;

export default function Plans() {
  useReveal();
  const features = PLAN_FEATURES.filter((f) => !NOT_FREE.test(f));
  const faqs = FAQS.filter((f) => !NOT_FREE.test(`${f.q} ${f.a}`));

  return (
    <div className="lp pl-page">
      <Navbar />
      <main>
        {/* HERO */}
        <section className="pl-hero">
          <Blob className="b1" /><Blob className="b2" />
          <Sparkle className="s1" /><Sparkle className="s2" />
          <div className="pl-wrap pl-hero-copy">
            <p className="pl-tag">Simple pricing</p>
            <h1>One plan. <span>More possibilities.</span></h1>
            <p className="pl-lead">Everything your business needs to work smarter with AI.</p>
          </div>
          <svg className="pl-edge" viewBox="0 0 1440 90" preserveAspectRatio="none" aria-hidden="true">
            <path d="M0 50C200 10 380 10 560 40C760 74 940 84 1140 52C1280 30 1370 30 1440 44V90H0Z" fill="currentColor" />
          </svg>
        </section>

        {/* PRICING */}
        <section className="pl-pricing">
          <div className="pl-wrap">
            <div className="pl-card">
              <div className="pl-side">
                <Sparkle className="s3" />
                <span className="pl-badge">All-in-one plan</span>
                <h2>Rides AI Standard</h2>
                <p>Complete AI-powered business management.</p>
                <div className="pl-price"><strong>$90.86</strong><span>/ month</span></div>
                <Link to="/register" className="pl-button">Start your Business</Link>
              </div>

              <div className="pl-main">
                <h3>Everything included</h3>
                <ul className="pl-features">
                  {features.map((feature, i) => (
                    <li key={feature} className="pl-reveal" style={{ transitionDelay: `${i * 45}ms` }}>
                      <i>✓</i>{feature}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </section>

        {/* FAQ */}
        <section className="pl-faq-section">
          <div className="pl-wrap pl-faq-grid">
            <div className="pl-faq-heading pl-reveal">
              <div className="pl-q" aria-hidden="true">
                <svg viewBox="0 0 200 200"><path d={BLOB} transform="translate(100 100)" /></svg>
                <span>?</span>
              </div>
              <h2>Common questions</h2>
            </div>

            <div className="pl-faq">
              {faqs.map((item, i) => (
                <details className="pl-faq-item pl-reveal" key={item.q} style={{ transitionDelay: `${i * 60}ms` }}>
                  <summary>{item.q}<span>+</span></summary>
                  <p>{item.a}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        {/* CTA */}
        <section className="pl-cta">
          <div className="pl-wrap pl-cta-box pl-reveal">
            <Sparkle className="s4" /><Sparkle className="s5" />
            <h2>Ready to work smarter with AI?</h2>
            <p>Bring customers, your team and daily operations together in one workspace.</p>
            <Link to="/register" className="pl-button pl-button-solid">Start your Business</Link>
          </div>
        </section>
      </main>
      <Footer />
    </div>
  );
}