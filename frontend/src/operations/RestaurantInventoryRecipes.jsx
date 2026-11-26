import { useCallback, useEffect, useState } from "react";
import OwnerLayout from "../owner/components/OwnerLayout";
import StaffLayout from "../staff/components/StaffLayout";
import { operationsApi, restaurantInventoryApi, restaurantSuppliersApi } from "../api/operationsApi";
import { errorText } from "../api/axiosClient";

const STATUS_BADGE = {
  in_stock: { label: "In Stock", bg: "#ecfdf5", color: "#047857", border: "#6ee7b7" },
  low_stock: { label: "Low Stock", bg: "#fffbeb", color: "#b45309", border: "#fcd34d" },
  out_of_stock: { label: "Out of Stock", bg: "#fef2f2", color: "#b91c1c", border: "#fecaca" },
};

const UNITS = [
  { value: "kg", label: "kg (Kilograms)" },
  { value: "g", label: "g (Grams)" },
  { value: "l", label: "L (Liters)" },
  { value: "ml", label: "ml (Milliliters)" },
  { value: "pcs", label: "pcs (Pieces)" },
  { value: "packs", label: "packs (Packs)" },
];

const WEIGHT_UNIT_KEYWORDS = [
  "chicken", "beef", "mutton", "meat", "keema", "fish",
  "fries", "potato", "flour", "rice", "cheese",
];

