import { useEffect } from "react";
import { Link } from "react-router-dom";
import Navbar from "../components/Navbar";
import Footer from "../components/Footer";
import { FEATURE_GROUPS, SECURITY_POINTS } from "../data/siteContent";
import "../styles/Landing.css"; // Navbar + Footer styles live here
import "../styles/features.css";

const STAR = "M12 0C13 8 16 11 24 12C16 13 13 16 12 24C11 16 8 13 0 12C8 11 11 8 12 0Z";
const BLOB = "M44.7,-58.3C57.6,-49.5,67.4,-35.6,71.6,-20.1C75.8,-4.6,74.4,12.5,66.6,25.6C58.8,38.7,44.6,47.8,30.1,56.2C15.6,64.6,0.8,72.3,-14.5,71.1C-29.8,69.9,-45.6,59.8,-56.3,46.2C-67,32.6,-72.6,15.5,-70.8,-0.9C-69,-17.3,-59.8,-33,-47.2,-42C-34.6,-51,-17.3,-53.3,-0.9,-52.2C15.5,-51.1,31.8,-67.1,44.7,-58.3Z";
const NODES = [[390, 220], [315, 350], [165, 350], [90, 220], [165, 90], [315, 90]];

function Blob({ className = "" }) {
  return (
    <svg className={`ft-blob ${className}`} viewBox="0 0 200 200" aria-hidden="true">
      <path d={BLOB} transform="translate(100 100)" fill="currentColor" />
    </svg>
  );
}

function Sparkle({ className = "" }) {
  return (
    <svg className={`ft-spark ${className}`} viewBox="0 0 24 24" aria-hidden="true">
      <path d={STAR} fill="currentColor" />
    </svg>
  );
}

// Hub-and-spoke vector: "everything connected"
function HubArt() {
  const items = FEATURE_GROUPS.slice(0, 6);
  return (
    <svg className="ft-hub" viewBox="0 0 480 440" role="img" aria-label="Rides AI at the center, connected to every feature">
      <circle className="ring r1" cx="240" cy="220" r="170" />
      <circle className="ring r2" cx="240" cy="220" r="115" />
      {items.map((_, i) => (
        <line key={i} className="spoke" x1="240" y1="220" x2={NODES[i][0]} y2={NODES[i][1]} style={{ animationDelay: `${i * -0.4}s` }} />
      ))}
      <circle className="core-glow" cx="240" cy="220" r="64" />
      <circle className="core" cx="240" cy="220" r="48" />
      <text className="core-t" x="240" y="220" textAnchor="middle" dominantBaseline="central">R</text>
      {items.map((g, i) => (
        <g key={g.title} className="node" style={{ animationDelay: `${i * -0.8}s` }}>
          <circle cx={NODES[i][0]} cy={NODES[i][1]} r="31" />
          <text x={NODES[i][0]} y={NODES[i][1]} textAnchor="middle" dominantBaseline="central">{g.icon}</text>
        </g>
      ))}
    </svg>
  );
}

function useReveal() {
  useEffect(() => {
    const els = document.querySelectorAll(".ft-reveal");
    if (!("IntersectionObserver" in window)) { els.forEach((e) => e.classList.add("in")); return; }
    const io = new IntersectionObserver((entries) => {
      entries.forEach((en) => { if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); } });
    }, { threshold: 0.12 });
    els.forEach((e) => io.observe(e));
    return () => io.disconnect();
  }, []);
}

const slug = (t) => "f-" + String(t).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");

export default function Features() {
  useReveal();

  return (
    <div className="lp ft">
      <Navbar />
      <main>
        {/* HERO */}
        <section className="ft-hero">
          <Blob className="b1" /><Blob className="b2" />
          <Sparkle className="s1" /><Sparkle className="s2" />
          <div className="ft-wrap ft-hero-grid">
            <div className="ft-hero-copy">
              <p className="ft-tag">What Rides AI does</p>
              <h1>Everything connected. <span>Everything under control.</span></h1>
              <p className="ft-lead">A closer look at what Rides AI does for your customers, your team and your daily operations.</p>
              <div className="ft-actions">
                <Link to="/register" className="ft-btn ft-btn-pink">Get started</Link>
                <Link to="/pricing" className="ft-btn ft-btn-line">View plans</Link>
              </div>
            </div>
            <HubArt />
          </div>
          <svg className="ft-edge" viewBox="0 0 1440 90" preserveAspectRatio="none" aria-hidden="true">
            <path d="M0 50C200 10 380 10 560 40C760 74 940 84 1140 52C1280 30 1370 30 1440 44V90H0Z" fill="currentColor" />
          </svg>
        </section>

        {/* JUMP NAV */}
        <nav className="ft-jump" aria-label="Feature sections">
          <div className="ft-wrap ft-jump-row">
            {FEATURE_GROUPS.map((g) => (
              <a key={g.title} href={`#${slug(g.title)}`}><span>{g.icon}</span>{g.title}</a>
            ))}
          </div>
        </nav>

        {/* FEATURE GROUPS */}
        {FEATURE_GROUPS.map((group, i) => (
          <section key={group.title} id={slug(group.title)} className={`ft-group ${i % 2 ? "alt" : ""}`}>
            <div className="ft-wrap ft-group-grid">
              <div className="ft-gl ft-reveal">
                <div className="ft-gicon">
                  <svg viewBox="0 0 200 200" aria-hidden="true"><path d={BLOB} transform="translate(100 100)" /></svg>
                  <span>{group.icon}</span>
                </div>
                <h2>{group.title}</h2>
                <p>{group.intro}</p>
              </div>
              <ul className="ft-points">
                {group.points.map((point, k) => (
                  <li key={point} className="ft-reveal" style={{ transitionDelay: `${k * 60}ms` }}>
                    <i>✓</i>{point}
                  </li>
                ))}
              </ul>
            </div>
          </section>
        ))}

        {/* SECURITY */}
        <section className="ft-secure">
          <Blob className="b3" />
          <svg className="ft-shield" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M12 1.5 3.5 5v6.2c0 5.2 3.6 9.9 8.5 11.3 4.9-1.4 8.5-6.1 8.5-11.3V5L12 1.5Z" fill="currentColor" />
          </svg>
          <div className="ft-wrap">
            <div className="ft-secure-head ft-reveal">
              <p className="ft-tag light">Secure by design</p>
              <h2>Your data stays yours.</h2>
              <p>Built so every business is kept separate and every action is accountable.</p>
            </div>
            <div className="ft-secure-grid">
              {SECURITY_POINTS.map((item, i) => (
                <div className="ft-secure-card ft-reveal" key={item.title} style={{ transitionDelay: `${i * 80}ms` }}>
                  <span>{item.icon}</span>
                  <strong>{item.title}</strong>
                  <p>{item.text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* CTA */}
        <section className="ft-cta">
          <div className="ft-wrap ft-cta-box ft-reveal">
            <Sparkle className="s3" /><Sparkle className="s4" />
            <h2>Ready to put your business on autopilot?</h2>
            <p>Bring customers, your team and daily operations together in one workspace.</p>
            <div className="ft-actions">
              <Link to="/register" className="ft-btn ft-btn-white">Get started with Rides AI</Link>
              <Link to="/pricing" className="ft-btn ft-btn-ghost">View plans</Link>
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </div>
  );
}