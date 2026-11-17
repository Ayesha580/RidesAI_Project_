import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import api from "../api/axiosClient";
import VoiceControls from "./components/VoiceControls";

export default function PublicAgentPage() {
  const { publicId } = useParams();
  const [customer, setCustomer] = useState({ name: "", email: "", phone: "" });
  const [message, setMessage] = useState("");
  const [conversationId, setConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [catalog, setCatalog] = useState([]);
  const [canOrder, setCanOrder] = useState(false);
  const [canHandover, setCanHandover] = useState(false);
  const [showOrder, setShowOrder] = useState(false);
  const [orderForm, setOrderForm] = useState({ item_id: "", quantity: "1", fulfillment_type: "delivery", address: "", city: "", country: "", latitude: "", longitude: "" });
  const [confirmOrder, setConfirmOrder] = useState(false);
  const [businessName, setBusinessName] = useState("Business assistant");
  const [lastAssistantReply, setLastAssistantReply] = useState("");
  useEffect(() => {
    api.get(`/operations/public/agent/${publicId}/catalog/`).then(({ data }) => {
      setCatalog(data.items || []); setCanOrder(!!data.can_order); setCanHandover(!!data.can_handover); setBusinessName(data.business || "Business assistant");
    }).catch((err) => setError(err.response?.data?.detail || "This business assistant is unavailable."));
  }, [publicId]);
  const sendPayload = async (text, action = null) => {
    setMessages((list) => [...list, { role: "user", content: text }]); setSending(true); setError("");
    try {
      const { data } = await api.post(`/operations/public/agent/${publicId}/chat/`, {
        message: text, action, conversation_id: conversationId, customer_name: customer.name,
        customer_email: customer.email, customer_phone: customer.phone,
      });
      setConversationId(data.conversation_id); setLastAssistantReply(data.answer || ""); setMessages((list) => [...list, { role: "assistant", content: data.answer }]);
    } catch (err) { setError(err.response?.data?.detail || "The assistant is temporarily unavailable."); }
    finally { setSending(false); }
  };
  const send = async (e) => {
    e.preventDefault(); if (!message.trim()) return;
    const text = message.trim(); setMessage(""); await sendPayload(text);
  };
  const placeOrder = async (e) => {
    e.preventDefault();
    if (!customer.name.trim() || !orderForm.item_id) { setError("Enter your name and select an available item."); return; }
    const item = catalog.find((x) => String(x.id) === String(orderForm.item_id));
    if (orderForm.fulfillment_type === "delivery" && (!orderForm.address.trim() || !orderForm.city.trim() || !orderForm.country.trim())) { setError("Enter the full delivery address, city and country."); return; }
    if (!confirmOrder) { setError("Please confirm the order summary before submitting."); return; }
    setShowOrder(false);
    await sendPayload(`Please place this confirmed ${orderForm.fulfillment_type} order for ${item?.name || "the selected item"}.`, {
      type: "create_order", confirmed: true, data: { customer_name: customer.name, customer_email: customer.email,
        customer_phone: customer.phone, fulfillment_type: orderForm.fulfillment_type,
        delivery_address: orderForm.fulfillment_type === "delivery" ? orderForm.address : "",
        city: orderForm.city, country: orderForm.country, latitude: orderForm.latitude || null, longitude: orderForm.longitude || null,
        items: [{ item_id: Number(orderForm.item_id), quantity: orderForm.quantity }] },
    });
    setConfirmOrder(false);
  };
  const handover = () => sendPayload("Please connect me to a human team member.", { type: "handover" });
  const refreshConversation = async () => {
    if (!conversationId) return;
    try {
      const { data } = await api.get(`/operations/public/agent/${publicId}/conversation/${conversationId}/`);
      setMessages(data.messages || []);
    } catch (err) { setError(err.response?.data?.detail || "Could not refresh this conversation."); }
  };
  return <main style={{ minHeight: "100vh", background: "#f8fafc", display: "grid", placeItems: "center", padding: 18 }}>
    <section style={{ width: "min(680px,100%)", background: "white", border: "1px solid #e5e7eb", borderRadius: 18, padding: 20, boxShadow: "0 12px 35px rgba(15,23,42,.06)" }}>
      <h1 style={{ margin: 0 }}>{businessName}</h1><p style={{ color: "#64748b", marginTop: 6 }}>Ask about products, services, prices or your order.</p>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(160px,1fr))", gap: 8, marginBottom: 12 }}>
        <input placeholder="Your name" value={customer.name} onChange={(e) => setCustomer({ ...customer, name: e.target.value })} />
        <input type="email" placeholder="Your email (optional)" value={customer.email} onChange={(e) => setCustomer({ ...customer, email: e.target.value })} />
        <input placeholder="Your phone (optional)" value={customer.phone} onChange={(e) => setCustomer({ ...customer, phone: e.target.value })} />
      </div>
      <div aria-live="polite" style={{ minHeight: 300, maxHeight: "55vh", overflowY: "auto", background: "#f8fafc", borderRadius: 12, padding: 12, marginBottom: 12 }}>
        {messages.length === 0 ? <p style={{ color: "#94a3b8" }}>Hello! How can we help you today?</p> : messages.map((m, i) => <div key={i} style={{ textAlign: m.role === "user" ? "right" : "left", margin: "8px 0" }}><span style={{ display: "inline-block", padding: 10, borderRadius: 12, maxWidth: "85%", background: m.role === "user" ? "#fce7f3" : "white", border: "1px solid #e5e7eb", whiteSpace: "pre-wrap" }}>{m.content}</span></div>)}
      </div>
      {error && <p role="alert" style={{ color: "#b91c1c" }}>{error}</p>}
      <form onSubmit={send} style={{ display: "flex", gap: 8 }}><input style={{ flex: 1, minWidth: 0 }} placeholder="Type your question..." value={message} onChange={(e) => setMessage(e.target.value)} /><button className="ad-btn ad-btn-primary" disabled={sending || !message.trim()}>{sending ? "Sending..." : "Send"}</button></form>
      <VoiceControls onTranscript={(transcript) => setMessage(transcript)} speechText={lastAssistantReply} disabled={sending} />
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12 }}>
        {canOrder && <button type="button" className="ad-btn ad-btn-ghost" onClick={() => setShowOrder((v) => !v)}>Place an order</button>}
        {canHandover && <button type="button" className="ad-btn ad-btn-ghost" disabled={sending} onClick={handover}>Talk to a person</button>}
        {conversationId && <button type="button" className="ad-btn ad-btn-ghost" onClick={refreshConversation}>Refresh replies</button>}
      </div>
      {showOrder && <form onSubmit={placeOrder} style={{ display: "grid", gap: 8, marginTop: 12, padding: 12, border: "1px solid #e5e7eb", borderRadius: 12 }}>
        <strong>Place an order</strong>
        <select required value={orderForm.item_id} onChange={(e) => setOrderForm({ ...orderForm, item_id: e.target.value })}><option value="">Select an item</option>{catalog.map((item) => <option key={item.id} value={item.id} disabled={!item.in_stock}>{item.name} · {item.price}{item.unit ? ` / ${item.unit}` : ""}{item.in_stock ? "" : " · Out of stock"}</option>)}</select>
        <input required type="number" min="0.001" step="0.001" placeholder="Quantity" value={orderForm.quantity} onChange={(e) => setOrderForm({ ...orderForm, quantity: e.target.value })} />
        <select value={orderForm.fulfillment_type} onChange={(e) => setOrderForm({ ...orderForm, fulfillment_type: e.target.value })}><option value="delivery">Delivery</option><option value="collection">Collection / pickup</option></select>
        {orderForm.fulfillment_type === "delivery" && <>
          <input required placeholder="Full delivery address" value={orderForm.address} onChange={(e) => setOrderForm({ ...orderForm, address: e.target.value })} />
          <input required placeholder="City" value={orderForm.city} onChange={(e) => setOrderForm({ ...orderForm, city: e.target.value })} />
          <input required placeholder="Country" value={orderForm.country} onChange={(e) => setOrderForm({ ...orderForm, country: e.target.value })} />
          <input type="number" step="any" placeholder="Latitude (required for radius zones)" value={orderForm.latitude} onChange={(e) => setOrderForm({ ...orderForm, latitude: e.target.value })} />
          <input type="number" step="any" placeholder="Longitude (required for radius zones)" value={orderForm.longitude} onChange={(e) => setOrderForm({ ...orderForm, longitude: e.target.value })} />
        </>}
        <p style={{fontSize:13,margin:0}}>Order summary: {item?.name} × {orderForm.quantity} = {item ? (Number(item.price) * Number(orderForm.quantity)).toFixed(2) : "—"}. Delivery fee is calculated by the business system.</p>
        <label style={{display:"flex",gap:8,alignItems:"center",fontSize:13}}><input type="checkbox" checked={confirmOrder} onChange={e=>setConfirmOrder(e.target.checked)}/> I confirm these items and fulfilment details.</label>
        <button className="ad-btn ad-btn-primary" disabled={sending || !confirmOrder}>Confirm and submit order</button>
      </form>}
    </section>
  </main>;
}