export default function RestaurantInventoryRecipes({ staff = false }) {
  const Layout = staff ? StaffLayout : OwnerLayout;

  const [activeTab, setActiveTab] = useState("ingredients"); // "ingredients" | "recipes"
  const [ingredients, setIngredients] = useState([]);
  const [summary, setSummary] = useState({ total: 0, in_stock: 0, low_stock: 0, out_of_stock: 0 });
  const [statusFilter, setStatusFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  // Add Ingredient Modal
  const [showAddModal, setShowAddModal] = useState(false);
  const [unitManuallySet, setUnitManuallySet] = useState(false);
  const [newForm, setNewForm] = useState({
    name: "",
    sku: "",
    unit: "pcs",
    current_stock: "10",
    low_stock_threshold: "5",
    cost_per_unit: "0",
    supplier_id: "",
    supplier_name: "",
    log_as_expense: true,
  });
  const [saving, setSaving] = useState(false);

  // Adjust Stock Modal (Restock / Waste / Manual)
  const [adjustModal, setAdjustModal] = useState(null); // { ingredient, mode }
  const [adjustQty, setAdjustQty] = useState("5");
  const [adjustReason, setAdjustReason] = useState("");
  const [adjustSupplierId, setAdjustSupplierId] = useState("");
  const [adjustPurchaseCost, setAdjustPurchaseCost] = useState("");
  const [adjustLogExpense, setAdjustLogExpense] = useState(true);

  // Suppliers State
  const [suppliers, setSuppliers] = useState([]);
  const [showSupplierModal, setShowSupplierModal] = useState(false);
  const [editingSupplier, setEditingSupplier] = useState(null);
  const [supplierForm, setSupplierForm] = useState({
    name: "",
    contact_person: "",
    phone: "",
    email: "",
    address: "",
    category: "Meat",
    notes: "",
  });

  // Stock History Modal
  const [historyModal, setHistoryModal] = useState(null); // { ingredient, movements, loading }

  // Recipe Builder State
  const [dishes, setDishes] = useState([]);
  const [selectedDishId, setSelectedDishId] = useState("");
  const [recipeRows, setRecipeRows] = useState([]);
  const [loadingRecipe, setLoadingRecipe] = useState(false);
  const [savingRecipe, setSavingRecipe] = useState(false);

  const flashNotice = (msg) => {
    setNotice(msg);
    setTimeout(() => setNotice(""), 3200);
  };

  const loadIngredients = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = {};
      if (statusFilter !== "all") params.status = statusFilter;
      if (search.trim()) params.q = search.trim();
      const { data } = await restaurantInventoryApi.list(params);
      setIngredients(Array.isArray(data?.ingredients) ? data.ingredients : []);
      setSummary(data?.summary || { total: 0, in_stock: 0, low_stock: 0, out_of_stock: 0 });
    } catch (err) {
      setError(errorText(err) || "Failed to load restaurant inventory.");
    } finally {
      setLoading(false);
    }
  }, [statusFilter, search]);

  const loadSuppliers = useCallback(async () => {
    try {
      const { data } = await restaurantSuppliersApi.list();
      setSuppliers(Array.isArray(data) ? data : []);
    } catch {}
  }, []);

  useEffect(() => {
    loadIngredients();
    loadSuppliers();
  }, [loadIngredients, loadSuppliers]);

  // Load menu dishes when Recipe Builder tab is opened
  useEffect(() => {
    if (activeTab !== "recipes") return;
    operationsApi
      .orderCatalog()
      .then(({ data }) => {
        const list = Array.isArray(data) ? data : [];
        setDishes(list);
        if (!selectedDishId && list.length > 0) {
          setSelectedDishId(String(list[0].id));
        }
      })
      .catch(() => {});
  }, [activeTab, selectedDishId]);

  // Load recipe for selected dish
  useEffect(() => {
    if (activeTab !== "recipes" || !selectedDishId) return;
    setLoadingRecipe(true);
    restaurantInventoryApi
      .getRecipe(selectedDishId)
      .then(({ data }) => {
        const rows = Array.isArray(data?.ingredients) ? data.ingredients : [];
        setRecipeRows(
          rows.map((r) => ({
            ingredient_id: String(r.ingredient_id),
            quantity_required: String(r.quantity_required),
          }))
        );
      })
      .catch(() => setRecipeRows([]))
      .finally(() => setLoadingRecipe(false));
  }, [activeTab, selectedDishId]);

  const handleCreateIngredient = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      await restaurantInventoryApi.create(newForm);
      setShowAddModal(false);
      setNewForm({
        name: "",
        sku: "",
        unit: "pcs",
        current_stock: "10",
        low_stock_threshold: "5",
        cost_per_unit: "0",
        supplier_name: "",
      });
      await loadIngredients();
      flashNotice("Ingredient added to stock.");
    } catch (err) {
      setError(errorText(err) || "Failed to create ingredient.");
    } finally {
      setSaving(false);
    }
  };

  const handleAdjustStock = async (e) => {
    e.preventDefault();
    if (!adjustModal) return;
    setSaving(true);
    setError("");
    try {
      const payload = {
        movement_type: adjustModal.mode,
        quantity: Number(adjustQty || 0),
        reason: adjustReason.trim(),
      };
      if (adjustModal.mode === "restock") {
        if (adjustSupplierId) payload.supplier_id = Number(adjustSupplierId);
        if (adjustPurchaseCost !== "" && Number(adjustPurchaseCost) > 0) {
          payload.purchase_cost = Number(adjustPurchaseCost);
          payload.log_as_expense = adjustLogExpense;
        }
      }
      await restaurantInventoryApi.adjust(adjustModal.ingredient.id, payload);
      setAdjustModal(null);
      setAdjustQty("5");
      setAdjustReason("");
      setAdjustSupplierId("");
      setAdjustPurchaseCost("");
      setAdjustLogExpense(true);
      await loadIngredients();
      flashNotice("Stock level updated and logged.");
    } catch (err) {
      setError(errorText(err) || "Failed to adjust stock.");
    } finally {
      setSaving(false);
    }
  };

  const handleSaveSupplier = async (e) => {
    e.preventDefault();
    if (!supplierForm.name.trim()) return;
    setSaving(true);
    setError("");
    try {
      if (editingSupplier) {
        await restaurantSuppliersApi.update(editingSupplier.id, supplierForm);
        flashNotice(`Updated supplier "${supplierForm.name}".`);
      } else {
        await restaurantSuppliersApi.create(supplierForm);
        flashNotice(`Added supplier "${supplierForm.name}".`);
      }
      setShowSupplierModal(false);
      setEditingSupplier(null);
      setSupplierForm({ name: "", contact_person: "", phone: "", email: "", address: "", category: "Meat", notes: "" });
      await loadSuppliers();
    } catch (err) {
      setError(errorText(err) || "Failed to save supplier.");
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteSupplier = async (sup) => {
    if (!window.confirm(`Delete supplier "${sup.name}"?`)) return;
    try {
      await restaurantSuppliersApi.remove(sup.id);
      await loadSuppliers();
      flashNotice(`Deleted supplier "${sup.name}".`);
    } catch (err) {
      setError(errorText(err) || "Failed to delete supplier.");
    }
  };

  const openHistory = async (ing) => {
    setHistoryModal({ ingredient: ing, movements: [], loading: true });
    try {
      const { data } = await restaurantInventoryApi.movements(ing.id);
      setHistoryModal({ ingredient: ing, movements: Array.isArray(data) ? data : [], loading: false });
    } catch {
      setHistoryModal({ ingredient: ing, movements: [], loading: false });
    }
  };

  const handleDeleteIngredient = async (ing) => {
    if (!window.confirm(`Delete ingredient "${ing.name}"?`)) return;
    try {
      await restaurantInventoryApi.remove(ing.id);
      await loadIngredients();
      flashNotice(`Deleted "${ing.name}".`);
    } catch (err) {
      setError(errorText(err) || "Failed to delete ingredient.");
    }
  };

  const handleSaveRecipe = async (e) => {
    e.preventDefault();
    if (!selectedDishId) return;
    setSavingRecipe(true);
    setError("");
    try {
      const payload = recipeRows
        .filter((r) => r.ingredient_id && Number(r.quantity_required) > 0)
        .map((r) => ({
          ingredient_id: Number(r.ingredient_id),
          quantity_required: Number(r.quantity_required),
        }));
      await restaurantInventoryApi.saveRecipe(selectedDishId, payload);
      await loadIngredients();
      flashNotice("Dish recipe saved! Orders will now auto-deduct these ingredients.");
    } catch (err) {
      setError(errorText(err) || "Failed to save dish recipe.");
    } finally {
      setSavingRecipe(false);
    }
  };

  const cardStyle = {
    background: "#ffffff",
    border: "1px solid #f0e6f2",
    borderRadius: 16,
    padding: 18,
    boxShadow: "0 2px 10px rgba(42, 16, 48, 0.03)",
  };

  return (
    <Layout
      title="Inventory & Recipes"
      subtitle="Track raw ingredients, map dish recipes for automatic order deduction, and prevent out-of-stock orders."
    >
      <div style={{ maxWidth: 1320, margin: "0 auto", display: "flex", flexDirection: "column", gap: 18 }}>
        {/* Top KPI Strip */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: 14 }}>
          <div style={cardStyle}>
            <div style={{ fontSize: 12.5, fontWeight: 600, color: "#7f7288" }}>Total Ingredients</div>
            <div style={{ fontSize: 28, fontWeight: 800, color: "#211426", marginTop: 4 }}>{summary.total}</div>
          </div>
          <div style={{ ...cardStyle, borderLeft: "4px solid #10b981" }}>
            <div style={{ fontSize: 12.5, fontWeight: 600, color: "#047857" }}>In Stock</div>
            <div style={{ fontSize: 28, fontWeight: 800, color: "#047857", marginTop: 4 }}>{summary.in_stock}</div>
          </div>
          <div style={{ ...cardStyle, borderLeft: "4px solid #f59e0b" }}>
            <div style={{ fontSize: 12.5, fontWeight: 600, color: "#b45309" }}>Low Stock Alerts</div>
            <div style={{ fontSize: 28, fontWeight: 800, color: "#b45309", marginTop: 4 }}>{summary.low_stock}</div>
          </div>
          <div style={{ ...cardStyle, borderLeft: "4px solid #ef4444" }}>
            <div style={{ fontSize: 12.5, fontWeight: 600, color: "#b91c1c" }}>Out of Stock</div>
            <div style={{ fontSize: 28, fontWeight: 800, color: "#b91c1c", marginTop: 4 }}>{summary.out_of_stock}</div>
          </div>
        </div>

        {/* Tab Switcher & Primary CTA */}
        <div
          style={{
            ...cardStyle,
            padding: "12px 16px",
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 12,
          }}
        >
          <div style={{ display: "inline-flex", background: "#faf5fb", border: "1px solid #eedff0", borderRadius: 11, padding: 4, gap: 4 }}>
            <button
              type="button"
              onClick={() => setActiveTab("ingredients")}
              style={{
                border: "none",
                borderRadius: 8,
                padding: "8px 16px",
                fontSize: 13.5,
                fontWeight: activeTab === "ingredients" ? 800 : 600,
                cursor: "pointer",
                background: activeTab === "ingredients" ? "#ff77ff" : "transparent",
                color: activeTab === "ingredients" ? "#240729" : "#6b5a75",
              }}
            >
              📦 Ingredients & Stock
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("recipes")}
              style={{
                border: "none",
                borderRadius: 8,
                padding: "8px 16px",
                fontSize: 13.5,
                fontWeight: activeTab === "recipes" ? 800 : 600,
                cursor: "pointer",
                background: activeTab === "recipes" ? "#ff77ff" : "transparent",
                color: activeTab === "recipes" ? "#240729" : "#6b5a75",
              }}
            >
              📖 Manage Dish Recipes
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("suppliers")}
              style={{
                border: "none",
                borderRadius: 8,
                padding: "8px 16px",
                fontSize: 13.5,
                fontWeight: activeTab === "suppliers" ? 800 : 600,
                cursor: "pointer",
                background: activeTab === "suppliers" ? "#ff77ff" : "transparent",
                color: activeTab === "suppliers" ? "#240729" : "#6b5a75",
              }}
            >
              🚚 Suppliers ({suppliers.length})
            </button>
          </div>

          <button
            type="button"
            onClick={() => {
              if (activeTab === "suppliers") {
                setEditingSupplier(null);
                setSupplierForm({ name: "", contact_person: "", phone: "", email: "", address: "", category: "Meat", notes: "" });
                setShowSupplierModal(true);
              } else {
                setUnitManuallySet(false);
                setShowAddModal(true);
              }
            }}
            style={{
              border: "none",
              background: "#ff77ff",
              color: "#240729",
              borderRadius: 10,
              padding: "9px 16px",
              fontSize: 13.5,
              fontWeight: 800,
              cursor: "pointer",
              boxShadow: "0 4px 12px rgba(255, 119, 255, 0.35)",
            }}
          >
            {activeTab === "suppliers" ? "+ Add Supplier" : "+ Add Ingredient"}
          </button>
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

        {/* TAB 3: SUPPLIERS DIRECTORY */}
        {activeTab === "suppliers" && (
          <div style={cardStyle}>
            <div style={{ marginBottom: 14 }}>
              <h3 style={{ margin: 0, fontSize: 16, fontWeight: 800, color: "#211426" }}>
                🚚 Inventory Suppliers Directory
              </h3>
              <div style={{ fontSize: 12.5, color: "#7f7288", marginTop: 2 }}>
                Manage meat, produce, dairy, packaging &amp; beverage vendors with 1-click Call &amp; WhatsApp reorder.
              </div>
            </div>
            {suppliers.length === 0 ? (
              <div style={{ padding: 36, textAlign: "center", color: "#7f7288", fontSize: 13 }}>
                No suppliers added yet. Click <strong>+ Add Supplier</strong> to add your first vendor.
              </div>
            ) : (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(290px, 1fr))", gap: 12 }}>
                {suppliers.map((sup) => {
                  const waDigits = String(sup.phone || "").replace(/\D/g, "");
                  const waNum = waDigits.startsWith("03") && waDigits.length === 11 ? `92${waDigits.slice(1)}` : waDigits;
                  return (
                    <div
                      key={sup.id}
                      style={{
                        border: "1px solid #f0e6f2",
                        borderRadius: 12,
                        padding: 14,
                        background: "#fcfafd",
                        display: "flex",
                        flexDirection: "column",
                        gap: 8,
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
                        <div>
                          <div style={{ fontWeight: 800, fontSize: 14.5, color: "#211426" }}>{sup.name}</div>
                          <div style={{ fontSize: 12, color: "#6b5a75" }}>
                            {sup.category || "General"}
                            {sup.contact_person ? ` • ${sup.contact_person}` : ""}
                          </div>
                        </div>
                        <span
                          style={{
                            fontSize: 11,
                            fontWeight: 700,
                            padding: "2px 8px",
                            borderRadius: 999,
                            background: "#fdf4ff",
                            color: "#86198f",
                            border: "1px solid #f0abfc",
                          }}
                        >
                          {sup.ingredients_count || 0} items
                        </span>
                      </div>
                      {sup.phone && <div style={{ fontSize: 12.5, color: "#374151" }}>📞 {sup.phone}</div>}
                      {sup.address && <div style={{ fontSize: 12, color: "#6b5a75" }}>📍 {sup.address}</div>}
                      {sup.notes && <div style={{ fontSize: 11.5, color: "#7f7288" }}>📝 {sup.notes}</div>}
                      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 4 }}>
                        {sup.phone && (
                          <>
                            <a
                              href={`tel:${sup.phone}`}
                              style={{
                                textDecoration: "none",
                                fontSize: 11.5,
                                fontWeight: 700,
                                padding: "5px 9px",
                                borderRadius: 8,
                                background: "#fff",
                                color: "#211426",
                                border: "1px solid #d1d5db",
                              }}
                            >
                              📞 Call
                            </a>
                            <a
                              href={`https://wa.me/${waNum}?text=${encodeURIComponent(
                                `Assalam-o-Alaikum ${sup.contact_person || sup.name}, humein kitchen stock reorder karna hai.`
                              )}`}
                              target="_blank"
                              rel="noreferrer"
                              style={{
                                textDecoration: "none",
                                fontSize: 11.5,
                                fontWeight: 700,
                                padding: "5px 9px",
                                borderRadius: 8,
                                background: "#ecfdf5",
                                color: "#047857",
                                border: "1px solid #a7f3d0",
                              }}
                            >
                              💬 WhatsApp
                            </a>
                          </>
                        )}
                        <button
                          type="button"
                          onClick={() => {
                            setEditingSupplier(sup);
                            setSupplierForm({
                              name: sup.name || "",
                              contact_person: sup.contact_person || "",
                              phone: sup.phone || "",
                              email: sup.email || "",
                              address: sup.address || "",
                              category: sup.category || "Meat",
                              notes: sup.notes || "",
                            });
                            setShowSupplierModal(true);
                          }}
                          style={{
                            border: "1px solid #d1d5db",
                            background: "#fff",
                            color: "#374151",
                            borderRadius: 8,
                            padding: "5px 9px",
                            fontSize: 11.5,
                            fontWeight: 700,
                            cursor: "pointer",
                          }}
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDeleteSupplier(sup)}
                          style={{
                            border: "1px solid #fecaca",
                            background: "#fff",
                            color: "#b91c1c",
                            borderRadius: 8,
                            padding: "5px 9px",
                            fontSize: 11.5,
                            fontWeight: 700,
                            cursor: "pointer",
                          }}
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* TAB 1: INGREDIENTS & STOCK */}
        {activeTab === "ingredients" && (
          <div style={{ ...cardStyle, padding: 0, overflow: "hidden" }}>
            {/* Filters & Search */}
            <div
              style={{
                padding: "14px 18px",
                borderBottom: "1px solid #f0e6f2",
                display: "flex",
                flexWrap: "wrap",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 12,
              }}
            >
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                {[
                  { key: "all", label: "All" },
                  { key: "low_stock", label: "⚠️ Low Stock" },
                  { key: "out_of_stock", label: "🔴 Out of Stock" },
                ].map((f) => {
                  const active = statusFilter === f.key;
                  return (
                    <button
                      key={f.key}
                      type="button"
                      onClick={() => setStatusFilter(f.key)}
                      style={{
                        border: active ? "1px solid #d946ef" : "1px solid #eedff0",
                        background: active ? "#fdf2ff" : "#ffffff",
                        color: active ? "#86198f" : "#564861",
                        borderRadius: 999,
                        padding: "6px 13px",
                        fontSize: 12.5,
                        fontWeight: active ? 800 : 600,
                        cursor: "pointer",
                      }}
                    >
                      {f.label}
                    </button>
                  );
                })}
              </div>

              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search ingredient, SKU, or supplier..."
                style={{
                  padding: "8px 13px",
                  borderRadius: 10,
                  border: "1px solid #e5d6ea",
                  fontSize: 13,
                  minWidth: 240,
                }}
              />
            </div>

            {loading ? (
              <div style={{ padding: 48, textAlign: "center", color: "#8c7d96" }}>Loading ingredients...</div>
            ) : ingredients.length === 0 ? (
              <div style={{ padding: 52, textAlign: "center" }}>
                <div style={{ fontSize: 36, marginBottom: 8 }}>🥬</div>
                <h3 style={{ margin: 0, fontSize: 16.5, fontWeight: 800, color: "#211426" }}>No Ingredients Found</h3>
                <p style={{ margin: "6px 0 14px", fontSize: 13, color: "#7f7288" }}>
                  Add raw kitchen ingredients (e.g. Chicken Fillet, Burger Bun, Cheese Slice) and link them to your dishes.
                </p>
                <button
                  type="button"
                  onClick={() => setShowAddModal(true)}
                  style={{ border: "none", background: "#ff77ff", color: "#240729", borderRadius: 10, padding: "9px 18px", fontSize: 13, fontWeight: 800, cursor: "pointer" }}
                >
                  + Add First Ingredient
                </button>
              </div>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13.5 }}>
                  <thead>
                    <tr style={{ background: "#faf7fb", borderBottom: "1px solid #f0e6f2", textAlign: "left", color: "#7f7288", fontSize: 12 }}>
                      <th style={{ padding: "12px 16px", fontWeight: 700 }}>Ingredient</th>
                      <th style={{ padding: "12px 16px", fontWeight: 700 }}>Current Stock</th>
                      <th style={{ padding: "12px 16px", fontWeight: 700 }}>Low Threshold</th>
                      <th style={{ padding: "12px 16px", fontWeight: 700 }}>Status</th>
                      <th style={{ padding: "12px 16px", fontWeight: 700, textAlign: "right" }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ingredients.map((ing) => {
                      const st = STATUS_BADGE[ing.status] || STATUS_BADGE.in_stock;
                      return (
                        <tr key={ing.id} style={{ borderBottom: "1px solid #f6eff8" }}>
                          <td style={{ padding: "13px 16px" }}>
                            <div style={{ fontWeight: 750, color: "#211426" }}>{ing.name}</div>
                            <div style={{ fontSize: 12, color: "#7f7288", marginTop: 2 }}>
                              {ing.linked_dishes_count || 0} linked {ing.linked_dishes_count === 1 ? "dish" : "dishes"}
                              {ing.supplier_name ? ` · Supplier: ${ing.supplier_name}` : ""}
                              {ing.cost_per_unit > 0 ? ` · Rs. ${ing.cost_per_unit}/${ing.unit}` : ""}
                            </div>
                          </td>
                          <td style={{ padding: "13px 16px", fontWeight: 800, fontSize: 14.5, color: "#211426" }}>
                            {ing.current_stock} <span style={{ fontSize: 12, fontWeight: 600, color: "#7f7288" }}>{ing.unit}</span>
                          </td>
                          <td style={{ padding: "13px 16px", color: "#6b5a75" }}>
                            {ing.low_stock_threshold} {ing.unit}
                          </td>
                          <td style={{ padding: "13px 16px" }}>
                            <span
                              style={{
                                display: "inline-block",
                                padding: "3px 10px",
                                borderRadius: 999,
                                fontSize: 11.5,
                                fontWeight: 800,
                                background: st.bg,
                                color: st.color,
                                border: `1px solid ${st.border}`,
                              }}
                            >
                              {st.label}
                            </span>
                          </td>
                          <td style={{ padding: "13px 16px", textAlign: "right", whiteSpace: "nowrap" }}>
                            <div style={{ display: "inline-flex", gap: 6 }}>
                              <button
                                type="button"
                                onClick={() => {
                                  setAdjustQty("10");
                                  setAdjustReason("");
                                  setAdjustModal({ ingredient: ing, mode: "restock" });
                                }}
                                style={{ border: "1px solid #6ee7b7", background: "#ecfdf5", color: "#047857", borderRadius: 8, padding: "5px 10px", fontSize: 12, fontWeight: 750, cursor: "pointer" }}
                              >
                                + Restock
                              </button>
                              <button
                                type="button"
                                onClick={() => {
                                  setAdjustQty("1");
                                  setAdjustReason("");
                                  setAdjustModal({ ingredient: ing, mode: "waste" });
                                }}
                                style={{ border: "1px solid #fcd34d", background: "#fffbeb", color: "#b45309", borderRadius: 8, padding: "5px 10px", fontSize: 12, fontWeight: 750, cursor: "pointer" }}
                              >
                                - Waste/Adjust
                              </button>
                              <button
                                type="button"
                                onClick={() => openHistory(ing)}
                                style={{ border: "1px solid #e5d6ea", background: "#ffffff", color: "#4e3c57", borderRadius: 8, padding: "5px 10px", fontSize: 12, fontWeight: 700, cursor: "pointer" }}
                              >
                                📜 History
                              </button>
                              <button
                                type="button"
                                onClick={() => handleDeleteIngredient(ing)}
                                title="Delete Ingredient"
                                style={{ border: "1px solid #fecaca", background: "#fef2f2", color: "#b91c1c", borderRadius: 8, padding: "5px 9px", fontSize: 12, fontWeight: 700, cursor: "pointer" }}
                              >
                                🗑️
                              </button>
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
        )}

        {/* TAB 2: MANAGE DISH RECIPES */}
        {activeTab === "recipes" && (
          <form onSubmit={handleSaveRecipe} style={{ ...cardStyle, display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
              <div>
                <h2 style={{ margin: 0, fontSize: 17, fontWeight: 800, color: "#211426" }}>
                  Dish Recipe Builder (Auto-Deduction)
                </h2>
                <p style={{ margin: "3px 0 0", fontSize: 13, color: "#7f7288" }}>
                  Map ingredients required per 1 serving. Every POS & AI order automatically deducts these quantities.
                </p>
              </div>

              <select
                value={selectedDishId}
                onChange={(e) => setSelectedDishId(e.target.value)}
                style={{ padding: "9px 14px", borderRadius: 10, border: "1px solid #d946ef", fontSize: 13.5, fontWeight: 700, minWidth: 240 }}
              >
                <option value="">— Select Menu Dish —</option>
                {dishes.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} (Rs. {Number(d.price || 0).toLocaleString()})
                  </option>
                ))}
              </select>
            </div>

            {loadingRecipe ? (
              <div style={{ padding: 28, textAlign: "center", color: "#8c7d96" }}>Loading recipe...</div>
            ) : !selectedDishId ? (
              <div style={{ padding: 28, textAlign: "center", color: "#8c7d96", background: "#faf7fb", borderRadius: 12 }}>
                Select a menu dish above to configure its ingredients.
              </div>
            ) : (
              <>
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  {recipeRows.map((row, idx) => {
                    const selectedIng = ingredients.find(
                      (ing) => String(ing.id) === String(row.ingredient_id)
                    );
                    const unitDisplay = selectedIng
                      ? selectedIng.unit === "l"
                        ? "L"
                        : selectedIng.unit
                      : "unit";
                    const qtyNum = Number(row.quantity_required || 0);
                    const unitCost = Number(selectedIng?.cost_per_unit || 0);
                    const estCost = selectedIng && qtyNum > 0 && unitCost > 0 ? qtyNum * unitCost : null;
                    return (
                      <div
                        key={idx}
                        style={{
                          display: "flex",
                          flexWrap: "wrap",
                          gap: 10,
                          alignItems: "center",
                          background: "#fcfafd",
                          border: "1px solid #efe4f2",
                          borderRadius: 12,
                          padding: 12,
                        }}
                      >
                        <select
                          required
                          value={row.ingredient_id}
                          onChange={(e) =>
                            setRecipeRows((prev) =>
                              prev.map((r, i) => (i === idx ? { ...r, ingredient_id: e.target.value } : r))
                            )
                          }
                          style={{ flex: 2, minWidth: 200, padding: "8px 12px", borderRadius: 9, border: "1px solid #d1d5db", fontSize: 13 }}
                        >
                          <option value="">Select ingredient...</option>
                          {ingredients.map((ing) => (
                            <option key={ing.id} value={ing.id}>
                              {ing.name} ({ing.current_stock} {ing.unit === "l" ? "L" : ing.unit} available)
                            </option>
                          ))}
                        </select>

                        <input
                          type="number"
                          min="0.01"
                          step="0.01"
                          required
                          value={row.quantity_required}
                          onChange={(e) =>
                            setRecipeRows((prev) =>
                              prev.map((r, i) => (i === idx ? { ...r, quantity_required: e.target.value } : r))
                            )
                          }
                          placeholder="Qty per 1 serving"
                          style={{ width: 130, padding: "8px 12px", borderRadius: 9, border: "1px solid #d1d5db", fontSize: 13 }}
                        />

                        {selectedIng && (
                          <span
                            style={{
                              display: "inline-flex",
                              alignItems: "center",
                              gap: 4,
                              padding: "6px 10px",
                              borderRadius: 999,
                              background: "#fdf4ff",
                              border: "1px solid #f0abfc",
                              color: "#86198f",
                              fontSize: 12,
                              fontWeight: 800,
                              whiteSpace: "nowrap",
                            }}
                          >
                            {unitDisplay}
                            {estCost !== null && (
                              <span style={{ fontWeight: 600, color: "#6b5a75" }}>
                                · Rs. {estCost.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                              </span>
                            )}
                          </span>
                        )}

                        <button
                          type="button"
                          onClick={() => setRecipeRows((prev) => prev.filter((_, i) => i !== idx))}
                          style={{ border: "1px solid #fecaca", background: "#fef2f2", color: "#b91c1c", borderRadius: 8, padding: "7px 11px", fontSize: 12.5, fontWeight: 700, cursor: "pointer" }}
                        >
                          Remove
                        </button>
                      </div>
                    );
                  })}
                </div>

                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 10 }}>
                  <button
                    type="button"
                    onClick={() =>
                      setRecipeRows((prev) => [...prev, { ingredient_id: "", quantity_required: "1" }])
                    }
                    style={{
                      border: "1px solid #f0abfc",
                      background: "#fdf2ff",
                      color: "#86198f",
                      borderRadius: 10,
                      padding: "8px 14px",
                      fontSize: 13,
                      fontWeight: 750,
                      cursor: "pointer",
                    }}
                  >
                    + Add Ingredient to Recipe
                  </button>

                  <button
                    type="submit"
                    disabled={savingRecipe}
                    style={{
                      border: "none",
                      background: "#ff77ff",
                      color: "#240729",
                      borderRadius: 10,
                      padding: "10px 22px",
                      fontSize: 13.5,
                      fontWeight: 800,
                      cursor: "pointer",
                    }}
                  >
                    {savingRecipe ? "Saving Recipe..." : "💾 Save Dish Recipe"}
                  </button>
                </div>
              </>
            )}
          </form>
        )}
      </div>

      {/* Add Ingredient Modal */}
      {showAddModal && (
        <div
          onMouseDown={(e) => e.target === e.currentTarget && setShowAddModal(false)}
          style={{ position: "fixed", inset: 0, background: "rgba(25, 12, 32, 0.48)", zIndex: 120, display: "grid", placeItems: "center", padding: 16 }}
        >
          <form
            onSubmit={handleCreateIngredient}
            style={{ width: "100%", maxWidth: 480, background: "#ffffff", borderRadius: 18, border: "1px solid #f0e6f2", padding: 22, display: "flex", flexDirection: "column", gap: 13 }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h2 style={{ margin: 0, fontSize: 18, fontWeight: 800, color: "#211426" }}>Add Raw Ingredient</h2>
              <button type="button" onClick={() => setShowAddModal(false)} style={{ border: "none", background: "transparent", fontSize: 20, cursor: "pointer" }}>
                ✕
              </button>
            </div>

            <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12.5, fontWeight: 600, color: "#4b5563" }}>
              Ingredient Name *
              <input
                required
                value={newForm.name}
                onChange={(e) => {
                  const val = e.target.value;
                  const lower = val.toLowerCase();
                  const shouldDefaultKg =
                    !unitManuallySet && WEIGHT_UNIT_KEYWORDS.some((kw) => lower.includes(kw));
                  setNewForm((p) => ({
                    ...p,
                    name: val,
                    unit: shouldDefaultKg ? "kg" : p.unit,
                  }));
                }}
                placeholder="e.g. Chicken Breast, Beef Keema, Burger Bun, Cheese"
                style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #d1d5db", fontSize: 13 }}
              />
            </label>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12.5, fontWeight: 600, color: "#4b5563" }}>
                Unit
                <select
                  value={newForm.unit}
                  onChange={(e) => {
                    setUnitManuallySet(true);
                    setNewForm((p) => ({ ...p, unit: e.target.value }));
                  }}
                  style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #d1d5db", fontSize: 13, background: "#fff" }}
                >
                  {UNITS.map((u) => (
                    <option key={u.value} value={u.value}>{u.label}</option>
                  ))}
                </select>
              </label>

              <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12.5, fontWeight: 600, color: "#4b5563" }}>
                Initial Stock ({newForm.unit === "l" ? "L" : newForm.unit})
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={newForm.current_stock}
                  onChange={(e) => setNewForm((p) => ({ ...p, current_stock: e.target.value }))}
                  style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #d1d5db", fontSize: 13 }}
                />
              </label>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12.5, fontWeight: 600, color: "#4b5563" }}>
                Low-Stock Threshold ({newForm.unit === "l" ? "L" : newForm.unit})
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={newForm.low_stock_threshold}
                  onChange={(e) => setNewForm((p) => ({ ...p, low_stock_threshold: e.target.value }))}
                  style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #d1d5db", fontSize: 13 }}
                />
              </label>

              <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12.5, fontWeight: 600, color: "#4b5563" }}>
                Cost per {newForm.unit === "l" ? "L" : newForm.unit} (Rs.)
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={newForm.cost_per_unit}
                  onChange={(e) => setNewForm((p) => ({ ...p, cost_per_unit: e.target.value }))}
                  style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #d1d5db", fontSize: 13 }}
                />
              </label>
            </div>

            <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12.5, fontWeight: 600, color: "#4b5563" }}>
              Supplier (Optional)
              <select
                value={newForm.supplier_id}
                onChange={(e) => {
                  const sid = e.target.value;
                  const found = suppliers.find((s) => String(s.id) === sid);
                  setNewForm((p) => ({
                    ...p,
                    supplier_id: sid,
                    supplier_name: found ? found.name : p.supplier_name,
                  }));
                }}
                style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #d1d5db", fontSize: 13, background: "#fff" }}
              >
                <option value="">— Select Saved Supplier —</option>
                {suppliers.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} ({s.category})
                  </option>
                ))}
              </select>
            </label>

            {Number(newForm.current_stock) > 0 && Number(newForm.cost_per_unit) > 0 && (
              <label
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "9px 12px",
                  borderRadius: 10,
                  background: "#fdf4ff",
                  border: "1px solid #f0abfc",
                  fontSize: 12.5,
                  fontWeight: 700,
                  color: "#86198f",
                  cursor: "pointer",
                }}
              >
                <input
                  type="checkbox"
                  checked={Boolean(newForm.log_as_expense)}
                  onChange={(e) => setNewForm((p) => ({ ...p, log_as_expense: e.target.checked }))}
                />
                Log initial purchase (Rs.{" "}
                {(Number(newForm.current_stock) * Number(newForm.cost_per_unit)).toLocaleString(
                  undefined,
                  { maximumFractionDigits: 0 }
                )}
                ) as Operating Expense
              </label>
            )}

            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 4 }}>
              <button type="button" onClick={() => setShowAddModal(false)} style={{ border: "1px solid #d1d5db", background: "#ffffff", color: "#374151", borderRadius: 10, padding: "9px 15px", fontSize: 13, fontWeight: 600, cursor: "pointer" }}>
                Cancel
              </button>
              <button type="submit" disabled={saving} style={{ border: "none", background: "#ff77ff", color: "#240729", borderRadius: 10, padding: "9px 18px", fontSize: 13.5, fontWeight: 800, cursor: "pointer" }}>
                {saving ? "Saving..." : "Add Ingredient"}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Restock / Waste / Adjust Modal */}
      {adjustModal && (
        <div
          onMouseDown={(e) => e.target === e.currentTarget && setAdjustModal(null)}
          style={{ position: "fixed", inset: 0, background: "rgba(25, 12, 32, 0.48)", zIndex: 120, display: "grid", placeItems: "center", padding: 16 }}
        >
          <form
            onSubmit={handleAdjustStock}
            style={{ width: "100%", maxWidth: 420, background: "#ffffff", borderRadius: 18, border: "1px solid #f0e6f2", padding: 22, display: "flex", flexDirection: "column", gap: 13 }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <h2 style={{ margin: 0, fontSize: 17.5, fontWeight: 800, color: "#211426" }}>
                  {adjustModal.mode === "restock" ? "+ Restock Ingredient" : "- Log Waste / Adjustment"}
                </h2>
                <div style={{ fontSize: 12.5, color: "#7f7288", marginTop: 2 }}>
                  {adjustModal.ingredient.name} (Current: {adjustModal.ingredient.current_stock} {adjustModal.ingredient.unit})
                </div>
              </div>
              <button type="button" onClick={() => setAdjustModal(null)} style={{ border: "none", background: "transparent", fontSize: 20, cursor: "pointer" }}>
                ✕
              </button>
            </div>

            <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12.5, fontWeight: 600, color: "#4b5563" }}>
              Movement Type
              <select
                value={adjustModal.mode}
                onChange={(e) => setAdjustModal((p) => ({ ...p, mode: e.target.value }))}
                style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #d1d5db", fontSize: 13 }}
              >
                <option value="restock">Restock (+ Add)</option>
                <option value="waste">Waste / Spoilage (- Deduct)</option>
                <option value="manual_adjustment">Manual Adjustment (+/-)</option>
              </select>
            </label>

            <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12.5, fontWeight: 600, color: "#4b5563" }}>
              Quantity ({adjustModal.ingredient.unit === "l" ? "L" : adjustModal.ingredient.unit}) *
              <input
                type="number"
                step="0.01"
                required
                value={adjustQty}
                onChange={(e) => setAdjustQty(e.target.value)}
                style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #d1d5db", fontSize: 13 }}
              />
            </label>

            {adjustModal.mode === "restock" && (
              <>
                <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12.5, fontWeight: 600, color: "#4b5563" }}>
                  Supplier (Optional)
                  <select
                    value={adjustSupplierId}
                    onChange={(e) => setAdjustSupplierId(e.target.value)}
                    style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #d1d5db", fontSize: 13, background: "#fff" }}
                  >
                    <option value="">— Use Default / None —</option>
                    {suppliers.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name} ({s.category})
                      </option>
                    ))}
                  </select>
                </label>
                <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12.5, fontWeight: 600, color: "#4b5563" }}>
                  Total Purchase Cost (Rs.) — Optional
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={adjustPurchaseCost}
                    onChange={(e) => setAdjustPurchaseCost(e.target.value)}
                    placeholder="e.g. 4500"
                    style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #d1d5db", fontSize: 13 }}
                  />
                </label>
                <label style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 12.5, fontWeight: 600, color: "#4b5563", cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={adjustLogExpense}
                    onChange={(e) => setAdjustLogExpense(e.target.checked)}
                  />
                  Auto-log purchase cost as Operating Expense
                </label>
              </>
            )}

            <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12.5, fontWeight: 600, color: "#4b5563" }}>
              Reason / Note
              <input
                value={adjustReason}
                onChange={(e) => setAdjustReason(e.target.value)}
                placeholder="e.g. Morning delivery, spoiled batch, physical count..."
                style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #d1d5db", fontSize: 13 }}
              />
            </label>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 4 }}>
              <button type="button" onClick={() => setAdjustModal(null)} style={{ border: "1px solid #d1d5db", background: "#ffffff", color: "#374151", borderRadius: 10, padding: "9px 15px", fontSize: 13, fontWeight: 600, cursor: "pointer" }}>
                Cancel
              </button>
              <button type="submit" disabled={saving} style={{ border: "none", background: "#ff77ff", color: "#240729", borderRadius: 10, padding: "9px 18px", fontSize: 13.5, fontWeight: 800, cursor: "pointer" }}>
                {saving ? "Updating..." : "Apply Adjustment"}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Stock Movement History Modal */}
      {historyModal && (
        <div
          onMouseDown={(e) => e.target === e.currentTarget && setHistoryModal(null)}
          style={{ position: "fixed", inset: 0, background: "rgba(25, 12, 32, 0.48)", zIndex: 120, display: "grid", placeItems: "center", padding: 16 }}
        >
          <div
            style={{ width: "100%", maxWidth: 580, maxHeight: "82vh", overflowY: "auto", background: "#ffffff", borderRadius: 18, border: "1px solid #f0e6f2", padding: 22, display: "flex", flexDirection: "column", gap: 14 }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <h2 style={{ margin: 0, fontSize: 18, fontWeight: 800, color: "#211426" }}>
                  Stock History — {historyModal.ingredient.name}
                </h2>
                <div style={{ fontSize: 12.5, color: "#7f7288" }}>
                  Current balance: <strong>{historyModal.ingredient.current_stock} {historyModal.ingredient.unit}</strong>
                </div>
              </div>
              <button type="button" onClick={() => setHistoryModal(null)} style={{ border: "none", background: "transparent", fontSize: 20, cursor: "pointer" }}>
                ✕
              </button>
            </div>

            {historyModal.loading ? (
              <div style={{ padding: 28, textAlign: "center", color: "#8c7d96" }}>Loading movements...</div>
            ) : historyModal.movements.length === 0 ? (
              <div style={{ padding: 28, textAlign: "center", color: "#8c7d96", background: "#faf7fb", borderRadius: 12 }}>
                No stock movements logged yet.
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {historyModal.movements.map((m) => {
                  const isPositive = Number(m.quantity_delta) > 0;
                  return (
                    <div
                      key={m.id}
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        gap: 12,
                        padding: "10px 12px",
                        borderRadius: 10,
                        border: "1px solid #f0e6f2",
                        background: "#fcfafd",
                      }}
                    >
                      <div>
                        <div style={{ fontSize: 13, fontWeight: 750, color: "#211426" }}>
                          {m.movement_label}
                        </div>
                        <div style={{ fontSize: 12, color: "#6b5a75", marginTop: 2 }}>
                          {m.reason || "—"}
                        </div>
                        <div style={{ fontSize: 11, color: "#9b8ca6", marginTop: 2 }}>
                          {m.created_at ? new Date(m.created_at).toLocaleString() : ""}
                        </div>
                      </div>
                      <div style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                        <div style={{ fontSize: 14, fontWeight: 800, color: isPositive ? "#047857" : "#b91c1c" }}>
                          {isPositive ? `+${m.quantity_delta}` : m.quantity_delta} {m.unit}
                        </div>
                        <div style={{ fontSize: 11.5, color: "#7f7288" }}>
                          After: {m.stock_after} {m.unit}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Add / Edit Supplier Modal */}
      {showSupplierModal && (
        <div
          onMouseDown={(e) => e.target === e.currentTarget && setShowSupplierModal(false)}
          style={{ position: "fixed", inset: 0, background: "rgba(25, 12, 32, 0.48)", zIndex: 130, display: "grid", placeItems: "center", padding: 16 }}
        >
          <form
            onSubmit={handleSaveSupplier}
            style={{ width: "100%", maxWidth: 460, background: "#ffffff", borderRadius: 18, border: "1px solid #f0e6f2", padding: 22, display: "flex", flexDirection: "column", gap: 12 }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h2 style={{ margin: 0, fontSize: 17.5, fontWeight: 800, color: "#211426" }}>
                {editingSupplier ? "Edit Supplier" : "🚚 Add Supplier"}
              </h2>
              <button type="button" onClick={() => setShowSupplierModal(false)} style={{ border: "none", background: "transparent", fontSize: 20, cursor: "pointer" }}>
                ✕
              </button>
            </div>
            <input
              required
              placeholder="Supplier Name * (e.g., Fresh Poultry Farms)"
              value={supplierForm.name}
              onChange={(e) => setSupplierForm((p) => ({ ...p, name: e.target.value }))}
              style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #d1d5db", fontSize: 13 }}
            />
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <input
                placeholder="Contact Person"
                value={supplierForm.contact_person}
                onChange={(e) => setSupplierForm((p) => ({ ...p, contact_person: e.target.value }))}
                style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #d1d5db", fontSize: 13 }}
              />
              <input
                placeholder="Phone (e.g. 03001234567)"
                value={supplierForm.phone}
                onChange={(e) => setSupplierForm((p) => ({ ...p, phone: e.target.value }))}
                style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #d1d5db", fontSize: 13 }}
              />
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <select
                value={supplierForm.category}
                onChange={(e) => setSupplierForm((p) => ({ ...p, category: e.target.value }))}
                style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #d1d5db", fontSize: 13, background: "#fff" }}
              >
                {["Meat", "Produce", "Dairy", "Packaging", "Beverages", "Spices & Dry Goods", "General"].map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
              <input
                type="email"
                placeholder="Email (optional)"
                value={supplierForm.email}
                onChange={(e) => setSupplierForm((p) => ({ ...p, email: e.target.value }))}
                style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #d1d5db", fontSize: 13 }}
              />
            </div>
            <input
              placeholder="Address (optional)"
              value={supplierForm.address}
              onChange={(e) => setSupplierForm((p) => ({ ...p, address: e.target.value }))}
              style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #d1d5db", fontSize: 13 }}
            />
            <textarea
              rows={2}
              placeholder="Notes (delivery days, payment terms, etc.)"
              value={supplierForm.notes}
              onChange={(e) => setSupplierForm((p) => ({ ...p, notes: e.target.value }))}
              style={{ padding: "9px 12px", borderRadius: 9, border: "1px solid #d1d5db", fontSize: 13 }}
            />
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 4 }}>
              <button type="button" onClick={() => setShowSupplierModal(false)} style={{ border: "1px solid #d1d5db", background: "#fff", color: "#374151", borderRadius: 10, padding: "9px 15px", fontSize: 13, fontWeight: 600, cursor: "pointer" }}>
                Cancel
              </button>
              <button type="submit" disabled={saving} style={{ border: "none", background: "#ff77ff", color: "#240729", borderRadius: 10, padding: "9px 18px", fontSize: 13.5, fontWeight: 800, cursor: "pointer" }}>
                {saving ? "Saving..." : editingSupplier ? "Update Supplier" : "Save Supplier"}
              </button>
            </div>
          </form>
        </div>
      )}
    </Layout>
  );
}
