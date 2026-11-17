import { useState } from "react";
import { Link } from "react-router-dom";
import logo from "../assets/logo.webp";
import { useAuth } from "../context/AuthContext";
import { homeFor } from "./Guards";

// "/#section" works on the landing page AND on /login, /register (takes you home, then scrolls)
export default function Navbar() {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);

  const actions = user ? (
    <Link className="lp-btn" to={homeFor(user)} onClick={close}>Dashboard</Link>
  ) : (
    <>
      <Link className="lp-btn ghost" to="/login" onClick={close}>Login</Link>
      <Link className="lp-btn" to="/register" onClick={close}>Sign up</Link>
    </>
  );

  return (
    <header className="lp-nav">
      <div className="lp-nav-inner">
        <a href="/#top" className="lp-logo" onClick={close}>
          <img src={logo} alt="Rides AI" />
        </a>

        <nav className={`lp-links ${open ? "open" : ""}`}>
          <a href="/" onClick={close}>Home</a>
          <a href="/features" onClick={close}>Features</a>
          <a href="/how" onClick={close}>How it works</a>
          <a href="/industries" onClick={close}>Industries</a>
          <a href="/businesses" onClick={close}>Our businesses</a>
          <a href="/pricing" onClick={close}>Pricing</a>

          <div className="lp-actions-mobile">{actions}</div>
        </nav>

        <div className="lp-actions">{actions}</div>

        <button
          className="lp-burger"
          onClick={() => setOpen(!open)}
          aria-label="Menu"
          aria-expanded={open}
        >
          {open ? "✕" : "☰"}
        </button>
      </div>
    </header>
  );
}