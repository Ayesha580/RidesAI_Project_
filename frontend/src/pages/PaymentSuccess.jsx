import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { billingApi } from "../api/billingApi";
import { errorText } from "../api/axiosClient";
import Footer from "../components/Footer";
import Navbar from "../components/Navbar";
import "../styles/landing.css";
import "../styles/auth.css";

const MAX_TRIES = 8;

export default function PaymentSuccess() {
  const [params] = useSearchParams();
  const checkoutId = params.get("checkout_id");
  const [status, setStatus] = useState("checking");
  const [error, setError] = useState("");
  const started = useRef(false);
  useEffect(() => {
  if (started.current) return;
  started.current = true;

  if (!checkoutId) {
    setStatus("failed");
    setError("Missing checkout reference.");
    return;
  }

  async function run() {
    for (let i = 0; i < MAX_TRIES; i++) {
      try {
        const res = await billingApi.completePayment(checkoutId);
        if (res.status === 200 && res.data.success) {
          setStatus("done");
          setTimeout(
            () => window.location.replace(res.data.redirect || "/owner/dashboard"),
            1500
          );
          return;
        }
      } catch (e) {
        const code = e?.response?.status;
        if (code !== 202 && code !== 400) {
          setStatus("failed");
          setError(errorText(e));
          return;
        }
      }
      await new Promise((r) => setTimeout(r, 3000));
    }
    setStatus("failed");
    setError("Payment received but confirmation is taking longer than expected. Do not pay again. Please refresh this page in a minute.");
  }

  run();
}, [checkoutId]);

  return (
    <div className="lp">
      <Navbar />
      <main className="au-main">
        <div className="au-shell">
          <div className="au-card">
            {status === "checking" && (
              <>
                <h2>Confirming your payment...</h2>
                <p>Please do not close this page.</p>
              </>
            )}
            {status === "done" && (
              <>
                <h2>Payment successful 🎉</h2>
                <p>Your account is active. Redirecting to your dashboard...</p>
              </>
            )}
            {status === "failed" && (
              <>
                <h2>We could not confirm your payment</h2>
                <div className="au-alert" role="alert">{error}</div>
                <button className="lp-btn lp-btn-primary au-submit" onClick={() => window.location.reload()}>Try again</button>
                <p className="au-switch"><Link to="/select-plan">Back to plans</Link></p>
              </>
            )}
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
}