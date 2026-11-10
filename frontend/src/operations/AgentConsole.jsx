import { useEffect, useState } from "react";
import OwnerLayout from "../owner/components/OwnerLayout";
import { operationsApi } from "../api/operationsApi";
import { errorText } from "../api/axiosClient";
import VoiceControls from "./components/VoiceControls";

const ACTIONS = [
  ["lookup_order", "Look up order status"],
  ["create_order", "Create orders"],
  ["update_order_status", "Update order status"],
  ["handover", "Hand over to a human"],
];
export default function AgentConsole() {
  const [settings, setSettings] = useState({ enabled: false, allowed_actions: [], greeting: "", tone: "friendly", support_phone: "", support_email: "" });
  const [messages, setMessages] = useState([]);
  const [message, setMessage] = useState("");
  const [conversationId, setConversationId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [lastAssistantReply, setLastAssistantReply] = useState("");
  useEffect(() => { operationsApi.agentSettings().then(({ data }) => setSettings(data)).catch((e) => setError(errorText(e))).finally(() => setLoading(false)); }, []);
  const toggleAction = (key) => setSettings((s) => ({ ...s, allowed_actions: s.allowed_actions.includes(key) ? s.allowed_actions.filter((x) => x !== key) : [...s.allowed_actions, key] }));
  const save = async () => { setError(""); try { const { data } = await operationsApi.updateAgentSettings(settings); setSettings(data); } catch (e) { setError(errorText(e)); } };
  const send = async (e) => {
    e.preventDefault(); if (!message.trim()) return; setSending(true); setError("");
    const outgoing = message.trim(); setMessages((m) => [...m, { role: "user", content: outgoing }]); setMessage("");
    try {
      const { data } = await operationsApi.chat({ message: outgoing, conversation_id: conversationId });
      setConversationId(data.conversation_id); setLastAssistantReply(data.answer || ""); setMessages((m) => [...m, { role: "assistant", content: data.answer }]);
    } catch (e) { setError(errorText(e)); }
    finally { setSending(false); }
  };
  const publicUrl = settings.public_id ? `${window.location.origin}/agent/${settings.public_id}` : "";
  return <OwnerLayout title="AI Agent" subtitle="Connect the assistant to this business catalogue and order records.">
    {error && <div className="ad-alert" role="alert">{error}</div>}
    <section style={{ background: "white", border: "1px solid #e5e7eb", borderRadius: 14, padding: 18, marginBottom: 18 }}>
      <h3 style={{ marginTop: 0 }}>Agent permissions</h3>
      <p style={{ color: "#6b7280", fontSize: 13 }}>Only enable actions the agent is allowed to execute. Every action is checked and logged by the backend.</p>
      <label style={{ display: "flex", gap: 8, margin: "12px 0" }}><input type="checkbox" checked={settings.enabled} onChange={(e) => setSettings({ ...settings, enabled: e.target.checked })} /> Enable AI Agent</label>
      {ACTIONS.map(([key, label]) => <label key={key} style={{ display: "flex", gap: 8, margin: "8px 0" }}><input type="checkbox" checked={settings.allowed_actions.includes(key)} onChange={() => toggleAction(key)} /> {label}</label>)}
      <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(190px,1fr))",gap:10,marginTop:14}}>
        <label style={{display:"grid",gap:5,fontSize:13}}>Response tone<select value={settings.tone || "friendly"} onChange={e=>setSettings({...settings,tone:e.target.value})}><option value="friendly">Friendly</option><option value="professional">Professional</option><option value="concise">Concise</option></select></label>
        <label style={{display:"grid",gap:5,fontSize:13}}>Support phone<input value={settings.support_phone || ""} onChange={e=>setSettings({...settings,support_phone:e.target.value})} /></label>
        <label style={{display:"grid",gap:5,fontSize:13}}>Support email<input type="email" value={settings.support_email || ""} onChange={e=>setSettings({...settings,support_email:e.target.value})} /></label>
      </div>
      <label style={{display:"grid",gap:5,fontSize:13,marginTop:12}}>Welcome greeting<textarea rows={2} value={settings.greeting || ""} onChange={e=>setSettings({...settings,greeting:e.target.value})} placeholder="Welcome! How can I help you today?" /></label>
      <button className="ad-btn ad-btn-primary" disabled={loading} onClick={save}>Save agent settings</button>
      {publicUrl && <p style={{ marginBottom: 0, marginTop: 14, fontSize: 13 }}>Public customer chat link: <a href={publicUrl} target="_blank" rel="noreferrer">{publicUrl}</a></p>}
    </section>
    <section style={{ background: "white", border: "1px solid #e5e7eb", borderRadius: 14, padding: 18 }}>
      <h3 style={{ marginTop: 0 }}>Test conversation</h3>
      <div style={{ minHeight: 170, maxHeight: 360, overflowY: "auto", background: "#f9fafb", padding: 12, borderRadius: 10, marginBottom: 12 }}>
        {messages.length === 0 ? <p style={{ color: "#9ca3af" }}>Ask about your products, prices or an order to test the backend connection.</p> : messages.map((m, i) => <div key={i} style={{ margin: "8px 0", textAlign: m.role === "user" ? "right" : "left" }}><span style={{ display: "inline-block", padding: 10, borderRadius: 10, background: m.role === "user" ? "#fce7f3" : "white", maxWidth: "85%" }}>{m.content}</span></div>)}
      </div>
      <form onSubmit={send} style={{ display: "flex", gap: 8 }}><input style={{ flex: 1, minWidth: 0 }} value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Ask the business assistant..." /><button className="ad-btn ad-btn-primary" disabled={sending || !settings.enabled}>{sending ? "Sending..." : "Send"}</button></form>
      <VoiceControls onTranscript={(transcript) => setMessage(transcript)} speechText={lastAssistantReply} disabled={sending || !settings.enabled} />
      {!settings.enabled && <small style={{ color: "#9ca3af" }}>Enable the agent before testing.</small>}
    </section>
  </OwnerLayout>;
}
