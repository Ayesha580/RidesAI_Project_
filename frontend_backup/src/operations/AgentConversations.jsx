import { useCallback, useEffect, useState } from "react";
import OwnerLayout from "../owner/components/OwnerLayout";
import { operationsApi } from "../api/operationsApi";
import { errorText } from "../api/axiosClient";
export default function AgentConversations() {
  const [rows, setRows] = useState([]); const [error, setError] = useState("");
  const load = useCallback(async () => { try { const { data } = await operationsApi.conversations(); setRows(data); } catch (e) { setError(errorText(e)); } }, []);
  useEffect(() => { load(); }, [load]);
  const [replies, setReplies] = useState({});
  const handover = async (row, status) => { try { await operationsApi.updateConversation({ conversation_id: row.id, status }); await load(); } catch (e) { setError(errorText(e)); } };
  const reply = async (row) => { const message = (replies[row.id] || "").trim(); if (!message) return; try { await operationsApi.updateConversation({ conversation_id: row.id, status: "human", message }); setReplies((s) => ({ ...s, [row.id]: "" })); await load(); } catch (e) { setError(errorText(e)); } };
  return <OwnerLayout title="Conversations" subtitle="Review customer conversations and manage human handover.">
    {error && <div className="ad-alert" role="alert">{error}</div>}
    {rows.length === 0 ? <div className="ad-empty"><span>💬</span><h3>No conversations yet</h3><p>Conversations created through the AI Agent will appear here.</p></div> : <div style={{ display: "grid", gap: 12 }}>{rows.map((r) => <article key={r.id} style={{ background: "white", border: "1px solid #e5e7eb", borderRadius: 14, padding: 16 }}><div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}><strong>{r.customer_name || r.customer_email || "Customer"}</strong><span>{r.status}</span></div><div style={{ margin: "12px 0" }}>{r.messages.slice(-4).map((m, i) => <p key={i} style={{ fontSize: 13, color: "#4b5563" }}><b>{m.role}:</b> {m.content}</p>)}</div><div style={{ display: "flex", gap: 8 }}><button className="ad-btn ad-btn-primary" onClick={() => handover(r, "human")}>Take over</button><button className="ad-btn ad-btn-ghost" onClick={() => handover(r, "bot")}>Return to AI</button><button className="ad-btn ad-btn-ghost" onClick={() => handover(r, "closed")}>Close</button></div><form onSubmit={(e) => { e.preventDefault(); reply(r); }} style={{ display: "flex", gap: 8, marginTop: 12 }}><input style={{ flex: 1, minWidth: 0 }} placeholder="Reply as a human agent..." value={replies[r.id] || ""} onChange={(e) => setReplies((s) => ({ ...s, [r.id]: e.target.value }))} /><button className="ad-btn ad-btn-primary">Send reply</button></form></article>)}</div>}
  </OwnerLayout>;
}
