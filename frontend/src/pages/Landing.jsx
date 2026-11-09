import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { publicApi } from "../api/publicApi";
import Navbar from "../components/Navbar";
import Footer from "../components/Footer";
import "../styles/Landing.css";
import "../styles/home.css";

const FEATURES = [
  { icon: "✳", title: "AI Business Agent", text: "An intelligent assistant for customer questions and everyday requests." },
  { icon: "▦", title: "Products & Services", text: "Keep products, services, menus and pricing organized." },
  { icon: "↗", title: "Order Management", text: "Receive orders and send requests directly to your dashboard." },
  { icon: "◎", title: "Customer Conversations", text: "Keep enquiries, conversations and follow-ups in one place." },
  { icon: "♙", title: "Team Management", text: "Organize your staff with roles and access permissions." },
  { icon: "⌁", title: "Business Insights", text: "Track customer activity, orders and business performance." }
];

const STEPS = [
  ["01", "Create your workspace", "Register your business and set up your account."],
  ["02", "Add your business details", "Configure products, services, team and operating rules."],
  ["03", "Connect your AI agent", "Share your agent through your website, WhatsApp or a direct link."],
  ["04", "Manage everything", "View customer requests and activity from your dashboard."]
];

const INDUSTRIES = ["Restaurants", "Retail & E-commerce", "Beauty & Salons", "Healthcare", "Hotels", "Logistics", "Education", "Fitness", "Professional Services"];

