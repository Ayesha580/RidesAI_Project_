import { useEffect, useState } from "react";
import ConversationsView from "./ConversationsView";
import OrdersView from "./OrdersView";

const css = `
.cod-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
  width: 100%;
}

.cod-tabs {
  display: flex;
  gap: 8px;
  background: #ffffff;
  padding: 6px;
  border-radius: 14px;
  border: 1px solid #e8e3ec;
  box-shadow: 0 2px 8px rgba(0,0,0,0.03);
  width: fit-content;
}

.cod-tab-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 20px;
  border-radius: 10px;
  border: none;
  background: transparent;
  color: #645f6d;
  font-size: 13.5px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s ease;
}

.cod-tab-btn:hover {
  color: #1e1b24;
  background: #f7f4f9;
}

.cod-tab-btn.active {
  background: #302b38;
  color: #ffffff;
  box-shadow: 0 4px 12px rgba(48,43,56,0.15);
}
`;

export default function ConversationsAndOrdersDashboard({ defaultTab = "conversations", viewMode = null }) {
  const [activeTab, setActiveTab] = useState(defaultTab);

  useEffect(() => {
    if (defaultTab) setActiveTab(defaultTab);
  }, [defaultTab]);

  if (viewMode === "conversations") {
    return <ConversationsView />;
  }

  if (viewMode === "orders") {
    return <OrdersView />;
  }

  return (
    <div className="cod-container">
      <style>{css}</style>

      {/* Top Tabs Switcher */}
      <div className="cod-tabs">
        <button
          className={`cod-tab-btn ${activeTab === "conversations" ? "active" : ""}`}
          onClick={() => setActiveTab("conversations")}
        >
          <span>💬 Customer Conversations</span>
        </button>
        <button
          className={`cod-tab-btn ${activeTab === "orders" ? "active" : ""}`}
          onClick={() => setActiveTab("orders")}
        >
          <span>📦 Database Orders</span>
        </button>
      </div>

      {activeTab === "conversations" ? <ConversationsView /> : <OrdersView />}
    </div>
  );
}
