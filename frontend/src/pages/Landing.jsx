import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { publicApi } from "../api/publicApi";
import Navbar from "../components/Navbar";
import Footer from "../components/Footer";
import "../styles/Landing.css"; // Navbar + Footer styles live here
import "../styles/landing-v2.css";
import bannerVideo from "../assets/videos/banner.mp4";


const FEATURES = [
  { icon: "✳", title: "AI Voice Agent", text: "Answers calls, handles requests and speaks naturally, day and night.", size: "big" },
  { icon: "▦", title: "Products & Services", text: "Menus, services and pricing, organized in one place." },
  { icon: "▣", title: "Order Management", text: "Orders land straight in your dashboard." },
  { icon: "◎", title: "Call Logs & Transcripts", text: "Every call recorded, transcribed and summarized in one place.", size: "wide" },
  { icon: "♙", title: "Team Management", text: "Roles and access for every staff member." },
  { icon: "⌁", title: "Business Insights", text: "See customer activity, orders and performance." }
];

const STEPS = [
  ["Create your workspace", "Register your business and set up your account."],
  ["Add your business details", "Configure products, services, team and operating rules."],
  ["Connect your voice agent", "Get a phone number or call link and go live."],
  ["Manage everything", "Follow customer requests and activity from your dashboard."]
];

const CHANNELS = [
  ["Phone number", "Customers call your number and the agent answers."],
  ["Website", "Add a talk-to-us voice button to any page."],
  ["Shareable call link", "Share one link that starts a voice call instantly."]
];

const INDUSTRIES = ["Restaurants", "Retail & E-commerce", "Beauty & Salons", "Healthcare", "Hotels", "Logistics", "Education", "Fitness", "Professional Services"];

const BLOB = "M44.7,-58.3C57.6,-49.5,67.4,-35.6,71.6,-20.1C75.8,-4.6,74.4,12.5,66.6,25.6C58.8,38.7,44.6,47.8,30.1,56.2C15.6,64.6,0.8,72.3,-14.5,71.1C-29.8,69.9,-45.6,59.8,-56.3,46.2C-67,32.6,-72.6,15.5,-70.8,-0.9C-69,-17.3,-59.8,-33,-47.2,-42C-34.6,-51,-17.3,-53.3,-0.9,-52.2C15.5,-51.1,31.8,-67.1,44.7,-58.3Z";
const STAR = "M12 0C13 8 16 11 24 12C16 13 13 16 12 24C11 16 8 13 0 12C8 11 11 8 12 0Z";

function Blob({ className = "" }) {
  return (
    <svg className={`rx-blob ${className}`} viewBox="0 0 200 200" aria-hidden="true">
      <path d={BLOB} transform="translate(100 100)" fill="currentColor" />
    </svg>
  );
}

function Sparkle({ className = "" }) {
  return (
    <svg className={`rx-spark ${className}`} viewBox="0 0 24 24" aria-hidden="true">
      <path d={STAR} fill="currentColor" />
    </svg>
  );
}

function useReveal() {
  useEffect(() => {
    const els = document.querySelectorAll(".rx-reveal");
    if (!("IntersectionObserver" in window)) { els.forEach((e) => e.classList.add("in")); return; }
    const io = new IntersectionObserver((entries) => {
      entries.forEach((en) => { if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); } });
    }, { threshold: 0.15 });
    els.forEach((e) => io.observe(e));
    return () => io.disconnect();
  });
}

