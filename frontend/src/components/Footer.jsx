import { Link } from "react-router-dom";
import logo from "../assets/logo.webp";

export default function Footer() {
  return (
    <footer className="lp-footer">
      <div className="lp-container lp-footer-grid">
        <div className="lp-footer-brand">
          <Link to="/" className="lp-footer-brand-link">
            <img src={logo} alt="Rides AI" className="lp-footer-logo" />
          </Link>
          <p>
            Intelligent AI agents that simplify business operations,
            manage customer interactions and help teams work smarter.
          </p>
        </div>

        <div className="lp-footer-column">
          <h4>Product</h4>
          <a href="/#features">Features</a>
          <a href="/#how">How It Works</a>
          <a href="/#pricing">Pricing</a>
        </div>

        <div className="lp-footer-column">
          <h4>Explore</h4>
          <a href="/#industries">Industries</a>
          <a href="/#businesses">Our Businesses</a>
        </div>

        <div className="lp-footer-column">
          <h4>Account</h4>
          <Link to="/login">Sign In</Link>
          <Link to="/register">Create Account</Link>
        </div>
      </div>

      <div className="lp-footer-bottom">
        <p>© {new Date().getFullYear()} Rides AI. All rights reserved.</p>
        <span>Powered by Rides Technologies</span>
      </div>
    </footer>
  );
}