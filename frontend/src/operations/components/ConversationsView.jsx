import { useCallback, useEffect, useRef, useState } from "react";
import { dashboardApi } from "../../api/operationsApi";
import { errorText } from "../../api/axiosClient";
import { useAuth } from "../../context/AuthContext";

const css = `
.cv-workspace {
  display: grid;
  grid-template-columns: 360px 1fr;
  gap: 20px;
  min-height: 680px;
  height: calc(100vh - 210px);
  width: 100%;
}
@media (max-width: 960px) {
  .cv-workspace {
    grid-template-columns: 1fr;
    height: auto;
  }
}

/* Sidebar */
.cv-sidebar {
  display: flex;
  flex-direction: column;
  background: #ffffff;
  border: 1px solid #e8e3ec;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 2px 10px rgba(0,0,0,0.03);
}
.cv-sidebar-head {
  padding: 16px;
  border-bottom: 1px solid #f0ebf3;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.cv-search-box {
  position: relative;
  display: flex;
  align-items: center;
}
.cv-search-input {
  width: 100%;
  padding: 9px 12px 9px 34px;
  background: #f8f6fa;
  border: 1px solid #e4dfe9;
  border-radius: 10px;
  font-size: 13.5px;
  outline: none;
  transition: border-color 0.2s ease;
}
.cv-search-input:focus {
  border-color: #c026d3;
  background: #ffffff;
}
.cv-search-icon {
  position: absolute;
  left: 10px;
  color: #9891a0;
  font-size: 14px;
}
.cv-filter-pills {
  display: flex;
  gap: 6px;
  overflow-x: auto;
  padding-bottom: 2px;
}
.cv-pill {
  padding: 4px 10px;
  font-size: 11.5px;
  font-weight: 600;
  border-radius: 20px;
  border: 1px solid #e5dfea;
  background: #ffffff;
  color: #6b6474;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.15s ease;
}
.cv-pill.active {
  background: #ff77ff;
  color: #ffffff;
  border-color: #ff77ff;
}

/* Conversation Cards List */
.cv-conv-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.cv-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px;
  border-radius: 12px;
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 0.15s ease;
  background: #ffffff;
}
.cv-card:hover {
  background: #fbf9fc;
}
.cv-card.active {
  background: #fff3ff;
  border-color: #f2afff;
  box-shadow: 0 2px 8px rgba(255,119,255,0.08);
}
.cv-avatar {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: #f0eaf5;
  color: #8b3297;
  font-weight: 750;
  font-size: 15px;
  display: grid;
  place-items: center;
  flex-shrink: 0;
  position: relative;
}
.cv-avatar-dot {
  position: absolute;
  bottom: -2px;
  right: -2px;
  width: 11px;
  height: 11px;
  border-radius: 50%;
  border: 2px solid #ffffff;
}
.dot-bot { background: #22c55e; }
.dot-human { background: #a855f7; }
.dot-closed { background: #9ca3af; }

.cv-card-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.cv-card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}
.cv-card-name {
  font-size: 13.5px;
  font-weight: 700;
  color: #27222d;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cv-card-time {
  font-size: 11px;
  color: #9f97a6;
  white-space: nowrap;
}
.cv-card-phone {
  font-size: 12px;
  color: #847d8c;
  font-family: monospace;
}
.cv-card-snippet {
  font-size: 12.5px;
  color: #5d5666;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-top: 2px;
}

/* Sidebar Footer (Pagination) */
.cv-sidebar-footer {
  padding: 10px 14px;
  border-top: 1px solid #f0ebf3;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #faf8fc;
  font-size: 12px;
  color: #71697a;
}
.cv-page-btn {
  padding: 5px 12px;
  border-radius: 8px;
  border: 1px solid #dbd4e0;
  background: #ffffff;
  color: #4b4454;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}
.cv-page-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* Chat Main Panel */
.cv-chat-panel {
  display: flex;
  flex-direction: column;
  background: #ffffff;
  border: 1px solid #e8e3ec;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 2px 10px rgba(0,0,0,0.03);
}
.cv-chat-head {
  padding: 16px 20px;
  border-bottom: 1px solid #f0ebf3;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  background: #faf8fc;
}
.cv-chat-user {
  display: flex;
  align-items: center;
  gap: 12px;
}
.cv-chat-user h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 750;
  color: #27222d;
}
.cv-chat-user p {
  margin: 2px 0 0;
  font-size: 12.5px;
  color: #787081;
}
.cv-chat-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.cv-action-btn {
  padding: 7px 14px;
  border-radius: 9px;
  font-size: 12.5px;
  font-weight: 650;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.15s ease;
}
.btn-handover {
  background: #fdf2fe;
  color: #a21caf;
  border-color: #f5d0fe;
}
.btn-handover:hover { background: #fae8ff; }
.btn-bot {
  background: #f0fdf4;
  color: #15803d;
  border-color: #bbf7d0;
}
.btn-bot:hover { background: #dcfce7; }
.btn-close {
  background: #f3f4f6;
  color: #4b5563;
  border-color: #e5e7eb;
}
.btn-close:hover { background: #e5e7eb; }

/* Messages Bubble Flow */
.cv-chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 22px 24px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  background: #fbfafc;
}
.cv-msg-bubble {
  max-width: 72%;
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.cv-msg-bubble.user {
  align-self: flex-start;
}
.cv-msg-bubble.assistant,
.cv-msg-bubble.human {
  align-self: flex-end;
}
.cv-bubble-content {
  padding: 12px 16px;
  border-radius: 16px;
  font-size: 13.5px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
}
.cv-msg-bubble.user .cv-bubble-content {
  background: #ffffff;
  color: #26212c;
  border: 1px solid #e7e1eb;
  border-bottom-left-radius: 4px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.03);
}
.cv-msg-bubble.assistant .cv-bubble-content {
  background: #302b38;
  color: #ffffff;
  border-bottom-right-radius: 4px;
  box-shadow: 0 2px 8px rgba(48,43,56,0.18);
}
.cv-msg-bubble.human .cv-bubble-content {
  background: #9333ea;
  color: #ffffff;
  border-bottom-right-radius: 4px;
}
.cv-bubble-meta {
  font-size: 11px;
  color: #9a92a2;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 4px;
}
.cv-msg-bubble.assistant .cv-bubble-meta,
.cv-msg-bubble.human .cv-bubble-meta {
  justify-content: flex-end;
}
.cv-role-tag {
  font-weight: 700;
  text-transform: uppercase;
  font-size: 10px;
  letter-spacing: 0.3px;
}

/* Chat Input Bar */
.cv-chat-footer {
  padding: 14px 20px;
  border-top: 1px solid #f0ebf3;
  background: #ffffff;
  display: flex;
  gap: 10px;
  align-items: center;
}
.cv-reply-input {
  flex: 1;
  padding: 11px 16px;
  border: 1px solid #ded8e4;
  border-radius: 12px;
  font-size: 14px;
  outline: none;
  background: #fbfafc;
  transition: all 0.2s ease;
}
.cv-reply-input:focus {
  border-color: #c026d3;
  background: #ffffff;
}
.cv-send-btn {
  padding: 11px 22px;
  border-radius: 12px;
  border: none;
  background: #c026d3;
  color: #ffffff;
  font-size: 13.5px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
}
.cv-send-btn:hover:not(:disabled) {
  background: #a21caf;
  transform: translateY(-1px);
}
.cv-send-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.cv-empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
  color: #8c8594;
}
.cv-empty-icon {
  font-size: 42px;
  margin-bottom: 12px;
}
.cv-empty-state h4 {
  margin: 0;
  color: #312b39;
  font-size: 16px;
}
.cv-empty-state p {
  margin: 4px 0 0;
  font-size: 13px;
}
`;

