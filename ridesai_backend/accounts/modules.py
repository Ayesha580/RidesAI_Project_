

MODULES = {
    "services": "Services Catalog",
    # ---- common ----
    "pos": "Point of Sale",
    "reports": "Reports",
    "attendance": "Attendance",
    # ---- shared business tools ----
    "customers": "Customers",
    "inventory": "Inventory / Stock",
    "suppliers": "Suppliers",
    "expenses": "Expenses",
    # ---- orders (AI agent ke orders) ----
    "orders": "Orders",
    # ---- restaurant ----
    "menu": "Menu",
    "tables": "Tables",
    "kitchen_display": "Kitchen Display",
    "reservations": "Reservations",
    # ---- delivery ----
    "deliveries": "Deliveries (all)",
    "my_deliveries": "My Deliveries (Rider)",
    # ---- pharmacy ----
    "medicines": "Medicine Catalog",
    "prescriptions": "Prescriptions",
    "expiry_tracking": "Medicine Expiry",
    "controlled_drugs": "Controlled Drugs Register",
    # ---- grocery / retail ----
    "products": "Products",
    "stock_alerts": "Low Stock Alerts",
    "returns": "Returns & Refunds",
    "fulfillment": "Fulfillment",
    # ---- clinic & hospital ----
    "departments": "Departments & Wards",
    "appointments": "Appointments",
    "doctors": "Doctors Directory",
    "patients": "Patients",
    "lab_tests": "Lab Tests",
}

COMMON = ["pos", "reports", "attendance"]

BUSINESS_TYPES = {
    "restaurant": {
        "label": "Restaurant",
        "keywords": ["restaurant", "cafe", "café", "hotel", "food", "bakery", "fast food"],
        "modules": ["orders", "menu", "tables", "kitchen_display", "reservations",
                    "deliveries", "my_deliveries",
                    "customers", "inventory", "suppliers", "expenses"],
        "owner_menu": ["orders", "menu", "tables", "reservations", "deliveries",
                       "customers", "inventory", "reports"],
        "templates": {
            "Manager": ["orders", "pos", "menu", "inventory", "reports", "attendance",
                        "tables", "expenses"],
            "Kitchen Staff": ["kitchen_display", "orders"],
            "Waiter": ["orders", "tables", "pos"],
            "Rider": ["my_deliveries"],
        },
    },
    "pharmacy": {
        "label": "Pharmacy",
        "keywords": ["pharmacy", "pharma", "medical", "chemist", "medicine", "drug"],
        "modules": ["orders", "medicines", "prescriptions", "expiry_tracking",
                    "controlled_drugs", "returns", "deliveries", "my_deliveries",
                    "customers", "inventory", "suppliers", "expenses"],
        "owner_menu": ["orders", "medicines", "prescriptions", "expiry_tracking",
                       "controlled_drugs", "customers", "deliveries", "inventory", "reports"],
        "templates": {
            "Pharmacist": ["medicines", "prescriptions", "expiry_tracking", "controlled_drugs",
                           "inventory", "orders", "pos", "customers"],
            "Cashier": ["orders", "pos", "customers"],
            "Delivery Boy": ["my_deliveries"],
        },
    },
    "grocery": {
        "label": "Grocery / General Store",
        "keywords": ["grocery", "general store", "mart", "supermarket", "kiryana", "store"],
        "modules": ["orders", "products", "stock_alerts", "returns", "deliveries",
                    "my_deliveries", "customers", "inventory", "suppliers", "expenses"],
        "owner_menu": ["orders", "products", "stock_alerts", "returns", "customers",
                       "deliveries", "suppliers", "reports"],
        "templates": {
            "Manager": ["orders", "products", "pos", "inventory", "suppliers", "reports", "expenses", "deliveries"],
            "Cashier": ["orders", "pos", "customers"],
            "Stock Keeper": ["products", "inventory", "stock_alerts"],
            "Delivery Boy": ["my_deliveries"],
        },
    },
    "hospital": {
        "label": "Hospital",
        "keywords": ["hospital", "medical center", "medical centre", "trauma", "healthcare center"],
        "modules": ["departments", "orders", "appointments", "doctors", "patients", "prescriptions", "lab_tests",
                    "inventory", "expenses"],
        "owner_menu": ["departments", "appointments", "doctors", "patients", "lab_tests", "prescriptions",
                       "reports"],
        "templates": {
            "Doctor": ["appointments", "patients", "prescriptions", "lab_tests"],
            "Receptionist": ["departments", "orders", "appointments", "doctors", "patients", "lab_tests", "pos"],
            "Ward Manager": ["departments", "patients", "appointments"],
            "Lab Technician": ["lab_tests", "patients"],
            "Manager": ["departments", "orders", "reports", "expenses", "attendance", "appointments", "doctors", "lab_tests"],
        },
    },
    "clinic": {
        "label": "Clinic",
        "keywords": ["clinic", "doctor", "dental", "lab"],
        "modules": ["orders", "appointments", "doctors", "patients", "prescriptions", "lab_tests",
                    "inventory", "expenses"],
        "owner_menu": ["orders", "appointments", "doctors", "patients", "prescriptions", "lab_tests",
                       "inventory", "reports"],
        "templates": {
            "Doctor": ["appointments", "patients", "prescriptions", "lab_tests"],
            "Receptionist": ["orders", "appointments", "doctors", "patients", "pos"],
            "Manager": ["orders", "reports", "expenses", "attendance", "appointments", "doctors"],
        },
    },
    "retail": {
        "label": "Retail Shop",
        "keywords": ["retail", "shop", "boutique", "clothing", "electronics"],
        "modules": ["orders", "fulfillment", "products", "returns", "deliveries", "my_deliveries",
                    "customers", "inventory", "suppliers", "expenses"],
        "owner_menu": ["orders", "fulfillment", "products", "returns", "customers", "deliveries",
                       "inventory", "reports"],
        "templates": {
            "Manager": ["orders", "fulfillment", "products", "pos", "inventory", "reports", "expenses", "deliveries"],
            "Packer": ["fulfillment", "orders"],
            "Cashier": ["orders", "pos", "customers", "returns"],
            "Stock Keeper": ["products", "inventory"],
            "Delivery Boy": ["my_deliveries"],
        },
    },
    # "Other" ya koi unknown business type
    "general": {
        "label": "General",
        "keywords": [],
        "modules": ["orders", "products", "customers", "inventory", "suppliers", "expenses"],
        "owner_menu": ["orders", "products", "customers", "inventory", "reports"],
        "templates": {
            "Manager": ["orders", "pos", "inventory", "customers", "reports", "expenses", "attendance"],
            "Staff": ["pos", "customers"],
        },
    },
}


