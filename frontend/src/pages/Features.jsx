import { Link } from "react-router-dom";
import Navbar from "../components/Navbar";
import Footer from "../components/Footer";
import { PageHero, PageCta } from "../components/PageHero";
import { FEATURE_GROUPS, SECURITY_POINTS } from "../data/siteContent";
import "../styles/landing.css";
import "../styles/pages.css";

export default function Features() {
  return (
    <div className="lp">
      <Navbar />
      <main>
        <PageHero
          label="POWERFUL CAPABILITIES"
          title="Everything connected."
          highlight="Everything under control."
          text="A closer look at what Rides AI does for your customers, your team and your daily operations."
        >
          <Link to="/register" className="lp-btn lp-btn-primary">Get Started <span>↗</span></Link>
          <Link to="/pricing" className="lp-btn lp-btn-secondary">View Plans <span>→</span></Link>
        </PageHero>

        <section className="lp-section">
          <div className="lp-container">
            <div className="lp-detail-grid">
              {FEATURE_GROUPS.map((group) => (
                <article className="lp-detail-card" key={group.title}>
                  <div className="lp-feature-icon">{group.icon}</div>
                  <h3>{group.title}</h3>
                  <p className="lp-detail-intro">{group.intro}</p>
                  <ul className="lp-check-list">
                    {group.points.map((point) => (
                      <li key={point}><span>✓</span>{point}</li>
                    ))}
                  </ul>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="lp-section lp-features">
          <div className="lp-container">
            <div className="lp-section-heading">
              <span className="lp-section-label">SECURE BY DESIGN</span>
              <h2>Your data stays <span className="lp-gradient-text">yours.</span></h2>
              <p>Built so every business is kept separate and every action is accountable.</p>
            </div>
            <div className="lp-trust-grid">
              {SECURITY_POINTS.map((item) => (
                <div className="lp-trust-card" key={item.title}>
                  <span className="lp-industry-icon">{item.icon}</span>
                  <strong>{item.title}</strong>
                  <p>{item.text}</p>
                </div>
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