export default function ConversationsView() {
  const { user } = useAuth();
  const [conversations, setConversations] = useState([]);
  const [selectedConv, setSelectedConv] = useState(null);
  const [convLoading, setConvLoading] = useState(true);
  const [convError, setConvError] = useState("");
  const [convSearch, setConvSearch] = useState("");
  const [convStatus, setConvStatus] = useState("all");
  const [convPage, setConvPage] = useState(1);
  const [convTotalPages, setConvTotalPages] = useState(1);
  const [convCount, setConvCount] = useState(0);

  // Human reply input
  const [replyText, setReplyText] = useState("");
  const [sendingReply, setSendingReply] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const loadConversations = useCallback(async (page = 1) => {
    setConvLoading(true);
    setConvError("");
    try {
      const params = { page, page_size: 10 };
      const companyId = user?.company_id || user?.company;
      if (companyId) params.company_id = companyId;
      if (convSearch.trim()) params.search = convSearch.trim();
      if (convStatus !== "all") params.status = convStatus;

      const { data } = await dashboardApi.getConversations(params);
      const results = data.results || [];
      setConversations(results);
      setConvTotalPages(data.total_pages || 1);
      setConvPage(data.current_page || 1);
      setConvCount(data.count || 0);

      if (results.length > 0) {
        setSelectedConv((prev) => {
          if (!prev) return results[0];
          const found = results.find((r) => r.conversation_key === prev.conversation_key);
          return found || results[0];
        });
      } else {
        setSelectedConv(null);
      }
    } catch (err) {
      setConvError(errorText(err));
    } finally {
      setConvLoading(false);
    }
  }, [convSearch, convStatus, user]);

  useEffect(() => {
    loadConversations(1);
  }, [loadConversations]);

  useEffect(() => {
    scrollToBottom();
  }, [selectedConv]);

  const handleSendReply = async (e) => {
    e.preventDefault();
    if (!selectedConv || !replyText.trim()) return;

    setSendingReply(true);
    try {
      await dashboardApi.sendConversationReply(selectedConv.conversation_key, {
        message: replyText.trim(),
        status: "human",
      });
      setReplyText("");
      await loadConversations(convPage);
    } catch (err) {
      alert("Failed to dispatch reply: " + errorText(err));
    } finally {
      setSendingReply(false);
    }
  };

  const handleUpdateStatus = async (newStatus) => {
    if (!selectedConv) return;
    try {
      await dashboardApi.sendConversationReply(selectedConv.conversation_key, {
        status: newStatus,
      });
      await loadConversations(convPage);
    } catch (err) {
      alert("Failed to update status: " + errorText(err));
    }
  };

  return (
    <div style={{ width: "100%" }}>
      <style>{css}</style>
      <div className="cv-workspace">
        {/* Sidebar (Left) */}
        <aside className="cv-sidebar">
          <div className="cv-sidebar-head">
            <div className="cv-search-box">
              <span className="cv-search-icon">🔍</span>
              <input
                type="text"
                className="cv-search-input"
                placeholder="Search phone or name..."
                value={convSearch}
                onChange={(e) => {
                  setConvSearch(e.target.value);
                  setConvPage(1);
                }}
              />
            </div>

            <div className="cv-filter-pills">
              {["all", "bot", "human", "closed"].map((f) => (
                <button
                  key={f}
                  className={`cv-pill ${convStatus === f ? "active" : ""}`}
                  onClick={() => {
                    setConvStatus(f);
                    setConvPage(1);
                  }}
                >
                  {f === "all" ? "All Chats" : f === "bot" ? "🤖 AI Bot" : f === "human" ? "👤 Human" : "Closed"}
                </button>
              ))}
            </div>
          </div>

          {/* Conversation Cards List */}
          <div className="cv-conv-list">
            {convLoading && conversations.length === 0 ? (
              <div className="cv-empty-state">
                <div className="cv-empty-icon">⏳</div>
                <p>Loading conversations...</p>
              </div>
            ) : conversations.length === 0 ? (
              <div className="cv-empty-state">
                <div className="cv-empty-icon">💬</div>
                <h4>No conversations found</h4>
                <p>Incoming customer messages will appear here.</p>
              </div>
            ) : (
              conversations.map((c) => {
                const isSelected = selectedConv?.conversation_key === c.conversation_key;
                const initial = (c.customer_name || "C")[0].toUpperCase();
                const dotClass = c.status === "bot" ? "dot-bot" : c.status === "human" ? "dot-human" : "dot-closed";

                return (
                  <article
                    key={c.conversation_key}
                    className={`cv-card ${isSelected ? "active" : ""}`}
                    onClick={() => setSelectedConv(c)}
                  >
                    <div className="cv-avatar">
                      {initial}
                      <span className={`cv-avatar-dot ${dotClass}`} title={c.status_display} />
                    </div>
                    <div className="cv-card-body">
                      <div className="cv-card-top">
                        <span className="cv-card-name">{c.customer_name}</span>
                        <span className="cv-card-time">
                          {new Date(c.last_message_at || c.updated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                        </span>
                      </div>
                      <span className="cv-card-phone">{c.customer_phone}</span>
                      <p className="cv-card-snippet">{c.last_message || "Chat opened"}</p>
                    </div>
                  </article>
                );
              })
            )}
          </div>

          {/* Sidebar Footer (Pagination) */}
          <footer className="cv-sidebar-footer">
            <span>Page {convPage} of {convTotalPages || 1}</span>
            <div style={{ display: "flex", gap: 6 }}>
              <button
                className="cv-page-btn"
                disabled={convPage <= 1 || convLoading}
                onClick={() => {
                  const p = Math.max(1, convPage - 1);
                  setConvPage(p);
                  loadConversations(p);
                }}
              >
                ◀ Prev
              </button>
              <button
                className="cv-page-btn"
                disabled={convPage >= convTotalPages || convLoading}
                onClick={() => {
                  const p = convPage + 1;
                  setConvPage(p);
                  loadConversations(p);
                }}
              >
                Next ▶
              </button>
            </div>
          </footer>
        </aside>

        {/* Main Chat Panel (Right) */}
        <main className="cv-chat-panel">
          {selectedConv ? (
            <>
              {/* Chat Header */}
              <header className="cv-chat-head">
                <div className="cv-chat-user">
                  <div className="cv-avatar" style={{ width: 44, height: 44, fontSize: 17 }}>
                    {(selectedConv.customer_name || "C")[0].toUpperCase()}
                  </div>
                  <div>
                    <h3>{selectedConv.customer_name}</h3>
                    <p>
                      <span>📞 {selectedConv.customer_phone}</span>
                      <span style={{ margin: "0 6px" }}>•</span>
                      <span>Mode: <strong>{selectedConv.status === "bot" ? "🤖 AI Autonomous" : selectedConv.status === "human" ? "👤 Human Handover" : "Closed"}</strong></span>
                    </p>
                  </div>
                </div>

                <div className="cv-chat-actions">
                  {selectedConv.status !== "human" && (
                    <button className="cv-action-btn btn-handover" onClick={() => handleUpdateStatus("human")}>
                      👤 Take Over
                    </button>
                  )}
                  {selectedConv.status !== "bot" && (
                    <button className="cv-action-btn btn-bot" onClick={() => handleUpdateStatus("bot")}>
                      🤖 Return to AI
                    </button>
                  )}
                  {selectedConv.status !== "closed" && (
                    <button className="cv-action-btn btn-close" onClick={() => handleUpdateStatus("closed")}>
                      ✕ Close Chat
                    </button>
                  )}
                </div>
              </header>

              {/* Messages Body (Chat Bubbles) */}
              <div className="cv-chat-body">
                {(selectedConv.messages || []).length === 0 ? (
                  <div className="cv-empty-state">
                    <p>No messages recorded in this thread yet.</p>
                  </div>
                ) : (
                  selectedConv.messages.map((m) => {
                    const isCustomer = m.role === "user";
                    const bubbleRole = isCustomer ? "user" : m.role === "human" ? "human" : "assistant";

                    return (
                      <div key={m.id} className={`cv-msg-bubble ${bubbleRole}`}>
                        <div className="cv-bubble-content">
                          {m.content}
                        </div>
                        <div className="cv-bubble-meta">
                          <span className="cv-role-tag">
                            {isCustomer ? "Customer" : m.role === "human" ? "Staff Agent" : "AI Assistant"}
                          </span>
                          <span>•</span>
                          <span>{m.time_formatted || new Date(m.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                        </div>
                      </div>
                    );
                  })
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Reply Footer */}
              <form className="cv-chat-footer" onSubmit={handleSendReply}>
                <input
                  type="text"
                  className="cv-reply-input"
                  placeholder="Type a human response to dispatch to this customer..."
                  value={replyText}
                  onChange={(e) => setReplyText(e.target.value)}
                  disabled={sendingReply}
                />
                <button type="submit" className="cv-send-btn" disabled={sendingReply || !replyText.trim()}>
                  {sendingReply ? "Sending..." : "Send Reply ➔"}
                </button>
              </form>
            </>
          ) : (
            <div className="cv-empty-state" style={{ height: "100%" }}>
              <div className="cv-empty-icon">💬</div>
              <h4>Select a Conversation</h4>
              <p>Choose any customer from the left list to inspect the live AI chat history.</p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