function useStepProgress(ref) {
  const [p, setP] = useState(0);
  useEffect(() => {
    const onScroll = () => {
      const el = ref.current; if (!el) return;
      const r = el.getBoundingClientRect();
      const v = (window.innerHeight * 0.6 - r.top) / r.height;
      setP(Math.min(1, Math.max(0, v)));
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [ref]);
  return p;
}

export default function Landing() {
  const [businesses, setBusinesses] = useState([]);
  const [loaded, setLoaded] = useState(false);
  const stepsRef = useRef(null);
  const progress = useStepProgress(stepsRef);

  useEffect(() => {
    let active = true;
    publicApi.businesses()
      .then(({ data }) => { if (active) setBusinesses(Array.isArray(data) ? data : []); })
      .catch(() => { if (active) setBusinesses([]); })
      .finally(() => { if (active) setLoaded(true); });
    return () => { active = false; };
  }, []);

  useReveal();

  return (
    <div className="lp rx" id="top">
      <Navbar />
      <main>
        {/* HERO */}
        <section className="rx-hero">
          <video className="rx-video" src={bannerVideo} autoPlay muted loop playsInline preload="auto" />
          <div className="rx-hero-shade" />
          <div className="rx-wrap rx-hero-grid">
            <div className="rx-hero-copy">
              <h1>Your AI agent that runs the business.</h1>
              <p className="rx-lead">Takes customer orders, assigns your team and keeps you updated, 24/7.</p>
              <div className="rx-actions">
                <Link to="/register" className="rx-btn rx-btn-pink">Get started</Link>
                <a href="#agent" className="rx-btn rx-btn-glass">Explore platform</a>
              </div>
            </div>
          </div>
          <svg className="rx-wave-edge" viewBox="0 0 1440 90" preserveAspectRatio="none" aria-hidden="true">
            <path d="M0 40C180 90 360 90 540 55C720 20 900 10 1080 40C1240 66 1340 70 1440 50V90H0Z" fill="currentColor" />
          </svg>
        </section>

        {/* MARQUEE */}
        <div className="rx-marquee" aria-hidden="true">
          <div>{[...INDUSTRIES, ...INDUSTRIES].map((x, i) => <span key={i}>{x}</span>)}</div>
        </div>

        {/* INTRO */}
        <section className="rx-section rx-intro" id="agent">
          <div className="rx-wrap rx-intro-grid">
            <h2 className="rx-reveal">Not a phone menu. A voice that knows your business.</h2>
            <p className="rx-reveal rx-d1">Customers talk to your agent like a real person and get answers right away. You get organized orders, call transcripts and insights.</p>
          </div>
        </section>

        {/* BENTO */}
        <section className="rx-section rx-bento-sec">
          <Blob className="b1" /><Blob className="b2" />
          <div className="rx-wrap">
            <h2 className="rx-title rx-reveal">Everything connected, nothing complicated.</h2>
            <div className="rx-bento">
              {FEATURES.map((f, i) => (
                <article key={f.title} className={`rx-card rx-reveal ${f.size || ""}`} style={{ transitionDelay: `${i * 70}ms` }}>
                  <span className="rx-ico">{f.icon}</span>
                  <h3>{f.title}</h3>
                  <p>{f.text}</p>
                </article>
              ))}
            </div>
            <div className="rx-more"><Link to="/features">Explore all features</Link></div>
          </div>
        </section>

        {/* STEPS */}
        <section className="rx-section rx-steps-sec">
          <Blob className="b3" />
          <div className="rx-wrap rx-steps-grid">
            <div className="rx-steps-head rx-reveal">
              <h2>From sign-up to a working agent in four steps.</h2>
              <Link to="/how-it-works" className="rx-btn rx-btn-pink">See how it works</Link>
            </div>
            <ol className="rx-steps" ref={stepsRef}>
              <span className="rx-rail"><b style={{ height: `${progress * 100}%` }} /></span>
              {STEPS.map(([t, d], i) => (
                <li key={t} className={`rx-reveal ${progress * STEPS.length > i + 0.3 ? "on" : ""}`}>
                  <span>{i + 1}</span>
                  <div><h3>{t}</h3><p>{d}</p></div>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* CHANNELS */}
        <section className="rx-section rx-channels">
          <div className="rx-wrap">
            <h2 className="rx-title rx-reveal">One voice agent, every way customers call.</h2>
            <div className="rx-channel-row">
              {CHANNELS.map(([t, d], i) => (
                <div key={t} className="rx-channel rx-reveal" style={{ transitionDelay: `${i * 100}ms` }}>
                  <h3>{t}</h3><p>{d}</p><span className="rx-arrow">↗</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* INDUSTRIES */}
        <section className="rx-section rx-industries">
          <div className="rx-wrap">
            <h2 className="rx-title rx-reveal">Different businesses, one platform.</h2>
            <div className="rx-chips rx-reveal">{INDUSTRIES.map((n) => <span key={n}>{n}</span>)}</div>
            <div className="rx-more"><Link to="/industries">Explore industries</Link></div>
          </div>
        </section>


        {/* CTA */}
        <section className="rx-cta">
          <Sparkle className="s4" /><Sparkle className="s5" /><Blob className="b5" />
          <div className="rx-wrap rx-reveal">
            <h2>Let your business move forward with AI.</h2>
            <p>Bring customers, your team and daily operations together.</p>
            <Link to="/register" className="rx-btn rx-btn-white">Get started with Rides AI</Link>
          </div>
        </section>
      </main>
      <Footer />
    </div>
  );
}