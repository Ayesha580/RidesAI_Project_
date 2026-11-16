import React, { useState, useEffect, useCallback } from "react";
import OwnerLayout from "../../../owner/components/OwnerLayout";
import api, { errorText } from "../../../api/axiosClient";

const css = `
.kb-container {
  max-width: 980px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 24px;
}
.kb-alert {
  padding: 13px 18px;
  border-radius: 12px;
  font-size: 13.5px;
  font-weight: 500;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.kb-alert-success {
  background: #f0fdf4;
  color: #166534;
  border: 1px solid #bbf7d0;
}
.kb-alert-error {
  background: #fef2f2;
  color: #991b1b;
  border: 1px solid #fecaca;
}
.kb-card {
  background: #ffffff;
  border-radius: 16px;
  border: 1px solid #eee8f0;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.04);
  overflow: hidden;
}
.kb-card-header {
  padding: 22px 24px;
  border-bottom: 1px solid #f1ebf2;
  background: #faf8fb;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
}
.kb-brand {
  display: flex;
  align-items: center;
  gap: 14px;
}
.kb-icon-badge {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: rgba(192, 38, 211, 0.1);
  color: #c026d3;
  display: grid;
  place-items: center;
  font-size: 22px;
}
.kb-brand h2 {
  margin: 0;
  font-size: 17px;
  font-weight: 750;
  color: #1f2937;
}
.kb-brand p {
  margin: 3px 0 0;
  font-size: 12.5px;
  color: #6b7280;
}
.kb-form {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.kb-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.kb-label {
  font-size: 11.5px;
  font-weight: 750;
  letter-spacing: 0.8px;
  text-transform: uppercase;
  color: #4b5563;
}
.kb-input, .kb-textarea, .kb-select {
  width: 100%;
  box-sizing: border-box;
  padding: 10px 14px;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  font-size: 13.5px;
  color: #111827;
  background: #ffffff;
  outline: none;
  font-family: inherit;
  transition: all 0.2s ease;
}
.kb-input:focus, .kb-textarea:focus, .kb-select:focus {
  border-color: #c026d3;
  box-shadow: 0 0 0 3px rgba(192, 38, 211, 0.15);
}
.kb-textarea {
  min-height: 95px;
  resize: vertical;
  line-height: 1.5;
}
.kb-suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 4px;
}
.kb-pill {
  background: #fdf4ff;
  border: 1px solid #f5d0fe;
  color: #a21caf;
  border-radius: 20px;
  padding: 4px 12px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.18s ease;
}
.kb-pill:hover {
  background: #fae8ff;
  border-color: #e879f9;
  transform: translateY(-1px);
}
.kb-btn-save {
  padding: 11px 24px;
  background: #c026d3;
  color: #ffffff;
  border: 1px solid #c026d3;
  border-radius: 11px;
  font-size: 14px;
  font-weight: 650;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  box-shadow: 0 4px 14px rgba(192, 38, 211, 0.25);
  transition: all 0.2s ease;
}
.kb-btn-save:hover:not(:disabled) {
  background: #a21caf;
  border-color: #a21caf;
  transform: translateY(-1px);
  box-shadow: 0 6px 18px rgba(192, 38, 211, 0.35);
}
.kb-btn-save:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.kb-table-wrap {
  overflow-x: auto;
}
.kb-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  font-size: 13.5px;
}
.kb-table th {
  background: #faf8fb;
  padding: 13px 18px;
  font-size: 11px;
  font-weight: 750;
  text-transform: uppercase;
  letter-spacing: 0.7px;
  color: #6b7280;
  border-bottom: 1px solid #eee8f0;
}
.kb-table td {
  padding: 16px 18px;
  border-bottom: 1px solid #f1ebf2;
  vertical-align: top;
}
.kb-table tr:hover td {
  background: #fdfcff;
}
.kb-badge {
  display: inline-block;
  padding: 3px 9px;
  border-radius: 16px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.kb-badge-faq {
  background: #fdf4ff;
  color: #a21caf;
  border: 1px solid #f5d0fe;
}
.kb-badge-policy {
  background: #eff6ff;
  color: #1d4ed8;
  border: 1px solid #bfdbfe;
}
.kb-badge-approved {
  background: #f0fdf4;
  color: #15803d;
  border: 1px solid #bbf7d0;
}
.kb-action-del {
  padding: 6px 12px;
  background: #fff;
  border: 1px solid #fecaca;
  color: #dc2626;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}
.kb-action-del:hover {
  background: #fef2f2;
  border-color: #ef4444;
}
.kb-search-bar {
  padding: 8px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  font-size: 13px;
  width: 240px;
  outline: none;
}
.kb-search-bar:focus {
  border-color: #c026d3;
}
.kb-empty {
  padding: 48px 20px;
  text-align: center;
  color: #6b7280;
}
.kb-empty-icon {
  font-size: 32px;
  margin-bottom: 8px;
  display: block;
}
`;

