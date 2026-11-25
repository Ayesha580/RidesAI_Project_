import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import OwnerLayout from "../owner/components/OwnerLayout";
import StaffLayout from "../staff/components/StaffLayout";
import { useAuth } from "../context/AuthContext";
import { customersApi, operationsApi, tablesApi } from "../api/operationsApi";
import { errorText } from "../api/axiosClient";
import { staffApi } from "../api/StaffApi";
import OrdersView from "./components/OrdersView";
import RestaurantKDSBoard from "./components/RestaurantKDSBoard";

const RESTAURANT_HINTS = ["restaurant", "cafe", "café", "food", "bakery", "fast food", "hotel"];

function isRestaurantOwner(user) {
  const t = String(user?.business_type || "").toLowerCase();
  const l = String(user?.business_label || "").toLowerCase();
  return RESTAURANT_HINTS.some((h) => t.includes(h) || l.includes(h));
}

function OwnerOrdersWorkspace({ user }) {
  const isRestaurant = isRestaurantOwner(user);
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeView, setActiveView] = useState("list");
  const [refreshTick, setRefreshTick] = useState(0);

  // Quick POS New Order Modal state
  const [showNewModal, setShowNewModal] = useState(false);
  const [catalog, setCatalog] = useState([]);
  const [tables, setTables] = useState([]);
  const [orderType, setOrderType] = useState("dine_in");
  const [tableId, setTableId] = useState("");
  const [allowWaitingArea, setAllowWaitingArea] = useState(false);
  const [customerName, setCustomerName] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [deliveryAddress, setDeliveryAddress] = useState("");
  const [orderNotes, setOrderNotes] = useState("");
  const [cartLines, setCartLines] = useState([
    { item_id: "", quantity: 1, selected_modifiers: [], item_notes: "" },
  ]);

  // Support deep-link from Interactive Floor Plan: /owner/m/orders?newOrder=1&orderType=dine_in&tableId=5
  useEffect(() => {
    if (searchParams.get("newOrder") === "1") {
      const ot = searchParams.get("orderType");
      const tid = searchParams.get("tableId");
      if (ot && ["dine_in", "takeaway", "delivery"].includes(ot)) setOrderType(ot);
      if (tid) setTableId(String(tid));
      setShowNewModal(true);
      setSearchParams({}, { replace: true });
    }
  }, [searchParams, setSearchParams]);
  const [creating, setCreating] = useState(false);
  const [createErr, setCreateErr] = useState("");

  // Returning Customer Auto-Recall state
  const [customerMatches, setCustomerMatches] = useState([]);
  const [showCustomerDropdown, setShowCustomerDropdown] = useState(false);
  const [searchingCustomers, setSearchingCustomers] = useState(false);
  const [selectedReturningCustomer, setSelectedReturningCustomer] = useState(null);
  const lookupTimerRef = useRef(null);

  const triggerCustomerLookup = (query) => {
    if (lookupTimerRef.current) clearTimeout(lookupTimerRef.current);
    const trimmed = (query || "").trim();
    if (trimmed.length < 2) {
      setCustomerMatches([]);
      setShowCustomerDropdown(false);
      setSearchingCustomers(false);
      return;
    }
    setSearchingCustomers(true);
    lookupTimerRef.current = setTimeout(async () => {
      try {
        const { data } = await customersApi.lookup(trimmed);
        const list = Array.isArray(data) ? data : [];
        setCustomerMatches(list);
        setShowCustomerDropdown(list.length > 0);
      } catch {
        setCustomerMatches([]);
        setShowCustomerDropdown(false);
      } finally {
        setSearchingCustomers(false);
      }
    }, 250);
  };

  useEffect(() => {
    return () => {
      if (lookupTimerRef.current) clearTimeout(lookupTimerRef.current);
    };
  }, []);

  const handleSelectReturningCustomer = (cust) => {
    setCustomerName(cust.name || "");
    setCustomerPhone(cust.phone || "");
    if (cust.delivery_address) {
      setDeliveryAddress(cust.delivery_address);
    }
    setSelectedReturningCustomer(cust);
    setShowCustomerDropdown(false);
    setCustomerMatches([]);
  };

  const handleClearReturningCustomer = () => {
    setSelectedReturningCustomer(null);
    setCustomerName("");
    setCustomerPhone("");
    setDeliveryAddress("");
    setCustomerMatches([]);
    setShowCustomerDropdown(false);
  };

  useEffect(() => {
    if (!showNewModal) return;
    operationsApi.orderCatalog().then(({ data }) => setCatalog(Array.isArray(data) ? data : [])).catch(() => {});
    if (isRestaurant) {
      tablesApi.list().then(({ data }) => setTables(Array.isArray(data) ? data : [])).catch(() => {});
    }
  }, [showNewModal, isRestaurant]);

  const getCatalogItem = (id) => catalog.find((c) => String(c.id) === String(id));

  const toggleModifier = (lineIdx, groupName, opt) => {
    setCartLines((prev) =>
      prev.map((line, idx) => {
        if (idx !== lineIdx) return line;
        const exists = (line.selected_modifiers || []).some(
          (m) => m.name === opt.name && m.group === groupName
        );
        const nextMods = exists
          ? (line.selected_modifiers || []).filter((m) => !(m.name === opt.name && m.group === groupName))
          : [...(line.selected_modifiers || []), { group: groupName, name: opt.name, price: Number(opt.price || 0) }];
        return { ...line, selected_modifiers: nextMods };
      })
    );
  };

  const liveTotal = cartLines.reduce((acc, line) => {
    const ci = getCatalogItem(line.item_id);
    if (!ci) return acc;
    const base = Number(ci.price || 0);
    const modSum = (line.selected_modifiers || []).reduce((mAcc, m) => mAcc + Number(m.price || 0), 0);
    return acc + (base + modSum) * Number(line.quantity || 1);
  }, 0);

  const availableTables = tables.filter((t) => String(t.status || "").toLowerCase() !== "occupied");
  const allTablesOccupied = tables.length > 0 && availableTables.length === 0;

  const handleCreateOrder = async (e) => {
    e.preventDefault();
    setCreateErr("");
    if (orderType === "delivery" && !deliveryAddress.trim()) {
      setCreateErr("Delivery address is required for delivery orders.");
      return;
    }
    if (orderType === "dine_in" && tables.length > 0 && !tableId && !allowWaitingArea) {
      setCreateErr("Please select an available table, enable Waiting Area / Counter (No Table), or switch to Takeaway.");
      return;
    }
    const validItems = cartLines
      .filter((l) => l.item_id)
      .map((l) => ({
        item_id: Number(l.item_id),
        quantity: Number(l.quantity || 1),
        selected_modifiers: l.selected_modifiers || [],
        item_notes: l.item_notes || "",
      }));
    if (!validItems.length) {
      setCreateErr("Please select at least one menu item.");
      return;
    }
    setCreating(true);
    try {
      const selectedTable = tables.find((t) => String(t.id) === String(tableId));
      const payload = {
        order_type: orderType,
        customer_name:
          customerName.trim() ||
          (orderType === "dine_in" && selectedTable ? `Table ${selectedTable.table_number}` : "Walk-in Guest"),
        customer_phone: customerPhone.trim(),
        delivery_address: orderType === "delivery" ? deliveryAddress.trim() : "",
        fulfillment_type: orderType === "delivery" ? "delivery" : "collection",
        notes: orderNotes.trim(),
        items: validItems,
      };
      if (orderType === "dine_in") {
        if (tableId) {
          payload.table_id = Number(tableId);
          payload.table_number = selectedTable ? selectedTable.table_number : "";
        } else if (allowWaitingArea) {
          payload.allow_waiting_area = true;
          payload.table_number = "Waiting Area";
        }
      }
      await operationsApi.createOrder(payload);
      setShowNewModal(false);
      setCustomerName("");
      setCustomerPhone("");
      setDeliveryAddress("");
      setOrderNotes("");
      setTableId("");
      setAllowWaitingArea(false);
      setSelectedReturningCustomer(null);
      setCustomerMatches([]);
      setShowCustomerDropdown(false);
      setCartLines([{ item_id: "", quantity: 1, selected_modifiers: [], item_notes: "" }]);
      setRefreshTick((t) => t + 1);
    } catch (err) {
      setCreateErr(errorText(err) || "Failed to create order.");
    } finally {
      setCreating(false);
    }
  };

  return (
    <OwnerLayout
      title={activeView === "kds" ? "Live Kitchen Display (KDS)" : "Orders"}
      subtitle={`Manage customer orders, modifiers, and live kitchen prep for ${user?.company_name || "your store"}.`}
    >
      {/* Top View Switcher + Quick New Order Button */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
          marginBottom: 18,
          background: "#ffffff",
          border: "1px solid #f0e6f2",
          borderRadius: 14,
          padding: "10px 14px",
        }}
      >
        <div style={{ display: "inline-flex", background: "#faf5fb", border: "1px solid #eedff0", borderRadius: 11, padding: 4, gap: 4 }}>
          <button
            type="button"
            onClick={() => setActiveView("list")}
            style={{
              border: "none",
              borderRadius: 8,
              padding: "8px 16px",
              fontSize: 13.5,
              fontWeight: activeView === "list" ? 800 : 600,
              cursor: "pointer",
              background: activeView === "list" ? "#ff77ff" : "transparent",
              color: activeView === "list" ? "#240729" : "#6b5a75",
            }}
          >
            📋 Orders List
          </button>
          {isRestaurant && (
            <button
              type="button"
              onClick={() => setActiveView("kds")}
              style={{
                border: "none",
                borderRadius: 8,
                padding: "8px 16px",
                fontSize: 13.5,
                fontWeight: activeView === "kds" ? 800 : 600,
                cursor: "pointer",
                background: activeView === "kds" ? "#ff77ff" : "transparent",
                color: activeView === "kds" ? "#240729" : "#6b5a75",
              }}
            >
              👨‍🍳 Live Kitchen Display (KDS)
            </button>
          )}
        </div>

        <button
          type="button"
          onClick={() => {
            setCreateErr("");
            setShowNewModal(true);
          }}
          style={{
            border: "none",
            borderRadius: 11,
            padding: "9px 18px",
            fontSize: 13.5,
            fontWeight: 800,
            cursor: "pointer",
            background: "#ff77ff",
            color: "#240729",
            boxShadow: "0 4px 12px rgba(255, 119, 255, 0.35)",
          }}
        >
          + New Order
        </button>
      </div>

      {activeView === "kds" && isRestaurant ? (
        <RestaurantKDSBoard refreshTrigger={refreshTick} />
      ) : (
        <OrdersView key={refreshTick} />
      )}

      {/* Quick POS New Order Modal */}
      {showNewModal && (
        <div
          onMouseDown={(e) => e.target === e.currentTarget && setShowNewModal(false)}
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(25, 12, 32, 0.48)",
            zIndex: 120,
            display: "grid",
            placeItems: "center",
            padding: 16,
          }}
        >
          <form
            onSubmit={handleCreateOrder}
            style={{
              width: "100%",
              maxWidth: 640,
              maxHeight: "90vh",
              overflowY: "auto",
              background: "#ffffff",
              borderRadius: 18,
              border: "1px solid #f0e6f2",
              padding: 22,
              boxShadow: "0 20px 50px rgba(30, 10, 40, 0.22)",
              display: "flex",
              flexDirection: "column",
              gap: 14,
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <h2 style={{ margin: 0, fontSize: 18, fontWeight: 800, color: "#211426" }}>
                  Create Quick Order
                </h2>
                <p style={{ margin: "2px 0 0", fontSize: 12.5, color: "#7f7288" }}>
                  Select order type, menu items, and modifiers — sends straight to KDS.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowNewModal(false)}
                style={{ border: "none", background: "transparent", fontSize: 20, cursor: "pointer", color: "#6b7280" }}
              >
                ✕
              </button>
            </div>

            {createErr && (
              <div style={{ background: "#fef2f2", border: "1px solid #fecaca", color: "#991b1b", padding: "10px 12px", borderRadius: 10, fontSize: 13 }}>
                {createErr}
              </div>
            )}

            {/* Order Type Pills */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
              {[
                { key: "dine_in", label: "🍽️ Dine-In" },
                { key: "takeaway", label: "🥡 Takeaway" },
                { key: "delivery", label: "🛵 Delivery" },
              ].map((ot) => {
                const active = orderType === ot.key;
                return (
                  <button
                    key={ot.key}
                    type="button"
                    onClick={() => setOrderType(ot.key)}
                    style={{
                      padding: "10px 12px",
                      borderRadius: 11,
                      border: active ? "2px solid #d946ef" : "1px solid #e5d6ea",
                      background: active ? "#fdf2ff" : "#ffffff",
                      color: active ? "#86198f" : "#4b5563",
                      fontWeight: 750,
                      fontSize: 13,
                      cursor: "pointer",
                    }}
                  >
                    {ot.label}
                  </button>
                );
              })}
            </div>

            {/* Returning Customer Badge */}
            {selectedReturningCustomer && (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 10,
                  background: "#fdf2ff",
                  border: "1px solid #f0abfc",
                  borderRadius: 10,
                  padding: "8px 12px",
                  fontSize: 12.5,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                  <span
                    style={{
                      background: "#ff77ff",
                      color: "#240729",
                      fontWeight: 800,
                      padding: "2px 8px",
                      borderRadius: 999,
                      fontSize: 11.5,
                    }}
                  >
                    ★ Returning Customer
                  </span>
                  <strong style={{ color: "#211426" }}>{selectedReturningCustomer.name || selectedReturningCustomer.phone}</strong>
                  <span style={{ color: "#7a3b82" }}>
                    · {selectedReturningCustomer.total_orders || 0}{" "}
                    {selectedReturningCustomer.total_orders === 1 ? "past order" : "past orders"}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={handleClearReturningCustomer}
                  style={{
                    border: "1px solid #e9d5ff",
                    background: "#ffffff",
                    color: "#7e22ce",
                    borderRadius: 7,
                    padding: "3px 9px",
                    fontSize: 11.5,
                    fontWeight: 700,
                    cursor: "pointer",
                  }}
                >
                  Clear
                </button>
              </div>
            )}

            <div style={{ position: "relative" }}>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 10 }}>
                <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12.5, fontWeight: 600, color: "#4b5563" }}>
                  Customer Name *
                  <input
                    required
                    value={customerName}
                    onChange={(e) => {
                      setCustomerName(e.target.value);
                      setSelectedReturningCustomer(null);
                      triggerCustomerLookup(e.target.value);
                    }}
                    onFocus={() => customerMatches.length > 0 && setShowCustomerDropdown(true)}
                    placeholder="Type name or search guest..."
                    autoComplete="off"
                    style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #d1d5db", fontSize: 13 }}
                  />
                </label>

                <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12.5, fontWeight: 600, color: "#4b5563" }}>
                  Phone Number
                  <input
                    value={customerPhone}
                    onChange={(e) => {
                      setCustomerPhone(e.target.value);
                      setSelectedReturningCustomer(null);
                      triggerCustomerLookup(e.target.value);
                    }}
                    onFocus={() => customerMatches.length > 0 && setShowCustomerDropdown(true)}
                    placeholder="03xx-xxxxxxx (auto-recall)"
                    autoComplete="off"
                    style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #d1d5db", fontSize: 13 }}
                  />
                </label>

                {orderType === "dine_in" && (
                  <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12.5, fontWeight: 600, color: "#4b5563" }}>
                    Select Table {tables.length > 0 && !allowWaitingArea ? "*" : ""}
                    <select
                      value={tableId}
                      disabled={allowWaitingArea}
                      onChange={(e) => {
                        setTableId(e.target.value);
                        if (e.target.value) setAllowWaitingArea(false);
                      }}
                      style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #d1d5db", fontSize: 13 }}
                    >
                      <option value="">— Choose Available Table —</option>
                      {tables.map((t) => {
                        const isOcc = String(t.status || "").toLowerCase() === "occupied";
                        const statusLabel = t.status
                          ? t.status.charAt(0).toUpperCase() + t.status.slice(1)
                          : "Available";
                        return (
                          <option key={t.id} value={t.id} disabled={isOcc}>
                            {t.table_number} ({t.capacity} seats • {statusLabel})
                          </option>
                        );
                      })}
                    </select>
                  </label>
                )}
              </div>

              {/* Full-House / Waiting Area Fallback Banner for Dine-In */}
              {orderType === "dine_in" && tables.length > 0 && (
                <div
                  style={{
                    marginTop: 10,
                    background: allTablesOccupied ? "#fffbeb" : "#faf7fb",
                    border: allTablesOccupied ? "1px solid #fcd34d" : "1px solid #efe4f2",
                    borderRadius: 11,
                    padding: "10px 12px",
                    display: "flex",
                    flexWrap: "wrap",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: 10,
                  }}
                >
                  <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    {allTablesOccupied && (
                      <div style={{ fontSize: 12.5, fontWeight: 800, color: "#b45309" }}>
                        ⚠️ All tables are currently occupied
                      </div>
                    )}
                    <label style={{ display: "inline-flex", alignItems: "center", gap: 7, fontSize: 12.5, fontWeight: 600, color: "#4b5563", cursor: "pointer" }}>
                      <input
                        type="checkbox"
                        checked={allowWaitingArea}
                        onChange={(e) => {
                          setAllowWaitingArea(e.target.checked);
                          if (e.target.checked) setTableId("");
                        }}
                        style={{ accentColor: "#d946ef" }}
                      />
                      <span>Allow Waiting Area / Counter (No Table)</span>
                    </label>
                  </div>

                  {allTablesOccupied && (
                    <button
                      type="button"
                      onClick={() => {
                        setOrderType("takeaway");
                        setTableId("");
                        setAllowWaitingArea(false);
                        setCreateErr("");
                      }}
                      style={{
                        border: "1px solid #f59e0b",
                        background: "#ffffff",
                        color: "#b45309",
                        borderRadius: 8,
                        padding: "6px 12px",
                        fontSize: 12,
                        fontWeight: 800,
                        cursor: "pointer",
                      }}
                    >
                      🥡 Switch to Takeaway
                    </button>
                  )}
                </div>
              )}

              {/* Debounced Customer Auto-Recall Typeahead Dropdown */}
              {showCustomerDropdown && (customerMatches.length > 0 || searchingCustomers) && (
                <div
                  style={{
                    position: "absolute",
                    left: 0,
                    right: 0,
                    top: "100%",
                    marginTop: 6,
                    background: "#ffffff",
                    border: "1px solid #f0abfc",
                    borderRadius: 12,
                    boxShadow: "0 14px 32px rgba(42, 16, 48, 0.16)",
                    zIndex: 50,
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      padding: "7px 12px",
                      background: "#fdf4ff",
                      borderBottom: "1px solid #f5d0fe",
                      fontSize: 11.5,
                      fontWeight: 700,
                      color: "#86198f",
                    }}
                  >
                    <span>
                      {searchingCustomers ? "Searching guests..." : "★ Matching Returning Guests — Click to Auto-Fill"}
                    </span>
                    <button
                      type="button"
                      onClick={() => setShowCustomerDropdown(false)}
                      style={{ border: "none", background: "transparent", color: "#86198f", cursor: "pointer", fontSize: 12 }}
                    >
                      ✕
                    </button>
                  </div>
                  <div style={{ maxHeight: 210, overflowY: "auto" }}>
                    {customerMatches.map((cust, idx) => (
                      <button
                        key={`${cust.phone || cust.name}-${idx}`}
                        type="button"
                        onClick={() => handleSelectReturningCustomer(cust)}
                        style={{
                          width: "100%",
                          border: "none",
                          borderBottom: "1px solid #f6eff8",
                          background: "#ffffff",
                          padding: "10px 12px",
                          textAlign: "left",
                          cursor: "pointer",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          gap: 10,
                        }}
                      >
                        <div style={{ minWidth: 0 }}>
                          <div style={{ fontSize: 13, fontWeight: 750, color: "#211426" }}>
                            {cust.name || "Unnamed Guest"}{" "}
                            {cust.phone && (
                              <span style={{ fontWeight: 500, color: "#6b7280", fontFamily: "monospace", fontSize: 12 }}>
                                · {cust.phone}
                              </span>
                            )}
                          </div>
                          {cust.delivery_address && (
                            <div
                              style={{
                                fontSize: 11.5,
                                color: "#7f7288",
                                marginTop: 2,
                                whiteSpace: "nowrap",
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                                maxWidth: 360,
                              }}
                            >
                              📍 {cust.delivery_address}
                            </div>
                          )}
                        </div>
                        <span
                          style={{
                            flexShrink: 0,
                            fontSize: 11,
                            fontWeight: 800,
                            background: "#fdf2ff",
                            color: "#9c1e9c",
                            border: "1px solid #f5b8f5",
                            borderRadius: 999,
                            padding: "3px 9px",
                          }}
                        >
                          ★ Returning · {cust.total_orders || 0} {cust.total_orders === 1 ? "order" : "orders"}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {orderType === "delivery" && (
              <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12.5, fontWeight: 600, color: "#4b5563" }}>
                Delivery Address *
                <input
                  required
                  value={deliveryAddress}
                  onChange={(e) => setDeliveryAddress(e.target.value)}
                  placeholder="Street, sector, city..."
                  style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #d1d5db", fontSize: 13 }}
                />
              </label>
            )}

            {/* Menu Items + Modifiers */}
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: 13, fontWeight: 800, color: "#211426" }}>Order Items</span>
                <button
                  type="button"
                  onClick={() =>
                    setCartLines((prev) => [
                      ...prev,
                      { item_id: "", quantity: 1, selected_modifiers: [], item_notes: "" },
                    ])
                  }
                  style={{
                    border: "1px solid #f0abfc",
                    background: "#fdf2ff",
                    color: "#9c1e9c",
                    borderRadius: 8,
                    padding: "5px 10px",
                    fontSize: 12,
                    fontWeight: 700,
                    cursor: "pointer",
                  }}
                >
                  + Add Item
                </button>
              </div>

              {cartLines.map((line, idx) => {
                const ci = getCatalogItem(line.item_id);
                const modsSchema = Array.isArray(ci?.modifiers_schema) ? ci.modifiers_schema : [];
                return (
                  <div
                    key={idx}
                    style={{
                      border: "1px solid #efe4f2",
                      background: "#fcfafd",
                      borderRadius: 12,
                      padding: 12,
                      display: "flex",
                      flexDirection: "column",
                      gap: 8,
                    }}
                  >
                    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                      <select
                        required
                        value={line.item_id}
                        onChange={(e) =>
                          setCartLines((prev) =>
                            prev.map((l, i) =>
                              i === idx ? { ...l, item_id: e.target.value, selected_modifiers: [] } : l
                            )
                          )
                        }
                        style={{ flex: 1, padding: "8px 10px", borderRadius: 8, border: "1px solid #d1d5db", fontSize: 13 }}
                      >
                        <option value="">Select menu item...</option>
                        {catalog.map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.name} — Rs. {Number(c.price || 0).toLocaleString()}
                          </option>
                        ))}
                      </select>

                      <input
                        type="number"
                        min="1"
                        value={line.quantity}
                        onChange={(e) =>
                          setCartLines((prev) =>
                            prev.map((l, i) => (i === idx ? { ...l, quantity: e.target.value } : l))
                          )
                        }
                        style={{ width: 68, padding: "8px", borderRadius: 8, border: "1px solid #d1d5db", fontSize: 13 }}
                      />

                      {cartLines.length > 1 && (
                        <button
                          type="button"
                          onClick={() => setCartLines((prev) => prev.filter((_, i) => i !== idx))}
                          style={{ border: "none", background: "transparent", color: "#ef4444", cursor: "pointer", fontSize: 16 }}
                        >
                          ✕
                        </button>
                      )}
                    </div>

                    {/* Modifier Checkboxes */}
                    {modsSchema.length > 0 && (
                      <div style={{ display: "flex", flexDirection: "column", gap: 6, paddingLeft: 4 }}>
                        {modsSchema.map((grp, gIdx) => (
                          <div key={gIdx}>
                            <div style={{ fontSize: 11.5, fontWeight: 700, color: "#7a1f7a", marginBottom: 4 }}>
                              {grp.group}
                            </div>
                            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                              {(grp.options || []).map((opt, oIdx) => {
                                const checked = (line.selected_modifiers || []).some(
                                  (m) => m.name === opt.name && m.group === grp.group
                                );
                                return (
                                  <label
                                    key={oIdx}
                                    style={{
                                      display: "inline-flex",
                                      alignItems: "center",
                                      gap: 5,
                                      padding: "4px 9px",
                                      borderRadius: 8,
                                      border: checked ? "1px solid #d946ef" : "1px solid #e5d6ea",
                                      background: checked ? "#fdf2ff" : "#ffffff",
                                      fontSize: 12,
                                      fontWeight: checked ? 700 : 500,
                                      cursor: "pointer",
                                    }}
                                  >
                                    <input
                                      type="checkbox"
                                      checked={checked}
                                      onChange={() => toggleModifier(idx, grp.group, opt)}
                                      style={{ accentColor: "#d946ef" }}
                                    />
                                    <span>
                                      {opt.name}
                                      {Number(opt.price || 0) > 0 ? ` (+Rs. ${opt.price})` : ""}
                                    </span>
                                  </label>
                                );
                              })}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    <input
                      placeholder="Special kitchen note (e.g. no onions, extra spicy)..."
                      value={line.item_notes}
                      onChange={(e) =>
                        setCartLines((prev) =>
                          prev.map((l, i) => (i === idx ? { ...l, item_notes: e.target.value } : l))
                        )
                      }
                      style={{ padding: "7px 10px", borderRadius: 8, border: "1px solid #e5e7eb", fontSize: 12.5 }}
                    />
                  </div>
                );
              })}
            </div>

            <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12.5, fontWeight: 600, color: "#4b5563" }}>
              General Order Notes
              <input
                value={orderNotes}
                onChange={(e) => setOrderNotes(e.target.value)}
                placeholder="Optional order-level note..."
                style={{ padding: "8px 12px", borderRadius: 9, border: "1px solid #d1d5db", fontSize: 13 }}
              />
            </label>

            {/* Footer with Live Total */}
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                borderTop: "1px solid #f0e6f2",
                paddingTop: 14,
              }}
            >
              <div>
                <div style={{ fontSize: 11.5, color: "#7f7288", fontWeight: 600 }}>Estimated Total</div>
                <div style={{ fontSize: 20, fontWeight: 800, color: "#211426" }}>
                  Rs. {liveTotal.toLocaleString("en-PK", { maximumFractionDigits: 0 })}
                </div>
              </div>

              <div style={{ display: "flex", gap: 8 }}>
                <button
                  type="button"
                  onClick={() => setShowNewModal(false)}
                  style={{
                    border: "1px solid #d1d5db",
                    background: "#ffffff",
                    color: "#374151",
                    borderRadius: 10,
                    padding: "10px 16px",
                    fontSize: 13,
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  style={{
                    border: "none",
                    background: "#ff77ff",
                    color: "#240729",
                    borderRadius: 10,
                    padding: "10px 20px",
                    fontSize: 13.5,
                    fontWeight: 800,
                    cursor: creating ? "wait" : "pointer",
                  }}
                >
                  {creating ? "Creating..." : "Place Order & Send to KDS"}
                </button>
              </div>
            </div>
          </form>
        </div>
      )}
    </OwnerLayout>
  );
}

