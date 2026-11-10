import { useCallback, useEffect, useState } from "react";
import StaffLayout from "../staff/components/StaffLayout";
import { operationsApi } from "../api/operationsApi";
import { errorText } from "../api/axiosClient";

const NEXT = { assigned: "picked_up", picked_up: "on_the_way", on_the_way: "delivered" };
const LABEL = { assigned: "Mark picked up", picked_up: "Start delivery", on_the_way: "Mark delivered" };

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
        <strong>{o.order_number}</strong><p style={{ margin: "6px 0", fontWeight: 600 }}>{o.customer_name} · {o.customer_phone || "No phone"}</p>
        <p style={{ color: "#4b5563", fontSize: 13 }}>{o.delivery_address || "No delivery address provided"}</p>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <span>{o.status.replaceAll("_", " ")}</span>
          {NEXT[o.status] && <button className="ad-btn ad-btn-primary" disabled={busy === o.id} onClick={() => advance(o)}>{busy === o.id ? "Updating..." : LABEL[o.status]}</button>}
        </div>
      </article>)}
    </div>}
  </StaffLayout>;
}
