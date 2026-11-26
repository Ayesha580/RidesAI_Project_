import { useCallback, useEffect, useState } from "react";
import StaffLayout from "../staff/components/StaffLayout";
import { operationsApi } from "../api/operationsApi";
import { errorText } from "../api/axiosClient";

const NEXT = { assigned: "picked_up", picked_up: "on_the_way", on_the_way: "delivered" };
const LABEL = { assigned: "Mark picked up", picked_up: "Start delivery", on_the_way: "Mark delivered" };

function toWaNumber(raw) {
  const digits = String(raw || "").replace(/\D/g, "");
  if (!digits) return "";
  if (digits.startsWith("03") && digits.length === 11) return "92" + digits.slice(1);
  if (digits.startsWith("00")) return digits.slice(2);
  return digits;
}

export default function RiderDeliveries() {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    try { const { data } = await operationsApi.myDeliveries(); setOrders(data); }
    catch (e) { setError(errorText(e)); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);
  const advance = async (order) => {
    setBusy(order.id); setError("");
    try { await operationsApi.updateOrderStatus(order.id, NEXT[order.status]); await load(); }
    catch (e) { setError(errorText(e)); }
    finally { setBusy(null); }
  };
  return <StaffLayout title="My deliveries" subtitle="Only deliveries assigned to your rider account are shown.">
    {error && <div className="ad-alert" role="alert">{error}</div>}
    {loading ? <div className="ad-skeleton" style={{ height: 150 }} /> : orders.length === 0 ? <div className="ad-empty"><span>🛵</span><h3>No assigned deliveries</h3><p>Your assigned orders will appear here.</p></div> : <div style={{ display: "grid", gap: 12 }}>
      {orders.map((o) => <article key={o.id} style={{ background: "white", border: "1px solid #e5e7eb", borderRadius: 14, padding: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <strong>{o.order_number}</strong>
          {(o.is_exchange || (o.notes && o.notes.includes("EXCHANGE SWAP"))) && (
            <span style={{
              background: "rgba(255, 119, 255, 0.16)",
              color: "#c026d3",
              border: "1px solid rgba(255, 119, 255, 0.4)",
              borderRadius: "20px",
              padding: "2px 8px",
              fontSize: "11px",
              fontWeight: "800",
            }}>
              🔄 SWAP
            </span>
          )}
        </div>
        {(o.is_exchange || (o.notes && o.notes.includes("EXCHANGE SWAP"))) && (
          <div style={{
            margin: "8px 0",
            padding: "8px 10px",
            background: "#fdf4ff",
            border: "1px solid #f0abfc",
            borderRadius: "8px",
            color: "#86198f",
            fontSize: "12px",
            fontWeight: "600",
          }}>
            🔄 <strong>EXCHANGE SWAP:</strong> Hand over replacement &amp; collect original item!
          </div>
        )}
        <p style={{ margin: "6px 0", fontWeight: 600 }}>{o.customer_name} · {o.customer_phone || "No phone"}</p>
        <p style={{ color: "#4b5563", fontSize: 13 }}>{o.delivery_address || "No delivery address provided"}</p>
        {o.customer_phone && (
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", margin: "8px 0 10px" }}>
            <a
              href={`tel:${o.customer_phone}`}
              style={{
                textDecoration: "none",
                fontSize: 12,
                fontWeight: 700,
                padding: "5px 10px",
                borderRadius: 8,
                background: "#f8fafc",
                color: "#0f172a",
                border: "1px solid #cbd5e1",
              }}
            >
              📞 Call Customer
            </a>
            <a
              href={`https://wa.me/${toWaNumber(o.customer_phone)}?text=${encodeURIComponent(
                `Assalam-o-Alaikum, aapka Order #${o.order_number} delivery par hai. Please exact location/address confirm kar dein.`
              )}`}
              target="_blank"
              rel="noreferrer"
              style={{
                textDecoration: "none",
                fontSize: 12,
                fontWeight: 700,
                padding: "5px 10px",
                borderRadius: 8,
                background: "#ecfdf5",
                color: "#047857",
                border: "1px solid #a7f3d0",
              }}
            >
              💬 WhatsApp Customer
            </a>
          </div>
        )}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <span>{o.status.replaceAll("_", " ")}</span>
          {NEXT[o.status] && <button className="ad-btn ad-btn-primary" disabled={busy === o.id} onClick={() => advance(o)}>{busy === o.id ? "Updating..." : LABEL[o.status]}</button>}
        </div>
      </article>)}
    </div>}
  </StaffLayout>;
}
