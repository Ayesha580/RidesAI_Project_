import { useEffect, useMemo, useRef, useState } from "react";
import OwnerLayout from "../owner/components/OwnerLayout";
import StaffLayout from "../staff/components/StaffLayout";
import { tablesApi } from "../api/operationsApi";
import { errorText } from "../api/axiosClient";

const STATUS_STYLES = {
  available: { bg: "#ecfdf5", border: "#10b981", text: "#047857", badge: "Available" },
  occupied: { bg: "#fdf2f8", border: "#ec4899", text: "#be185d", badge: "Occupied" },
  reserved: { bg: "#fffbeb", border: "#f59e0b", text: "#b45309", badge: "Reserved" },
};

const DEFAULT_ZONES = ["Main Hall", "Outdoor", "VIP / Family"];

export default function TablesFloorPlan({ staff = false }) {
  const [viewMode, setViewMode] = useState("floorplan"); // "floorplan" | "grid"
  const [tables, setTables] = useState([]);
  const [zoneFilter, setZoneFilter] = useState("ALL");
  const [selectedId, setSelectedId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const canvasRef = useRef(null);
  const dragStateRef = useRef(null);

  const [newTable, setNewTable] = useState({
    table_number: "",
    capacity: 4,
    zone: "Main Hall",
    shape: "square",
  });

  const [editForm, setEditForm] = useState({
    status: "available",
    zone: "Main Hall",
    shape: "square",
    capacity: 4,
    pos_x: 60,
    pos_y: 60,
    guest_name: "",
    guest_phone: "",
    reservation_time: "",
    notes: "",
  });

  const loadTables = async () => {
    setError("");
    try {
      const { data } = await tablesApi.list();
      setTables(Array.isArray(data) ? data : []);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTables();
  }, []);

  const zones = useMemo(() => {
    const set = new Set(DEFAULT_ZONES);
    tables.forEach((t) => {
      if (t.zone) set.add(t.zone);
    });
    return ["ALL", ...Array.from(set)];
  }, [tables]);

  const filteredTables = useMemo(
    () => (zoneFilter === "ALL" ? tables : tables.filter((t) => t.zone === zoneFilter)),
    [tables, zoneFilter]
  );

  const selectedTable = useMemo(
    () => tables.find((t) => t.id === selectedId) || null,
    [tables, selectedId]
  );

  useEffect(() => {
    if (selectedTable) {
      setEditForm({
        status: selectedTable.status || "available",
        zone: selectedTable.zone || "Main Hall",
        shape: selectedTable.shape || "square",
        capacity: selectedTable.capacity || 4,
        pos_x: selectedTable.pos_x ?? 60,
        pos_y: selectedTable.pos_y ?? 60,
        guest_name: selectedTable.guest_name || "",
        guest_phone: selectedTable.guest_phone || "",
        reservation_time: selectedTable.reservation_time || "",
        notes: selectedTable.notes || "",
      });
    }
  }, [selectedTable]);

  const flashNotice = (msg) => {
    setNotice(msg);
    setTimeout(() => setNotice(""), 2800);
  };

  const handleAddTable = async (e) => {
    e.preventDefault();
    if (!newTable.table_number.trim()) return;
    setSaving(true);
    setError("");
    try {
      const { data } = await tablesApi.create({
        ...newTable,
        table_number: newTable.table_number.trim(),
        capacity: Number(newTable.capacity || 4),
      });
      setNewTable({ table_number: "", capacity: 4, zone: newTable.zone, shape: newTable.shape });
      setSelectedId(data.id);
      await loadTables();
      flashNotice(`Added table ${data.table_number}.`);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setSaving(false);
    }
  };

  const handleSaveSelected = async (e) => {
    e.preventDefault();
    if (!selectedTable) return;
    setSaving(true);
    setError("");
    try {
      await tablesApi.update(selectedTable.id, {
        ...editForm,
        capacity: Number(editForm.capacity || 1),
        pos_x: Math.max(0, Number(editForm.pos_x || 0)),
        pos_y: Math.max(0, Number(editForm.pos_y || 0)),
      });
      await loadTables();
      flashNotice(`Saved ${selectedTable.table_number}.`);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setSaving(false);
    }
  };

  const handleQuickStatus = async (table, nextStatus) => {
    setSaving(true);
    setError("");
    try {
      await tablesApi.update(table.id, { status: nextStatus });
      await loadTables();
      flashNotice(`Table ${table.table_number} marked ${nextStatus}.`);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteTable = async (table) => {
    setSaving(true);
    setError("");
    try {
      await tablesApi.remove(table.id);
      if (selectedId === table.id) setSelectedId(null);
      await loadTables();
      flashNotice(`Removed table ${table.table_number}.`);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setSaving(false);
    }
  };

  // Drag-and-drop repositioning on the visual floor-plan canvas
  const handlePointerDown = (e, table) => {
    if (!canvasRef.current) return;
    const rect = canvasRef.current.getBoundingClientRect();
    setSelectedId(table.id);
    dragStateRef.current = {
      id: table.id,
      offsetX: e.clientX - rect.left - (table.pos_x || 0),
      offsetY: e.clientY - rect.top - (table.pos_y || 0),
      moved: false,
      lastX: table.pos_x || 0,
      lastY: table.pos_y || 0,
    };
  };

  const handleCanvasPointerMove = (e) => {
    const drag = dragStateRef.current;
    if (!drag || !canvasRef.current) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const nx = Math.max(8, Math.min(Math.round(rect.width - 120), Math.round(e.clientX - rect.left - drag.offsetX)));
    const ny = Math.max(8, Math.min(Math.round(rect.height - 95), Math.round(e.clientY - rect.top - drag.offsetY)));
    if (Math.abs(nx - drag.lastX) > 2 || Math.abs(ny - drag.lastY) > 2) {
      drag.moved = true;
      drag.lastX = nx;
      drag.lastY = ny;
      setTables((prev) => prev.map((t) => (t.id === drag.id ? { ...t, pos_x: nx, pos_y: ny } : t)));
    }
  };

  const handleCanvasPointerUp = async () => {
    const drag = dragStateRef.current;
    dragStateRef.current = null;
    if (!drag || !drag.moved) return;
    try {
      await tablesApi.update(drag.id, { pos_x: drag.lastX, pos_y: drag.lastY });
      flashNotice("Saved table position.");
    } catch (err) {
      setError(errorText(err));
    }
  };

  const counts = useMemo(() => {
    const c = { available: 0, occupied: 0, reserved: 0 };
    tables.forEach((t) => {
      if (c[t.status] !== undefined) c[t.status] += 1;
    });
    return c;
  }, [tables]);

  const Layout = staff ? StaffLayout : OwnerLayout;

  return (
    <Layout
      title="Tables & Visual Floor Plan"
      subtitle="Manage dine-in tables, reservations, zones, and drag-and-drop floor-plan layout."
    >
      {error && <div className="ad-alert" role="alert">{error}</div>}
      {notice && (
        <div style={{ background: "#fdf4ff", border: "1px solid #f0abfc", color: "#86198f", padding: "9px 14px", borderRadius: 10, fontSize: 13, fontWeight: 600, marginBottom: 14 }}>
          ✅ {notice}
        </div>
      )}

      {/* Top Status & View Toggle Bar */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12, marginBottom: 16 }}>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <span style={{ padding: "5px 12px", borderRadius: 999, background: "#ecfdf5", color: "#047857", fontSize: 12.5, fontWeight: 700 }}>
            🟢 Available: {counts.available}
          </span>
          <span style={{ padding: "5px 12px", borderRadius: 999, background: "#fdf2f8", color: "#be185d", fontSize: 12.5, fontWeight: 700 }}>
            🔴 Occupied: {counts.occupied}
          </span>
          <span style={{ padding: "5px 12px", borderRadius: 999, background: "#fffbeb", color: "#b45309", fontSize: 12.5, fontWeight: 700 }}>
            🟡 Reserved: {counts.reserved}
          </span>
        </div>

        <div style={{ display: "flex", gap: 8 }}>
          <button
            type="button"
            onClick={() => setViewMode("floorplan")}
            style={{
              padding: "8px 14px",
              borderRadius: 10,
              border: viewMode === "floorplan" ? "1px solid #ff77ff" : "1px solid #e2e8f0",
              background: viewMode === "floorplan" ? "#ff77ff" : "#fff",
              color: viewMode === "floorplan" ? "#fff" : "#475569",
              fontWeight: 700,
              fontSize: 12.5,
              cursor: "pointer",
            }}
          >
            🗺️ Visual Floor-Plan
          </button>
          <button
            type="button"
            onClick={() => setViewMode("grid")}
            style={{
              padding: "8px 14px",
              borderRadius: 10,
              border: viewMode === "grid" ? "1px solid #ff77ff" : "1px solid #e2e8f0",
              background: viewMode === "grid" ? "#ff77ff" : "#fff",
              color: viewMode === "grid" ? "#fff" : "#475569",
              fontWeight: 700,
              fontSize: 12.5,
              cursor: "pointer",
            }}
          >
            📋 List / Grid View
          </button>
        </div>
      </div>

      {/* Add Table Form + Zone Filter */}
      <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 14, padding: 14, marginBottom: 16, display: "grid", gap: 12 }}>
        <form onSubmit={handleAddTable} style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 10, alignItems: "center" }}>
          <input placeholder="Table # (e.g. T1, VIP-1)" value={newTable.table_number} onChange={(e) => setNewTable({ ...newTable, table_number: e.target.value })} required style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid #d1d5db" }} />
          <input type="number" min="1" placeholder="Seats" value={newTable.capacity} onChange={(e) => setNewTable({ ...newTable, capacity: e.target.value })} style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid #d1d5db" }} />
          <select value={newTable.zone} onChange={(e) => setNewTable({ ...newTable, zone: e.target.value })} style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid #d1d5db" }}>
            {DEFAULT_ZONES.map((z) => <option key={z} value={z}>{z}</option>)}
          </select>
          <select value={newTable.shape} onChange={(e) => setNewTable({ ...newTable, shape: e.target.value })} style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid #d1d5db" }}>
            <option value="square">Square</option>
            <option value="round">Round</option>
            <option value="rect">Rectangle</option>
          </select>
          <button type="submit" disabled={saving} className="ad-btn ad-btn-primary">+ Add Table</button>
        </form>

        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {zones.map((z) => (
            <button
              key={z}
              type="button"
              onClick={() => setZoneFilter(z)}
              style={{
                padding: "5px 12px",
                borderRadius: 999,
                border: zoneFilter === z ? "1px solid #ff77ff" : "1px solid #e2e8f0",
                background: zoneFilter === z ? "#fdf4ff" : "#fff",
                color: zoneFilter === z ? "#a21caf" : "#64748b",
                fontWeight: 700,
                fontSize: 12,
                cursor: "pointer",
              }}
            >
              {z === "ALL" ? "All Zones" : z}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <p style={{ color: "#64748b" }}>Loading tables...</p>
      ) : viewMode === "floorplan" ? (
        <div style={{ display: "grid", gridTemplateColumns: selectedTable ? "minmax(0, 1fr) 310px" : "1fr", gap: 16, alignItems: "start" }}>
          {/* Visual Drag-and-Drop Floor Plan Canvas */}
          <div
            ref={canvasRef}
            onPointerMove={handleCanvasPointerMove}
            onPointerUp={handleCanvasPointerUp}
            onPointerLeave={handleCanvasPointerUp}
            style={{
              position: "relative",
              minHeight: 460,
              background: "radial-gradient(#e9d5ff 1px, transparent 1px) #fcfaff",
              backgroundSize: "24px 24px",
              border: "2px dashed #e9d5ff",
              borderRadius: 16,
              overflow: "hidden",
              userSelect: "none",
            }}
          >
            <div style={{ position: "absolute", top: 10, left: 14, fontSize: 11.5, fontWeight: 700, color: "#94a3b8" }}>
              Drag any table to reposition · Click a table to edit status or reservation
            </div>

            {filteredTables.length === 0 ? (
              <div style={{ display: "grid", placeItems: "center", height: 420, color: "#94a3b8", textAlign: "center", padding: 20 }}>
                <div>
                  <div style={{ fontSize: 32 }}>🪑</div>
                  <strong>No tables in this zone yet.</strong>
                  <p style={{ margin: "4px 0 0", fontSize: 12.5 }}>Add your first table above to design your visual floor plan.</p>
                </div>
              </div>
            ) : (
              filteredTables.map((t) => {
                const st = STATUS_STYLES[t.status] || STATUS_STYLES.available;
                const isSelected = selectedId === t.id;
                const width = t.shape === "rect" ? 138 : 96;
                const height = t.shape === "round" ? 96 : 84;
                const radius = t.shape === "round" ? "50%" : "14px";
                return (
                  <div
                    key={t.id}
                    onPointerDown={(e) => handlePointerDown(e, t)}
                    style={{
                      position: "absolute",
                      left: t.pos_x ?? 40,
                      top: t.pos_y ?? 40,
                      width,
                      height,
                      borderRadius: radius,
                      background: st.bg,
                      border: `2px solid ${isSelected ? "#ff77ff" : st.border}`,
                      boxShadow: isSelected ? "0 0 0 4px rgba(255,119,255,0.28)" : "0 4px 12px rgba(15,23,42,0.08)",
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      justifyContent: "center",
                      cursor: "grab",
                      padding: 6,
                      textAlign: "center",
                    }}
                  >
                    <div style={{ fontWeight: 800, fontSize: 14, color: "#0f172a" }}>{t.table_number}</div>
                    <div style={{ fontSize: 11, fontWeight: 700, color: st.text }}>{st.badge} · {t.capacity}p</div>
                    {t.guest_name && (
                      <div style={{ fontSize: 10, color: "#475569", maxWidth: "90%", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {t.guest_name}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>

          {/* Table Inspector Panel */}
          {selectedTable && (
            <form onSubmit={handleSaveSelected} style={{ background: "#fff", border: "1px solid #f0abfc", borderRadius: 16, padding: 16, display: "grid", gap: 10 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h4 style={{ margin: 0 }}>Table {selectedTable.table_number}</h4>
                <button type="button" onClick={() => setSelectedId(null)} style={{ background: "none", border: "none", cursor: "pointer", fontWeight: 700 }}>✕</button>
              </div>

              <div style={{ display: "flex", gap: 6 }}>
                {["available", "occupied", "reserved"].map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => handleQuickStatus(selectedTable, s)}
                    style={{
                      flex: 1,
                      padding: "6px 4px",
                      borderRadius: 8,
                      border: editForm.status === s ? `2px solid ${STATUS_STYLES[s].border}` : "1px solid #e2e8f0",
                      background: STATUS_STYLES[s].bg,
                      color: STATUS_STYLES[s].text,
                      fontWeight: 700,
                      fontSize: 11,
                      cursor: "pointer",
                      textTransform: "capitalize",
                    }}
                  >
                    {s}
                  </button>
                ))}
              </div>

              <label style={{ fontSize: 12, fontWeight: 600 }}>
                Zone
                <select value={editForm.zone} onChange={(e) => setEditForm({ ...editForm, zone: e.target.value })} style={{ width: "100%", marginTop: 3, padding: 7, borderRadius: 8, border: "1px solid #d1d5db" }}>
                  {DEFAULT_ZONES.map((z) => <option key={z} value={z}>{z}</option>)}
                </select>
              </label>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                <label style={{ fontSize: 12, fontWeight: 600 }}>
                  Shape
                  <select value={editForm.shape} onChange={(e) => setEditForm({ ...editForm, shape: e.target.value })} style={{ width: "100%", marginTop: 3, padding: 7, borderRadius: 8, border: "1px solid #d1d5db" }}>
                    <option value="square">Square</option>
                    <option value="round">Round</option>
                    <option value="rect">Rectangle</option>
                  </select>
                </label>
                <label style={{ fontSize: 12, fontWeight: 600 }}>
                  Seats
                  <input type="number" min="1" value={editForm.capacity} onChange={(e) => setEditForm({ ...editForm, capacity: e.target.value })} style={{ width: "100%", marginTop: 3, padding: 7, borderRadius: 8, border: "1px solid #d1d5db" }} />
                </label>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                <label style={{ fontSize: 12, fontWeight: 600 }}>
                  X Pos
                  <input type="number" min="0" value={editForm.pos_x} onChange={(e) => setEditForm({ ...editForm, pos_x: e.target.value })} style={{ width: "100%", marginTop: 3, padding: 7, borderRadius: 8, border: "1px solid #d1d5db" }} />
                </label>
                <label style={{ fontSize: 12, fontWeight: 600 }}>
                  Y Pos
                  <input type="number" min="0" value={editForm.pos_y} onChange={(e) => setEditForm({ ...editForm, pos_y: e.target.value })} style={{ width: "100%", marginTop: 3, padding: 7, borderRadius: 8, border: "1px solid #d1d5db" }} />
                </label>
              </div>

              <label style={{ fontSize: 12, fontWeight: 600 }}>
                Guest / Reservation Name
                <input value={editForm.guest_name} onChange={(e) => setEditForm({ ...editForm, guest_name: e.target.value })} placeholder="Optional guest name" style={{ width: "100%", marginTop: 3, padding: 7, borderRadius: 8, border: "1px solid #d1d5db" }} />
              </label>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                <input value={editForm.guest_phone} onChange={(e) => setEditForm({ ...editForm, guest_phone: e.target.value })} placeholder="Phone" style={{ padding: 7, borderRadius: 8, border: "1px solid #d1d5db", fontSize: 12 }} />
                <input value={editForm.reservation_time} onChange={(e) => setEditForm({ ...editForm, reservation_time: e.target.value })} placeholder="Time (8:00 PM)" style={{ padding: 7, borderRadius: 8, border: "1px solid #d1d5db", fontSize: 12 }} />
              </div>

              <button type="submit" disabled={saving} className="ad-btn ad-btn-primary">
                {saving ? "Saving..." : "Save Table Details"}
              </button>
              {!staff && (
                <button type="button" disabled={saving} onClick={() => handleDeleteTable(selectedTable)} style={{ background: "none", border: "none", color: "#ef4444", fontSize: 12, cursor: "pointer", padding: 0, textAlign: "left" }}>
                  Delete Table
                </button>
              )}
            </form>
          )}
        </div>
      ) : (
        /* Grid / List View */
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(230px, 1fr))", gap: 12 }}>
          {filteredTables.length === 0 ? (
            <p style={{ color: "#64748b" }}>No tables configured yet.</p>
          ) : (
            filteredTables.map((t) => {
              const st = STATUS_STYLES[t.status] || STATUS_STYLES.available;
              return (
                <div key={t.id} style={{ background: "#fff", border: `1.5px solid ${st.border}`, borderRadius: 14, padding: 14 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <strong style={{ fontSize: 16 }}>Table {t.table_number}</strong>
                    <span style={{ fontSize: 11, fontWeight: 700, padding: "2px 8px", borderRadius: 999, background: st.bg, color: st.text }}>{st.badge}</span>
                  </div>
                  <div style={{ fontSize: 12.5, color: "#64748b", marginTop: 4 }}>
                    {t.zone} · {t.capacity} seats · {t.shape}
                  </div>
                  {t.guest_name && (
                    <div style={{ fontSize: 12, color: "#0f172a", marginTop: 6 }}>
                      👤 {t.guest_name}{t.reservation_time ? ` (${t.reservation_time})` : ""}
                    </div>
                  )}
                  <div style={{ display: "flex", gap: 6, marginTop: 10 }}>
                    {["available", "occupied", "reserved"].map((s) => (
                      <button
                        key={s}
                        type="button"
                        onClick={() => handleQuickStatus(t, s)}
                        style={{
                          flex: 1,
                          padding: "5px 4px",
                          borderRadius: 7,
                          border: "1px solid #e2e8f0",
                          background: t.status === s ? STATUS_STYLES[s].bg : "#fff",
                          color: t.status === s ? STATUS_STYLES[s].text : "#64748b",
                          fontSize: 11,
                          fontWeight: 700,
                          cursor: "pointer",
                          textTransform: "capitalize",
                        }}
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}
    </Layout>
  );
}
