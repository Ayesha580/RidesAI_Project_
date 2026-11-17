
import React, { useEffect, useState } from "react";
import axios from "axios";
import {
  FiPlus, FiSearch, FiEdit2, FiTrash2, FiPackage,
  FiUpload, FiDownload, FiX, FiTag, FiLayers,
  FiTrendingUp, FiBox, FiMinus, FiRefreshCw
} from "react-icons/fi";
import "./Catalog.css";

const API = "/api/companies/catalog";
const getToken = () => localStorage.getItem("access") || localStorage.getItem("access_token") || localStorage.getItem("accessToken");

const api = axios.create({ baseURL: API });
api.interceptors.request.use(config => {
  const token = getToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

const businessConfig = {
  restaurant: { title: "Menu", singular: "Dish", icon: "🍽", type: "product" },
  pharmacy: { title: "Medicines", singular: "Medicine", icon: "💊", type: "product" },
  grocery: { title: "Products", singular: "Product", icon: "🛒", type: "product" },
  retail: { title: "Products", singular: "Product", icon: "🛍", type: "product" },
  clinic: { title: "Services", singular: "Service", icon: "🏥", type: "service" },
  general: { title: "Products", singular: "Product", icon: "📦", type: "product" }
};

const getBusinessKey = value => {
  const text = (value || "").toLowerCase();
  if (/restaurant|cafe|café|food|bakery|hotel/.test(text)) return "restaurant";
  if (/pharmacy|pharma|medical|chemist|medicine|drug/.test(text)) return "pharmacy";
  if (/grocery|mart|supermarket|kiryana|general store/.test(text)) return "grocery";
  if (/clinic|hospital|doctor|dental|lab/.test(text)) return "clinic";
  if (/retail|shop|boutique|clothing|electronics/.test(text)) return "retail";
  return "general";
};

const emptyForm = {
  name: "",
  item_type: "product",
  category: "",
  description: "",
  sku: "",
  barcode: "",
  brand: "",
  price: "",
  cost_price: "",
  unit: "",
  is_available: true,
  attributes: {},
  inventory: { is_unlimited: true, quantity: 0, low_stock_threshold: 5 },
  variants: [],
  batches: []
};

export default function Catalog({ moduleKey }) {
    const [business, setBusiness] = useState("general");
  const [items, setItems] = useState([]);
  const [categories, setCategories] = useState([]);
  const [deals, setDeals] = useState([]);
  const [activeTab, setActiveTab] = useState("items");
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [modal, setModal] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [categoryName, setCategoryName] = useState("");
  const [showCategory, setShowCategory] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [stockItem, setStockItem] = useState(null);
  const [stockQuantity, setStockQuantity] = useState("");
  const [stockNote, setStockNote] = useState("");
  const [stockAction, setStockAction] = useState("add");
  const [attributeKey, setAttributeKey] = useState("");
  const [attributeValue, setAttributeValue] = useState("");
  const moduleConfig = {
  menu: { title: "Menu", singular: "Dish", type: "product" },
  products: { title: "Products", singular: "Product", type: "product" },
  medicines: { title: "Medicines", singular: "Medicine", type: "product" },
  services: { title: "Services", singular: "Service", type: "service" },
};

   const config = moduleConfig[moduleKey] || businessConfig[business] || businessConfig.general;

  useEffect(() => {
    const user = JSON.parse(localStorage.getItem("user") || "{}");
    const type = user.company?.business_type || user.business_type || "";
    setBusiness(getBusinessKey(type));
  }, []);

  useEffect(() => {
    loadData();
  }, [business]);

  const loadData = async () => {
  setLoading(true);
  setError("");
  try {
    const [itemsRes, categoriesRes, dealsRes] = await Promise.all([
      api.get("/items/"),
      api.get("/categories/"),
      api.get("/deals/")
    ]);

    const getList = data => {
      if (Array.isArray(data)) return data;
      if (Array.isArray(data?.results)) return data.results;
      return [];
    };

    setItems(getList(itemsRes.data));
    setCategories(getList(categoriesRes.data));
    setDeals(getList(dealsRes.data));
  } catch (err) {
    console.log("Catalog API Error:", err.response?.data || err);
    setError(err.response?.data?.detail || "Unable to load catalog data.");
    setItems([]);
    setCategories([]);
    setDeals([]);
  } finally {
    setLoading(false);
  }
};

  const updateForm = (key, value) => {
    setForm(prev => ({ ...prev, [key]: value }));
  };

  const openCreate = () => {
    setEditing(null);
    setForm({ ...emptyForm, item_type: config.type });
    setError("");
    setModal(true);
  };

  const openEdit = item => {
    setEditing(item.id);
    setForm({
      ...emptyForm,
      ...item,
      category: item.category || "",
      inventory: item.inventory || emptyForm.inventory,
      variants: item.variants || [],
      batches: item.batches || [],
      attributes: item.attributes || {}
    });
    setError("");
    setModal(true);
  };

  const saveItem = async e => {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      const payload = {
        ...form,
        category: form.category || null,
        price: form.price || "0",
        cost_price: form.cost_price || "0",
        inventory: {
          ...form.inventory,
          quantity: form.inventory.is_unlimited ? 0 : Number(form.inventory.quantity || 0)
        }
      };
      if (editing) {
        await api.patch(`/items/${editing}/`, payload);
      } else {
        await api.post("/items/", payload);
      }
      setModal(false);
      loadData();
    } catch (err) {
      setError(JSON.stringify(err.response?.data || "Unable to save item."));
    } finally {
      setSaving(false);
    }
  };

  const deleteItem = async id => {
    if (!window.confirm("Are you sure you want to delete this item?")) return;
    try {
      await api.delete(`/items/${id}/`);
      loadData();
    } catch (err) {
      alert(err.response?.data?.detail || "Unable to delete item.");
    }
  };

  const saveCategory = async e => {
    e.preventDefault();
    if (!categoryName.trim()) return;
    try {
      await api.post("/categories/", { name: categoryName });
      setCategoryName("");
      setShowCategory(false);
      loadData();
    } catch (err) {
      alert(JSON.stringify(err.response?.data || "Unable to create category."));
    }
  };

  const deleteCategory = async id => {
    if (!window.confirm("Delete this category?")) return;
    try {
      await api.delete(`/categories/${id}/`);
      loadData();
    } catch (err) {
      alert("Unable to delete category.");
    }
  };

  const openStock = (item, action = "add") => {
    setStockItem(item);
    setStockAction(action);
    setStockQuantity("");
    setStockNote("");
  };

  const updateStock = async e => {
    e.preventDefault();
    try {
      await api.post(`/items/${stockItem.id}/${stockAction}_stock/`, {
        quantity: stockQuantity,
        note: stockNote
      });
      setStockItem(null);
      loadData();
    } catch (err) {
      alert(err.response?.data?.error || "Unable to update stock.");
    }
  };

  const addAttribute = () => {
    if (!attributeKey.trim()) return;
    updateForm("attributes", {
      ...form.attributes,
      [attributeKey.trim()]: attributeValue
    });
    setAttributeKey("");
    setAttributeValue("");
  };

  const removeAttribute = key => {
    const updated = { ...form.attributes };
    delete updated[key];
    updateForm("attributes", updated);
  };

  const addVariant = () => {
    updateForm("variants", [...form.variants, { name: "", sku: "", price: "", attributes: {}, is_available: true }]);
  };

  const updateVariant = (index, key, value) => {
    const variants = [...form.variants];
    variants[index] = { ...variants[index], [key]: value };
    updateForm("variants", variants);
  };

  const importCSV = async e => {
    const file = e.target.files[0];
    if (!file) return;
    const data = new FormData();
    data.append("file", file);
    try {
      await api.post("/import/", data);
      alert("CSV imported successfully.");
      loadData();
    } catch (err) {
      alert(JSON.stringify(err.response?.data || "Import failed."));
    }
    e.target.value = "";
  };

  const exportCSV = async () => {
    try {
      const response = await api.get("/export/", { responseType: "blob" });
      const url = URL.createObjectURL(response.data);
      const link = document.createElement("a");
      link.href = url;
      link.download = "catalog_items.csv";
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert("Export failed.");
    }
  };

    const filteredItems = (Array.isArray(items) ? items : []).filter(item => {
    const matchesSearch = `${item.name} ${item.sku} ${item.barcode} ${item.brand}`.toLowerCase().includes(search.toLowerCase());
    const matchesCategory = !categoryFilter || String(item.category) === categoryFilter;
    return matchesSearch && matchesCategory;
  });

    const safeItems = Array.isArray(items) ? items : [];
    const limitedStock = safeItems.filter(item => item.inventory && !item.inventory.is_unlimited);
    const lowStock = limitedStock.filter(item => Number(item.inventory.quantity) <= Number(item.inventory.low_stock_threshold));
    const availableItems = safeItems.filter(item => item.is_available).length;

  return (
    <div className="catalog-page">
      <div className="catalog-header">
        <div>
          <div className="catalog-eyebrow">BUSINESS MANAGEMENT</div>
          <h1>{config.title}</h1>
          <p>Manage your {config.title.toLowerCase()}, categories, stock and offers.</p>
        </div>
        <div className="catalog-header-actions">
          <button className="catalog-btn secondary" onClick={exportCSV}><FiDownload /> Export CSV</button>
          <label className="catalog-btn secondary">
            <FiUpload /> Import CSV
            <input type="file" accept=".csv" hidden onChange={importCSV} />
          </label>
          <button className="catalog-btn primary" onClick={openCreate}><FiPlus /> Add {config.singular}</button>
        </div>
      </div>

      <div className="catalog-stats">
        <div className="catalog-stat">
          <span className="stat-icon purple"><FiPackage /></span>
          <div><small>Total Items</small><strong>{items.length}</strong></div>
        </div>
        <div className="catalog-stat">
          <span className="stat-icon green"><FiTrendingUp /></span>
          <div><small>Available</small><strong>{availableItems}</strong></div>
        </div>
        <div className="catalog-stat">
          <span className="stat-icon orange"><FiBox /></span>
          <div><small>Limited Stock</small><strong>{limitedStock.length}</strong></div>
        </div>
        <div className="catalog-stat">
          <span className="stat-icon red"><FiLayers /></span>
          <div><small>Low Stock</small><strong>{lowStock.length}</strong></div>
        </div>
      </div>

      <div className="catalog-tabs">
        <button className={activeTab === "items" ? "active" : ""} onClick={() => setActiveTab("items")}>{config.title}</button>
        <button className={activeTab === "categories" ? "active" : ""} onClick={() => setActiveTab("categories")}>Categories</button>
        <button className={activeTab === "deals" ? "active" : ""} onClick={() => setActiveTab("deals")}>Deals & Offers</button>
      </div>

      {activeTab === "items" && <>
        <div className="catalog-toolbar">
          <div className="catalog-search"><FiSearch /><input value={search} onChange={e => setSearch(e.target.value)} placeholder={`Search ${config.title.toLowerCase()}...`} /></div>
          <select value={categoryFilter} onChange={e => setCategoryFilter(e.target.value)}>
            <option value="">All Categories</option>
            {categories.map(category => <option key={category.id} value={category.id}>{category.name}</option>)}
          </select>
          <button className="catalog-btn secondary" onClick={loadData}><FiRefreshCw /> Refresh</button>
        </div>

        {loading ? <div className="catalog-empty">Loading catalog...</div> : filteredItems.length === 0 ? (
          <div className="catalog-empty"><FiPackage /><h3>No {config.title.toLowerCase()} found</h3><p>Add your first {config.singular.toLowerCase()} to get started.</p><button className="catalog-btn primary" onClick={openCreate}><FiPlus /> Add {config.singular}</button></div>
        ) : (
          <div className="catalog-table-wrap">
            <table className="catalog-table">
              <thead><tr><th>Item</th><th>Category</th><th>SKU / Barcode</th><th>Price</th><th>Stock</th><th>Status</th><th>Actions</th></tr></thead>
              <tbody>
                {filteredItems.map(item => {
                  const stock = item.inventory;
                  return <tr key={item.id}>
                    <td><div className="catalog-item-name"><div className="catalog-item-image">{item.image ? <img src={item.image} alt="" /> : <FiPackage />}</div><div><strong>{item.name}</strong><small>{item.brand || item.description || item.item_type}</small></div></div></td>
                    <td>{item.category_name || "Uncategorized"}</td>
                    <td><span>{item.sku || "—"}</span><small className="table-sub">{item.barcode || ""}</small></td>
                    <td className="price-cell">{Number(item.price).toLocaleString()}</td>
                    <td>
                      {stock?.is_unlimited ? <span className="stock-unlimited">Unlimited</span> : <div className="stock-cell"><strong>{stock?.quantity ?? 0} {item.unit}</strong><div className="stock-actions"><button title="Add stock" onClick={() => openStock(item, "add")}><FiPlus /></button><button title="Remove stock" onClick={() => openStock(item, "remove")}><FiMinus /></button></div></div>}
                    </td>
                    <td><span className={`catalog-status ${item.is_available ? "available" : "unavailable"}`}>{item.is_available ? "Available" : "Unavailable"}</span></td>
                    <td><div className="catalog-row-actions"><button onClick={() => openEdit(item)} title="Edit"><FiEdit2 /></button><button onClick={() => deleteItem(item.id)} title="Delete"><FiTrash2 /></button></div></td>
                  </tr>;
                })}
              </tbody>
            </table>
          </div>
        )}
      </>}

      {activeTab === "categories" && <div className="catalog-section">
        <div className="catalog-section-heading"><div><h2>Categories</h2><p>Organize your catalog into categories.</p></div><button className="catalog-btn primary" onClick={() => setShowCategory(true)}><FiPlus /> Add Category</button></div>
        <div className="catalog-category-grid">
          {categories.map(category => <div className="catalog-category-card" key={category.id}><span><FiTag /></span><div><strong>{category.name}</strong><small>{category.description || "Catalog category"}</small></div><button onClick={() => deleteCategory(category.id)}><FiTrash2 /></button></div>)}
          {!categories.length && <div className="catalog-empty">No categories created yet.</div>}
        </div>
      </div>}

      {activeTab === "deals" && <div className="catalog-section">
        <div className="catalog-section-heading"><div><h2>Deals & Offers</h2><p>Create bundles, discounts and business packages.</p></div><button className="catalog-btn primary" onClick={() => alert("Deal creation form will be connected next.")}><FiPlus /> Add Deal</button></div>
        <div className="catalog-deal-grid">
          {deals.map(deal => <div className="catalog-deal-card" key={deal.id}><span><FiTag /></span><h3>{deal.name}</h3><p>{deal.description}</p><strong>{Number(deal.price).toLocaleString()}</strong><small>{deal.is_active ? "Active" : "Inactive"}</small></div>)}
          {!deals.length && <div className="catalog-empty">No deals or offers created yet.</div>}
        </div>
      </div>}

      {modal && <div className="catalog-overlay" onMouseDown={e => e.target === e.currentTarget && setModal(false)}>
        <form className="catalog-modal" onSubmit={saveItem}>
          <div className="catalog-modal-header"><div><h2>{editing ? "Edit" : "Add"} {config.singular}</h2><p>Enter the item information below.</p></div><button type="button" onClick={() => setModal(false)}><FiX /></button></div>
          {error && <div className="catalog-error">{error}</div>}
          <div className="catalog-form-grid">
            <label className="full">Name *<input required value={form.name} onChange={e => updateForm("name", e.target.value)} placeholder="Enter item name" /></label>
            <label>Category<select value={form.category} onChange={e => updateForm("category", e.target.value)}><option value="">Select category</option>{categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
            <label>Item Type<select value={form.item_type} onChange={e => updateForm("item_type", e.target.value)}><option value="product">Product</option><option value="service">Service</option></select></label>
            <label>Price *<input required type="number" min="0" step="0.01" value={form.price} onChange={e => updateForm("price", e.target.value)} /></label>
            <label>Cost Price<input type="number" min="0" step="0.01" value={form.cost_price} onChange={e => updateForm("cost_price", e.target.value)} /></label>
            <label>SKU<input value={form.sku} onChange={e => updateForm("sku", e.target.value)} /></label>
            <label>Barcode<input value={form.barcode} onChange={e => updateForm("barcode", e.target.value)} /></label>
            <label>Brand<input value={form.brand} onChange={e => updateForm("brand", e.target.value)} /></label>
            <label>Unit<input value={form.unit} onChange={e => updateForm("unit", e.target.value)} placeholder="piece, kg, pack, hour..." /></label>
            <label className="full">Description<textarea value={form.description} onChange={e => updateForm("description", e.target.value)} rows="3" /></label>
          </div>

          <div className="catalog-form-section"><h3>Custom Attributes</h3><p>Add business-specific information such as size, color, strength, ingredients or duration.</p>
            <div className="catalog-attribute-add"><input placeholder="Attribute name" value={attributeKey} onChange={e => setAttributeKey(e.target.value)} /><input placeholder="Value" value={attributeValue} onChange={e => setAttributeValue(e.target.value)} /><button type="button" onClick={addAttribute}><FiPlus /></button></div>
            {Object.entries(form.attributes).map(([key, value]) => <div className="catalog-attribute-row" key={key}><span>{key}: <strong>{String(value)}</strong></span><button type="button" onClick={() => removeAttribute(key)}><FiX /></button></div>)}
          </div>

          <div className="catalog-form-section"><div className="catalog-section-heading"><div><h3>Variants</h3><p>Sizes, colors, strengths or other options.</p></div><button type="button" className="catalog-btn secondary" onClick={addVariant}><FiPlus /> Add Variant</button></div>
            {form.variants.map((variant, index) => <div className="catalog-variant-row" key={index}><input placeholder="Variant name (Large / Red / 500mg)" value={variant.name} onChange={e => updateVariant(index, "name", e.target.value)} /><input placeholder="SKU" value={variant.sku} onChange={e => updateVariant(index, "sku", e.target.value)} /><input type="number" min="0" placeholder="Price" value={variant.price ?? ""} onChange={e => updateVariant(index, "price", e.target.value)} /><button type="button" onClick={() => updateForm("variants", form.variants.filter((_, i) => i !== index))}><FiTrash2 /></button></div>)}
          </div>

          {form.item_type === "product" && <div className="catalog-form-section"><h3>Inventory Management</h3><label className="catalog-check"><input type="checkbox" checked={form.inventory.is_unlimited} onChange={e => updateForm("inventory", { ...form.inventory, is_unlimited: e.target.checked })} /> Unlimited stock</label>
            {!form.inventory.is_unlimited && <div className="catalog-form-grid"><label>Quantity<input type="number" min="0" step="0.001" value={form.inventory.quantity} onChange={e => updateForm("inventory", { ...form.inventory, quantity: e.target.value })} /></label><label>Low Stock Alert<input type="number" min="0" step="0.001" value={form.inventory.low_stock_threshold} onChange={e => updateForm("inventory", { ...form.inventory, low_stock_threshold: e.target.value })} /></label></div>}
          </div>}

          <label className="catalog-check"><input type="checkbox" checked={form.is_available} onChange={e => updateForm("is_available", e.target.checked)} /> Available for sale / booking</label>
          <div className="catalog-modal-actions"><button type="button" className="catalog-btn secondary" onClick={() => setModal(false)}>Cancel</button><button className="catalog-btn primary" disabled={saving}>{saving ? "Saving..." : editing ? "Update Item" : "Create Item"}</button></div>
        </form>
      </div>}

      {showCategory && <div className="catalog-overlay"><form className="catalog-small-modal" onSubmit={saveCategory}><div className="catalog-modal-header"><h2>Add Category</h2><button type="button" onClick={() => setShowCategory(false)}><FiX /></button></div><input required autoFocus placeholder="Category name" value={categoryName} onChange={e => setCategoryName(e.target.value)} /><div className="catalog-modal-actions"><button type="button" className="catalog-btn secondary" onClick={() => setShowCategory(false)}>Cancel</button><button className="catalog-btn primary">Save Category</button></div></form></div>}

      {stockItem && <div className="catalog-overlay"><form className="catalog-small-modal" onSubmit={updateStock}><div className="catalog-modal-header"><div><h2>{stockAction === "add" ? "Add Stock" : "Remove Stock"}</h2><p>{stockItem.name}</p></div><button type="button" onClick={() => setStockItem(null)}><FiX /></button></div><label>Quantity<input required type="number" min="0.001" step="0.001" value={stockQuantity} onChange={e => setStockQuantity(e.target.value)} /></label><label>Note<input value={stockNote} onChange={e => setStockNote(e.target.value)} placeholder="Optional note" /></label><div className="catalog-modal-actions"><button type="button" className="catalog-btn secondary" onClick={() => setStockItem(null)}>Cancel</button><button className="catalog-btn primary">{stockAction === "add" ? "Add Stock" : "Remove Stock"}</button></div></form></div>}
    </div>
  );
}
