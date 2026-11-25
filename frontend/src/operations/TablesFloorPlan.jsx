import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import OwnerLayout from "../owner/components/OwnerLayout";
import StaffLayout from "../staff/components/StaffLayout";
import { restaurantFloorApi, tablesApi } from "../api/operationsApi";
import { errorText } from "../api/axiosClient";

const SECTIONS = [
  { key: "all", label: "All Sections" },
  { key: "indoor", label: "Indoor" },
  { key: "outdoor", label: "Outdoor" },
  { key: "vip", label: "VIP" },
  { key: "rooftop", label: "Rooftop" },
];

const STATUS_META = {
  available: { label: "Available", bg: "#ecfdf5", border: "#6ee7b7", text: "#047857", dot: "#10b981" },
  occupied: { label: "Occupied", bg: "#fdf2ff", border: "#f0abfc", text: "#9c1e9c", dot: "#d946ef" },
  reserved: { label: "Reserved", bg: "#fffbeb", border: "#fcd34d", text: "#b45309", dot: "#f59e0b" },
  cleaning: { label: "Cleaning", bg: "#eff6ff", border: "#93c5fd", text: "#1d4ed8", dot: "#3b82f6" },
};

export default function TablesFloorPlan({ staff = false }) {
  const navigate = useNavigate();
  const Layout = staff ? StaffLayout : OwnerLayout;

  const [tables, setTables] = useState([]);
  const [summary, setSummary] = useState({ total: 0, by_status: {}, by_section: {} });
  const [sectionFilter, setSectionFilter] = useState("all");
  const [selectedTable, setSelectedTable] = useState(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const [newTable, setNewTable] = useState({
    table_number: "",
    capacity: 4,
    section: "indoor",
  });

  const flashNotice = (msg) => {
    setNotice(msg);
    setTimeout(() => setNotice(""), 3000);
  };

  const loadFloorPlan = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    setError("");
    try {
      const { data } = await restaurantFloorApi.getFloorPlan();
      setTables(Array.isArray(data?.tables) ? data.tables : []);
      setSummary(data?.summary || { total: 0, by_status: {}, by_section: {} });
    } catch (err) {
      setError(errorText(err) || "Failed to load floor plan.");
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadFloorPlan(false);
    const timer = setInterval(() => loadFloorPlan(true), 20000);
    return () => clearInterval(timer);
  }, [loadFloorPlan]);

  const filteredTables = useMemo(() => {
    if (sectionFilter === "all") return tables;
    return tables.filter((t) => (t.section || "indoor") === sectionFilter);
  }, [tables, sectionFilter]);

  const handleAddTable = async (e) => {
    e.preventDefault();
    if (!newTable.table_number.trim()) return;
    setBusy(true);
    setError("");
    try {
      const { data } = await tablesApi.create({
        table_number: newTable.table_number.trim(),
        capacity: Number(newTable.capacity || 4),
        section: newTable.section,
        zone: newTable.section.charAt(0).toUpperCase() + newTable.section.slice(1),
      });
      setShowAddModal(false);
      setNewTable({ table_number: "", capacity: 4, section: newTable.section });
      await loadFloorPlan(true);
      flashNotice(`Added Table ${data.table_number}.`);
    } catch (err) {
      setError(errorText(err) || "Failed to create table.");
    } finally {
      setBusy(false);
    }
  };

  const handleStatusTransition = async (table, nextStatus) => {
    setBusy(true);
    setError("");
    try {
      await restaurantFloorApi.updateTableStatus(table.id, nextStatus);
      await loadFloorPlan(true);
      setSelectedTable((prev) => (prev && prev.id === table.id ? { ...prev, status: nextStatus } : prev));
      flashNotice(`Table ${table.table_number} marked as ${nextStatus}.`);
    } catch (err) {
      setError(errorText(err) || "Failed to update table status.");
    } finally {
      setBusy(false);
    }
  };

  const handleDeleteTable = async (table) => {
    if (!window.confirm(`Delete Table ${table.table_number}?`)) return;
    setBusy(true);
    setError("");
    try {
      await tablesApi.remove(table.id);
      setSelectedTable(null);
      await loadFloorPlan(true);
      flashNotice(`Removed Table ${table.table_number}.`);
    } catch (err) {
      setError(errorText(err) || "Failed to delete table.");
    } finally {
      setBusy(false);
    }
  };

  const handleStartDineInOrder = (table) => {
    const ordersBase = staff ? "/staff/orders" : "/owner/m/orders";
    navigate(`${ordersBase}?newOrder=1&orderType=dine_in&tableId=${table.id}`);
  };

  const byStatus = summary.by_status || {};
  const bySection = summary.by_section || {};

  return (
    <Layout
      title="Interactive Floor Plan"
      subtitle="Live dining room status, active dine-in orders, and upcoming reservations."
    >
      <div style={{ maxWidth: 1320, margin: "0 auto", display: "flex", flexDirection: "column", gap: 18 }}>
        {/* Top Controls: Section Pills + Status Legend + Actions */}
        <div
          style={{
            background: "#ffffff",
            border: "1px solid #f0e6f2",
            borderRadius: 16,
            padding: "14px 18px",
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 12,
          }}
        >
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {SECTIONS.map((sec) => {
              const active = sectionFilter === sec.key;
              const cnt = sec.key === "all" ? summary.total || tables.length : bySection[sec.key] || 0;
              return (
                <button
                  key={sec.key}
                  type="button"
                  onClick={() => setSectionFilter(sec.key)}
                  style={{
                    border: active ? "1px solid #e040e0" : "1px solid #eedff0",
                    background: active ? "#ff77ff" : "#faf6fb",
                    color: active ? "#240729" : "#564861",
                    borderRadius: 999,
                    padding: "7px 14px",
                    fontSize: 13,
                    fontWeight: active ? 800 : 600,
                    cursor: "pointer",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                  }}
                >
                  <span>{sec.label}</span>
                  <span
                    style={{
                      fontSize: 11.5,
                      fontWeight: 800,
                      padding: "1px 7px",
                      borderRadius: 999,
                      background: active ? "rgba(36, 7, 41, 0.14)" : "#ffffff",
                      color: active ? "#240729" : "#7a6985",
                    }}
                  >
                    {cnt}
                  </span>
                </button>
              );
            })}
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <Link
              to={staff ? "/staff/reservations" : "/owner/m/reservations"}
              style={{
                textDecoration: "none",
                border: "1px solid #f0abfc",
                background: "#fdf2ff",
                color: "#86198f",
                borderRadius: 10,
                padding: "8px 14px",
                fontSize: 13,
                fontWeight: 700,
              }}
            >
              📅 Reservations →
            </Link>
            <button
              type="button"
              onClick={() => setShowAddModal(true)}
              style={{
                border: "none",
                background: "#ff77ff",
                color: "#240729",
                borderRadius: 10,
                padding: "9px 16px",
                fontSize: 13,
                fontWeight: 800,
                cursor: "pointer",
                boxShadow: "0 4px 12px rgba(255, 119, 255, 0.35)",
              }}
            >
              + Add Table
            </button>
          </div>
        </div>

        {/* Live Status Legend Strip */}
        <div style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center" }}>
          {Object.entries(STATUS_META).map(([key, meta]) => (
            <div
              key={key}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 7,
                background: "#ffffff",
                border: `1px solid ${meta.border}`,
                borderRadius: 999,
                padding: "5px 12px",
                fontSize: 12.5,
                fontWeight: 700,
                color: meta.text,
              }}
            >
              <span style={{ width: 8, height: 8, borderRadius: "50%", background: meta.dot }} />
              <span>{meta.label}:</span>
              <strong>{byStatus[key] ?? 0}</strong>
            </div>
          ))}
        </div>

        {notice && (
          <div style={{ background: "#ecfdf5", border: "1px solid #a7f3d0", color: "#047857", borderRadius: 12, padding: "11px 16px", fontSize: 13, fontWeight: 600 }}>
            ✅ {notice}
          </div>
        )}
        {error && (
          <div style={{ background: "#fef2f2", border: "1px solid #fecaca", color: "#991b1b", borderRadius: 12, padding: "11px 16px", fontSize: 13 }}>
            {error}
          </div>
        )}

        {/* Interactive Visual Table Grid */}
        {loading ? (
          <div style={{ background: "#ffffff", border: "1px solid #f0e6f2", borderRadius: 16, padding: 48, textAlign: "center", color: "#8c7d96" }}>
            Loading floor plan...
          </div>
        ) : filteredTables.length === 0 ? (
          <div style={{ background: "#ffffff", border: "1px solid #f0e6f2", borderRadius: 16, padding: 52, textAlign: "center" }}>
            <div style={{ fontSize: 36, marginBottom: 8 }}>🪑</div>
            <h3 style={{ margin: 0, fontSize: 17, fontWeight: 800, color: "#211426" }}>No Tables in This Section</h3>
            <p style={{ margin: "6px 0 16px", fontSize: 13.5, color: "#7f7288" }}>
              Add your dining tables to track live occupancy, dine-in orders, and AI reservations.
            </p>
            <button
              type="button"
              onClick={() => setShowAddModal(true)}
              style={{
                border: "none",
                background: "#ff77ff",
                color: "#240729",
                borderRadius: 10,
                padding: "9px 18px",
                fontSize: 13.5,
                fontWeight: 800,
                cursor: "pointer",
              }}
            >
              + Add Your First Table
            </button>
          </div>
        ) : (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(245px, 1fr))",
              gap: 16,
            }}
          >
            {filteredTables.map((tbl) => {
              const meta = STATUS_META[tbl.status] || STATUS_META.available;
              return (
                <button
                  key={tbl.id}
                  type="button"
                  onClick={() => setSelectedTable(tbl)}
                  style={{
                    textAlign: "left",
                    background: "#ffffff",
                    border: `2px solid ${meta.border}`,
                    borderRadius: 16,
                    padding: 18,
                    cursor: "pointer",
                    boxShadow: "0 4px 14px rgba(42, 16, 48, 0.04)",
                    display: "flex",
                    flexDirection: "column",
                    gap: 10,
                    transition: "transform 0.12s ease, box-shadow 0.12s ease",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
                    <div>
                      <div style={{ fontSize: 20, fontWeight: 800, color: "#211426" }}>
                        {tbl.table_number}
                      </div>
                      <div style={{ fontSize: 12, color: "#7f7288", marginTop: 2 }}>
                        👥 {tbl.capacity} seats ·{" "}
                        <span style={{ textTransform: "capitalize", fontWeight: 600 }}>
                          {tbl.section || "indoor"}
                        </span>
                      </div>
                    </div>

                    <span
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 5,
                        background: meta.bg,
                        color: meta.text,
                        border: `1px solid ${meta.border}`,
                        borderRadius: 999,
                        padding: "3px 10px",
                        fontSize: 11.5,
                        fontWeight: 800,
                      }}
                    >
                      <span style={{ width: 6, height: 6, borderRadius: "50%", background: meta.dot }} />
                      {meta.label}
                    </span>
                  </div>

                  {/* Live Order Context */}
                  {tbl.active_order && (
                    <div
                      style={{
                        background: "#fdf4ff",
                        border: "1px solid #f5d0fe",
                        borderRadius: 10,
                        padding: "8px 10px",
                        fontSize: 12,
                        color: "#701a75",
                      }}
                    >
                      <div style={{ fontWeight: 800 }}>
                        🍽️ #{tbl.active_order.reference} · Rs. {Number(tbl.active_order.total || 0).toLocaleString()}
                      </div>
                      <div style={{ fontSize: 11.5, opacity: 0.85, marginTop: 2 }}>
                        {tbl.active_order.customer_name} · {tbl.active_order.elapsed_minutes}m elapsed
                      </div>
                    </div>
                  )}

                  {/* Upcoming Today Reservation Context */}
                  {tbl.next_reservation && (
                    <div
                      style={{
                        background: "#fffbeb",
                        border: "1px solid #fde68a",
                        borderRadius: 10,
                        padding: "8px 10px",
                        fontSize: 12,
                        color: "#92400e",
                      }}
                    >
                      <div style={{ fontWeight: 800 }}>
                        📅 {tbl.next_reservation.reservation_time} · {tbl.next_reservation.customer_name}
                      </div>
                      <div style={{ fontSize: 11.5, opacity: 0.85, marginTop: 2 }}>
                        Party of {tbl.next_reservation.party_size}
                      </div>
                    </div>
                  )}

                  {!tbl.active_order && !tbl.next_reservation && (
                    <div style={{ fontSize: 12, color: "#9b8ca6", paddingTop: 2 }}>
                      Click for quick actions & dine-in order →
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Table Action Drawer / Modal */}
      {selectedTable && (
        <div
          onMouseDown={(e) => e.target === e.currentTarget && setSelectedTable(null)}
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
          <div
            style={{
              width: "100%",
              maxWidth: 460,
              background: "#ffffff",
              borderRadius: 18,
              border: "1px solid #f0e6f2",
              padding: 22,
              boxShadow: "0 20px 50px rgba(30, 10, 40, 0.22)",
              display: "flex",
              flexDirection: "column",
              gap: 16,
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <h2 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: "#211426" }}>
                  Table {selectedTable.table_number}
                </h2>
                <div style={{ fontSize: 13, color: "#7f7288", marginTop: 2 }}>
                  👥 {selectedTable.capacity} seats · Section:{" "}
                  <strong style={{ textTransform: "capitalize" }}>{selectedTable.section || "indoor"}</strong> · Status:{" "}
                  <strong style={{ textTransform: "capitalize" }}>{selectedTable.status}</strong>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setSelectedTable(null)}
                style={{ border: "none", background: "transparent", fontSize: 20, cursor: "pointer", color: "#6b7280" }}
              >
                ✕
              </button>
            </div>

            {selectedTable.active_order && (
              <div style={{ background: "#fdf4ff", border: "1px solid #f0abfc", borderRadius: 12, padding: 12, fontSize: 13 }}>
                <div style={{ fontWeight: 800, color: "#86198f" }}>
                  Active Dine-In Order: #{selectedTable.active_order.reference}
                </div>
                <div style={{ color: "#4b5563", marginTop: 4 }}>
                  Total: <strong>Rs. {Number(selectedTable.active_order.total || 0).toLocaleString()}</strong> ·{" "}
                  {selectedTable.active_order.elapsed_minutes} mins ago
                </div>
              </div>
            )}

            {/* Primary CTA: Start Dine-In Order */}
            <button
              type="button"
              onClick={() => handleStartDineInOrder(selectedTable)}
              style={{
                width: "100%",
                border: "none",
                borderRadius: 12,
                padding: "12px 16px",
                fontSize: 14,
                fontWeight: 800,
                cursor: "pointer",
                background: "#ff77ff",
                color: "#240729",
                boxShadow: "0 4px 14px rgba(255, 119, 255, 0.35)",
              }}
            >
              🍽️ Start Dine-In Order for {selectedTable.table_number}
            </button>

            {/* 1-Click Status Actions */}
            <div>
              <div style={{ fontSize: 12, fontWeight: 700, color: "#7f7288", marginBottom: 8, textTransform: "uppercase" }}>
                Quick Status Change
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 8 }}>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => handleStatusTransition(selectedTable, "occupied")}
                  style={{ padding: "10px 12px", borderRadius: 10, border: "1px solid #f0abfc", background: "#fdf2ff", color: "#86198f", fontWeight: 700, fontSize: 13, cursor: "pointer" }}
                >
                  🪑 Mark Occupied
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => handleStatusTransition(selectedTable, "cleaning")}
                  style={{ padding: "10px 12px", borderRadius: 10, border: "1px solid #93c5fd", background: "#eff6ff", color: "#1d4ed8", fontWeight: 700, fontSize: 13, cursor: "pointer" }}
                >
                  🧹 Mark Cleaning
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => handleStatusTransition(selectedTable, "available")}
                  style={{ padding: "10px 12px", borderRadius: 10, border: "1px solid #6ee7b7", background: "#ecfdf5", color: "#047857", fontWeight: 700, fontSize: 13, cursor: "pointer" }}
                >
                  ✅ Mark Available
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => handleStatusTransition(selectedTable, "reserved")}
                  style={{ padding: "10px 12px", borderRadius: 10, border: "1px solid #fcd34d", background: "#fffbeb", color: "#b45309", fontWeight: 700, fontSize: 13, cursor: "pointer" }}
                >
                  📅 Mark Reserved
                </button>
              </div>
            </div>

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderTop: "1px solid #f2e9f5", paddingTop: 12 }}>
              <button
                type="button"
                disabled={busy}
                onClick={() => handleDeleteTable(selectedTable)}
                style={{ border: "none", background: "transparent", color: "#dc2626", fontSize: 12.5, fontWeight: 700, cursor: "pointer" }}
              >
                🗑️ Delete Table
              </button>
              <button
                type="button"
                onClick={() => setSelectedTable(null)}
                style={{ border: "1px solid #d1d5db", background: "#ffffff", color: "#374151", borderRadius: 9, padding: "7px 14px", fontSize: 13, fontWeight: 600, cursor: "pointer" }}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add Table Modal */}
      {showAddModal && (
        <div
          onMouseDown={(e) => e.target === e.currentTarget && setShowAddModal(false)}
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
            onSubmit={handleAddTable}
            style={{
              width: "100%",
              maxWidth: 420,
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
              <h2 style={{ margin: 0, fontSize: 18, fontWeight: 800, color: "#211426" }}>Add New Table</h2>
              <button type="button" onClick={() => setShowAddModal(false)} style={{ border: "none", background: "transparent", fontSize: 20, cursor: "pointer" }}>
                ✕
              </button>
            </div>

            <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12.5, fontWeight: 600, color: "#4b5563" }}>
              Table Number / Name *
              <input
                required
                value={newTable.table_number}
                onChange={(e) => setNewTable((p) => ({ ...p, table_number: e.target.value }))}
                placeholder="e.g. T1, VIP-2, Patio-4"
                style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #d1d5db", fontSize: 13.5 }}
              />
            </label>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12.5, fontWeight: 600, color: "#4b5563" }}>
                Capacity (Seats)
                <input
                  type="number"
                  min="1"
                  max="50"
                  value={newTable.capacity}
                  onChange={(e) => setNewTable((p) => ({ ...p, capacity: e.target.value }))}
                  style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #d1d5db", fontSize: 13.5 }}
                />
              </label>

              <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12.5, fontWeight: 600, color: "#4b5563" }}>
                Section
                <select
                  value={newTable.section}
                  onChange={(e) => setNewTable((p) => ({ ...p, section: e.target.value }))}
                  style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #d1d5db", fontSize: 13.5 }}
                >
                  <option value="indoor">Indoor</option>
                  <option value="outdoor">Outdoor</option>
                  <option value="vip">VIP</option>
                  <option value="rooftop">Rooftop</option>
                </select>
              </label>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 4 }}>
              <button
                type="button"
                onClick={() => setShowAddModal(false)}
                style={{ border: "1px solid #d1d5db", background: "#ffffff", color: "#374151", borderRadius: 10, padding: "9px 15px", fontSize: 13, fontWeight: 600, cursor: "pointer" }}
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={busy}
                style={{ border: "none", background: "#ff77ff", color: "#240729", borderRadius: 10, padding: "9px 18px", fontSize: 13.5, fontWeight: 800, cursor: "pointer" }}
              >
                {busy ? "Adding..." : "Create Table"}
              </button>
            </div>
          </form>
        </div>
      )}
    </Layout>
  );
}
