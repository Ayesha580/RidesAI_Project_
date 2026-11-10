import { useCallback, useEffect, useState } from "react";
import StaffLayout from "../staff/components/StaffLayout";
import { operationsApi } from "../api/operationsApi";
import { errorText } from "../api/axiosClient";
export default function DeliveriesDashboard() {
  const [rows, setRows] = useState([]); const [error, setError] = useState(""); const [loading, setLoading] = useState(true);
  const load = useCallback(async () => { try { const { data } = await operationsApi.deliveries(); setRows(data); } catch (e) { setError(errorText(e)); } finally { setLoading(false); } }, []);
  useEffect(() => { load(); }, [load]);
  return <StaffLayout title="Deliveries" subtitle="View delivery assignments for your business role.">
    {error && <div className="ad-alert" role="alert">{error}</div>}
    {loading ? <div className="ad-skeleton" style={{ height: 140 }} /> : rows.length === 0 ? <div className="ad-empty"><span>🛵</span><h3>No active delivery assignments</h3></div> : <div style={{ display: "grid", gap: 12 }}>{rows.map((r) => <article key={r.id} style={{ background: "white", border: "1px solid #e5e7eb", borderRadius: 14, padding: 16 }}><strong>{r.order_number}</strong><p>{r.customer_name} · {r.customer_phone}</p><p>{r.delivery_address}</p><small>Rider: {r.rider_name} · {r.delivery_status}</small></article>)}</div>}
  </StaffLayout>;
}
