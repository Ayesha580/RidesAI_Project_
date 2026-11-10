

const ICONS = {
  pos: "💳",
  customers: "🙋",
  inventory: "📊",
  suppliers: "🏭",
  expenses: "💸",
  reports: "📈",
  attendance: "🗓️",

  orders: "📦",
  menu: "🍽️",
  tables: "🪑",
  kitchen_display: "👨‍🍳",
  reservations: "📅",

  deliveries: "🚚",
  my_deliveries: "🏍️",

  medicines: "💊",
  prescriptions: "📝",
  expiry_tracking: "⏳",
  controlled_drugs: "🔒",

  products: "🛒",
  stock_alerts: "🔔",
  returns: "↩️",

  appointments: "🩺",
  patients: "🧑‍⚕️",
  lab_tests: "🧪",

  // ---- legacy ----
  staff_management: "👥",
};

const LABELS = {
  // common
  pos: "Point of Sale",
  reports: "Reports",
  attendance: "Attendance",

  // restaurant
  orders: "Orders",
  menu: "Menu",
  tables: "Tables",
  kitchen_display: "Kitchen Display",
  reservations: "Reservations",

  // delivery
  deliveries: "Deliveries (all)",
  my_deliveries: "My Deliveries (Rider)",

  // pharmacy
  medicines: "Medicine Catalog",
  prescriptions: "Prescriptions",
  expiry_tracking: "Medicine Expiry",
  controlled_drugs: "Controlled Drugs Register",

  // grocery / retail
  products: "Products",
  stock_alerts: "Low Stock Alerts",
  returns: "Returns & Refunds",

  // clinic
  appointments: "Appointments",
  patients: "Patients",
  lab_tests: "Lab Tests",

  // legacy
  staff_management: "Staff Management",
};

export const moduleIcon = (key) => ICONS[key] || "🧩";

export const moduleLabel = (key) => {
  if (LABELS[key]) return LABELS[key];
  const text = key.replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
};