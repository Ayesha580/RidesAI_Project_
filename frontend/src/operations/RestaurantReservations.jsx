import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import OwnerLayout from "../owner/components/OwnerLayout";
import StaffLayout from "../staff/components/StaffLayout";
import { customersApi, restaurantFloorApi, tablesApi } from "../api/operationsApi";
import { errorText } from "../api/axiosClient";

const DATE_FILTERS = [
  { key: "today", label: "Today" },
  { key: "tomorrow", label: "Tomorrow" },
  { key: "upcoming", label: "All Upcoming" },
];

const STATUS_FILTERS = [
  { key: "all", label: "All" },
  { key: "confirmed", label: "Confirmed" },
  { key: "seated", label: "Seated" },
  { key: "completed", label: "Completed" },
  { key: "cancelled", label: "Cancelled" },
];

const RES_STATUS_BADGE = {
  pending: { bg: "#fffbeb", color: "#b45309", border: "#fcd34d" },
  confirmed: { bg: "#fdf2ff", color: "#9c1e9c", border: "#f5b8f5" },
  seated: { bg: "#eff6ff", color: "#1d4ed8", border: "#93c5fd" },
  completed: { bg: "#ecfdf5", color: "#047857", border: "#6ee7b7" },
  cancelled: { bg: "#fef2f2", color: "#b91c1c", border: "#fecaca" },
  no_show: { bg: "#f3f4f6", color: "#4b5563", border: "#d1d5db" },
};

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