def business_key(business_type: str) -> str:
    bt = (business_type or "").strip().lower()
    for key, cfg in BUSINESS_TYPES.items():
        if key == "general":
            continue
        if key in bt or any(k in bt for k in cfg["keywords"]):
            return key
    return "general"


def modules_for(business_type: str) -> list:
    cfg = BUSINESS_TYPES[business_key(business_type)]
    return list(dict.fromkeys(COMMON + cfg["modules"]))


def catalog_for(business_type: str) -> list:
    return [
        {"key": k, "label": MODULES[k], "group": "common" if k in COMMON else "business"}
        for k in modules_for(business_type)
    ]


def template_for(business_type: str) -> dict:
    cfg = BUSINESS_TYPES[business_key(business_type)]
    allowed = set(modules_for(business_type))
    return {name: [m for m in mods if m in allowed] for name, mods in cfg["templates"].items()}


def owner_nav_for(business_type: str) -> list:
    cfg = BUSINESS_TYPES[business_key(business_type)]
    allowed = set(modules_for(business_type))
    return [{"key": k, "label": MODULES[k]} for k in cfg["owner_menu"] if k in allowed]


def _validate():
    for bkey, cfg in BUSINESS_TYPES.items():
        allowed = set(COMMON) | set(cfg["modules"])
        used = set(cfg["owner_menu"]) | {m for mods in cfg["templates"].values() for m in mods}
        unknown = {m for m in (allowed | used) if m not in MODULES}
        not_allowed = used - allowed
        if unknown or not_allowed:
            raise ValueError(
                f"modules.py [{bkey}]: unknown={sorted(unknown)} not_allowed_for_type={sorted(not_allowed)}"
            )


_validate()