export default function Landing() {
  const [businesses, setBusinesses] = useState([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let active = true;
    publicApi.businesses()
      .then(({ data }) => {
        if (active) setBusinesses(Array.isArray(data) ? data : []);
      })
      .catch(() => {
        if (active) setBusinesses([]);
      })
      .finally(() => {
        if (active) setLoaded(true);
      });
    return () => { active = false; };
  }, []);

  return (
    <div className="lp home-page" id="top">
      <Navbar />
      <main>
        <section className="hm-hero">
          <div className="hm-orb hm-orb-one" />
          <div className="hm-orb hm-orb-two" />
          <div className="hm-wrap hm-hero-grid">
            <div className="hm-hero-copy">
              <span className="hm-kicker"><i /> AI-POWERED BUSINESS MANAGEMENT</span>
              <h1>Your business,<br /><span>working smarter.</span></h1>
              <p>Meet your AI business partner. Manage customer conversations, orders and daily operations from one simple platform.</p>
              <div className="hm-actions">
                <Link to="/register" className="hm-primary">Get started <span>↗</span></Link>
                <a href="#platform" className="hm-secondary">Explore platform <span>↓</span></a>
              </div>
              <div className="hm-proof"><span>✓</span> One workspace <span>✓</span> Multiple channels <span>✓</span> Your team in control</div>
            </div>

            <div className="hm-hero-art">
              <div className="hm-art-circle" />
              <div className="hm-art-dots" />
              <div className="hm-dashboard">
                <div className="hm-dash-head">
                  <div className="hm-brand-symbol">R</div>
                  <div><strong>Rides AI</strong><small>Business workspace</small></div>
                  <span className="hm-online"><i /> Live</span>
                </div>
                <div className="hm-dash-welcome"><small>OVERVIEW</small><h3>Your business at a glance.</h3><p>Here’s what’s happening today.</p></div>
                <div className="hm-stats">
                  <div><small>AI Assistant</small><strong>Active</strong><span>Ready to help</span></div>
                  <div><small>Availability</small><strong>24/7</strong><span>Always on</span></div>
                  <div><small>Workspace</small><strong>Connected</strong><span>All in one place</span></div>
                </div>
                <div className="hm-activity">
                  <div className="hm-activity-title"><strong>Recent activity</strong><span>Live preview</span></div>
                  <div><i>✉</i><p><strong>Customer enquiry</strong><small>Product information requested</small></p><b>✓</b></div>
                  <div><i>▣</i><p><strong>New order request</strong><small>Sent to business dashboard</small></p><b>↗</b></div>
                  <div><i>♙</i><p><strong>Team update</strong><small>Request assigned to staff</small></p><b>✓</b></div>
                </div>
              </div>
              <div className="hm-float hm-float-top"><span>✳</span><div><strong>AI assistant</strong><small>Ready to assist</small></div></div>
              <div className="hm-float hm-float-bottom"><span>↗</span><div><strong>Work smarter</strong><small>Less routine work</small></div></div>
            </div>
          </div>
          <div className="hm-strip"><span>ONE PLATFORM</span><i /><span>CONNECTED CUSTOMERS</span><i /><span>SMARTER OPERATIONS</span><i /><span>YOUR BUSINESS, YOUR CONTROL</span></div>
        </section>

        <section className="hm-intro" id="platform">
          <div className="hm-wrap hm-intro-grid">
            <div><span className="hm-label">MEET RIDES AI</span><h2>Not just a chatbot.<br /><em>A smarter way to run business.</em></h2></div>
            <p>Rides AI brings your AI agent, customers and team together. Give your customers a better way to connect while keeping your business operations organized.</p>
          </div>
        </section>

        <section className="hm-features">
          <div className="hm-wrap">
            <div className="hm-heading"><span className="hm-label">THE PLATFORM</span><h2>Everything connected.<br /><em>Nothing complicated.</em></h2><p>Essential tools to help your business run smoothly.</p></div>
            <div className="hm-feature-grid">
              {FEATURES.map((item, i) => (
                <article className={`hm-feature hm-feature-${i + 1}`} key={item.title}>
                  <span className="hm-feature-icon">{item.icon}</span>
                  <small>0{i + 1}</small>
                  <h3>{item.title}</h3>
                  <p>{item.text}</p>
                  <span className="hm-feature-arrow">↗</span>
                </article>
              ))}
            </div>
            <div className="hm-link-row"><Link to="/features">Explore all features <span>→</span></Link></div>
          </div>
        </section>

        <section className="hm-workflow">
          <div className="hm-wrap hm-workflow-grid">
            <div className="hm-workflow-visual">
              <div className="hm-flow-line" />
              <div className="hm-flow-core"><span>R</span><strong>RIDES AI</strong><small>YOUR BUSINESS AGENT</small></div>
              <div className="hm-flow-node hm-flow-a"><span>✉</span> Customers</div>
              <div className="hm-flow-node hm-flow-b"><span>▣</span> Orders</div>
              <div className="hm-flow-node hm-flow-c"><span>♙</span> Your team</div>
              <div className="hm-flow-node hm-flow-d"><span>⌁</span> Insights</div>
            </div>
            <div className="hm-workflow-copy">
              <span className="hm-label">GET STARTED IN FOUR STEPS</span>
              <h2>From setup to<br /><em>smarter operations.</em></h2>
              <div className="hm-steps">
                {STEPS.map(([num, title, text]) => (
                  <div className="hm-step" key={num}><span>{num}</span><div><h3>{title}</h3><p>{text}</p></div></div>
                ))}
              </div>
              <Link to="/how-it-works" className="hm-inline-link">See how it works <span>→</span></Link>
            </div>
          </div>
        </section>

        <section className="hm-channels">
          <div className="hm-wrap hm-channel-grid">
            <div><span className="hm-label">MEET CUSTOMERS WHERE THEY ARE</span><h2>One AI agent.<br /><em>More ways to connect.</em></h2><p>Make it easy for customers to reach your business through the channels you use.</p>
              <div className="hm-channel-list">
                <div><span>◉</span><p><strong>WhatsApp</strong><small>Connect your WhatsApp Business channel.</small></p><b>↗</b></div>
                <div><span>⌘</span><p><strong>Website</strong><small>Add an AI chat widget to your website.</small></p><b>↗</b></div>
                <div><span>↗</span><p><strong>Shareable link</strong><small>Share your own AI agent link.</small></p><b>↗</b></div>
              </div>
            </div>
            <div className="hm-channel-art">
              <div className="hm-channel-ring ring-one" /><div className="hm-channel-ring ring-two" />
              <div className="hm-channel-center"><span>R</span><strong>RIDES AI</strong><small>BUSINESS AGENT</small></div>
              <span className="hm-channel-tag tag-one">WhatsApp</span><span className="hm-channel-tag tag-two">Website</span><span className="hm-channel-tag tag-three">AI Link</span><span className="hm-channel-tag tag-four">Customers</span>
            </div>
          </div>
        </section>

        <section className="hm-industries">
          <div className="hm-wrap">
            <div className="hm-heading"><span className="hm-label">MADE FOR YOUR INDUSTRY</span><h2>Different businesses.<br /><em>One intelligent platform.</em></h2><p>Flexible workflows for the way your business operates.</p></div>
            <div className="hm-industry-list">{INDUSTRIES.map((name, i) => <span key={name}><i>{["✳","▦","✧","✚","⌂","➜","▤","◉","⚙"][i]}</i>{name}</span>)}</div>
            <div className="hm-link-row"><Link to="/industries">Explore industries <span>→</span></Link></div>
          </div>
        </section>

        <section className="hm-community">
          <div className="hm-wrap">
            <div className="hm-community-head"><div><span className="hm-label">OUR BUSINESS COMMUNITY</span><h2>Growing with <em>Rides AI.</em></h2></div><p>Meet businesses that are part of our platform.</p></div>
            {!loaded && <p className="hm-loading">Loading businesses...</p>}
            {loaded && businesses.length > 0 && <div className="hm-business-grid">{businesses.map((business) => <article key={business.id}><span>{(business.name || "B").charAt(0).toUpperCase()}</span><div><strong>{business.name}</strong><small>{business.business_type || "Rides AI business"}</small></div><i>✓</i></article>)}</div>}
            {loaded && businesses.length === 0 && <div className="hm-community-empty"><span>✳</span><p>Be among the businesses building a smarter way to work.</p><Link to="/register">Join the community ↗</Link></div>}
          </div>
        </section>

        <section className="hm-testimonial">
          <div className="hm-wrap hm-testimonial-inner">
            <div className="hm-quote-mark">“</div>
            <div className="hm-quote-content"><span className="hm-label">CUSTOMER STORIES</span><blockquote>[Add an approved customer quote about their experience using Rides AI.]</blockquote><div className="hm-quote-person"><span className="hm-quote-avatar"> </span><div><strong>[Customer name]</strong><small>[Business name · Industry]</small></div></div></div>
            <div className="hm-quote-side"><span>REAL EXPERIENCES</span><p>Hear how businesses use Rides AI in their day-to-day operations.</p></div>
          </div>
        </section>

        <section className="hm-cta">
          <div className="hm-cta-shape shape-one" /><div className="hm-cta-shape shape-two" />
          <div className="hm-wrap hm-cta-content"><span>READY FOR A SMARTER WORKFLOW?</span><h2>Let your business<br />move forward with AI.</h2><p>Bring customers, your team and daily operations together.</p><Link to="/register">Get started with Rides AI <span>↗</span></Link></div>
        </section>
      </main>
      <Footer />
    </div>
  );
}