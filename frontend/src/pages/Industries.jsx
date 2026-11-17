import { Link } from "react-router-dom";
import Navbar from "../components/Navbar";
import Footer from "../components/Footer";
import { PageHero, PageCta } from "../components/PageHero";
import { INDUSTRIES } from "../data/siteContent";
import "../styles/landing.css";
import "../styles/pages.css";

export default function Industries() {
  return (
    <div className="lp">
      <Navbar />
      <main>
        <PageHero
          label="BUILT FOR EVERY INDUSTRY"
          title="One platform."
          highlight="Unlimited possibilities."
          text="Rides AI adapts its dashboard and workflows to the kind of business you run, from customer orders to appointments and service requests."
        >
          <Link to="/register" className="lp-btn lp-btn-primary">Register Your Business <span>↗</span></Link>
        </PageHero>

        <section className="lp-section">
          <div className="lp-container">
            <div className="lp-industry-detail-grid">
              {INDUSTRIES.map((industry) => (
                <article className="lp-industry-detail" key={industry.name}>
                  <span className="lp-industry-icon">{industry.icon}</span>
                  <div>
                    <h3>{industry.name}</h3>
                    <p>{industry.text}</p>
                  </div>
                </article>
              ))}
            </div>

            <p className="lp-industry-note">
              Do not see your business here? Rides AI is built around configurable,
              category-based workflows, so more business types can be supported over time.
              Choose "Other" when you register and tell us what you do.
            </p>
          </div>
        </section>

        <PageCta />
      </main>
      <Footer />
    </div>
  );
}