import React from "react";
import { useAuth } from "../context/AuthContext";
import RestaurantKDSBoard from "./components/RestaurantKDSBoard";

export default function KitchenDashboard() {
  const { user, signOut } = useAuth();

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#fbf9fc",
        color: "#1e293b",
        fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
        padding: 24,
        boxSizing: "border-box",
      }}
    >
      <div style={{ maxWidth: 1400, margin: "0 auto", display: "flex", flexDirection: "column", gap: 20 }}>
        {/* Standalone Kitchen Staff Header */}
        <header
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background: "#ffffff",
            padding: "16px 22px",
            borderRadius: 16,
            border: "1px solid #f0e6f2",
            boxShadow: "0 2px 12px rgba(42, 16, 48, 0.04)",
            flexWrap: "wrap",
            gap: 14,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <div
              style={{
                width: 44,
                height: 44,
                borderRadius: 12,
                background: "#fdf2ff",
                border: "1px solid #f5b8f5",
                display: "grid",
                placeItems: "center",
                fontSize: 22,
              }}
            >
              👨‍🍳
            </div>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                <h1 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: "#211426" }}>
                  Kitchen Display System (KDS)
                </h1>
                <span
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                    background: "#fdf4ff",
                    color: "#c026d3",
                    fontSize: 11.5,
                    fontWeight: 800,
                    padding: "4px 11px",
                    borderRadius: 999,
                    border: "1px solid #f0abfc",
                    textTransform: "uppercase",
                  }}
                >
                  <span
                    style={{
                      width: 7,
                      height: 7,
                      borderRadius: "50%",
                      background: "#ff77ff",
                      boxShadow: "0 0 8px #ff77ff",
                    }}
                  />
                  LIVE
                </span>
              </div>
              <p style={{ margin: "3px 0 0", fontSize: 13, color: "#7f7288" }}>
                {user?.company_name || "Restaurant Kitchen"} · Signed in as{" "}
                <strong style={{ color: "#36203e" }}>
                  {user?.full_name || user?.first_name || user?.username || "Kitchen Staff"}
                </strong>
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={signOut}
            style={{
              border: "1px solid #fecaca",
              background: "#fef2f2",
              color: "#b91c1c",
              borderRadius: 11,
              padding: "9px 16px",
              fontSize: 13,
              fontWeight: 700,
              cursor: "pointer",
            }}
          >
            ↪ Sign Out
          </button>
        </header>

        {/* Synced Upgraded KDS Board (Station Filters, Modifiers Chips, Order Type/Table Badges, Live Timers, 1-Click Bump, KOT) */}
        <RestaurantKDSBoard />
      </div>
    </div>
  );
}