const SUGGESTIONS = [
  { q: "What are your operating hours?", a: "We are open Monday to Sunday from 9:00 AM to 10:00 PM." },
  { q: "What is your delivery coverage?", a: "We deliver across the central metro zone with typical delivery times within 30-45 minutes." },
  { q: "What payment methods do you accept?", a: "We accept credit/debit cards, Apple Pay, Google Pay, and Cash on Delivery." },
  { q: "What is your return or refund policy?", a: "If your order has an issue or missing items, contact our support team within 24 hours for a prompt replacement or refund." },
];

export default function KnowledgeBaseForm() {
  const [faqs, setFaqs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState("");
  const [notice, setNotice] = useState({ type: "", text: "" });

  // Form State
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [entryType, setEntryType] = useState("faq");

  // Fetch knowledge items from backend
  const loadKnowledge = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/companies/knowledge/");
      setFaqs(Array.isArray(data) ? data : data.results || []);
    } catch (err) {
      setNotice({ type: "error", text: errorText(err) });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadKnowledge();
  }, [loadKnowledge]);

  // Handle Create Knowledge Q&A
  const handleAddFaq = async (e) => {
    e.preventDefault();
    if (!question.trim() || !answer.trim()) return;

    setSaving(true);
    setNotice({ type: "", text: "" });

    try {
      await api.post("/companies/knowledge/", {
        entry_type: entryType,
        title: question.trim(),
        content: answer.trim(),
        is_approved: true,
        is_active: true,
      });

      setNotice({ type: "success", text: "Q&A pair saved and immediately grounded in AI agent memory!" });
      setQuestion("");
      setAnswer("");
      await loadKnowledge();
    } catch (err) {
      setNotice({ type: "error", text: errorText(err) });
    } finally {
      setSaving(false);
    }
  };

  // Handle Delete Knowledge Q&A
  const handleDeleteFaq = async (id) => {
    if (!window.confirm("Are you sure you want to delete this FAQ entry? The AI Agent will no longer use it.")) return;

    try {
      await api.delete(`/companies/knowledge/${id}/`);
      setNotice({ type: "success", text: "FAQ entry removed." });
      setFaqs((prev) => prev.filter((item) => item.id !== id));
    } catch (err) {
      setNotice({ type: "error", text: errorText(err) });
    }
  };

  // Pre-fill prompt from template pill
  const handleApplySuggestion = (s) => {
    setQuestion(s.q);
    setAnswer(s.a);
  };

  const filteredFaqs = faqs.filter((f) => {
    const q = (f.title || "").toLowerCase();
    const a = (f.content || "").toLowerCase();
    const query = search.toLowerCase();
    return q.includes(query) || a.includes(query);
  });

  return (
    <OwnerLayout
      title="AI Knowledge Base"
      subtitle="Teach your AI Voice & Chat Agent approved answers to common customer questions, store policies, and operating details."
    >
      <style>{css}</style>
      <div className="kb-container max-w-5xl mx-auto space-y-6 text-gray-800">
        {/* Notice Banner */}
        {notice.text && (
          <div className={`kb-alert ${notice.type === "success" ? "kb-alert-success" : "kb-alert-error"}`}>
            <span>{notice.text}</span>
            <button
              type="button"
              onClick={() => setNotice({ type: "", text: "" })}
              style={{ background: "transparent", border: "none", cursor: "pointer", fontWeight: 700 }}
            >
              ✕
            </button>
          </div>
        )}

        {/* Add Q&A Card */}
        <div className="kb-card bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="kb-card-header p-6 border-b border-gray-100 flex items-center justify-between">
            <div className="kb-brand flex items-center space-x-3.5">
              <div className="kb-icon-badge w-11 h-11 rounded-xl bg-fuchsia-500/10 text-fuchsia-600 flex items-center justify-center text-2xl">
                🧠
              </div>
              <div>
                <h2 className="text-lg font-bold text-gray-900">Add New Business Knowledge</h2>
                <p className="text-xs text-gray-500 mt-0.5">
                  Ground your conversational AI with real business facts
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-gray-500">Quick template:</span>
              <div className="kb-suggestions flex flex-wrap gap-2">
                {SUGGESTIONS.map((s, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => handleApplySuggestion(s)}
                    className="kb-pill text-xs px-3 py-1 bg-fuchsia-50 text-fuchsia-700 hover:bg-fuchsia-100 rounded-full border border-fuchsia-200"
                  >
                    {s.q.split(" ")[0]} {s.q.split(" ")[1]}...
                  </button>
                ))}
              </div>
            </div>
          </div>

          <form onSubmit={handleAddFaq} className="kb-form p-6 space-y-5">
            <div style={{ display: "grid", gridTemplateColumns: "1fr 220px", gap: "16px" }}>
              <div className="kb-field">
                <label className="kb-label block text-xs font-bold uppercase tracking-wider text-gray-600 mb-1.5">
                  Question / Customer Inquiry <span style={{ color: "#ef4444" }}>*</span>
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. What are your opening hours on weekends?"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  className="kb-input w-full px-3.5 py-2.5 bg-white border border-gray-300 rounded-xl text-sm"
                />
              </div>

              <div className="kb-field">
                <label className="kb-label block text-xs font-bold uppercase tracking-wider text-gray-600 mb-1.5">
                  Category
                </label>
                <select
                  value={entryType}
                  onChange={(e) => setEntryType(e.target.value)}
                  className="kb-select w-full px-3.5 py-2.5 bg-white border border-gray-300 rounded-xl text-sm"
                >
                  <option value="faq">FAQ</option>
                  <option value="policy">Policy / Terms</option>
                  <option value="procedure">Procedure</option>
                  <option value="support">Support Contact</option>
                </select>
              </div>
            </div>

            <div className="kb-field">
              <label className="kb-label block text-xs font-bold uppercase tracking-wider text-gray-600 mb-1.5">
                Approved Answer / Business Policy <span style={{ color: "#ef4444" }}>*</span>
              </label>
              <textarea
                required
                rows={3}
                placeholder="e.g. We are open from 9:00 AM to 10:00 PM on Saturdays and Sundays. Delivery closes at 9:30 PM."
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                className="kb-textarea w-full px-3.5 py-2.5 bg-white border border-gray-300 rounded-xl text-sm"
              />
              <span style={{ fontSize: 11, color: "#9ca3af", marginTop: 4 }}>
                The AI Agent retrieves this context dynamically whenever customers ask related queries.
              </span>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", paddingTop: 8 }}>
              <button
                type="submit"
                disabled={saving}
                className="kb-btn-save px-6 py-2.5 bg-fuchsia-600 hover:bg-fuchsia-700 text-white font-semibold text-sm rounded-xl shadow-md transition"
              >
                {saving ? "Saving Q&A..." : "+ Add to Agent Knowledge"}
              </button>
            </div>
          </form>
        </div>

        {/* Existing FAQs Table Card */}
        <div className="kb-card bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="kb-card-header p-6 border-b border-gray-100 flex items-center justify-between">
            <div>
              <h2 className="text-base font-bold text-gray-900">Current Knowledge Base Items</h2>
              <p className="text-xs text-gray-500 mt-0.5">
                {faqs.length} active {faqs.length === 1 ? "entry" : "entries"} available to the assistant
              </p>
            </div>

            <div>
              <input
                type="text"
                placeholder="🔍 Search questions or answers..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="kb-search-bar"
              />
            </div>
          </div>

          <div className="kb-table-wrap">
            {loading ? (
              <div className="kb-empty">
                <span className="kb-empty-icon">⏳</span>
                <p>Loading business knowledge...</p>
              </div>
            ) : filteredFaqs.length === 0 ? (
              <div className="kb-empty">
                <span className="kb-empty-icon">📚</span>
                <p>No knowledge base entries found. Add your first Q&A above to train your agent!</p>
              </div>
            ) : (
              <table className="kb-table">
                <thead>
                  <tr>
                    <th style={{ width: "110px" }}>Category</th>
                    <th style={{ width: "32%" }}>Question / Topic</th>
                    <th>Approved AI Answer</th>
                    <th style={{ width: "90px", textAlign: "right" }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredFaqs.map((item) => (
                    <tr key={item.id}>
                      <td>
                        <span className={`kb-badge ${item.entry_type === "policy" ? "kb-badge-policy" : "kb-badge-faq"}`}>
                          {item.entry_type || "FAQ"}
                        </span>
                      </td>
                      <td>
                        <strong style={{ color: "#111827", display: "block" }}>{item.title}</strong>
                        {item.is_approved && (
                          <span style={{ fontSize: 11, color: "#16a34a", marginTop: 2, display: "inline-block" }}>
                            ● AI Ready
                          </span>
                        )}
                      </td>
                      <td style={{ color: "#4b5563", whiteSpace: "pre-wrap", lineHeight: 1.5 }}>
                        {item.content}
                      </td>
                      <td style={{ textAlign: "right" }}>
                        <button
                          type="button"
                          onClick={() => handleDeleteFaq(item.id)}
                          className="kb-action-del"
                          title="Delete entry"
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>
    </OwnerLayout>
  );
}
