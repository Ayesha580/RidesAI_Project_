import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { billingApi } from "../api/billingApi";
import { errorText } from "../api/axiosClient";
import Footer from "../components/Footer";
import Navbar from "../components/Navbar";
import "../styles/landing.css";
import "../styles/auth.css";

export default function MockPayment() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const checkoutId = params.get("checkout_id") || "";
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function confirmTestPayment() {
    if (!checkoutId || busy) return;
    setBusy(true);
    setError("");
    try {
      const { data } = await billingApi.completePayment(checkoutId);
      if (data.success && data.mock) {
        navigate("/owner/dashboard", { replace: true });
      } else {
        setError("The local test payment could not be confirmed.");
      }
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="lp">
      <Navbar />
      <main className="au-main">
        <div className="au-shell">
          <section className="au-card">
            <span className="au-card-label">LOCAL DEVELOPMENT ONLY</span>
            <h1>Test checkout</h1>
            <p>This is a local payment simulator. It does not connect to Polar, charge a card, or transfer money.</p>
            {!checkoutId && <div className="au-alert" role="alert">Missing test checkout reference.</div>}
            {error && <div className="au-alert" role="alert">{error}</div>}
            <button
              className="lp-btn lp-btn-primary au-submit"
              type="button"
              onClick={confirmTestPayment}
              disabled={!checkoutId || busy}
            >
              {busy ? "Activating test subscription..." : "Simulate successful test payment"}
            </button>
            <p className="au-switch">
              <Link to="/checkout">Return to checkout</Link>
            </p>
          </section>
        </div>
      </main>
      <Footer />
    </div>
  );
}
