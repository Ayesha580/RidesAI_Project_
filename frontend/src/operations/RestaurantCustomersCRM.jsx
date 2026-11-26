import { useCallback, useEffect, useState } from "react";
import OwnerLayout from "../owner/components/OwnerLayout";
import StaffLayout from "../staff/components/StaffLayout";
import { restaurantCustomersApi } from "../api/operationsApi";

const ACCENT = "#ff77ff";

const SEGMENT_META = {
  vip: { label: "👑 VIP", bg: "#fdf4ff", color: "#86198f", border: "#f0abfc" },
  repeat: { label: "🔁 Repeat", bg: "#eff6ff", color: "#1d4ed8", border: "#bfdbfe" },
  new: { label: "✨ New", bg: "#ecfdf5", color: "#047857", border: "#a7f3d0" },
  at_risk: { label: "⚠️ At-Risk", bg: "#fffbeb", color: "#b45309", border: "#fde68a" },
};

const FILTER_PILLS = [
  { key: "all", label: "All Guests" },
  { key: "vip", label: "👑 VIP" },
  { key: "repeat", label: "🔁 Repeat" },
  { key: "new", label: "✨ New" },
  { key: "at_risk", label: "⚠️ At-Risk" },
];

function formatMoney(val) {
  const num = Number(val || 0);
  return `Rs. ${num.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function formatDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString([], {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return "—";
  }
}

export default function RestaurantCustomersCRM({ staff = false }) {
  const Layout = staff ? StaffLayout : OwnerLayout;

  const [segment, setSegment] = useState("all");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");

  const [kpis, setKpis] = useState({
    total_guests: 0,
    vip_count: 0,
    repeat_count: 0,
    at_risk_count: 0,
    new_count: 0,
    avg_lifetime_value: 0,
  });
  const [customers, setCustomers] = useState([]);

  // Profile Drawer / Modal state
  const [selectedPhone, setSelectedPhone] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detail, setDetail] = useState(null);
  const [editName, setEditName] = useState("");
  const [editNotes, setEditNotes] = useState("");
  const [editTags, setEditTags] = useState("");
  const [editVip, setEditVip] = useState(false);
  const [saving, setSaving] = useState(false);

  const showToast = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(""), 3500);
  };

  const loadCustomers = useCallback(
    async (silent = false) => {
      if (!silent) setLoading(true);
      setError("");
      try {
        const params = { segment };
        if (search.trim()) params.search = search.trim();
        const res = await restaurantCustomersApi.list(params);
        const data = res.data || {};
        setKpis(
          data.kpis || {
            total_guests: 0,
            vip_count: 0,
            repeat_count: 0,
            at_risk_count: 0,
            new_count: 0,
            avg_lifetime_value: 0,
          }
        );
        setCustomers(Array.isArray(data.customers) ? data.customers : []);
      } catch (err) {
        setError(
          err?.response?.data?.detail || "Could not load restaurant customers directory."
        );
      } finally {
        if (!silent) setLoading(false);
      }
    },
    [segment, search]
  );

  useEffect(() => {
    const timer = setTimeout(() => {
      loadCustomers(false);
    }, 200);
    return () => clearTimeout(timer);
  }, [loadCustomers]);

  const openProfile = async (phone) => {
    setSelectedPhone(phone);
    setDetail(null);
    setDetailLoading(true);
    setError("");
    try {
      const res = await restaurantCustomersApi.getDetail(phone);
      const d = res.data || {};
      setDetail(d);
      setEditName(d.name || "");
      setEditNotes(d.dietary_notes || "");
      setEditTags(Array.isArray(d.tags) ? d.tags.join(", ") : "");
      setEditVip(Boolean(d.is_vip_override));
    } catch (err) {
      setError(err?.response?.data?.detail || "Could not load guest profile.");
      setSelectedPhone(null);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleSaveProfile = async () => {
    if (!selectedPhone) return;
    setSaving(true);
    setError("");
    try {
      const tagList = editTags
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean);
      const res = await restaurantCustomersApi.updateProfile(selectedPhone, {
        name: editName.trim(),
        dietary_notes: editNotes.trim(),
        tags: tagList,
        is_vip_override: editVip,
      });
      setDetail(res.data || null);
      showToast("Guest profile & AI preferences saved.");
      await loadCustomers(true);
    } catch (err) {
      setError(err?.response?.data?.detail || "Failed to save guest profile.");
    } finally {
      setSaving(false);
    }
  };

  const kpiCards = [
    {
      label: "Total Guests",
      value: kpis.total_guests,
      sub: "Unique diners & delivery guests",
      accent: "#6366f1",
    },
    {
      label: "VIP Guests",
      value: kpis.vip_count,
      sub: "5+ orders, Rs. 5k+, or VIP tag",
      accent: "#c026d3",
      highlight: kpis.vip_count > 0,
    },
    {
      label: "Repeat Customers",
      value: kpis.repeat_count,
      sub: "2+ completed orders",
      accent: "#2563eb",
    },
    {
      label: "At-Risk (30d+)",
      value: kpis.at_risk_count,
      sub: "No order in 30+ days",
      accent: "#d97706",
    },
    {
      label: "Avg Lifetime Spend",
      value: formatMoney(kpis.avg_lifetime_value),
      sub: "Average spend per guest",
      accent: "#059669",
    },
  ];

  return (
    <Layout title="Customers CRM">
      <div style={{ maxWidth: 1280, margin: "0 auto", padding: "8px 4px 36px" }}>
        {/* Header Bar */}
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 12,
            marginBottom: 18,
          }}
        >
          <div>
            <h2 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: "#0f172a" }}>
              Customers CRM &amp; Guest Retention
            </h2>
            <p style={{ margin: "4px 0 0", fontSize: 13, color: "#64748b" }}>
              Automated guest segmentation, lifetime spend, and dietary preferences synced live with your WhatsApp AI Agent.
            </p>
          </div>
          <button
            type="button"
            onClick={() => loadCustomers(false)}
            style={{
              border: "1px solid #e2e8f0",
              background: "#fff",
              color: "#0f172a",
              borderRadius: 10,
              padding: "8px 14px",
              fontSize: 13,
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            ↻ Refresh
          </button>
        </div>

        {/* Alerts */}
        {toast && (
          <div
            style={{
              marginBottom: 14,
              padding: "10px 14px",
              borderRadius: 10,
              background: "#ecfdf5",
              border: "1px solid #a7f3d0",
              color: "#065f46",
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            ✓ {toast}
          </div>
        )}
        {error && (
          <div
            style={{
              marginBottom: 14,
              padding: "10px 14px",
              borderRadius: 10,
              background: "#fef2f2",
              border: "1px solid #fecaca",
              color: "#991b1b",
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            ⚠ {error}
          </div>
        )}

        {/* Top KPI Strip */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
            gap: 12,
            marginBottom: 20,
          }}
        >
          {kpiCards.map((card) => (
            <div
              key={card.label}
              style={{
                background: "#ffffff",
                borderRadius: 14,
                padding: "16px 18px",
                border: card.highlight ? `1.5px solid ${ACCENT}` : "1px solid #e2e8f0",
                boxShadow: "0 1px 3px rgba(15, 23, 42, 0.04)",
              }}
            >
              <div style={{ fontSize: 12, fontWeight: 600, color: "#64748b", marginBottom: 6 }}>
                {card.label}
              </div>
              <div style={{ fontSize: 24, fontWeight: 800, color: "#0f172a", lineHeight: 1.15 }}>
                {card.value}
              </div>
              <div style={{ fontSize: 11, color: card.accent, fontWeight: 600, marginTop: 6 }}>
                {card.sub}
              </div>
            </div>
          ))}
        </div>

        {/* Filter Pills & Live Search */}
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 12,
            marginBottom: 16,
          }}
        >
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {FILTER_PILLS.map((pill) => {
              const active = segment === pill.key;
              return (
                <button
                  key={pill.key}
                  type="button"
                  onClick={() => setSegment(pill.key)}
                  style={{
                    border: active ? `1.5px solid ${ACCENT}` : "1px solid #e2e8f0",
                    background: active ? "#0f172a" : "#fff",
                    color: active ? "#fff" : "#475569",
                    borderRadius: 999,
                    padding: "7px 14px",
                    fontSize: 12,
                    fontWeight: 700,
                    cursor: "pointer",
                  }}
                >
                  {pill.label}
                </button>
              );
            })}
          </div>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search guest name, phone, favorite dish, notes..."
            style={{
              minWidth: 270,
              padding: "8px 12px",
              borderRadius: 10,
              border: "1px solid #cbd5e1",
              fontSize: 13,
              background: "#fff",
              color: "#0f172a",
            }}
          />
        </div>

        {/* Guests Directory Table */}
        <div
          style={{
            background: "#ffffff",
            border: "1px solid #e2e8f0",
            borderRadius: 14,
            overflow: "hidden",
            boxShadow: "0 1px 3px rgba(15, 23, 42, 0.04)",
          }}
        >
          {loading ? (
            <div style={{ padding: 44, textAlign: "center", color: "#64748b", fontSize: 14 }}>
              Loading guest profiles...
            </div>
          ) : customers.length === 0 ? (
            <div style={{ padding: 48, textAlign: "center", color: "#64748b" }}>
              <div style={{ fontSize: 32, marginBottom: 8 }}>👥</div>
              <div style={{ fontSize: 15, fontWeight: 700, color: "#0f172a", marginBottom: 4 }}>
                No guests match this filter
              </div>
              <div style={{ fontSize: 13 }}>
                Guests are automatically added as soon as orders or table reservations are placed.
              </div>
            </div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr style={{ background: "#f8fafc", textAlign: "left", color: "#475569" }}>
                    <th style={{ padding: "12px 16px", fontWeight: 700 }}>Guest</th>
                    <th style={{ padding: "12px 14px", fontWeight: 700 }}>Segment</th>
                    <th style={{ padding: "12px 14px", fontWeight: 700 }}>Orders</th>
                    <th style={{ padding: "12px 14px", fontWeight: 700 }}>Total Spend</th>
                    <th style={{ padding: "12px 14px", fontWeight: 700 }}>Favorite Dish</th>
                    <th style={{ padding: "12px 14px", fontWeight: 700 }}>Last Order</th>
                    <th style={{ padding: "12px 16px", fontWeight: 700, textAlign: "right" }}>
                      Profile
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {customers.map((g) => {
                    const seg = SEGMENT_META[g.segment] || SEGMENT_META.new;
                    return (
                      <tr
                        key={g.phone}
                        style={{ borderTop: "1px solid #f1f5f9", color: "#0f172a" }}
                      >
                        <td style={{ padding: "13px 16px" }}>
                          <div style={{ fontWeight: 700, fontSize: 14 }}>{g.name}</div>
                          <div style={{ fontSize: 12, color: "#64748b" }}>{g.display_phone}</div>
                          {g.dietary_notes && (
                            <div
                              style={{
                                fontSize: 11,
                                color: "#86198f",
                                marginTop: 3,
                                maxWidth: 240,
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                                whiteSpace: "nowrap",
                              }}
                              title={g.dietary_notes}
                            >
                              📝 {g.dietary_notes}
                            </div>
                          )}
                        </td>
                        <td style={{ padding: "13px 14px" }}>
                          <span
                            style={{
                              fontSize: 11,
                              fontWeight: 700,
                              padding: "4px 10px",
                              borderRadius: 999,
                              background: seg.bg,
                              color: seg.color,
                              border: `1px solid ${seg.border}`,
                              whiteSpace: "nowrap",
                            }}
                          >
                            {seg.label}
                          </span>
                        </td>
                        <td style={{ padding: "13px 14px", fontWeight: 700 }}>
                          {g.total_orders}
                          {g.reservations_count > 0 && (
                            <div style={{ fontSize: 11, fontWeight: 500, color: "#64748b" }}>
                              {g.reservations_count} res.
                            </div>
                          )}
                        </td>
                        <td style={{ padding: "13px 14px", fontWeight: 800 }}>
                          {formatMoney(g.total_spend)}
                          <div style={{ fontSize: 11, fontWeight: 500, color: "#64748b" }}>
                            Avg {formatMoney(g.avg_order_value)}
                          </div>
                        </td>
                        <td style={{ padding: "13px 14px", color: "#334155", fontWeight: 600 }}>
                          {g.favorite_dish || "—"}
                        </td>
                        <td style={{ padding: "13px 14px", color: "#475569" }}>
                          {formatDate(g.last_order_at)}
                        </td>
                        <td style={{ padding: "13px 16px", textAlign: "right" }}>
                          <button
                            type="button"
                            onClick={() => openProfile(g.phone)}
                            style={{
                              border: `1px solid ${ACCENT}`,
                              background: "#fdf4ff",
                              color: "#86198f",
                              borderRadius: 8,
                              padding: "7px 12px",
                              fontSize: 12,
                              fontWeight: 700,
                              cursor: "pointer",
                              whiteSpace: "nowrap",
                            }}
                          >
                            View Profile
                          </button>
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

      {/* Guest Profile Drawer / Modal */}
      {selectedPhone && (
        <div
          onClick={() => setSelectedPhone(null)}
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(15, 23, 42, 0.45)",
            display: "flex",
            justifyContent: "flex-end",
            zIndex: 1000,
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              width: "100%",
              maxWidth: 540,
              height: "100%",
              background: "#ffffff",
              boxShadow: "-8px 0 28px rgba(15, 23, 42, 0.16)",
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
            }}
          >
            {/* Drawer Header */}
            <div
              style={{
                padding: "18px 20px",
                borderBottom: "1px solid #e2e8f0",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 10,
              }}
            >
              <div>
                <div style={{ fontSize: 18, fontWeight: 800, color: "#0f172a" }}>
                  {detail?.name || "Guest Profile"}
                </div>
                <div style={{ fontSize: 12, color: "#64748b" }}>
                  {detail?.display_phone || selectedPhone}
                  {detail?.preferred_order_type
                    ? ` • Prefers ${detail.preferred_order_type.replace("_", " ")}`
                    : ""}
                </div>
              </div>
              <button
                type="button"
                onClick={() => setSelectedPhone(null)}
                style={{
                  border: "1px solid #e2e8f0",
                  background: "#fff",
                  borderRadius: 8,
                  padding: "6px 10px",
                  fontSize: 13,
                  fontWeight: 700,
                  cursor: "pointer",
                  color: "#475569",
                }}
              >
                ✕
              </button>
            </div>

            {/* Drawer Body */}
            <div style={{ flex: 1, overflowY: "auto", padding: 20, display: "grid", gap: 18 }}>
              {detailLoading || !detail ? (
                <div style={{ textAlign: "center", padding: 40, color: "#64748b" }}>
                  Loading guest history...
                </div>
              ) : (
                <>
                  {/* Quick Metrics */}
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
                    <div
                      style={{
                        background: "#f8fafc",
                        borderRadius: 10,
                        padding: 12,
                        border: "1px solid #e2e8f0",
                      }}
                    >
                      <div style={{ fontSize: 11, color: "#64748b", fontWeight: 600 }}>Orders</div>
                      <div style={{ fontSize: 20, fontWeight: 800, color: "#0f172a" }}>
                        {detail.total_orders}
                      </div>
                    </div>
                    <div
                      style={{
                        background: "#f8fafc",
                        borderRadius: 10,
                        padding: 12,
                        border: "1px solid #e2e8f0",
                      }}
                    >
                      <div style={{ fontSize: 11, color: "#64748b", fontWeight: 600 }}>
                        Lifetime Spend
                      </div>
                      <div style={{ fontSize: 18, fontWeight: 800, color: "#0f172a" }}>
                        {formatMoney(detail.total_spend)}
                      </div>
                    </div>
                    <div
                      style={{
                        background: "#f8fafc",
                        borderRadius: 10,
                        padding: 12,
                        border: "1px solid #e2e8f0",
                      }}
                    >
                      <div style={{ fontSize: 11, color: "#64748b", fontWeight: 600 }}>
                        Reservations
                      </div>
                      <div style={{ fontSize: 20, fontWeight: 800, color: "#0f172a" }}>
                        {detail.reservations_count}
                      </div>
                    </div>
                  </div>

                  {/* Favorite Dishes */}
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 800, color: "#0f172a", marginBottom: 8 }}>
                      🍽️ Top Favorite Dishes
                    </div>
                    {detail.top_dishes?.length ? (
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                        {detail.top_dishes.map((d) => (
                          <span
                            key={d.name}
                            style={{
                              padding: "5px 11px",
                              borderRadius: 999,
                              fontSize: 12,
                              fontWeight: 700,
                              background: "#fdf4ff",
                              color: "#86198f",
                              border: `1px solid ${ACCENT}`,
                            }}
                          >
                            {d.name} ({d.count}×)
                          </span>
                        ))}
                      </div>
                    ) : (
                      <div style={{ fontSize: 12, color: "#64748b" }}>No dish history yet.</div>
                    )}
                  </div>

                  {/* Editable Dietary Notes & VIP Toggle (Synced with AI Agent) */}
                  <div
                    style={{
                      background: "#fdf4ff",
                      border: `1px solid ${ACCENT}`,
                      borderRadius: 12,
                      padding: 14,
                      display: "grid",
                      gap: 10,
                    }}
                  >
                    <div style={{ fontSize: 13, fontWeight: 800, color: "#86198f" }}>
                      🤖 Guest Preferences &amp; AI Personalization
                    </div>
                    <div>
                      <label style={{ display: "block", fontSize: 11, fontWeight: 700, color: "#475569", marginBottom: 4 }}>
                        Guest Name
                      </label>
                      <input
                        type="text"
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                        style={{
                          width: "100%",
                          padding: "8px 10px",
                          borderRadius: 8,
                          border: "1px solid #cbd5e1",
                          fontSize: 13,
                          background: "#fff",
                          boxSizing: "border-box",
                        }}
                      />
                    </div>
                    <div>
                      <label style={{ display: "block", fontSize: 11, fontWeight: 700, color: "#475569", marginBottom: 4 }}>
                        Dietary / Preference Notes (automatically respected by WhatsApp AI)
                      </label>
                      <textarea
                        rows={3}
                        value={editNotes}
                        onChange={(e) => setEditNotes(e.target.value)}
                        placeholder="e.g., No onions, extra spicy, nut allergy, prefers crispy fries..."
                        style={{
                          width: "100%",
                          padding: "8px 10px",
                          borderRadius: 8,
                          border: "1px solid #cbd5e1",
                          fontSize: 13,
                          background: "#fff",
                          resize: "vertical",
                          boxSizing: "border-box",
                        }}
                      />
                    </div>
                    <div>
                      <label style={{ display: "block", fontSize: 11, fontWeight: 700, color: "#475569", marginBottom: 4 }}>
                        Tags (comma-separated)
                      </label>
                      <input
                        type="text"
                        value={editTags}
                        onChange={(e) => setEditTags(e.target.value)}
                        placeholder="e.g., Family Diner, Corporate, Spice Lover"
                        style={{
                          width: "100%",
                          padding: "8px 10px",
                          borderRadius: 8,
                          border: "1px solid #cbd5e1",
                          fontSize: 13,
                          background: "#fff",
                          boxSizing: "border-box",
                        }}
                      />
                    </div>
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        gap: 10,
                        marginTop: 2,
                      }}
                    >
                      <label
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 8,
                          fontSize: 13,
                          fontWeight: 700,
                          color: "#0f172a",
                          cursor: "pointer",
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={editVip}
                          onChange={(e) => setEditVip(e.target.checked)}
                        />
                        👑 Mark as VIP Guest
                      </label>
                      <button
                        type="button"
                        disabled={saving}
                        onClick={handleSaveProfile}
                        style={{
                          border: "none",
                          background: "#0f172a",
                          color: "#fff",
                          borderRadius: 9,
                          padding: "8px 16px",
                          fontSize: 12,
                          fontWeight: 700,
                          cursor: saving ? "wait" : "pointer",
                        }}
                      >
                        {saving ? "Saving..." : "💾 Save Notes"}
                      </button>
                    </div>
                  </div>

                  {/* Order History */}
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 800, color: "#0f172a", marginBottom: 8 }}>
                      🧾 Order History ({detail.orders?.length || 0})
                    </div>
                    {detail.orders?.length ? (
                      <div style={{ display: "grid", gap: 8 }}>
                        {detail.orders.map((o) => (
                          <div
                            key={o.id}
                            style={{
                              border: "1px solid #e2e8f0",
                              borderRadius: 10,
                              padding: "10px 12px",
                              background: "#fff",
                            }}
                          >
                            <div
                              style={{
                                display: "flex",
                                justifyContent: "space-between",
                                alignItems: "center",
                                marginBottom: 4,
                              }}
                            >
                              <span style={{ fontWeight: 800, fontSize: 13, color: "#0f172a" }}>
                                #{o.order_number}
                              </span>
                              <span style={{ fontWeight: 800, fontSize: 13, color: "#0f172a" }}>
                                {formatMoney(o.total)}
                              </span>
                            </div>
                            <div style={{ fontSize: 11, color: "#64748b", marginBottom: 4 }}>
                              {formatDate(o.created_at)} • {o.order_type?.replace("_", " ")} •{" "}
                              <strong style={{ textTransform: "capitalize" }}>
                                {o.status?.replace("_", " ")}
                              </strong>
                            </div>
                            <div style={{ fontSize: 12, color: "#334155" }}>
                              {(o.items || [])
                                .map((it) => `${it.quantity}× ${it.item_name}`)
                                .join(", ")}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div style={{ fontSize: 12, color: "#64748b" }}>No orders recorded yet.</div>
                    )}
                  </div>

                  {/* Reservation History */}
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 800, color: "#0f172a", marginBottom: 8 }}>
                      📅 Reservation History ({detail.reservations?.length || 0})
                    </div>
                    {detail.reservations?.length ? (
                      <div style={{ display: "grid", gap: 8 }}>
                        {detail.reservations.map((r) => (
                          <div
                            key={r.id}
                            style={{
                              border: "1px solid #e2e8f0",
                              borderRadius: 10,
                              padding: "10px 12px",
                              background: "#f8fafc",
                              fontSize: 12,
                            }}
                          >
                            <div style={{ fontWeight: 700, color: "#0f172a" }}>
                              {r.reservation_date} at {r.reservation_time} • Party of {r.party_size}
                              {r.table_number ? ` • Table ${r.table_number}` : ""}
                            </div>
                            <div style={{ color: "#64748b", marginTop: 2, textTransform: "capitalize" }}>
                              Status: {r.status?.replace("_", " ")}
                              {r.special_requests ? ` • "${r.special_requests}"` : ""}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div style={{ fontSize: 12, color: "#64748b" }}>
                        No table reservations recorded yet.
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
}
