import { useCallback, useEffect, useMemo, useState } from "react";
import OwnerLayout from "../owner/components/OwnerLayout";
import StaffLayout from "../staff/components/StaffLayout";
import { suppliersApi } from "../api/operationsApi";
import { errorText } from "../api/axiosClient";

const EMPTY_FORM = {
  name: "",
  contact_person: "",
  phone: "",
  email: "",
  category: "",
  payment_terms: "COD",
  address: "",
  notes: "",
  is_active: true,
};

export default function SuppliersManagement({ staff = false }) {
  const [suppliers, setSuppliers] = useState([]);
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const loadSuppliers = useCallback(async () => {
    setError("");
    try {
      const params = {};
      if (search.trim()) params.search = search.trim();
      if (categoryFilter !== "all") params.category = categoryFilter;
      const { data } = await suppliersApi.list(params);
      setSuppliers(Array.isArray(data) ? data : []);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setLoading(false);
    }
  }, [search, categoryFilter]);

  useEffect(() => {
    loadSuppliers();
  }, [loadSuppliers]);

  const categories = useMemo(() => {
    const set = new Set(["Produce", "Medicine Distributor", "Medical Equipment", "Packaging", "Wholesale"]);
    suppliers.forEach((s) => {
      if (s.category) set.add(s.category);
    });
    return ["all", ...Array.from(set)];
  }, [suppliers]);

  const flashNotice = (msg) => {
    setNotice(msg);
    setTimeout(() => setNotice(""), 2800);
  };

  const openAdd = () => {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setShowForm(true);
  };

  const openEdit = (sup) => {
    setEditingId(sup.id);
    setForm({
      name: sup.name || "",
      contact_person: sup.contact_person || "",
      phone: sup.phone || "",
      email: sup.email || "",
      category: sup.category || "",
      payment_terms: sup.payment_terms || "COD",
      address: sup.address || "",
      notes: sup.notes || "",
      is_active: Boolean(sup.is_active),
    });
    setShowForm(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.name.trim()) return;
    setSaving(true);
    setError("");
    try {
      if (editingId) {
        await suppliersApi.update(editingId, form);
        flashNotice(`Updated supplier "${form.name.trim()}".`);
      } else {
        await suppliersApi.create(form);
        flashNotice(`Added supplier "${form.name.trim()}".`);
      }
      setShowForm(false);
      setEditingId(null);
      setForm(EMPTY_FORM);
      await loadSuppliers();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setSaving(false);
    }
  };

  const toggleActive = async (sup) => {
    try {
      await suppliersApi.update(sup.id, { is_active: !sup.is_active });
      await loadSuppliers();
    } catch (err) {
      setError(errorText(err));
    }
  };

  const handleDelete = async (sup) => {
    if (!window.confirm(`Delete supplier "${sup.name}"?`)) return;
    try {
      await suppliersApi.remove(sup.id);
      flashNotice(`Deleted "${sup.name}".`);
      await loadSuppliers();
    } catch (err) {
      setError(errorText(err));
    }
  };

  const Layout = staff ? StaffLayout : OwnerLayout;

  return (
    <Layout
      title="Suppliers Directory"
      subtitle="Manage vendors, distributors, payment terms, and contact details for your business."
    >
      {error && <div className="ad-alert" role="alert">{error}</div>}
      {notice && (
        <div style={{ background: "#fdf4ff", border: "1px solid #f0abfc", color: "#86198f", padding: "9px 14px", borderRadius: 10, fontSize: 13, fontWeight: 600, marginBottom: 14 }}>
          ✅ {notice}
        </div>
      )}

      {/* Search, Filter & Add Supplier Bar */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 10, marginBottom: 16 }}>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", flex: 1 }}>
          <input
            placeholder="Search supplier name, contact, phone..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ flex: 1, minWidth: 200, padding: "9px 12px", borderRadius: 10, border: "1px solid #d1d5db", fontSize: 13.5 }}
          />
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            style={{ padding: "9px 12px", borderRadius: 10, border: "1px solid #d1d5db", fontSize: 13 }}
          >
            {categories.map((c) => (
              <option key={c} value={c}>{c === "all" ? "All Categories" : c}</option>
            ))}
          </select>
        </div>

        <button
          type="button"
          onClick={openAdd}
          style={{
            padding: "9px 16px",
            borderRadius: 10,
            border: "none",
            background: "#ff77ff",
            color: "#fff",
            fontWeight: 700,
            fontSize: 13,
            cursor: "pointer",
            boxShadow: "0 3px 10px rgba(255,119,255,0.35)",
          }}
        >
          + Add Supplier
        </button>
      </div>

      {/* Add / Edit Supplier Form */}
      {showForm && (
        <form onSubmit={handleSubmit} style={{ background: "#fff", border: "1px solid #f0abfc", borderRadius: 16, padding: 18, marginBottom: 18, display: "grid", gap: 12 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h4 style={{ margin: 0 }}>{editingId ? "Edit Supplier" : "Add New Supplier"}</h4>
            <button type="button" onClick={() => setShowForm(false)} style={{ background: "none", border: "none", cursor: "pointer", fontWeight: 700 }}>✕</button>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 10 }}>
            <input placeholder="Supplier / Vendor Name *" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid #d1d5db" }} />
            <input placeholder="Contact Person" value={form.contact_person} onChange={(e) => setForm({ ...form, contact_person: e.target.value })} style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid #d1d5db" }} />
            <input placeholder="Phone (03xx...)" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid #d1d5db" }} />
            <input type="email" placeholder="Email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid #d1d5db" }} />
            <input placeholder="Category (e.g. Produce, Packaging)" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid #d1d5db" }} />
            <input placeholder="Payment Terms (COD, Net 15, Net 30)" value={form.payment_terms} onChange={(e) => setForm({ ...form, payment_terms: e.target.value })} style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid #d1d5db" }} />
          </div>
          <input placeholder="Address" value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid #d1d5db" }} />
          <textarea rows={2} placeholder="Notes..." value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid #d1d5db", fontFamily: "inherit" }} />
          <div style={{ display: "flex", gap: 10 }}>
            <button type="submit" disabled={saving} className="ad-btn ad-btn-primary">{saving ? "Saving..." : editingId ? "Save Changes" : "Create Supplier"}</button>
            <button type="button" onClick={() => setShowForm(false)} className="ad-btn">Cancel</button>
          </div>
        </form>
      )}

      {/* Suppliers Directory */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 14 }}>
        {loading ? (
          <p style={{ color: "#64748b" }}>Loading suppliers...</p>
        ) : suppliers.length === 0 ? (
          <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 14, padding: 24, color: "#64748b" }}>
            No suppliers found. Click <strong>+ Add Supplier</strong> to add your first vendor.
          </div>
        ) : (
          suppliers.map((sup) => (
            <div key={sup.id} style={{ background: "#fff", border: sup.is_active ? "1px solid #f0abfc" : "1px solid #e2e8f0", borderRadius: 14, padding: 16, opacity: sup.is_active ? 1 : 0.7 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
                <div>
                  <h4 style={{ margin: 0, fontSize: 15.5 }}>{sup.name}</h4>
                  <div style={{ fontSize: 12, color: "#a21caf", fontWeight: 600, marginTop: 2 }}>
                    {sup.category || "General"} · {sup.payment_terms || "Standard"}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => toggleActive(sup)}
                  style={{
                    fontSize: 11,
                    fontWeight: 700,
                    padding: "3px 9px",
                    borderRadius: 999,
                    border: "none",
                    cursor: "pointer",
                    background: sup.is_active ? "#ecfdf5" : "#f1f5f9",
                    color: sup.is_active ? "#047857" : "#64748b",
                  }}
                >
                  {sup.is_active ? "Active" : "Inactive"}
                </button>
              </div>

              <div style={{ fontSize: 12.5, color: "#475569", marginTop: 10, display: "grid", gap: 3 }}>
                {sup.contact_person && <div>👤 {sup.contact_person}</div>}
                {sup.phone && <div>📞 {sup.phone}</div>}
                {sup.email && <div>✉️ {sup.email}</div>}
                {sup.address && <div>📍 {sup.address}</div>}
              </div>

              <div style={{ display: "flex", gap: 12, marginTop: 12 }}>
                <button type="button" onClick={() => openEdit(sup)} style={{ background: "none", border: "none", color: "#a21caf", fontWeight: 700, fontSize: 12.5, cursor: "pointer", padding: 0 }}>
                  Edit
                </button>
                {!staff && (
                  <button type="button" onClick={() => handleDelete(sup)} style={{ background: "none", border: "none", color: "#ef4444", fontWeight: 600, fontSize: 12.5, cursor: "pointer", padding: 0 }}>
                    Delete
                  </button>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </Layout>
  );
}