const FORWARD_STATUS_MAP = {
  new: ["confirmed", "preparing", "cancelled"],
  pending: ["confirmed", "preparing", "cancelled"],
  confirmed: ["preparing", "prepared", "ready", "cancelled"],
  preparing: ["prepared", "ready", "cancelled"],
  prepared: ["ready", "assigned", "picked_up", "on_the_way", "out_for_delivery", "delivered", "cancelled"],
  ready: ["assigned", "picked_up", "on_the_way", "out_for_delivery", "delivered", "cancelled"],
  assigned: ["picked_up", "on_the_way", "out_for_delivery", "delivered", "cancelled"],
  picked_up: ["on_the_way", "out_for_delivery", "delivered", "cancelled"],
  on_the_way: ["delivered", "cancelled"],
  out_for_delivery: ["delivered", "cancelled"],
  delivered: [],
  cancelled: [],
};

const getAvailableStatuses = (currentStatus) => {
  const current = (currentStatus || "").toLowerCase();
  const nextList = FORWARD_STATUS_MAP[current] || [];
  return Array.from(new Set([current, ...nextList]));
};

const isTerminalStatus = (status) => {
  const s = (status || "").toLowerCase();
  return s === "delivered" || s === "cancelled";
};

const can = (user, permission) => user?.role === "owner" || (user?.permissions || []).includes("*") || (user?.permissions || []).includes(permission);

export default function OrdersDashboard({ staff = false }) {
  const { user } = useAuth();

  // For business owners, render the dedicated Orders & Live KDS Workspace
  if (!staff) {
    return <OwnerOrdersWorkspace user={user} />;
  }

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
              {can(user, "orders.update_status") && (
                <select
                  aria-label={`Update status for ${order.order_number}`}
                  disabled={busy === order.id || isTerminalStatus(order.status)}
                  value={order.status}
                  onChange={(e) => updateStatus(order, e.target.value)}
                  style={{
                    opacity: isTerminalStatus(order.status) ? 0.6 : 1,
                    cursor: isTerminalStatus(order.status) ? "not-allowed" : "pointer",
                  }}
                >
                  {getAvailableStatuses(order.status).map((s) => (
                    <option key={s} value={s}>{s.replaceAll("_", " ")}</option>
                  ))}
                </select>
              )}
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