export default function RestaurantReservations({ staff = false }) {
  const Layout = staff ? StaffLayout : OwnerLayout;

  const [dateFilter, setDateFilter] = useState("today");
  const [statusFilter, setStatusFilter] = useState("all");
  const [reservations, setReservations] = useState([]);
  const [tables, setTables] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  // New Reservation Modal state
  const [showNewModal, setShowNewModal] = useState(false);
  const [customerName, setCustomerName] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [partySize, setPartySize] = useState(2);
  const [reservationDate, setReservationDate] = useState(todayIso());
  const [reservationTime, setReservationTime] = useState("19:30");
  const [tableId, setTableId] = useState("");
  const [specialRequests, setSpecialRequests] = useState("");
  const [creating, setCreating] = useState(false);
  const [createErr, setCreateErr] = useState("");

  // Returning customer auto-fill
  const [custMatches, setCustMatches] = useState([]);
  const [showCustDropdown, setShowCustDropdown] = useState(false);
  const lookupRef = useRef(null);

  const flashNotice = (msg) => {
    setNotice(msg);
    setTimeout(() => setNotice(""), 3000);
  };

  const loadReservations = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const { data } = await restaurantFloorApi.listReservations({
        date: dateFilter,
        status: statusFilter,
      });
      setReservations(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(errorText(err) || "Failed to load reservations.");
    } finally {
      setLoading(false);
    }
  }, [dateFilter, statusFilter]);

  useEffect(() => {
    loadReservations();
  }, [loadReservations]);

  useEffect(() => {
    if (!showNewModal) return;
    tablesApi.list().then(({ data }) => setTables(Array.isArray(data) ? data : [])).catch(() => {});
  }, [showNewModal]);

  const eligibleTables = useMemo(
    () => tables.filter((t) => Number(t.capacity || 0) >= Number(partySize || 1)),
    [tables, partySize]
  );

  const triggerLookup = (q) => {
    if (lookupRef.current) clearTimeout(lookupRef.current);
    const trimmed = (q || "").trim();
    if (trimmed.length < 2) {
      setCustMatches([]);
      setShowCustDropdown(false);
      return;
    }
    lookupRef.current = setTimeout(async () => {
      try {
        const { data } = await customersApi.lookup(trimmed);
        const list = Array.isArray(data) ? data : [];
        setCustMatches(list);
        setShowCustDropdown(list.length > 0);
      } catch {
        setCustMatches([]);
        setShowCustDropdown(false);
      }
    }, 250);
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    setCreateErr("");
    setCreating(true);
    try {
      await restaurantFloorApi.createReservation({
        customer_name: customerName.trim(),
        customer_phone: customerPhone.trim(),
        party_size: Number(partySize || 2),
        reservation_date: reservationDate,
        reservation_time: reservationTime,
        table_id: tableId ? Number(tableId) : undefined,
        special_requests: specialRequests.trim(),
      });
      setShowNewModal(false);
      setCustomerName("");
      setCustomerPhone("");
      setPartySize(2);
      setTableId("");
      setSpecialRequests("");
      setCustMatches([]);
      setShowCustDropdown(false);
      await loadReservations();
      flashNotice("Reservation booked successfully.");
    } catch (err) {
      setCreateErr(errorText(err) || "Could not create reservation.");
    } finally {
      setCreating(false);
    }
  };

  const handleSeat = async (res) => {
    setBusyId(res.id);
    setError("");
    try {
      await restaurantFloorApi.seatReservation(res.id);
      await loadReservations();
      flashNotice(`Seated ${res.customer_name}${res.table_number ? ` at Table ${res.table_number}` : ""}.`);
    } catch (err) {
      setError(errorText(err) || "Failed to seat guest.");
    } finally {
      setBusyId(null);
    }
  };

  const handleComplete = async (res) => {
    setBusyId(res.id);
    setError("");
    try {
      await restaurantFloorApi.completeReservation(res.id, "available");
      await loadReservations();
      flashNotice(`Completed reservation for ${res.customer_name}. Table freed.`);
    } catch (err) {
      setError(errorText(err) || "Failed to complete reservation.");
    } finally {
      setBusyId(null);
    }
  };

  const handleCancel = async (res) => {
    setBusyId(res.id);
    setError("");
    try {
      await restaurantFloorApi.updateReservation(res.id, { status: "cancelled" });
      await loadReservations();
      flashNotice(`Cancelled reservation for ${res.customer_name}.`);
    } catch (err) {
      setError(errorText(err) || "Failed to cancel reservation.");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <Layout
      title="Smart Reservations"
      subtitle="Conflict-free table bookings synced with your Interactive Floor Plan & AI Voice Agent."
    >
      <div style={{ maxWidth: 1320, margin: "0 auto", display: "flex", flexDirection: "column", gap: 18 }}>
        {/* Filter Bar */}
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
          <div style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center" }}>
            <div style={{ display: "inline-flex", background: "#faf5fb", border: "1px solid #eedff0", borderRadius: 11, padding: 3, gap: 3 }}>
              {DATE_FILTERS.map((df) => {
                const active = dateFilter === df.key;
                return (
                  <button
                    key={df.key}
                    type="button"
                    onClick={() => setDateFilter(df.key)}
                    style={{
                      border: "none",
                      borderRadius: 8,
                      padding: "6px 13px",
                      fontSize: 12.5,
                      fontWeight: active ? 800 : 600,
                      cursor: "pointer",
                      background: active ? "#ff77ff" : "transparent",
                      color: active ? "#240729" : "#6b5a75",
                    }}
                  >
                    {df.label}
                  </button>
                );
              })}
            </div>

            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {STATUS_FILTERS.map((sf) => {
                const active = statusFilter === sf.key;
                return (
                  <button
                    key={sf.key}
                    type="button"
                    onClick={() => setStatusFilter(sf.key)}
                    style={{
                      border: active ? "1px solid #d946ef" : "1px solid #eedff0",
                      background: active ? "#fdf2ff" : "#ffffff",
                      color: active ? "#86198f" : "#6b5a75",
                      borderRadius: 999,
                      padding: "5px 12px",
                      fontSize: 12,
                      fontWeight: active ? 800 : 600,
                      cursor: "pointer",
                    }}
                  >
                    {sf.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <Link
              to={staff ? "/staff/tables" : "/owner/m/tables"}
              style={{
                textDecoration: "none",
                border: "1px solid #eedff0",
                background: "#faf6fb",
                color: "#4e3c57",
                borderRadius: 10,
                padding: "8px 14px",
                fontSize: 13,
                fontWeight: 700,
              }}
            >
              🪑 Floor Plan →
            </Link>
            <button
              type="button"
              onClick={() => {
                setCreateErr("");
                setShowNewModal(true);
              }}
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
              + New Reservation
            </button>
          </div>
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

        {/* Reservations Table */}
        <div
          style={{
            background: "#ffffff",
            border: "1px solid #f0e6f2",
            borderRadius: 16,
            overflow: "hidden",
            boxShadow: "0 2px 10px rgba(42, 16, 48, 0.03)",
          }}
        >
          {loading ? (
            <div style={{ padding: 48, textAlign: "center", color: "#8c7d96" }}>Loading reservations...</div>
          ) : reservations.length === 0 ? (
            <div style={{ padding: 52, textAlign: "center" }}>
              <div style={{ fontSize: 34, marginBottom: 8 }}>📅</div>
              <h3 style={{ margin: 0, fontSize: 16.5, fontWeight: 800, color: "#211426" }}>
                No Reservations Found
              </h3>
              <p style={{ margin: "6px 0 0", fontSize: 13, color: "#7f7288" }}>
                Bookings created here or via your WhatsApp/Voice AI Agent will appear here automatically.
              </p>
            </div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13.5 }}>
                <thead>
                  <tr style={{ background: "#faf7fb", borderBottom: "1px solid #f0e6f2", textAlign: "left", color: "#7f7288", fontSize: 12 }}>
                    <th style={{ padding: "12px 16px", fontWeight: 700 }}>Guest</th>
                    <th style={{ padding: "12px 16px", fontWeight: 700 }}>Date & Time</th>
                    <th style={{ padding: "12px 16px", fontWeight: 700 }}>Party</th>
                    <th style={{ padding: "12px 16px", fontWeight: 700 }}>Table</th>
                    <th style={{ padding: "12px 16px", fontWeight: 700 }}>Status</th>
                    <th style={{ padding: "12px 16px", fontWeight: 700, textAlign: "right" }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {reservations.map((res) => {
                    const badge = RES_STATUS_BADGE[res.status] || RES_STATUS_BADGE.confirmed;
                    const canSeat = res.status === "pending" || res.status === "confirmed";
                    const canComplete = res.status === "seated" || res.status === "confirmed";
                    const canCancel = res.status === "pending" || res.status === "confirmed";
                    return (
                      <tr key={res.id} style={{ borderBottom: "1px solid #f5eef7" }}>
                        <td style={{ padding: "13px 16px" }}>
                          <div style={{ fontWeight: 750, color: "#211426" }}>
                            {res.customer_name}
                            {res.source === "agent" && (
                              <span style={{ marginLeft: 6, fontSize: 10.5, fontWeight: 700, background: "#fdf2ff", color: "#9c1e9c", padding: "2px 6px", borderRadius: 6 }}>
                                🤖 AI
                              </span>
                            )}
                          </div>
                          {res.customer_phone && (
                            <div style={{ fontSize: 12, color: "#6b7280", fontFamily: "monospace" }}>
                              {res.customer_phone}
                            </div>
                          )}
                          {res.special_requests && (
                            <div style={{ fontSize: 11.5, color: "#b45309", marginTop: 3 }}>
                              📝 {res.special_requests}
                            </div>
                          )}
                        </td>
                        <td style={{ padding: "13px 16px", whiteSpace: "nowrap" }}>
                          <div style={{ fontWeight: 700, color: "#211426" }}>{res.reservation_date}</div>
                          <div style={{ fontSize: 12.5, color: "#86198f", fontWeight: 700 }}>{res.reservation_time}</div>
                        </td>
                        <td style={{ padding: "13px 16px", fontWeight: 700, color: "#36203e" }}>
                          👥 {res.party_size}
                        </td>
                        <td style={{ padding: "13px 16px" }}>
                          {res.table_number ? (
                            <span style={{ fontWeight: 750, color: "#211426", background: "#f5eff7", padding: "4px 10px", borderRadius: 8, fontSize: 12.5 }}>
                              🪑 {res.table_number}
                            </span>
                          ) : (
                            <span style={{ color: "#9ca3af", fontSize: 12 }}>Unassigned</span>
                          )}
                        </td>
                        <td style={{ padding: "13px 16px" }}>
                          <span
                            style={{
                              display: "inline-block",
                              padding: "3px 10px",
                              borderRadius: 999,
                              fontSize: 11.5,
                              fontWeight: 800,
                              background: badge.bg,
                              color: badge.color,
                              border: `1px solid ${badge.border}`,
                              textTransform: "capitalize",
                            }}
                          >
                            {res.status_label || res.status}
                          </span>
                        </td>
                        <td style={{ padding: "13px 16px", textAlign: "right", whiteSpace: "nowrap" }}>
                          <div style={{ display: "inline-flex", gap: 6 }}>
                            {canSeat && (
                              <button
                                type="button"
                                disabled={busyId === res.id}
                                onClick={() => handleSeat(res)}
                                style={{
                                  border: "none",
                                  background: "#ff77ff",
                                  color: "#240729",
                                  borderRadius: 8,
                                  padding: "6px 11px",
                                  fontSize: 12,
                                  fontWeight: 800,
                                  cursor: "pointer",
                                }}
                              >
                                🪑 Seat Guest
                              </button>
                            )}
                            {canComplete && (
                              <button
                                type="button"
                                disabled={busyId === res.id}
                                onClick={() => handleComplete(res)}
                                style={{
                                  border: "1px solid #6ee7b7",
                                  background: "#ecfdf5",
                                  color: "#047857",
                                  borderRadius: 8,
                                  padding: "6px 10px",
                                  fontSize: 12,
                                  fontWeight: 700,
                                  cursor: "pointer",
                                }}
                              >
                                ✅ Complete
                              </button>
                            )}
                            {canCancel && (
                              <button
                                type="button"
                                disabled={busyId === res.id}
                                onClick={() => handleCancel(res)}
                                style={{
                                  border: "1px solid #fecaca",
                                  background: "#fef2f2",
                                  color: "#b91c1c",
                                  borderRadius: 8,
                                  padding: "6px 10px",
                                  fontSize: 12,
                                  fontWeight: 700,
                                  cursor: "pointer",
                                }}
                              >
                                ❌ Cancel
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* New Reservation Modal */}
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
            onSubmit={handleCreate}
            style={{
              width: "100%",
              maxWidth: 500,
              background: "#ffffff",
              borderRadius: 18,
              border: "1px solid #f0e6f2",
              padding: 22,
              boxShadow: "0 20px 50px rgba(30, 10, 40, 0.22)",
              display: "flex",
              flexDirection: "column",
              gap: 13,
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <h2 style={{ margin: 0, fontSize: 18, fontWeight: 800, color: "#211426" }}>New Reservation</h2>
                <p style={{ margin: "2px 0 0", fontSize: 12.5, color: "#7f7288" }}>
                  90-minute conflict check & automatic returning guest recall.
                </p>
              </div>
              <button type="button" onClick={() => setShowNewModal(false)} style={{ border: "none", background: "transparent", fontSize: 20, cursor: "pointer" }}>
                ✕
              </button>
            </div>

            {createErr && (
              <div style={{ background: "#fef2f2", border: "1px solid #fecaca", color: "#991b1b", padding: "10px 12px", borderRadius: 10, fontSize: 13 }}>
                {createErr}
              </div>
            )}

            <div style={{ position: "relative" }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12.5, fontWeight: 600, color: "#4b5563" }}>
                  Guest Name *
                  <input
                    required
                    value={customerName}
                    onChange={(e) => {
                      setCustomerName(e.target.value);
                      triggerLookup(e.target.value);
                    }}
                    placeholder="Type name..."
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
                      triggerLookup(e.target.value);
                    }}
                    placeholder="03xx-xxxxxxx"
                    autoComplete="off"
                    style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #d1d5db", fontSize: 13 }}
                  />
                </label>
              </div>

              {showCustDropdown && custMatches.length > 0 && (
                <div
                  style={{
                    position: "absolute",
                    left: 0,
                    right: 0,
                    top: "100%",
                    marginTop: 5,
                    background: "#ffffff",
                    border: "1px solid #f0abfc",
                    borderRadius: 11,
                    boxShadow: "0 12px 28px rgba(42, 16, 48, 0.16)",
                    zIndex: 40,
                    overflow: "hidden",
                  }}
                >
                  {custMatches.map((c, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => {
                        setCustomerName(c.name || "");
                        setCustomerPhone(c.phone || "");
                        setShowCustDropdown(false);
                      }}
                      style={{
                        width: "100%",
                        border: "none",
                        borderBottom: "1px solid #f6eff8",
                        background: "#ffffff",
                        padding: "9px 12px",
                        textAlign: "left",
                        cursor: "pointer",
                        display: "flex",
                        justifyContent: "space-between",
                        fontSize: 12.5,
                      }}
                    >
                      <span>
                        <strong>{c.name || "Guest"}</strong> · {c.phone}
                      </span>
                      <span style={{ color: "#9c1e9c", fontWeight: 700 }}>★ {c.total_orders || 0} orders</span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10 }}>
              <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12.5, fontWeight: 600, color: "#4b5563" }}>
                Party Size *
                <input
                  type="number"
                  min="1"
                  max="50"
                  required
                  value={partySize}
                  onChange={(e) => setPartySize(e.target.value)}
                  style={{ padding: "9px 10px", borderRadius: 9, border: "1px solid #d1d5db", fontSize: 13 }}
                />
              </label>

              <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12.5, fontWeight: 600, color: "#4b5563" }}>
                Date *
                <input
                  type="date"
                  required
                  value={reservationDate}
                  onChange={(e) => setReservationDate(e.target.value)}
                  style={{ padding: "9px 10px", borderRadius: 9, border: "1px solid #d1d5db", fontSize: 13 }}
                />
              </label>

              <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12.5, fontWeight: 600, color: "#4b5563" }}>
                Time *
                <input
                  type="time"
                  required
                  value={reservationTime}
                  onChange={(e) => setReservationTime(e.target.value)}
                  style={{ padding: "9px 10px", borderRadius: 9, border: "1px solid #d1d5db", fontSize: 13 }}
                />
              </label>
            </div>

            <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12.5, fontWeight: 600, color: "#4b5563" }}>
              Assign Table (filtered for {partySize}+ seats)
              <select
                value={tableId}
                onChange={(e) => setTableId(e.target.value)}
                style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #d1d5db", fontSize: 13 }}
              >
                <option value="">✨ Auto-assign best available table</option>
                {eligibleTables.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.table_number} ({t.section || t.zone || "Indoor"} · {t.capacity} seats)
                  </option>
                ))}
              </select>
            </label>

            <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12.5, fontWeight: 600, color: "#4b5563" }}>
              Special Requests
              <input
                value={specialRequests}
                onChange={(e) => setSpecialRequests(e.target.value)}
                placeholder="e.g. Birthday setup, window table, high chair..."
                style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #d1d5db", fontSize: 13 }}
              />
            </label>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 4 }}>
              <button
                type="button"
                onClick={() => setShowNewModal(false)}
                style={{ border: "1px solid #d1d5db", background: "#ffffff", color: "#374151", borderRadius: 10, padding: "9px 15px", fontSize: 13, fontWeight: 600, cursor: "pointer" }}
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={creating}
                style={{ border: "none", background: "#ff77ff", color: "#240729", borderRadius: 10, padding: "9px 18px", fontSize: 13.5, fontWeight: 800, cursor: "pointer" }}
              >
                {creating ? "Booking..." : "Confirm Reservation"}
              </button>
            </div>
          </form>
        </div>
      )}
    </Layout>
  );
}
