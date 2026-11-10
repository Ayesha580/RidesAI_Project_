import { useCallback, useEffect, useState } from "react";
import OwnerLayout from "../owner/components/OwnerLayout";
import StaffLayout from "../staff/components/StaffLayout";
import { useAuth } from "../context/AuthContext";
import { operationsApi } from "../api/operationsApi";
import { errorText } from "../api/axiosClient";
import { staffApi } from "../api/staff_api";

const STATUSES = ["new", "confirmed", "preparing", "ready", "assigned", "picked_up", "on_the_way", "delivered", "cancelled"];
const can = (user, permission) => user?.role === "owner" || (user?.permissions || []).includes("*") || (user?.permissions || []).includes(permission);

export default function OrdersDashboard({ staff = false }) {
  const { user } = useAuth();
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(null);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ customer_name: "", customer_phone: "", delivery_address: "", city: "", country: "", fulfillment_type: "collection", item_id: "", quantity: "1" });
  const [saving, setSaving] = useState(false);
  const [riders, setRiders] = useState([]);
  const [selectedRiders, setSelectedRiders] = useState({});
  const [catalogItems, setCatalogItems] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [selectedEmployees, setSelectedEmployees] = useState({});

  const load = useCallback(async () => {
    setError("");
    try { const { data } = await operationsApi.orders(); setOrders(data); }
    catch (e) { setError(errorText(e)); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (can(user, "orders.create")) {
      operationsApi.orderCatalog().then(({ data }) => setCatalogItems(data)).catch(() => {});
    }
    if (can(user, "deliveries.assign")) {
      operationsApi.riders().then(({ data }) => setRiders(data)).catch(() => {});
    }
    if (can(user, "orders.assign")) staffApi.list().then(({data}) => setEmployees((data || []).filter(x => x.is_active))).catch(() => {});
  }, [user]);

  const updateStatus = async (order, status) => {
    setBusy(order.id); setError("");
    try { await operationsApi.updateOrderStatus(order.id, status); await load(); }
    catch (e) { setError(errorText(e)); }
    finally { setBusy(null); }
  };

  const assignEmployee = async (order) => {
    const employeeId = selectedEmployees[order.id];
    if (!employeeId) return;
    setBusy(order.id); setError("");
    try { await operationsApi.assignOrder(order.id, { employee_id: Number(employeeId) }); await load(); }
    catch (e) { setError(errorText(e)); }
    finally { setBusy(null); }
  };

  const assignRider = async (order) => {
    const riderId = selectedRiders[order.id] || order.delivery?.rider_id;
    if (!riderId) return;
    setBusy(order.id); setError("");
    try { await operationsApi.assignDelivery(order.id, Number(riderId)); await load(); }
    catch (e) { setError(errorText(e)); }
    finally { setBusy(null); }
  };

  const create = async (e) => {
    e.preventDefault(); setSaving(true); setError("");
    try {
      await operationsApi.createOrder({
        customer_name: form.customer_name, customer_phone: form.customer_phone,
        fulfillment_type: form.fulfillment_type, delivery_address: form.fulfillment_type === "delivery" ? form.delivery_address : "",
        city: form.city, country: form.country,
        items: [{ item_id: Number(form.item_id), quantity: form.quantity }],
      });
      setShowCreate(false); setForm({ customer_name: "", customer_phone: "", delivery_address: "", city: "", country: "", fulfillment_type: "collection", item_id: "", quantity: "1" });
      await load();
    } catch (e) { setError(errorText(e)); }
    finally { setSaving(false); }
  };

  const content = (
    <>
      {error && <div className="ad-alert" role="alert">{error}</div>}
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", marginBottom: 16 }}>
        <p style={{ color: "#6b7280", margin: 0 }}>Orders for {user?.company_name || "your business"}. Status changes are saved to the backend audit trail.</p>
        {can(user, "orders.create") && <button className="ad-btn ad-btn-primary" onClick={() => setShowCreate((v) => !v)}>+ Create order</button>}
      </div>
      {showCreate && <form onSubmit={create} style={{ background: "white", border: "1px solid #e5e7eb", borderRadius: 14, padding: 18, marginBottom: 18, display: "grid", gap: 10, gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))" }}>
        <input required placeholder="Customer name" value={form.customer_name} onChange={(e) => setForm({ ...form, customer_name: e.target.value })} />
        <input placeholder="Phone" value={form.customer_phone} onChange={(e) => setForm({ ...form, customer_phone: e.target.value })} />
        <select required value={form.item_id} onChange={(e) => setForm({ ...form, item_id: e.target.value })}><option value="">Select catalogue item</option>{catalogItems.map((item) => <option key={item.id} value={item.id} disabled={!item.in_stock}>{item.name} · {item.price} {item.unit || ""}{item.in_stock ? "" : " · Out of stock"}</option>)}</select>
        <input required type="number" min="0.001" step="0.001" placeholder="Quantity" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} />
        <select value={form.fulfillment_type} onChange={e=>setForm({...form,fulfillment_type:e.target.value})}><option value="collection">Collection / pickup</option><option value="delivery">Delivery</option></select>
        {form.fulfillment_type === "delivery" && <><input required placeholder="Full delivery address" value={form.delivery_address} onChange={(e) => setForm({ ...form, delivery_address: e.target.value })} /><input required placeholder="City" value={form.city} onChange={e=>setForm({...form,city:e.target.value})}/><input required placeholder="Country" value={form.country} onChange={e=>setForm({...form,country:e.target.value})}/></>}
        <button className="ad-btn ad-btn-primary" disabled={saving || !catalogItems.length}>{saving ? "Saving..." : "Save order"}</button>
      </form>}
      {loading ? <div className="ad-skeleton" style={{ height: 160 }} /> : orders.length === 0 ? <div className="ad-empty"><span>📦</span><h3>No orders yet</h3><p>Orders created by your team and connected AI workflows will appear here.</p></div> :
        <div style={{ display: "grid", gap: 12 }}>
          {orders.map((order) => <article key={order.id} style={{ background: "white", border: "1px solid #e5e7eb", borderRadius: 14, padding: 16 }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
              <div><strong>{order.order_number}</strong><div style={{ color: "#6b7280", fontSize: 13 }}>{order.customer_name} · {order.customer_phone || "No phone"}</div></div>
              <strong>{order.total} {user?.currency || ""}</strong>
            </div>
            <div style={{ margin: "12px 0", color: "#4b5563", fontSize: 13 }}>{order.items.map((i) => `${i.name} × ${i.quantity}`).join(" · ")}</div>
            {(order.assigned_to_name || order.assigned_team) && <div style={{color:"#4b5563",fontSize:13,marginBottom:6}}>Assigned: {order.assigned_to_name || order.assigned_team}</div>}
            {order.delivery && <div style={{ color: "#4b5563", fontSize: 13, marginBottom: 8 }}>Rider: {order.delivery.rider_name} · {order.delivery.status}</div>}
            <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
              <span style={{ padding: "5px 9px", background: "#f3f4f6", borderRadius: 20, fontSize: 12 }}>{order.status.replaceAll("_", " ")}</span>
              {can(user, "orders.update_status") && <select aria-label={`Update status for ${order.order_number}`} disabled={busy === order.id} value={order.status} onChange={(e) => updateStatus(order, e.target.value)}>{STATUSES.map((s) => <option key={s} value={s}>{s.replaceAll("_", " ")}</option>)}</select>}
              {can(user, "orders.assign") && employees.length > 0 && <>
                <select aria-label={`Assign team member for ${order.order_number}`} value={selectedEmployees[order.id] || order.assigned_to_id || ""} onChange={e=>setSelectedEmployees(s=>({...s,[order.id]:e.target.value}))}>
                  <option value="">Assign employee</option>{employees.map(emp=><option key={emp.id} value={emp.id}>{emp.full_name || emp.username} · {emp.role_name || "Staff"}</option>)}
                </select>
                <button className="ad-btn ad-btn-ghost" disabled={busy===order.id || !(selectedEmployees[order.id] || order.assigned_to_id)} onClick={()=>assignEmployee(order)}>Assign</button>
              </>}
              {can(user, "deliveries.assign") && riders.length > 0 && order.status !== "delivered" && <>
                <select aria-label={`Select rider for ${order.order_number}`} value={selectedRiders[order.id] || order.delivery?.rider_id || ""} onChange={(e) => setSelectedRiders((s) => ({ ...s, [order.id]: e.target.value }))}>
                  <option value="">Select rider</option>{riders.map((r) => <option key={r.id} value={r.id}>{r.full_name}</option>)}
                </select>
                <button className="ad-btn ad-btn-ghost" disabled={busy === order.id || !(selectedRiders[order.id] || order.delivery?.rider_id)} onClick={() => assignRider(order)}>Assign rider</button>
              </>}
              <small style={{ color: "#9ca3af" }}>{new Date(order.created_at).toLocaleString()}</small>
            </div>
            {order.events?.length > 0 && <details style={{ marginTop: 10, color: "#6b7280", fontSize: 12 }}><summary>Order history ({order.events.length})</summary>{order.events.map((event, i) => <p key={i} style={{ margin: "6px 0" }}>{event.type.replaceAll("_", " ")} · {event.from_status || "-"} → {event.to_status || "-"} · {event.actor} · {new Date(event.created_at).toLocaleString()}</p>)}</details>}
          </article>)}
        </div>}
    </>
  );
  return staff ? <StaffLayout title="Orders" subtitle="View and update the orders your role allows.">{content}</StaffLayout> : <OwnerLayout title="Orders" subtitle="Manage customer orders and fulfilment.">{content}</OwnerLayout>;
}
