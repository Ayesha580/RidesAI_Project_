import { Link } from "react-router-dom";

export function PageHero({ label, title, highlight, text, children }) {
  return (
    <section className="lp-page-hero">
      <div className="lp-hero-glow lp-glow-one" />
      <div className="lp-hero-glow lp-glow-two" />
      <div className="lp-container lp-page-hero-inner">
        <span className="lp-section-label">{label}</span>
        <h1>
          {title}
          {highlight && (
            <>
              <br />
              <span className="lp-gradient-text">{highlight}</span>
            </>
          )}
        </h1>
        <p>{text}</p>
        {children && <div className="lp-page-hero-cta">{children}</div>}
      </div>
    </section>
  );
}

export function PageCta({ title = "Give your business", highlight = "an intelligent advantage.", text = "Bring your customers, team and business operations together with Rides AI." }) {
  return (
    <section className="lp-final-cta">
      <div className="lp-cta-spark lp-spark-one" />
      <div className="lp-cta-spark lp-spark-two" />
      <div className="lp-container lp-final-content">
        <h2>
          {title}
          <br />
          <span>{highlight}</span>
        </h2>
        <p>{text}</p>
        <Link to="/register" className="lp-btn lp-btn-light">
          Get Started with Rides AI <span>↗</span>
        </Link>
      </div>
    </section>
  );
}