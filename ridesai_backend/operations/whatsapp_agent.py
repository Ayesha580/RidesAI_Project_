"""
WhatsApp AI Agent & Dynamic Order Processing Workflow (Phase 3).

Dynamically parses customer inquiries and order requests using the OpenAI API (gpt-4o-mini).
Grounds responses in tenant-specific business data (Company, CatalogItem, BusinessKnowledge,
and BusinessHours), executes database transactions via strict Tool Calling (Function Calling),
and dispatches voice/text responses via Meta WhatsApp Cloud API using WhatsAppService.
"""

import json
import logging
import os
import re
from decimal import Decimal
from typing import Optional, Dict, Any, List

from django.conf import settings
from django.db import close_old_connections, transaction
from django.utils import timezone
from openai import OpenAI

from .whatsapp_service import WhatsAppService
from .whatsapp_storage import get_config_by_phone_number_id
from .audio_service import transcribe_audio, synthesize_speech
from operations.models import (
    Customer, Order, OrderItem, OrderEvent, AgentConversation, AgentMessage,
    Prescription,
)
from companies.models import Company, CatalogItem, BusinessKnowledge, BusinessHours, Inventory, StockMovement

logger = logging.getLogger("operations.whatsapp")

PAKISTAN_CITIES = [
    "Karachi", "Lahore", "Faisalabad", "Rawalpindi", "Gujranwala", "Peshawar",
    "Multan", "Islamabad", "Quetta", "Sialkot", "Hyderabad", "Bahawalpur", "Sargodha"
]


# ============================================================================
# OpenAI / Groq Tool Schemas (Phase 3 Tool Calling)
# ============================================================================

TOOL_GET_CATALOG_ITEMS = {
    "type": "function",
    "function": {
        "name": "get_catalog_items",
        "description": (
            "Fetches real-time available menu/catalog items, stock availability, "
            "descriptions, and prices for the current business store."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "search_query": {
                    "type": "string",
                    "description": "Optional keyword or category to search for specific items (e.g. 'burger', 'medicine', 'service').",
                }
            },
            "required": [],
        },
    },
}

TOOL_CREATE_ORDER = {
    "type": "function",
    "function": {
        "name": "create_order",
        "description": (
            "Executes a confirmed order transaction in the store database. "
            "Call this ONLY when the customer has clearly confirmed they want to order "
            "and has provided their delivery address."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "delivery_address": {
                    "type": "string",
                    "description": "The customer's complete delivery address or table/pickup location.",
                },
                "items": {
                    "type": "array",
                    "description": "List of items and quantities being ordered.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "item_name": {
                                "type": "string",
                                "description": "Name of the catalog item.",
                            },
                            "quantity": {
                                "type": "integer",
                                "description": "Number of units to order (minimum 1).",
                            },
                            "special_instructions": {
                                "type": "string",
                                "description": "Optional non-priced preparation notes ONLY (e.g. 'no onions', 'less salt'). NEVER put menu modifiers/add-ons like 'Extra Cheese' or 'Large' here — put those in `selected_modifiers`.",
                            },
                            "selected_modifiers": {
                                "type": "array",
                                "description": "REQUIRED whenever the customer asks for ANY add-on, size, or option listed in the item's `modifiers_schema` / `[Modifiers: ...]` (e.g. ['Large', 'Extra Cheese']). Always include modifier prices when quoting the order total.",
                                "items": {"type": "string"},
                            },
                        },
                        "required": ["item_name", "quantity"],
                    },
                },
                "order_type": {
                    "type": "string",
                    "enum": ["delivery", "dine_in", "takeaway"],
                    "description": "Order fulfillment type: delivery (default), dine_in, or takeaway.",
                },
                "table_number": {
                    "type": "string",
                    "description": "Optional table number if order_type is dine_in (e.g. 'T1').",
                },
                "customer_name": {
                    "type": "string",
                    "description": "Name of the customer placing the order.",
                },
                "customer_phone": {
                    "type": "string",
                    "description": "Contact phone number of the customer placing the order.",
                },
                "notes": {
                    "type": "string",
                    "description": "General delivery instructions or notes for the staff.",
                },
            },
            "required": ["delivery_address", "items"],
        },
    },
}

TOOL_CHECK_ORDER_STATUS = {
    "type": "function",
    "function": {
        "name": "check_order_status",
        "description": (
            "Queries the real-time status and details of recent orders for the customer "
            "by order number or customer phone number."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "order_number": {
                    "type": "string",
                    "description": "Optional order reference number (e.g., 'RA-261117-XXXX').",
                },
            },
            "required": [],
        },
    },
}

TOOL_SUBMIT_PRESCRIPTION_REQUEST = {
    "type": "function",
    "function": {
        "name": "submit_prescription_request",
        "description": (
            "Submits a prescription medicine request or doctor's prescription for pharmacist review. "
            "Use when a customer requests prescription-required medicines (Rx) or wants to submit their prescription."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "customer_name": {
                    "type": "string",
                    "description": "Name of the patient or customer.",
                },
                "requested_items": {
                    "type": "string",
                    "description": "Names and dosages/quantities of the requested prescription medicines.",
                },
                "notes": {
                    "type": "string",
                    "description": "Any doctor instructions, doctor name, or customer notes.",
                },
            },
            "required": ["requested_items"],
        },
    },
}

TOOL_GET_CLINIC_DOCTORS = {
    "type": "function",
    "function": {
        "name": "get_clinic_doctors",
        "description": (
            "Retrieves the list of active doctors, their specialties, qualifications, consultation fees (in Rs.), "
            "available days, and clinic consultation hours."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "specialty": {
                    "type": "string",
                    "description": "Optional medical specialty to filter by (e.g. 'Cardiologist', 'Dermatologist', 'General Physician').",
                },
            },
            "required": [],
        },
    },
}

TOOL_BOOK_APPOINTMENT = {
    "type": "function",
    "function": {
        "name": "book_appointment",
        "description": (
            "Books a doctor consultation appointment for a patient at the clinic. "
            "Registers a pending appointment and assigns the doctor."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "patient_name": {
                    "type": "string",
                    "description": "Full name of the patient seeking medical consultation.",
                },
                "doctor_name": {
                    "type": "string",
                    "description": "Name of the requested doctor or preferred specialty (e.g. 'Dr. Ayesha Tariq' or 'Cardiologist').",
                },
                "preferred_date": {
                    "type": "string",
                    "description": "Preferred appointment date (e.g., 'YYYY-MM-DD' or 'Tomorrow' or 'Saturday').",
                },
                "preferred_time": {
                    "type": "string",
                    "description": "Preferred appointment time (e.g., '11:00 AM' or '05:30 PM').",
                },
                "reason": {
                    "type": "string",
                    "description": "Brief health concern, symptoms, or reason for visit.",
                },
            },
            "required": ["patient_name"],
        },
    },
}

TOOL_SUBMIT_RETURN_REQUEST = {
    "type": "function",
    "function": {
        "name": "submit_return_request",
        "description": (
            "Submits a customer return or exchange request for retail items or previously placed orders. "
            "Creates a pending return request with return reference number (RET-YYMMDD-XXXX)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "customer_name": {
                    "type": "string",
                    "description": "Full name of the customer requesting the return or exchange.",
                },
                "order_number": {
                    "type": "string",
                    "description": "Optional order reference number (e.g., 'RA-261117-XXXX') if known.",
                },
                "item_summary": {
                    "type": "string",
                    "description": "Description and quantity of the items being returned or exchanged.",
                },
                "reason": {
                    "type": "string",
                    "description": "Customer's reason for the return or exchange (e.g. 'wrong size', 'defective item', 'change of mind').",
                },
                "request_type": {
                    "type": "string",
                    "enum": ["return", "exchange"],
                    "description": "Whether the customer wants a return (refund/credit) or an exchange for another item/size.",
                },
            },
            "required": ["reason"],
        },
    },
}

TOOL_GET_UPSELL_SUGGESTIONS = {
    "type": "function",
    "function": {
        "name": "get_upsell_suggestions",
        "description": (
            "Fetches up to 3 real, currently in-stock complementary add-on or cross-sell items "
            "(such as fries, drinks, dips, desserts, or related accessories) from this business's live catalog "
            "based on the items the customer is ordering."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ordered_item_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of item names the customer has already selected for their order.",
                }
            },
            "required": ["ordered_item_names"],
        },
    },
}

TOOL_GET_HOSPITAL_DEPARTMENTS = {
    "type": "function",
    "function": {
        "name": "get_hospital_departments",
        "description": (
            "Fetches the hospital's active departments, wards (OPD, Emergency, ICU, General Ward, Lab/Diagnostics), "
            "24/7 availability, head doctors, and real-time available bed counts."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ward_type": {
                    "type": "string",
                    "description": "Optional filter: 'opd', 'emergency', 'icu', 'general_ward', 'maternity', or 'diagnostics'.",
                }
            },
            "required": [],
        },
    },
}

TOOL_BOOK_LAB_TEST = {
    "type": "function",
    "function": {
        "name": "book_lab_test",
        "description": (
            "Books a diagnostic or laboratory test (e.g., CBC, Lipid Profile, X-Ray, Ultrasound, Full Body Checkup) "
            "at the hospital once the patient confirms the test name, their name, phone, and preferred date/time."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "patient_name": {"type": "string", "description": "Full name of the patient."},
                "patient_phone": {"type": "string", "description": "Patient's phone number."},
                "test_name": {"type": "string", "description": "Name of the lab or diagnostic test."},
                "scheduled_date": {"type": "string", "description": "Preferred date (YYYY-MM-DD or natural date)."},
                "scheduled_time": {"type": "string", "description": "Preferred time slot (e.g. '10:00 AM')."},
                "notes": {"type": "string", "description": "Optional fasting or clinical instructions."},
            },
            "required": ["patient_name", "test_name"],
        },
    },
}

TOOL_LOG_UNANSWERED_QUESTION = {
    "type": "function",
    "function": {
        "name": "log_unanswered_question",
        "description": (
            "Logs a customer's business policy or general question that is NOT answered by the current catalog "
            "or Frequently Asked Questions (e.g. parking, halal certification, insurance accepted, return window) "
            "so the business owner can review and approve an official FAQ answer."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The customer's unanswered question in clear form.",
                },
                "draft_answer": {
                    "type": "string",
                    "description": "Optional brief placeholder/draft answer if obvious, otherwise leave empty.",
                },
            },
            "required": ["question"],
        },
    },
}

AGENT_TOOLS = [
    TOOL_GET_CATALOG_ITEMS,
    TOOL_GET_UPSELL_SUGGESTIONS,
    TOOL_CREATE_ORDER,
    TOOL_CHECK_ORDER_STATUS,
    TOOL_SUBMIT_PRESCRIPTION_REQUEST,
    TOOL_GET_CLINIC_DOCTORS,
    TOOL_BOOK_APPOINTMENT,
    TOOL_GET_HOSPITAL_DEPARTMENTS,
    TOOL_BOOK_LAB_TEST,
    TOOL_SUBMIT_RETURN_REQUEST,
    TOOL_LOG_UNANSWERED_QUESTION,
]


# ============================================================================
# Category-Aware Modular Agent Profile Registry (PRD Multitenancy)
# ============================================================================

CATEGORY_AGENT_PROFILES = {
    "restaurant": {
        "key": "restaurant",
        "role_desc": "food ordering and customer service",
        "catalog_header": "FOOD MENU & AVAILABLE DISHES",
        "instructions": (
            "- Primary duty is presenting delicious food options, taking takeaway/delivery food orders, "
            "and confirming customer delivery addresses."
        ),
        "tools": [TOOL_GET_CATALOG_ITEMS, TOOL_GET_UPSELL_SUGGESTIONS, TOOL_CREATE_ORDER, TOOL_CHECK_ORDER_STATUS, TOOL_LOG_UNANSWERED_QUESTION],
    },
    "pharmacy": {
        "key": "pharmacy",
        "role_desc": "licensed pharmacy assistant and medicine ordering support",
        "catalog_header": "MEDICINES & HEALTHCARE PRODUCTS",
        "instructions": (
            "- Primary duty is answering inquiries about in-stock OTC medicines, wellness products, "
            "and taking delivery orders for healthcare supplies.\n"
            "- OTC MEDICINES (Rx Not Required): You may take orders directly via `create_order` once the customer confirms items and delivery address.\n"
            "- PRESCRIPTION MEDICINES (Rx Required): You CANNOT directly place orders for prescription medicines. "
            "Instead, call `submit_prescription_request` with the medicine names and customer details, and inform the customer that their prescription request has been registered and a licensed pharmacist will review and confirm it.\n"
            "- Inform customers that prescription-only medicines require presenting a valid physical or digital doctor's prescription upon delivery."
        ),
        "tools": [TOOL_GET_CATALOG_ITEMS, TOOL_GET_UPSELL_SUGGESTIONS, TOOL_CREATE_ORDER, TOOL_CHECK_ORDER_STATUS, TOOL_SUBMIT_PRESCRIPTION_REQUEST, TOOL_LOG_UNANSWERED_QUESTION],
    },
    "hospital": {
        "key": "hospital",
        "role_desc": "hospital reception, OPD appointment desk, lab/diagnostics booking, and ward information assistant",
        "catalog_header": "HOSPITAL SERVICES, DIAGNOSTIC LAB TESTS & CHECKUP PACKAGES",
        "instructions": (
            "- Primary duty is helping patients with hospital departments, 24/7 emergency & ward/bed availability, "
            "specialist doctors, OPD timings, consultation fees in Rs., OPD appointment bookings, and lab/diagnostic test bookings.\n"
            "- DEPARTMENTS & BEDS: Call `get_hospital_departments` when a patient asks about departments, emergency, ICU, wards, or bed availability.\n"
            "- DOCTORS & OPD: Call `get_clinic_doctors` to share active specialist doctors, qualifications, OPD hours, and fees in Rs.\n"
            "- OPD APPOINTMENTS: Collect patient's full name, phone number, preferred doctor/department, date, time, and reason, then call `book_appointment`.\n"
            "- LAB / DIAGNOSTIC TESTS: Collect patient's name, phone, test name, and preferred date/time, then call `book_lab_test`.\n"
            "- PREVENTIVE CHECKUP / LAB CROSS-SELL (when upselling is enabled): Before confirming an OPD appointment or lab test, "
            "politely suggest 1 relevant preventive health checkup package or complementary diagnostic test from THIS hospital's active catalog with its exact Rs. price (ask only once; respect declines immediately).\n"
            "- MEDICAL GUARDRAIL: You are a hospital reception assistant, NOT a physician. STRICTLY NEVER diagnose conditions, prescribe medicines, "
            "or give medical treatment advice. For medical emergencies, immediately direct the patient to the 24/7 Emergency Ward."
        ),
        "tools": [
            TOOL_GET_HOSPITAL_DEPARTMENTS,
            TOOL_GET_CLINIC_DOCTORS,
            TOOL_BOOK_APPOINTMENT,
            TOOL_BOOK_LAB_TEST,
            TOOL_GET_CATALOG_ITEMS,
            TOOL_GET_UPSELL_SUGGESTIONS,
            TOOL_CHECK_ORDER_STATUS,
            TOOL_LOG_UNANSWERED_QUESTION,
        ],
    },
    "clinic": {
        "key": "clinic",
        "role_desc": "clinic appointment desk and patient support assistant",
        "catalog_header": "CLINICAL SERVICES & SPECIALTIES",
        "instructions": (
            "- Primary duty is providing information regarding clinic hours, active doctors, consultation timings, "
            "consultation fees in Rs., and booking patient appointments.\n"
            "- DOCTOR INQUIRIES: Call `get_clinic_doctors` to view current doctors, qualifications, fees, and available days/hours.\n"
            "- APPOINTMENT BOOKING: Before calling `book_appointment`, collect the patient's name, preferred doctor or specialty, "
            "preferred date and time, and brief reason for consultation. Once confirmed with the patient, call `book_appointment`.\n"
            "- MEDICAL GUARDRAIL: You are an administrative assistant, NOT a doctor. STRICTLY NEVER diagnose symptoms, prescribe medicines, "
            "or offer medical treatment advice. Always advise consulting a qualified doctor or visiting the emergency room for urgent symptoms.\n"
            "- Do NOT attempt to place food or takeaway delivery orders via `create_order`."
        ),
        "tools": [TOOL_GET_CLINIC_DOCTORS, TOOL_BOOK_APPOINTMENT, TOOL_GET_CATALOG_ITEMS, TOOL_CHECK_ORDER_STATUS, TOOL_LOG_UNANSWERED_QUESTION],
    },
    "retail": {
        "key": "retail",
        "role_desc": "retail store assistant, order fulfillment, and customer return/exchange support",
        "catalog_header": "STORE CATALOG & INVENTORY",
        "instructions": (
            "- Primary duty is helping shoppers explore available retail merchandise, checking product stock, "
            "taking delivery orders, checking order status, and processing returns/exchanges.\n"
            "- PRODUCT ORDERS: Call `get_catalog_items` to verify items and prices in Rs. (PKR). Once customer confirms items and delivery address, place the order via `create_order`.\n"
            "- ORDER TRACKING: Call `check_order_status` if the customer inquires about their recent order.\n"
            "- RETURNS & EXCHANGES: If a customer wants to return or exchange an item, gather their details, reason, and order number (if known), then call `submit_return_request`."
        ),
        "tools": [TOOL_GET_CATALOG_ITEMS, TOOL_GET_UPSELL_SUGGESTIONS, TOOL_CREATE_ORDER, TOOL_CHECK_ORDER_STATUS, TOOL_SUBMIT_RETURN_REQUEST, TOOL_LOG_UNANSWERED_QUESTION],
    },
}


def get_category_agent_config(business_type: Optional[str]) -> Dict[str, Any]:
    """
    Returns the modular agent profile configuration for a business vertical.
    Resolves keywords to restaurant, pharmacy, clinic, or retail.
    """
    raw = (business_type or "").strip().lower()
    if any(k in raw for k in ("pharm", "med", "chemist", "drug")) and "medical center" not in raw and "medical centre" not in raw:
        return CATEGORY_AGENT_PROFILES["pharmacy"]
    if any(k in raw for k in ("hospital", "medical center", "medical centre", "trauma")):
        return CATEGORY_AGENT_PROFILES["hospital"]
    if any(k in raw for k in ("clinic", "doctor", "health", "dental", "physio")):
        return CATEGORY_AGENT_PROFILES["clinic"]
    if any(k in raw for k in ("retail", "store", "shop", "supermarket", "grocery", "mart", "general")):
        return CATEGORY_AGENT_PROFILES["retail"]
    # Default to restaurant
    return CATEGORY_AGENT_PROFILES["restaurant"]


# ============================================================================
# Smart Catalog-Grounded Upselling & Cross-Selling Engine (Multi-Tenant)
# ============================================================================

_RESTAURANT_MAIN_KEYWORDS = (
    "burger", "pizza", "biryani", "shawarma", "karahi", "wrap", "pasta",
    "steak", "sandwich", "roll", "tikka", "broast", "kebab", "platter",
    "rice", "handi", "pulao", "nihari", "haleem", "deal", "combo",
)
_RESTAURANT_SIDE_KEYWORDS = (
    "fries", "fry", "nugget", "wing", "salad", "dip", "sauce", "mayo",
    "garlic", "coleslaw", "raita", "naan", "roti", "side", "snack", "onion ring",
)
_RESTAURANT_DRINK_KEYWORDS = (
    "drink", "cola", "pepsi", "coke", "sprite", "7up", "fanta", "mirinda",
    "juice", "shake", "water", "tea", "chai", "coffee", "lassi", "beverage",
    "mojito", "soda", "margarita", "smoothie", "slush",
)
_RESTAURANT_DESSERT_KEYWORDS = (
    "cake", "brownie", "ice cream", "gulab", "kheer", "dessert", "sweet",
    "cookie", "lava", "pudding", "halwa", "pastry", "donut", "waffle",
)


def _classify_restaurant_bucket(name_and_cat: str) -> str:
    text = (name_and_cat or "").lower()
    if any(k in text for k in _RESTAURANT_DRINK_KEYWORDS):
        return "drink"
    if any(k in text for k in _RESTAURANT_DESSERT_KEYWORDS):
        return "dessert"
    if any(k in text for k in _RESTAURANT_SIDE_KEYWORDS):
        return "side"
    if any(k in text for k in _RESTAURANT_MAIN_KEYWORDS):
        return "main"
    return "other"


def get_upsell_suggestions(
    company: Optional[Company],
    ordered_item_names: Optional[List[str]] = None,
    max_suggestions: int = 3,
) -> List[Dict[str, Any]]:
    """
    Returns up to `max_suggestions` (default 3) real, currently available & in-stock
    CatalogItem upsell/cross-sell suggestions strictly scoped to `company`.

    Zero-Hallucination & Strict Multi-Tenant Guarantees:
    - Queries ONLY `CatalogItem.objects.filter(company=company, is_available=True)`.
    - Excludes items with tracked Inventory quantity <= 0 (out-of-stock).
    - Excludes items already in `ordered_item_names`.
    """
    if not company or not getattr(company, "enable_upselling", True):
        return []

    ordered_clean = [str(n).strip().lower() for n in (ordered_item_names or []) if str(n).strip()]

    qs = (
        CatalogItem.objects.filter(company=company, is_available=True)
        .select_related("category")
        .order_by("id")
    )

    # Preload inventory map for this company to exclude out-of-stock tracked items in O(1)
    inv_map = {
        inv.item_id: inv
        for inv in Inventory.objects.filter(company=company).only("item_id", "quantity", "is_unlimited")
    }

    available_candidates: List[Dict[str, Any]] = []
    ordered_categories = set()

    for item in qs:
        item_name_lower = (item.name or "").strip().lower()
        cat_name = (item.category.name if item.category else "").strip()

        # Check if item is already in ordered list
        is_already_ordered = any(
            ord_name == item_name_lower or ord_name in item_name_lower or item_name_lower in ord_name
            for ord_name in ordered_clean
        )
        if is_already_ordered:
            if cat_name:
                ordered_categories.add(cat_name.lower())
            continue

        # Exclude out-of-stock tracked inventory items
        inv = inv_map.get(item.id)
        if inv and not inv.is_unlimited and inv.quantity <= 0:
            continue

        price_val = float(item.price or 0)
        price_str = f"Rs. {int(price_val)}" if price_val == int(price_val) else f"Rs. {price_val:.2f}"
        available_candidates.append({
            "id": item.id,
            "name": item.name,
            "price": price_val,
            "price_formatted": price_str,
            "category": cat_name,
            "_bucket": _classify_restaurant_bucket(f"{item.name} {cat_name}"),
        })

    if not available_candidates:
        return []

    biz_type = (getattr(company, "business_type", "") or "restaurant").strip().lower()

    if "restaurant" in biz_type or not any(k in biz_type for k in ("pharm", "med", "clinic", "hosp", "retail", "store", "shop", "grocery")):
        ordered_buckets = {_classify_restaurant_bucket(n) for n in ordered_clean}
        ordered_has_main = "main" in ordered_buckets
        ordered_only_sides = bool(ordered_buckets) and ordered_buckets.issubset({"side", "other"})

        if ordered_only_sides and not ordered_has_main:
            # Customer ordered only snacks/sides -> suggest drinks and mains
            preferred_order = ["drink", "main", "dessert", "side", "other"]
        else:
            # Customer ordered main(s) (or empty) -> suggest sides/fries, drinks, dips/desserts
            preferred_order = ["side", "drink", "dessert", "other", "main"]

        # Diversity-first selection: pick 1 from each preferred bucket first, then fill remaining
        selected: List[Dict[str, Any]] = []
        used_ids = set()
        for bucket in preferred_order:
            if len(selected) >= max_suggestions:
                break
            for cand in available_candidates:
                if cand["id"] not in used_ids and cand["_bucket"] == bucket:
                    selected.append(cand)
                    used_ids.add(cand["id"])
                    break
        if len(selected) < max_suggestions:
            for bucket in preferred_order:
                for cand in available_candidates:
                    if len(selected) >= max_suggestions:
                        break
                    if cand["id"] not in used_ids and cand["_bucket"] == bucket:
                        selected.append(cand)
                        used_ids.add(cand["id"])
    else:
        # Retail / Pharmacy / Clinic: prioritize items from OTHER active categories first
        other_cat = [
            c for c in available_candidates
            if c["category"] and c["category"].lower() not in ordered_categories
        ]
        same_or_uncat = [c for c in available_candidates if c not in other_cat]
        selected = (other_cat + same_or_uncat)[:max_suggestions]

    return [
        {
            "id": c["id"],
            "name": c["name"],
            "price": c["price"],
            "price_formatted": c["price_formatted"],
            "category": c["category"],
        }
        for c in selected[:max_suggestions]
    ]


# ============================================================================
# Tool Execution Functions (Atomic Database Transactions & Multi-Tenant Guarded)
# ============================================================================

def log_unanswered_question(
    company: Optional[Company],
    question: str,
    draft_answer: str = "",
    source_channel: str = "public_web",
) -> Dict[str, Any]:
    """
    Logs an unanswered customer question as a company-scoped SuggestedFAQ.
    Deduplicates case-insensitively per company by incrementing `occurrence_count`
    if a matching pending suggestion already exists.
    """
    if not company:
        return {"success": False, "error": "Company context missing."}

    clean_q = re.sub(r"\s+", " ", str(question or "")).strip()
    if len(clean_q) < 3:
        return {"success": False, "error": "Question too short to log."}

    clean_draft = str(draft_answer or "").strip()[:1000]
    valid_channels = {"public_web", "widget", "whatsapp"}
    channel = source_channel if source_channel in valid_channels else "public_web"

    try:
        from operations.models import SuggestedFAQ
        existing = SuggestedFAQ.objects.filter(
            company=company,
            status=SuggestedFAQ.STATUS_PENDING,
            question__iexact=clean_q,
        ).first()

        if existing:
            existing.occurrence_count += 1
            update_fields = ["occurrence_count", "updated_at"]
            if clean_draft and not (existing.suggested_answer or "").strip():
                existing.suggested_answer = clean_draft
                update_fields.append("suggested_answer")
            existing.save(update_fields=update_fields)
            return {
                "success": True,
                "suggestion_id": existing.id,
                "deduplicated": True,
                "occurrence_count": existing.occurrence_count,
            }

        created = SuggestedFAQ.objects.create(
            company=company,
            question=clean_q,
            suggested_answer=clean_draft,
            source_channel=channel,
            occurrence_count=1,
            status=SuggestedFAQ.STATUS_PENDING,
        )
        return {
            "success": True,
            "suggestion_id": created.id,
            "deduplicated": False,
            "occurrence_count": 1,
        }
    except Exception as exc:
        logger.warning(f"[FAQ Learning] Failed to log unanswered question for company {company.id}: {exc}")
        return {"success": False, "error": str(exc)}


def execute_get_hospital_departments(company: Company, ward_type: Optional[str] = None) -> Dict[str, Any]:
    """Fetches active hospital departments, wards, and live bed availability strictly for `company`."""
    try:
        from operations.models import HospitalDepartment
        qs = HospitalDepartment.objects.filter(company=company, is_active=True).select_related("head_doctor")
        if ward_type and str(ward_type).strip():
            qs = qs.filter(ward_type__iexact=str(ward_type).strip())
        rows = []
        for dept in qs[:30]:
            rows.append({
                "name": dept.name,
                "ward_type": dept.get_ward_type_display(),
                "floor_or_location": dept.floor_or_location,
                "total_beds": dept.total_beds,
                "available_beds": dept.available_beds,
                "is_24_7": dept.is_24_7,
                "head_doctor": dept.head_doctor.name if dept.head_doctor else None,
            })
        return {"success": True, "departments": rows, "count": len(rows)}
    except Exception as e:
        logger.error(f"[Hospital Agent] get_hospital_departments error: {e}", exc_info=True)
        return {"success": False, "error": "Could not load hospital departments right now."}


def execute_book_lab_test(
    company: Company,
    sender_phone: str,
    patient_name: str,
    test_name: str,
    scheduled_date: Optional[str] = None,
    scheduled_time: Optional[str] = None,
    notes: str = "",
) -> Dict[str, Any]:
    """Books a lab/diagnostic test strictly isolated to `company`."""
    try:
        from datetime import datetime as _dt
        from operations.models import HospitalDepartment, LabTestBooking, Patient

        clean_name = (patient_name or "").strip() or "Patient"
        clean_phone = (sender_phone or "").strip()
        clean_test = (test_name or "").strip()
        if not clean_test:
            return {"success": False, "error": "Please specify the lab or diagnostic test name."}

        # Look up catalog price if test exists in company catalog
        matched_item = (
            CatalogItem.objects.filter(company=company, is_available=True, name__icontains=clean_test).first()
        )
        price = matched_item.price if matched_item else Decimal("0.00")

        patient = None
        if clean_phone:
            patient, _ = Patient.objects.get_or_create(
                company=company,
                phone=clean_phone,
                defaults={"name": clean_name},
            )

        lab_dept = HospitalDepartment.objects.filter(
            company=company, is_active=True, ward_type=HospitalDepartment.WARD_DIAGNOSTICS
        ).first()

        parsed_date = timezone.localdate()
        if scheduled_date:
            try:
                parsed_date = _dt.strptime(str(scheduled_date).strip()[:10], "%Y-%m-%d").date()
            except ValueError:
                parsed_date = timezone.localdate()

        booking = LabTestBooking.objects.create(
            company=company,
            patient=patient,
            department=lab_dept,
            patient_name=clean_name,
            patient_phone=clean_phone,
            test_name=matched_item.name if matched_item else clean_test,
            price=price,
            scheduled_date=parsed_date,
            scheduled_time=str(scheduled_time or "").strip()[:50],
            status=LabTestBooking.STATUS_SCHEDULED,
            notes=str(notes or "").strip(),
            source="agent",
        )
        return {
            "success": True,
            "booking_number": booking.booking_number,
            "test_name": booking.test_name,
            "price": float(booking.price),
            "scheduled_date": booking.scheduled_date.isoformat() if booking.scheduled_date else "",
            "scheduled_time": booking.scheduled_time,
            "status": booking.status,
        }
    except Exception as e:
        logger.error(f"[Hospital Agent] book_lab_test error: {e}", exc_info=True)
        return {"success": False, "error": "Could not complete the lab test booking right now."}


def execute_get_catalog_items(company: Company, search_query: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetches active catalog items strictly isolated to the specified tenant company.
    """
    try:
        qs = CatalogItem.objects.filter(company=company, is_available=True).select_related("category")
        if search_query and search_query.strip():
            q = search_query.strip()
            qs = qs.filter(name__icontains=q) | qs.filter(description__icontains=q)

        items_list = []
        for item in qs[:40]:
            stock_info = "in stock"
            try:
                inv = getattr(item, "inventory", None)
                if inv and not inv.is_unlimited:
                    if inv.quantity <= 0:
                        # Exclude out of stock items
                        continue
                    stock_info = f"{inv.quantity} available"
            except Exception:
                pass

            rx_required = bool(getattr(item, "requires_prescription", False))
            generic = getattr(item, "generic_name", "") or ""

            items_list.append({
                "id": item.id,
                "name": item.name,
                "generic_name": generic,
                "price": str(item.price),
                "category": item.category.name if item.category else "General",
                "description": item.description or "",
                "modifiers_schema": getattr(item, "modifiers_schema", None) or [],
                "kitchen_station": getattr(item, "kitchen_station", "general") or "general",
                "prep_time_minutes": getattr(item, "prep_time_minutes", 15) or 15,
                "requires_prescription": rx_required,
                "stock": stock_info,
            })

        return {
            "success": True,
            "company_name": company.name,
            "count": len(items_list),
            "items": items_list,
        }
    except Exception as e:
        logger.error(f"[Tool: get_catalog_items] Error: {e}", exc_info=True)
        return {"success": False, "error": str(e), "items": []}


def execute_create_order(
    company: Company,
    customer_name: str,
    customer_phone: str,
    items: List[Dict[str, Any]],
    delivery_address: str,
    notes: Optional[str] = None,
    order_type: Optional[str] = None,
    table_number: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Executes a multi-tenant isolated database transaction creating Order, OrderItem,
    and OrderEvent records with inventory deduction and audit trail.
    """
    if not items:
        return {"success": False, "error": "No items provided in order request."}
    if not delivery_address or not delivery_address.strip():
        return {"success": False, "error": "Delivery address is required to place an order."}

    # Auto Location Fallback Validation: check against effective service areas
    effective_areas = get_effective_service_areas(company)
    if effective_areas:
        PAKISTAN_CITIES = [
            "Karachi", "Lahore", "Faisalabad", "Rawalpindi", "Gujranwala", "Peshawar",
            "Multan", "Islamabad", "Quetta", "Sialkot", "Hyderabad", "Bahawalpur", "Sargodha"
        ]
        addr_lower = delivery_address.lower()
        effective_lower = [a.lower() for a in effective_areas]
        for city in PAKISTAN_CITIES:
            c_low = city.lower()
            if c_low in addr_lower and not any(c_low in eff or eff in c_low for eff in effective_lower):
                return {
                    "success": False,
                    "error": f"We currently only deliver within {', '.join(effective_areas)}. Unfortunately, delivery to {city} is not available.",
                }

    clean_name = (customer_name or "").strip()
    clean_phone = (customer_phone or "").strip()
    clean_notes = (notes or "").strip()

    DISALLOWED_NAMES = {"valued customer", "customer", "guest", "unknown", "user", "client", "none", "n/a"}
    DUMMY_PHONES = {
        "03001234567", "03000000000", "03001111111", "03123456789",
        "1234567890", "923001234567", "+923001234567", "0000000000"
    }

    phone_digits = re.sub(r"\D", "", clean_phone)
    if (
        not clean_name
        or clean_name.lower() in DISALLOWED_NAMES
        or not clean_phone
        or len(phone_digits) < 10
        or clean_phone in DUMMY_PHONES
        or phone_digits in DUMMY_PHONES
        or phone_digits == "0000000000"
    ):
        return {
            "success": False,
            "error": "Cannot place order yet: missing real customer name or phone number. Politely ask the customer for their name and phone number.",
        }

    try:
        with transaction.atomic():
            subtotal = Decimal("0.00")
            resolved_items = []

            # Pre-validate and match each requested item against tenant catalog
            for raw_item in items:
                name_req = str(raw_item.get("item_name") or "").strip()
                qty_raw = raw_item.get("quantity", 1)
                try:
                    qty = Decimal(str(qty_raw))
                except Exception:
                    qty = Decimal("1")

                if qty <= 0:
                    return {"success": False, "error": f"Quantity for '{name_req}' must be at least 1."}

                # Try matching by exact name, then icontains, then reverse substring
                catalog_item = (
                    CatalogItem.objects.select_for_update()
                    .filter(company=company, is_available=True, name__iexact=name_req)
                    .first()
                )
                if not catalog_item:
                    catalog_item = (
                        CatalogItem.objects.select_for_update()
                        .filter(company=company, is_available=True, name__icontains=name_req)
                        .first()
                    )
                if not catalog_item:
                    # Reverse check: catalog item name in requested string (e.g. "Beef burger with cheese")
                    all_avail = CatalogItem.objects.select_for_update().filter(company=company, is_available=True)
                    for c_it in all_avail:
                        if c_it.name.lower() in name_req.lower():
                            catalog_item = c_it
                            break

                if not catalog_item:
                    avail_names = list(CatalogItem.objects.filter(company=company, is_available=True).values_list("name", flat=True)[:10])
                    avail_str = ", ".join(avail_names) if avail_names else "none"
                    return {
                        "success": False,
                        "error": f"Item '{name_req}' was not found in our catalog. Currently available: {avail_str}.",
                    }

                # Check inventory if tracked
                inv = Inventory.objects.select_for_update().filter(company=company, item=catalog_item).first()
                if inv and not inv.is_unlimited:
                    if qty > inv.quantity:
                        return {
                            "success": False,
                            "error": f"Insufficient stock for '{catalog_item.name}'. Only {inv.quantity} left in stock.",
                        }

                from operations.restaurant_kds_views import normalize_selected_modifiers
                item_note_text = str(raw_item.get("special_instructions") or raw_item.get("item_notes") or "").strip()
                fallback_mod_text = " ".join(
                    part for part in [name_req, item_note_text, clean_notes] if part
                )
                norm_mods, mod_delta = normalize_selected_modifiers(
                    catalog_item,
                    raw_item.get("selected_modifiers"),
                    fallback_text=fallback_mod_text,
                )
                effective_unit_price = catalog_item.price + mod_delta
                line_total = qty * effective_unit_price
                subtotal += line_total
                resolved_items.append({
                    "catalog_item": catalog_item,
                    "item_name": catalog_item.name,
                    "quantity": qty,
                    "unit_price": effective_unit_price,
                    "line_total": line_total,
                    "selected_modifiers": norm_mods,
                    "inventory": inv,
                    "notes": item_note_text,
                })

            # Consolidate general notes and item-specific special instructions into order.notes
            combined_notes_parts = []
            if clean_notes:
                combined_notes_parts.append(clean_notes)
            for r in resolved_items:
                item_instr = str(r.get("notes") or "").strip()
                if item_instr and item_instr.lower() not in clean_notes.lower():
                    combined_notes_parts.append(f"{r['item_name']}: {item_instr}")
            consolidated_notes = " | ".join(combined_notes_parts)

            # Create Order
            clean_order_type = (order_type or Order.ORDER_TYPE_DELIVERY).strip().lower()
            if clean_order_type not in (Order.ORDER_TYPE_DELIVERY, Order.ORDER_TYPE_DINE_IN, Order.ORDER_TYPE_TAKEAWAY):
                clean_order_type = Order.ORDER_TYPE_DELIVERY
            clean_table_num = (table_number or "").strip()

            order = Order.objects.create(
                company=company,
                order_type=clean_order_type,
                table_number=clean_table_num,
                customer_name=clean_name,
                customer_phone=clean_phone,
                delivery_address=delivery_address.strip(),
                status=Order.STATUS_NEW,
                subtotal=subtotal,
                delivery_fee=Decimal("0.00"),
                total=subtotal,
                notes=consolidated_notes,
                source="agent",
            )

            # Create OrderItems and adjust inventory
            created_items_summary = []
            for r in resolved_items:
                OrderItem.objects.create(
                    order=order,
                    item=r["catalog_item"],
                    item_name=r["item_name"],
                    quantity=r["quantity"],
                    unit_price=r["unit_price"],
                    line_total=r["line_total"],
                    selected_modifiers=r.get("selected_modifiers") or [],
                    item_notes=str(r.get("notes") or "").strip(),
                )
                if r["inventory"] and not r["inventory"].is_unlimited:
                    r["inventory"].quantity -= r["quantity"]
                    r["inventory"].save(update_fields=["quantity", "updated_at"])
                    StockMovement.objects.create(
                        company=company,
                        item=r["catalog_item"],
                        movement_type="remove",
                        quantity=r["quantity"],
                        note=f"WhatsApp Agent Order {order.order_number}",
                    )

                created_items_summary.append({
                    "name": r["item_name"],
                    "quantity": str(r["quantity"]),
                    "price": str(r["unit_price"]),
                    "line_total": str(r["line_total"]),
                    "selected_modifiers": r.get("selected_modifiers") or [],
                })

            # Audit Trail
            OrderEvent.objects.create(
                company=company,
                order=order,
                event_type="agent_order_created",
                to_status=order.status,
                note=f"Order auto-created by WhatsApp Voice/Chat Agent from {clean_phone or 'customer'}.",
            )

        logger.info(f"[Tool: create_order] Order {order.order_number} created successfully for {company.name}.")
        return {
            "success": True,
            "order_number": order.order_number,
            "status": order.status,
            "customer_name": order.customer_name,
            "delivery_address": order.delivery_address,
            "items": created_items_summary,
            "subtotal": f"Rs. {subtotal:.2f}",
            "total": f"Rs. {order.total:.2f}",
            "estimated_delivery_time": "30-45 minutes",
        }

    except Exception as e:
        logger.error(f"[Tool: create_order] Failed to create order: {e}", exc_info=True)
        return {"success": False, "error": f"Database transaction failed: {str(e)}"}


def execute_check_order_status(
    company: Company,
    customer_phone: str,
    order_number: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Queries real-time status of orders isolated to the specified tenant company.
    """
    try:
        qs = Order.objects.filter(company=company)
        if order_number and order_number.strip():
            qs = qs.filter(order_number__icontains=order_number.strip())
        elif customer_phone and customer_phone.strip():
            clean = customer_phone.strip()
            # Match last 10 digits to be resilient to country codes
            suffix = clean[-10:] if len(clean) >= 10 else clean
            qs = qs.filter(customer_phone__icontains=suffix)
        else:
            return {"found": False, "message": "No phone number or order number provided."}

        orders = list(qs.prefetch_related("items").order_by("-created_at")[:5])
        if not orders:
            return {
                "found": False,
                "message": "No active or past orders found for your details.",
            }

        history = []
        for o in orders:
            history.append({
                "order_number": o.order_number,
                "status": o.status,
                "status_display": o.get_status_display(),
                "total": f"Rs. {o.total:.2f}",
                "delivery_address": o.delivery_address,
                "created_at": o.created_at.strftime("%Y-%m-%d %I:%M %p"),
                "items": [f"{it.quantity}x {it.item_name}" for it in o.items.all()],
            })

        return {
            "found": True,
            "latest_order": history[0],
            "total_orders": len(history),
            "orders": history,
        }
    except Exception as e:
        logger.error(f"[Tool: check_order_status] Error: {e}", exc_info=True)
        return {"found": False, "error": str(e)}


def execute_submit_prescription_request(
    company: Company,
    customer_phone: str,
    requested_items: str,
    customer_name: Optional[str] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates a pending Prescription record for pharmacist review on the Pharmacy Dashboard.
    """
    try:
        clean_name = (customer_name or "").strip() or "Valued Customer"
        clean_phone = (customer_phone or "").strip()
        items_text = (requested_items or "").strip()
        user_notes = (notes or "").strip()

        if not items_text:
            return {"success": False, "error": "Requested medicine names are required."}

        rx = Prescription.objects.create(
            company=company,
            customer_name=clean_name,
            customer_phone=clean_phone,
            requested_items_text=items_text,
            notes=user_notes,
            status=Prescription.STATUS_PENDING,
        )

        logger.info(
            f"[Tool: submit_prescription_request] Created prescription {rx.prescription_number} "
            f"for {clean_name} ({clean_phone}) at {company.name}."
        )

        return {
            "success": True,
            "prescription_number": rx.prescription_number,
            "status": "pending_pharmacist_review",
            "message": (
                f"Prescription request #{rx.prescription_number} has been registered with our licensed pharmacist. "
                "Our pharmacy team will review and confirm your order shortly via WhatsApp."
            ),
        }
    except Exception as e:
        logger.error(f"[Tool: submit_prescription_request] Error: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


def execute_get_clinic_doctors(company: Company, specialty: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetches active clinic doctors strictly isolated to the specified tenant company.
    """
    try:
        from operations.models import Doctor
        qs = Doctor.objects.filter(company=company, is_active=True)
        if specialty and specialty.strip():
            qs = qs.filter(specialty__icontains=specialty.strip())

        doctors_list = []
        for doc in qs:
            fee_num = int(doc.consultation_fee) if doc.consultation_fee % 1 == 0 else doc.consultation_fee
            doctors_list.append({
                "id": doc.id,
                "name": doc.name,
                "specialty": doc.specialty,
                "qualification": doc.qualification,
                "consultation_fee": f"Rs. {fee_num}",
                "available_days": doc.available_days,
                "available_hours": doc.available_hours,
            })

        logger.info(f"[Tool: get_clinic_doctors] Retrieved {len(doctors_list)} doctors for {company.name}.")
        return {
            "success": True,
            "count": len(doctors_list),
            "doctors": doctors_list,
        }
    except Exception as e:
        logger.error(f"[Tool: get_clinic_doctors] Error: {e}", exc_info=True)
        return {"success": False, "error": str(e), "doctors": []}


def execute_book_appointment(
    company: Company,
    sender_phone: str,
    patient_name: str,
    doctor_name: Optional[str] = None,
    preferred_date: Optional[str] = None,
    preferred_time: Optional[str] = None,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates a pending Appointment record and ensures Patient record exists for the clinic tenant.
    """
    try:
        from datetime import datetime
        from operations.models import Doctor, Patient, Appointment

        clean_name = (patient_name or "").strip() or "Patient"
        clean_phone = (sender_phone or "").strip()
        clean_time = (preferred_time or "").strip()
        clean_reason = (reason or "").strip()

        # Find or create patient
        patient, _ = Patient.objects.get_or_create(
            company=company,
            phone=clean_phone,
            defaults={"name": clean_name}
        )
        if patient.name != clean_name and clean_name != "Patient":
            patient.name = clean_name
            patient.save(update_fields=["name", "updated_at"])

        # Match doctor by name or specialty if provided
        matched_doctor = None
        if doctor_name and doctor_name.strip():
            query = doctor_name.strip()
            matched_doctor = (
                Doctor.objects.filter(company=company, is_active=True, name__icontains=query).first()
                or Doctor.objects.filter(company=company, is_active=True, specialty__icontains=query).first()
            )

        # Parse date if provided in YYYY-MM-DD
        parsed_date = None
        if preferred_date and preferred_date.strip():
            try:
                parsed_date = datetime.strptime(preferred_date.strip(), "%Y-%m-%d").date()
            except Exception:
                parsed_date = None

        time_str = clean_time
        if not parsed_date and preferred_date and preferred_date.strip():
            time_str = f"{preferred_date.strip()} {clean_time}".strip()

        with transaction.atomic():
            apt = Appointment.objects.create(
                company=company,
                doctor=matched_doctor,
                patient=patient,
                patient_name=clean_name,
                patient_phone=clean_phone,
                appointment_date=parsed_date,
                appointment_time=time_str or "To be scheduled",
                reason=clean_reason,
                status=Appointment.STATUS_PENDING,
                source="whatsapp_ai",
            )

        doc_fee = f"Rs. {int(matched_doctor.consultation_fee)}" if matched_doctor and matched_doctor.consultation_fee else "Rs. 0"

        logger.info(
            f"[Tool: book_appointment] Created appointment {apt.appointment_number} "
            f"for {clean_name} ({clean_phone}) with {matched_doctor.name if matched_doctor else 'Unassigned'} at {company.name}."
        )

        return {
            "success": True,
            "appointment_number": apt.appointment_number,
            "patient_name": apt.patient_name,
            "doctor": matched_doctor.name if matched_doctor else "To be assigned by clinic reception",
            "specialty": matched_doctor.specialty if matched_doctor else None,
            "consultation_fee": doc_fee,
            "appointment_date": str(apt.appointment_date) if apt.appointment_date else (preferred_date or "To be scheduled"),
            "appointment_time": apt.appointment_time,
            "status": "pending",
            "message": (
                f"Appointment request #{apt.appointment_number} has been registered successfully. "
                "Our clinic reception will confirm your slot shortly via WhatsApp."
            ),
        }
    except Exception as e:
        logger.error(f"[Tool: book_appointment] Error: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


def execute_submit_return_request(
    company: Company,
    sender_phone: str,
    customer_name: Optional[str] = None,
    order_number: Optional[str] = None,
    item_summary: Optional[str] = None,
    reason: Optional[str] = None,
    request_type: str = "return",
) -> Dict[str, Any]:
    """
    Submits a return or exchange request strictly scoped to the tenant company.
    Auto-associates with an existing company order if order_number or recent phone matches.
    """
    try:
        from operations.models import ReturnRequest, Order
        clean_phone = (sender_phone or "").strip()
        clean_name = (customer_name or "").strip()
        matched_order = None

        if order_number and str(order_number).strip():
            matched_order = Order.objects.filter(
                company=company,
                order_number__iexact=str(order_number).strip()
            ).first()
            if matched_order and not clean_name:
                clean_name = matched_order.customer_name
        elif clean_phone:
            # Fallback: check most recent order for phone (last 10 digits)
            suffix = clean_phone[-10:] if len(clean_phone) >= 10 else clean_phone
            matched_order = Order.objects.filter(
                company=company,
                customer_phone__icontains=suffix
            ).order_by("-created_at").first()
            if matched_order:
                order_number = matched_order.order_number
                if not clean_name:
                    clean_name = matched_order.customer_name

        req_type = "exchange" if str(request_type).strip().lower() == "exchange" else "return"
        ret = ReturnRequest.objects.create(
            company=company,
            order=matched_order,
            order_number=order_number or (matched_order.order_number if matched_order else ""),
            customer_name=clean_name or "Valued Customer",
            customer_phone=clean_phone,
            item_summary=item_summary or "",
            reason=reason or "Customer requested return/exchange via WhatsApp AI",
            request_type=req_type,
            status=ReturnRequest.STATUS_PENDING,
        )

        logger.info(
            f"[Tool: submit_return_request] Created {req_type} request {ret.return_number} "
            f"for {clean_name} ({clean_phone}) at {company.name}."
        )

        return {
            "success": True,
            "return_number": ret.return_number,
            "request_type": req_type,
            "order_number": ret.order_number,
            "status": ret.status,
            "message": (
                f"Your {req_type} request #{ret.return_number} has been submitted successfully. "
                f"Our retail team at {company.name} will review and contact you shortly."
            ),
        }
    except Exception as e:
        logger.error(f"[Tool: submit_return_request] Error: {e}", exc_info=True)
        return {"success": False, "error": str(e)}



# ============================================================================
# Business Context & Prompt Building (Multi-Tenant Hardened)
# ============================================================================

def get_effective_service_areas(company: Optional[Company]) -> List[str]:
    """
    Returns active ServiceArea cities. If no ServiceArea is configured, automatically
    falls back to the company's registered locations or address so orders are accepted within that city.
    """
    if not company:
        return []
    try:
        zones = list(company.service_areas.filter(is_active=True).exclude(city="").values_list("city", flat=True))
        if zones:
            return list(dict.fromkeys([z.strip() for z in zones if z and z.strip()]))

        # Fallback 1: BusinessLocation city
        loc_cities = list(company.locations.filter(is_active=True).exclude(city="").values_list("city", flat=True))
        if loc_cities:
            return list(dict.fromkeys([c.strip() for c in loc_cities if c and c.strip()]))

        # Fallback 2: Company address
        if company.address and company.address.strip():
            addr = company.address.strip()
            matched = [c for c in PAKISTAN_CITIES if c.lower() in addr.lower()]
            if matched:
                return matched
            segments = [s.strip() for s in addr.split(",") if s.strip()]
            countries = {"pakistan", "pk", "usa", "us", "uk", "uae", "canada"}
            cities = [s for s in segments if s.lower() not in countries]
            if cities:
                return [cities[0]]
            return [addr]
    except Exception:
        pass
    return []


def get_business_context_for_company(company: Optional[Company]) -> Dict[str, Any]:
    """
    Constructs the grounded tenant business context (company, catalog, FAQs, hours)
    for a given Company model instance.
    """
    context = {
        "company": company,
        "company_id": company.id if company else None,
        "is_configured": bool(company),
        "business_name": (company.name if company else "Rides AI Store") or "Our Store",
        "greeting": (company.agent_greeting if company else "") or (f"Welcome to {company.name}!" if company else "Welcome to our store!"),
        "tone": (company.agent_tone if company else "") or "friendly and helpful",
        "phone": (company.phone or company.agent_support_phone if company else "") or "",
        "address": (company.address if company else "") or "",
        "business_type": (company.business_type if company else "") or "restaurant",
        "enable_upselling": bool(getattr(company, "enable_upselling", True)) if company else False,
        "upsell_candidates": [],
        "catalog": [],
        "knowledge": [],
        "hours": [],
    }

    if not company:
        return context

    try:
        # Fetch active catalog items (up to 40)
        items = list(
            CatalogItem.objects.filter(company=company, is_available=True)
            .values("id", "name", "price", "description", "modifiers_schema")[:40]
        )
        context["catalog"] = items
        if context["enable_upselling"]:
            context["upsell_candidates"] = get_upsell_suggestions(company, ordered_item_names=[], max_suggestions=3)

        # Fetch approved FAQs and business knowledge
        faqs = list(
            BusinessKnowledge.objects.filter(company=company, is_active=True, is_approved=True)
            .values("title", "content", "entry_type")[:40]
        )
        context["knowledge"] = faqs

        # Fetch operating hours
        hours = list(
            BusinessHours.objects.filter(company=company)
            .values("day_of_week", "opens_at", "closes_at", "is_closed")
        )
        context["hours"] = hours

        # Fetch active delivery service areas / zones with automatic fallback
        context["delivery_zones"] = get_effective_service_areas(company)

        # Fetch hospital departments/wards if this is a hospital vertical
        if get_category_agent_config(context["business_type"]).get("key") == "hospital":
            from operations.models import HospitalDepartment
            context["hospital_departments"] = list(
                HospitalDepartment.objects.filter(company=company, is_active=True)
                .values("name", "ward_type", "total_beds", "available_beds", "is_24_7", "floor_or_location")[:20]
            )
    except Exception as e:
        logger.warning(f"[WhatsApp Agent] Could not load DB business context for company {company.id}: {e}", exc_info=True)

    return context


def _get_business_context(phone_number_id: str) -> Dict[str, Any]:
    """
    Retrieves the tenant business context (company, catalog, FAQs, hours)
    matching the destination WhatsApp phone_number_id.

    STRICT MULTI-TENANT RULE:
    If phone_number_id does not map to a registered Company, returns is_configured=False
    and company=None. NEVER falls back to random Company.objects.first()!
    """
    try:
        cfg = get_config_by_phone_number_id(phone_number_id)
        company = None
        if cfg and cfg.get("company_id"):
            try:
                company = Company.objects.filter(pk=cfg["company_id"]).first()
            except Exception:
                company = None

        if not company:
            # Check if phone_number_id matches an Evolution API instance_name
            company = Company.objects.filter(whatsapp_instance_name=phone_number_id).first()

        # Fail closed: Do NOT fallback to random Company.objects.first()
        if not company:
            logger.warning(
                f"[WhatsApp Agent] Destination phone_number_id '{phone_number_id}' "
                "is not associated with any registered business. Failing closed."
            )
            return get_business_context_for_company(None)

        return get_business_context_for_company(company)

    except Exception as e:
        logger.warning(f"[WhatsApp Agent] Could not load DB business context: {e}", exc_info=True)
        return get_business_context_for_company(None)


def _build_system_prompt(
    customer_name: str,
    context: Dict[str, Any],
    is_voice_note: bool = False,
    has_prior_history: bool = False,
) -> str:
    """
    Constructs a detailed grounding system prompt for the LLM using tenant metadata,
    catalog items, operating hours, business knowledge, and tool-calling directives.
    """
    biz_name = context.get("business_name") or "our store"
    greeting = context.get("greeting") or f"Welcome to {biz_name}!"
    tone = context.get("tone") or "friendly and helpful"
    phone = context.get("phone") or "our support team"
    address = context.get("address") or "our store location"
    delivery_zones_list = context.get("delivery_zones", [])
    delivery_zones_str = ", ".join(delivery_zones_list) if delivery_zones_list else (address or "our local delivery area")

    # Category profile resolution
    biz_type = context.get("business_type") or "restaurant"
    cat_cfg = get_category_agent_config(biz_type)
    role_desc = cat_cfg["role_desc"]
    catalog_header = cat_cfg["catalog_header"]
    category_instructions = cat_cfg["instructions"]

    # Format catalog items (including available restaurant modifiers/add-ons with extra prices)
    catalog_lines = []
    for item in context.get("catalog", []):
        price = f"Rs. {float(item['price']):.2f}" if item.get("price") else "Price on request"
        desc = f" - {item['description']}" if item.get("description") else ""
        mod_parts = []
        for grp in (item.get("modifiers_schema") or []):
            if not isinstance(grp, dict):
                continue
            grp_name = grp.get("group") or grp.get("name") or "Options"
            opts = []
            for opt in (grp.get("options") or []):
                if isinstance(opt, dict) and opt.get("name"):
                    op_price = float(opt.get("price") or 0)
                    opts.append(f"{opt['name']} (+Rs. {op_price:.0f})" if op_price > 0 else f"{opt['name']}")
            if opts:
                mod_parts.append(f"{grp_name}: {', '.join(opts)}")
        mod_str = f" [Modifiers: {' | '.join(mod_parts)}]" if mod_parts else ""
        catalog_lines.append(f"• {item['name']}: {price}{desc}{mod_str}")
    
    if catalog_lines:
        catalog_str = (
            "\n".join(catalog_lines)
            + "\n\n[MODIFIER PRICING RULE]: Whenever a customer requests ANY add-on, size, or option listed in [Modifiers: ...] "
            "(e.g. Extra Cheese +Rs. 100, Large +Rs. 150), you MUST pass it inside `selected_modifiers` when calling `create_order` "
            "(NEVER only inside `special_instructions`) and quote the updated total including all modifier prices."
        )
    else:
        catalog_str = (
            f"No catalog items are currently active. If a customer asks to view items or order, "
            f"politely inform them that the store catalog is currently being updated."
        )

    # Format knowledge base FAQs
    kb_lines = []
    for faq in context.get("knowledge", []):
        title = faq.get("title", "").strip()
        content = faq.get("content", "").strip()
        if title and content:
            kb_lines.append(f"Q: {title}\nA: {content}")
    kb_str = "\n\n".join(kb_lines) if kb_lines else "No additional FAQs configured."

    # Format hours
    hours_lines = []
    for h in context.get("hours", []):
        day = h.get("day_of_week", "")
        if h.get("is_closed"):
            hours_lines.append(f"• {day}: Closed")
        else:
            hours_lines.append(f"• {day}: {h.get('opens_at')} - {h.get('closes_at')}")
    hours_str = "\n".join(hours_lines) if hours_lines else "• Monday - Sunday: 9:00 AM - 10:00 PM"

    voice_mode_instruction = ""
    voice_end_reminder = ""
    if is_voice_note:
        voice_mode_instruction = (
            "\nCRITICAL VOICE NOTE INSTRUCTION (INCOMING AUDIO MESSAGE):\n"
            "- The customer communicated via VOICE NOTE.\n"
            "- CRITICAL VOICE RULE: Your reply will be spoken aloud by an English TTS engine. "
            "You MUST reply strictly in simple, plain English ONLY (no Urdu script, no Hindi, no Roman Urdu). "
            "Keep it under 2 short sentences.\n"
            "- Example: 'Your order is 1 Zinger Burger for 650 rupees, 1 Fries for 250 rupees, and 1 Cold Drink for 150 rupees. "
            "Total is 1050 rupees for delivery to Peoples Colony Faisalabad. Should I confirm your order?'\n"
            "- Do NOT use markdown symbols (*, _, #), bullet points, or complex words so the audio synthesis remains fluent.\n"
        )
        voice_end_reminder = (
            "\nCRITICAL VOICE RULE: Your reply will be spoken aloud by an English TTS engine. "
            "You MUST reply strictly in simple, plain English ONLY (no Urdu script, no Hindi, no Roman Urdu). "
            "Keep it under 2 short sentences.\n"
        )

    history_mode_instruction = ""
    if has_prior_history:
        history_mode_instruction = (
            "\nACTIVE CONVERSATION INSTRUCTION:\n"
            "- An active conversation is ALREADY IN PROGRESS with this customer. Previous messages are in context above.\n"
            "- NEVER start your reply with a welcome greeting ('Welcome to...') or introductory pleasantries.\n"
            "- Continue the conversation directly and fulfill their confirmation or query without resetting.\n"
        )

    upsell_instruction = ""
    upsell_checkout_step = ""
    if context.get("enable_upselling", True):
        upsell_candidates = context.get("upsell_candidates") or []
        candidate_hint = ""
        if upsell_candidates:
            pairs = ", ".join(f"{u['name']} ({u['price_formatted']})" for u in upsell_candidates[:3])
            candidate_hint = f"\n- Top available add-ons right now: {pairs}."
        upsell_instruction = (
            "\nSMART UPSELLING & CROSS-SELLING RULES (MANDATORY BEFORE CHECKOUT, NON-PUSHY, CATALOG-GROUNDED):\n"
            "- Whenever a customer orders a main item and upselling has NOT yet been offered for the current order in the conversation history, "
            "you MUST call `get_upsell_suggestions` with their selected item names and suggest 1-2 real, currently available add-ons with their exact Rs. prices "
            "BEFORE (or in the exact same turn as) asking for their name, phone number, and delivery address. "
            "NEVER skip straight to checkout without offering an add-on first!"
            f"{candidate_hint}\n"
            "- Match the customer's language (e.g., English: 'Would you like to add Crispy Fries (Rs. 250) or a Cold Drink (Rs. 150)?' "
            "or Roman Urdu: 'Kya aap is ke sath Crispy Fries (Rs. 250) ya Cold Drink (Rs. 150) add karna chahenge?').\n"
            "- ASK ONLY ONCE PER ORDER: If you already suggested add-ons earlier in this order OR if the customer declines "
            "('nahi', 'nahi bas yehi', 'no thanks', 'no', 'bas'), immediately respect their decision and proceed directly to confirm/place the order without asking again.\n"
            "- If the customer accepts an add-on, include it in `create_order`. NEVER invent items or prices not in the catalog.\n"
        )
        upsell_checkout_step = (
            " If upselling has NOT been offered yet for this order, you MUST call `get_upsell_suggestions` and suggest 1-2 real available add-ons "
            "(with exact Rs. prices) in this exact turn right before or alongside asking for their name, phone, and address."
        )

    hospital_dept_section = ""
    if context.get("hospital_departments"):
        dept_lines = []
        for d in context["hospital_departments"]:
            tag = " [24/7]" if d.get("is_24_7") else ""
            beds = f" ({d.get('available_beds', 0)}/{d.get('total_beds', 0)} beds available)" if d.get("total_beds", 0) > 0 else ""
            dept_lines.append(f"• {d['name']} ({d.get('ward_type', 'opd').upper()}){tag}{beds}")
        hospital_dept_section = "\nHOSPITAL DEPARTMENTS, WARDS & BED AVAILABILITY:\n" + "\n".join(dept_lines) + "\n"

    return f"""You are the official AI Assistant for {biz_name} on WhatsApp.
Your primary role is {role_desc}.

BUSINESS DETAILS:
- Business Name: {biz_name}
- Business Vertical: {biz_type.title()}
- Brand Voice / Tone: {tone}
- Default Greeting: {greeting}
- Store Address: {address}
- Delivery Zones / Service Areas: {delivery_zones_str}
- Support Phone: {phone}
- Customer Name: {customer_name}

OPERATING HOURS:
{hours_str}

AVAILABLE {catalog_header}:
{catalog_str}
{hospital_dept_section}
FREQUENTLY ASKED QUESTIONS & POLICIES:
{kb_str}

VERTICAL-SPECIFIC INSTRUCTIONS:
{category_instructions}

GLOBAL HEALTH & DIETARY GUARDRAILS (PRD MANDATORY):
- Never diagnose medical conditions, prescribe prescription medications, or claim that any food, supplement, or product treats or cures any illness.
- If a customer mentions serious health symptoms, allergies, or acute conditions, use cautious, supportive language and explicitly advise them to consult a qualified physician or healthcare professional.
- Do not promise medical efficacy or replace clinical judgment.
{history_mode_instruction}
{voice_mode_instruction}
{upsell_instruction}

STRICT TOOL CALLING RULES:
1. Tool `get_catalog_items`:
   - Use when the customer asks what you sell, asks to see the menu/catalog, asks for prices, or searches for a product/service.
   - ROMAN URDU & URDU INQUIRIES: Phrases like 'menu bhej do', 'menu bhejo', 'pehle menu toh bhejo', 'menu dikhao', 'kya items hain', 'rate list', 'kya price hai' are 100% valid catalog requests. NEVER say you can only help with orders or deflect—immediately list the items and prices!
2. Tool `create_order`:
   - Active for ordering verticals. Use ONLY when the customer has specified what they want to order, provided their real full name and real phone number, AND provided their delivery address.
   - MANDATORY REAL CONTACT RULE: If the customer's real name or phone number is unknown (e.g., web voice customer or name is 'Valued Customer'), you MUST ask for their full name, phone number, and delivery address before confirming or creating an order. NEVER invent or guess a dummy phone number (e.g. '03001234567') or use 'Valued Customer'.
   - If the customer lists items to order but has NOT provided an address, name, or phone number yet: do NOT call `create_order`. Instead, list their selected items with prices in Rs., calculate the total in Rs.,{upsell_checkout_step} and ask them for their full name, phone number, and delivery address to confirm and place the order.
   - When spoken by the customer, extract their real name, phone number, and delivery address and combine with items from conversation history to immediately call `create_order`.
   - Under NO circumstances loop or ask "What would you like to order?" if the customer has already stated the items in prior turns. Maintain full multi-turn context and combine the remembered items with the provided address and contact details to call `create_order`.
   - When the customer provides their contact info and confirms (e.g., 'hanjee', 'hanjee krden', 'ji kar dein', 'haan', 'done', 'ok', 'confirm', 'yes', 'bhej do'): IMMEDIATELY call `create_order` using the items, name, phone, and address from the conversation history, and return the confirmation.
   - After `create_order` succeeds, provide a cheerful confirmation containing the *order number*, items, total in Pakistani Rupees (e.g., *Total:* Rs. 850.00), and estimated delivery time (30-45 mins).
   - KITCHEN NOTES & SPECIAL INSTRUCTIONS / ALLERGIES: If the customer mentions any dietary requests, allergies, preparation instructions, or food customizations (such as 'no onions', 'extra spicy', 'nut allergy', 'no mayo', 'less oil', 'no cheese', or delivery gate codes), you MUST capture them into the `notes` argument or item `special_instructions` when calling `create_order` so the kitchen and dispatch team are alerted.
   - DELIVERY AREA VALIDATION:
     * Our active delivery service areas are: {delivery_zones_str}.
     * Accept delivery addresses in or near {delivery_zones_str} naturally.
     * If a customer specifies a different city (outside {delivery_zones_str}), politely inform them that we currently only deliver within {delivery_zones_str}.
3. Tool `check_order_status`:
   - Use when the customer asks about order status, tracking, or previous orders.
4. Tool `log_unanswered_question`:
   - If a customer asks a genuine business policy or store question that is NOT answered by the catalog or FREQUENTLY ASKED QUESTIONS & POLICIES above (e.g. parking, halal certification, insurance accepted, return window, franchise info), call `log_unanswered_question` with their question so the business owner can approve an official FAQ answer, then politely inform the customer that our team will confirm. NEVER fabricate policies!

STRICT CONVERSATIONAL & LOCALIZATION RULES:
- MULTILINGUAL INQUIRIES: English, Urdu, and Pakistani Roman Urdu requests about menus, items, prices, orders, delivery, medicines, appointments, or products (e.g., 'menu', 'bhej', 'bhejo', 'dikhao', 'chahiye', 'order', 'rate', 'price', 'kya hai') are ALWAYS valid in-scope inquiries. NEVER reject them, and NEVER deflect with 'I can only help with food orders'.
- CURRENCY RULE: Always quote all prices in Pakistani Rupees using `Rs.` (never use `$` or dollars). When speaking in voice mode, speak naturally as 'rupees' (e.g., '850 rupees').
- FORBIDDEN HINDI VOCABULARY: Under NO circumstances use formal Hindi words (strictly FORBIDDEN: 'kripya', 'pushti', 'dhanyavaad', 'namaste', 'aabhar', 'kripya pushti karein'). Use natural Pakistani Roman Urdu (e.g. 'shukriya', 'theek hai', 'order confirm kar diya hai', 'bhej dein') or clear English.
- CONFIRMATION UNDERSTANDING: Understand Pakistani Roman Urdu confirmations such as 'hanjee', 'hanjee krden', 'ji kar dein', 'haan', 'done', 'ok', 'confirm', 'bhej do', 'yes' as YES to the previous order summary—immediately call the order placement tool (`create_order`) and confirm the order. NEVER reply with a welcome greeting if a conversation is already in progress.
- Under NO circumstances provide financial advice, programming code, political commentary, or general trivia. Politely decline and bring the conversation back to {biz_name}.
- Keep replies concise, natural, and formatted nicely for WhatsApp (*bold* for highlights/order numbers, clear line breaks, and emojis).
- Ground all facts strictly in the business context and tool outputs above. Never invent prices or items that do not exist in the store catalog.

CRITICAL COST-SAVING RULES:
- You are a voice-first agent. Humans do not want to listen to long monologues.
- Answer in strictly 1 to 2 short sentences. Maximum 20 words per response.
- NEVER use filler words, introductory pleasantries, or formatting like markdown/bullet points.
- Be highly direct and concise.
{voice_end_reminder}"""


def _build_fallback_reply(message_text: str, customer_name: str, context: Dict[str, Any]) -> str:
    """
    Polite fallback response if LLM API call fails or times out.
    """
    biz_name = context.get("business_name") or "our store"
    phone = context.get("phone")
    support_line = f"\n\nFor immediate assistance, please call us directly at *{phone}*." if phone else ""

    if context.get("has_prior_history"):
        return f"Thank you! We received your message: '_{message_text}_'. Our team will assist you shortly.{support_line}"

    greeting = context.get("greeting") or f"Hello {customer_name}! Welcome to *{biz_name}*."
    return (
        f"{greeting}\n\n"
        f"Thank you for contacting *{biz_name}*! We have received your message:\n"
        f"_{message_text}_\n\n"
        f"Our team is currently reviewing your inquiry and will reply shortly.{support_line}"
    )


def record_conversation_turn(
    company: Optional[Company],
    sender_phone: str,
    customer_name: str,
    message_text: str,
    reply_text: str,
    is_voice: bool = False,
    metadata: Optional[Dict[str, Any]] = None,
):
    """
    Persists customer message and assistant response into AgentConversation and AgentMessage.
    """
    if not company or not sender_phone:
        return
    try:
        from operations.models import AgentConversation, AgentMessage
        clean_name = customer_name if customer_name and customer_name != "Valued Customer" else "Customer"
        conv, _ = AgentConversation.objects.get_or_create(
            company=company,
            customer_phone=sender_phone,
            defaults={"customer_name": clean_name, "status": "bot"},
        )
        if clean_name != "Customer" and (not conv.customer_name or conv.customer_name == "Customer"):
            conv.customer_name = clean_name
            conv.save(update_fields=["customer_name", "updated_at"])

        AgentMessage.objects.create(
            conversation=conv,
            role="user",
            content=message_text,
            metadata=metadata or {},
        )
        AgentMessage.objects.create(
            conversation=conv,
            role="assistant",
            content=reply_text,
            metadata={"is_voice": is_voice},
        )
        conv.save(update_fields=["updated_at"])
    except Exception as e:
        logger.warning(f"[WhatsApp Agent] Could not record conversation turn: {e}")


# ============================================================================
# LLM Generation & Tool Execution Loop (OpenAI gpt-4o-mini)
# ============================================================================

def _generate_agent_reply(
    message_text: Any,
    customer_name: Any = "Valued Customer",
    context: Any = None,
    sender_phone: str = "",
    is_voice_note: bool = False,
    record_turn: bool = True,
    conversation_obj: Optional[Any] = None,
) -> str:
    """
    Generates a dynamic response using OpenAI's gpt-4o-mini model with full tool calling:
    1. Loads recent conversation history from AgentConversation / AgentMessage to maintain multi-turn memory.
    2. Sends user message with registered tools (get_catalog_items, create_order, check_order_status).
    3. If the LLM requests tool execution, executes the function with multi-tenant isolation.
    4. Feeds tool outputs back into the conversation for a second pass to produce natural confirmation.

    Supports both standard call:
        _generate_agent_reply(message_text, customer_name, context, sender_phone, is_voice_note)
    and test / convenience call:
        _generate_agent_reply(company, sender_phone, message_text)
    """
    # Defensive normalization: Support test/convenience calls
    if isinstance(message_text, Company):
        company_obj = message_text
        actual_phone = str(customer_name or "")
        actual_message = str(context or "")
        customer_name = "Valued Customer"
        sender_phone = actual_phone
        message_text = actual_message
        context = get_business_context_for_company(company_obj)
    elif isinstance(context, Company):
        context = get_business_context_for_company(context)
    elif not isinstance(context, dict):
        if isinstance(customer_name, Company):
            context = get_business_context_for_company(customer_name)
            customer_name = "Valued Customer"
        else:
            context = get_business_context_for_company(None)

    company = context.get("company")
    if not company:
        return _build_fallback_reply(message_text, customer_name, context)

    # Multi-turn memory: Load recent conversation history (last 12 messages from past 24 hours or conversation_obj)
    history_messages: List[Dict[str, str]] = []
    has_prior_history = False

    if conversation_obj:
        try:
            msgs = list(conversation_obj.messages.order_by("-created_at")[:13])
            # If the most recent message matches the current turn's user message, skip it
            if msgs and msgs[0].role == "user" and (msgs[0].content or "").strip() == str(message_text).strip():
                msgs = msgs[1:]
            msgs.reverse()
            for m in msgs:
                role = "assistant" if m.role == "assistant" else "user"
                content_str = (m.content or "").strip()
                if content_str:
                    history_messages.append({"role": role, "content": content_str})
            if history_messages:
                has_prior_history = True
        except Exception as e:
            logger.warning(f"[WhatsApp Agent] Could not load history from conversation_obj: {e}")
    elif company and sender_phone:
        try:
            from operations.models import AgentConversation
            from datetime import timedelta
            conv = AgentConversation.objects.filter(company=company, customer_phone=sender_phone).last()
            if conv:
                recent_msgs = list(
                    conv.messages.filter(created_at__gte=timezone.now() - timedelta(hours=24))
                    .order_by("-created_at")[:12]
                )
                recent_msgs.reverse()
                for m in recent_msgs:
                    role = "assistant" if m.role == "assistant" else "user"
                    content_str = (m.content or "").strip()
                    if content_str:
                        history_messages.append({"role": role, "content": content_str})
                if history_messages:
                    has_prior_history = True
        except Exception as e:
            logger.warning(f"[WhatsApp Agent] Could not load conversation history: {e}")

    # Strict LLM sliding window cap (max 12 recent messages) to keep token costs flat
    history_messages = history_messages[-12:]
    context["has_prior_history"] = has_prior_history

    api_key = getattr(settings, "OPENAI_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")
    model = getattr(settings, "OPENAI_MODEL", "gpt-4o-mini")

    if api_key and len(api_key.strip()) > 10:
        try:
            client = OpenAI(api_key=api_key.strip(), timeout=25.0)
            system_prompt = _build_system_prompt(
                customer_name=customer_name,
                context=context,
                is_voice_note=is_voice_note,
                has_prior_history=has_prior_history,
            )

            messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
            messages.extend(history_messages)
            if is_voice_note:
                messages.append({
                    "role": "system",
                    "content": (
                        "CRITICAL VOICE RULE: Your reply will be spoken aloud by an English TTS engine. "
                        "You MUST reply strictly in simple, plain English ONLY (no Urdu script, no Hindi, no Roman Urdu). "
                        "Keep it under 2 short sentences."
                    ),
                })
            messages.append({"role": "user", "content": message_text})

            llm_max_tokens = int(getattr(settings, "OPENAI_MAX_TOKENS", 200))
            biz_type = context.get("business_type") or "restaurant"
            cat_cfg = get_category_agent_config(biz_type)
            active_tools = list(cat_cfg.get("tools") or AGENT_TOOLS)
            if not context.get("enable_upselling", True):
                active_tools = [t for t in active_tools if t.get("function", {}).get("name") != "get_upsell_suggestions"]

            response = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=active_tools,
                tool_choice="auto",
                temperature=0.3,
                max_tokens=llm_max_tokens,
            )

            response_msg = response.choices[0].message
            tool_calls = getattr(response_msg, "tool_calls", None)

            if tool_calls:
                logger.info(f"[WhatsApp Agent] LLM triggered {len(tool_calls)} tool call(s).")
                # Append the assistant's initial response (containing tool_calls) to conversation history
                messages.append(response_msg)

                for tc in tool_calls:
                    fn_name = tc.function.name
                    raw_args = tc.function.arguments or "{}"
                    try:
                        fn_args = json.loads(raw_args)
                    except Exception:
                        fn_args = {}

                    logger.info(f"[WhatsApp Agent] Executing tool '{fn_name}' with args: {fn_args}")

                    tool_result = {}
                    if fn_name == "get_catalog_items":
                        tool_result = execute_get_catalog_items(
                            company=company,
                            search_query=fn_args.get("search_query"),
                        )
                    elif fn_name == "get_upsell_suggestions":
                        suggestions = get_upsell_suggestions(
                            company=company,
                            ordered_item_names=fn_args.get("ordered_item_names") or [],
                            max_suggestions=3,
                        )
                        tool_result = {
                            "enabled": bool(getattr(company, "enable_upselling", True)),
                            "suggestions": suggestions,
                        }
                    elif fn_name == "create_order":
                        phone_arg = (fn_args.get("customer_phone") or "").strip() or sender_phone
                        if not phone_arg and conversation_obj and conversation_obj.customer_phone:
                            phone_arg = conversation_obj.customer_phone.strip()
                        name_arg = (fn_args.get("customer_name") or "").strip() or customer_name
                        if (not name_arg or name_arg == "Valued Customer") and conversation_obj and conversation_obj.customer_name:
                            name_arg = conversation_obj.customer_name.strip()

                        tool_result = execute_create_order(
                            company=company,
                            customer_name=name_arg,
                            customer_phone=phone_arg,
                            items=fn_args.get("items", []),
                            delivery_address=fn_args.get("delivery_address", ""),
                            notes=fn_args.get("notes", ""),
                            order_type=fn_args.get("order_type"),
                            table_number=fn_args.get("table_number"),
                        )
                        if tool_result.get("success"):
                            context["order_summary"] = {
                                "order_number": tool_result.get("order_number"),
                                "total": str(tool_result.get("total", "0.00")),
                                "status": "confirmed",
                            }
                            context["last_tool_result"] = tool_result
                            if conversation_obj:
                                updated_fields = []
                                real_name = tool_result.get("customer_name") or name_arg
                                real_phone = phone_arg
                                if real_name and real_name.lower() not in ("valued customer", "customer", "guest"):
                                    if not conversation_obj.customer_name or conversation_obj.customer_name.lower() in ("valued customer", "customer", "guest"):
                                        conversation_obj.customer_name = real_name
                                        updated_fields.append("customer_name")
                                if real_phone and len(re.sub(r"\D", "", real_phone)) >= 10:
                                    if not conversation_obj.customer_phone or conversation_obj.customer_phone in DUMMY_PHONES:
                                        conversation_obj.customer_phone = real_phone
                                        updated_fields.append("customer_phone")
                                if updated_fields:
                                    updated_fields.append("updated_at")
                                    try:
                                        conversation_obj.save(update_fields=updated_fields)
                                    except Exception as err:
                                        logger.warning(f"[WhatsApp Agent] Could not update conversation customer info: {err}")
                    elif fn_name == "check_order_status":
                        tool_result = execute_check_order_status(
                            company=company,
                            customer_phone=fn_args.get("customer_phone") or sender_phone,
                            order_number=fn_args.get("order_number"),
                        )
                    elif fn_name == "submit_prescription_request":
                        tool_result = execute_submit_prescription_request(
                            company=company,
                            customer_phone=fn_args.get("customer_phone") or sender_phone,
                            requested_items=fn_args.get("requested_items", ""),
                            customer_name=fn_args.get("customer_name") or customer_name,
                            notes=fn_args.get("notes", ""),
                        )
                    elif fn_name == "get_clinic_doctors":
                        tool_result = execute_get_clinic_doctors(
                            company=company,
                            specialty=fn_args.get("specialty"),
                        )
                    elif fn_name == "book_appointment":
                        tool_result = execute_book_appointment(
                            company=company,
                            sender_phone=sender_phone,
                            patient_name=fn_args.get("patient_name") or customer_name,
                            doctor_name=fn_args.get("doctor_name"),
                            preferred_date=fn_args.get("preferred_date"),
                            preferred_time=fn_args.get("preferred_time"),
                            reason=fn_args.get("reason"),
                        )
                    elif fn_name == "get_hospital_departments":
                        tool_result = execute_get_hospital_departments(
                            company=company,
                            ward_type=fn_args.get("ward_type"),
                        )
                    elif fn_name == "book_lab_test":
                        tool_result = execute_book_lab_test(
                            company=company,
                            sender_phone=fn_args.get("patient_phone") or sender_phone,
                            patient_name=fn_args.get("patient_name") or customer_name,
                            test_name=fn_args.get("test_name", ""),
                            scheduled_date=fn_args.get("scheduled_date"),
                            scheduled_time=fn_args.get("scheduled_time"),
                            notes=fn_args.get("notes", ""),
                        )
                    elif fn_name == "log_unanswered_question":
                        ch = "whatsapp" if (sender_phone and not conversation_obj) else "public_web"
                        tool_result = log_unanswered_question(
                            company=company,
                            question=fn_args.get("question") or str(message_text),
                            draft_answer=fn_args.get("draft_answer", ""),
                            source_channel=ch,
                        )
                    elif fn_name == "submit_return_request":
                        tool_result = execute_submit_return_request(
                            company=company,
                            sender_phone=sender_phone,
                            customer_name=fn_args.get("customer_name") or customer_name,
                            order_number=fn_args.get("order_number"),
                            item_summary=fn_args.get("item_summary"),
                            reason=fn_args.get("reason"),
                            request_type=fn_args.get("request_type") or "return",
                        )
                    else:
                        tool_result = {"error": f"Tool '{fn_name}' is not recognized."}

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(tool_result),
                    })

                if is_voice_note:
                    messages.append({
                        "role": "system",
                        "content": (
                            "CRITICAL VOICE RULE: Your reply will be spoken aloud by an English TTS engine. "
                            "You MUST reply strictly in simple, plain English ONLY (no Urdu script, no Hindi, no Roman Urdu). "
                            "Keep it under 2 short sentences."
                        ),
                    })

                # Second completion pass to generate customer-facing response based on tool results
                second_response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.3,
                    max_tokens=llm_max_tokens,
                )
                final_content = second_response.choices[0].message.content
                if final_content and final_content.strip():
                    reply = final_content.strip()
                    if record_turn:
                        record_conversation_turn(company, sender_phone, customer_name, message_text, reply, is_voice=is_voice_note)
                    return reply

            elif response_msg.content and response_msg.content.strip():
                reply = response_msg.content.strip()
                if record_turn:
                    record_conversation_turn(company, sender_phone, customer_name, message_text, reply, is_voice=is_voice_note)
                return reply

        except Exception as e:
            logger.error(f"[WhatsApp Agent] OpenAI tool-calling execution error: {e}", exc_info=True)
            print(f"[WhatsApp Agent ERROR] Tool calling failed: {e}")

    # Fallback when OpenAI key is missing, invalid, or request fails
    fallback_reply = _build_fallback_reply(message_text, customer_name, context)
    if record_turn:
        record_conversation_turn(company, sender_phone, customer_name, message_text, fallback_reply, is_voice=is_voice_note)
    return fallback_reply


# ============================================================================
# Main Entrypoint: Process Incoming WhatsApp Message
# ============================================================================

def check_and_enforce_voice_limit(
    company: Company,
    phone: str,
    customer_name: Optional[str] = None,
) -> tuple[bool, Optional[str], Customer]:
    """
    Checks if a customer has reached their daily voice note limit for the company.
    Resets the count to 0 if last_voice_date is older than today.
    Returns (False, limit_msg, customer) if limit exceeded.
    Returns (True, None, customer) and increments daily_voice_count if within limit.
    """
    today = timezone.now().date()
    customer, _ = Customer.objects.get_or_create(
        company=company,
        phone=phone,
        defaults={
            "name": customer_name or "",
            "daily_voice_count": 0,
            "last_voice_date": today,
        },
    )

    if customer.last_voice_date != today:
        customer.daily_voice_count = 0
        customer.last_voice_date = today

    max_limit = getattr(company, "max_daily_voice_notes", 15)
    if customer.daily_voice_count >= max_limit:
        customer.save(update_fields=["daily_voice_count", "last_voice_date"])
        limit_msg = (
            "⏳ You have reached the daily limit for voice messages. "
            "Please type your order or continue via text."
        )
        return False, limit_msg, customer

    customer.daily_voice_count += 1
    customer.last_voice_date = today
    customer.save(update_fields=["daily_voice_count", "last_voice_date"])
    return True, None, customer


def check_and_enforce_text_limit(
    company: Company,
    phone: str,
    customer_name: Optional[str] = None,
) -> tuple[bool, Optional[str], Customer]:
    """
    Checks if a customer has reached their daily text message limit for the company.
    Resets the count to 0 if last_text_date is older than today.
    Returns (False, limit_msg, customer) if limit exceeded.
    Returns (True, None, customer) and increments daily_text_count if within limit.
    """
    today = timezone.now().date()
    customer, _ = Customer.objects.get_or_create(
        company=company,
        phone=phone,
        defaults={
            "name": customer_name or "",
            "daily_text_count": 0,
            "last_text_date": today,
        },
    )

    if customer.last_text_date != today:
        customer.daily_text_count = 0
        customer.last_text_date = today

    max_limit = getattr(company, "max_daily_text_messages", 50)
    if customer.daily_text_count >= max_limit:
        customer.save(update_fields=["daily_text_count", "last_text_date"])
        limit_msg = (
            "⏳ You have reached the maximum message limit for today. "
            "A human agent will assist you shortly."
        )
        return False, limit_msg, customer

    customer.daily_text_count += 1
    customer.last_text_date = today
    customer.save(update_fields=["daily_text_count", "last_text_date"])
    return True, None, customer


def _dispatch_whatsapp_text(
    company: Optional[Company],
    phone: str,
    text: str,
    service: Optional[WhatsAppService] = None,
) -> Dict[str, Any]:
    """
    Routes outbound WhatsApp text message:
    - If company has `whatsapp_instance_name`, routes via Evolution API.
    - Otherwise, falls back to Meta WhatsAppService untouched.
    """
    instance_name = getattr(company, "whatsapp_instance_name", None) if company else None
    if instance_name:
        from operations import evolution_client
        logger.info(f"[WhatsApp Routing] Dispatching text via Evolution API (instance: {instance_name}) to {phone}")
        res = evolution_client.send_text_message(instance_name=instance_name, phone=phone, text=text)
        success = bool(res and not res.get("error") and res.get("success") is not False)
        if not success:
            logger.error(f"[WhatsApp Routing ERROR] Evolution text dispatch failed (instance: {instance_name}) -> {phone}: {res}")
        return {
            "success": success,
            "data": res,
            "provider": "evolution",
        }

    if service:
        return service.send_text_message(to=phone, text=text)
    return {"success": False, "error": "No WhatsApp provider configured"}


def _dispatch_whatsapp_audio(
    company: Optional[Company],
    phone: str,
    audio_bytes: bytes,
    service: Optional[WhatsAppService] = None,
) -> Dict[str, Any]:
    """
    Routes outbound WhatsApp audio voice note:
    - If company has `whatsapp_instance_name`, routes via Evolution API as base64 audio.
    - Otherwise, falls back to Meta WhatsAppService (upload_media -> send_audio_message).
    """
    import base64
    instance_name = getattr(company, "whatsapp_instance_name", None) if company else None
    if instance_name:
        from operations import evolution_client
        logger.info(f"[WhatsApp Routing] Dispatching audio via Evolution API (instance: {instance_name}) to {phone}")
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
        res = evolution_client.send_audio_message(instance_name=instance_name, phone=phone, audio_base64=audio_b64)
        success = bool(res and not res.get("error") and res.get("success") is not False)
        if not success:
            logger.error(f"[WhatsApp Routing ERROR] Evolution audio dispatch failed (instance: {instance_name}) -> {phone}: {res}")
        return {
            "success": success,
            "data": res,
            "provider": "evolution",
        }

    if service:
        outbound_media_id = service.upload_media(audio_bytes, mime_type="audio/ogg")
        if outbound_media_id:
            return service.send_audio_message(to=phone, media_id=outbound_media_id)
        return {"success": False, "error": "Media upload failed"}

    return {"success": False, "error": "No WhatsApp provider configured"}


def _safe_close_old_connections() -> None:
    """Close stale DB connections in background threads without disrupting active transactions."""
    from django.db import connection
    if not connection.in_atomic_block:
        close_old_connections()


def process_incoming_whatsapp_message(
    sender_phone: str,
    message_text: str,
    phone_number_id: str,
    customer_name: Optional[str] = None,
    media_id: Optional[str] = None,
    msg_type: str = "text",
    company: Optional[Company] = None,
    audio_bytes: Optional[bytes] = None,
) -> Dict[str, Any]:
    """
    Main background entrypoint for processing an incoming WhatsApp customer message:
    1. Multi-Tenant Guard: Validates that destination phone_number_id belongs to a registered company.
    2. Voice/Text Rate Limit & Cost Guard: Checks customer usage against daily quotas.
    3. Voice Input (STT): If audio note (.ogg), downloads via Meta Graph API or uses provided audio_bytes, and transcribes via Groq/Whisper.
    4. Tool-Calling Agent: Runs LLM with dynamic tool calling (get_catalog_items, create_order, check_order_status).
    5. Voice Output (TTS): If customer sent audio, synthesizes speech and uploads via Meta API or Evolution API.
    6. Dispatches reply via Evolution API (if instance configured) or Meta Cloud API using WhatsAppService.
    """
    _safe_close_old_connections()
    try:
        clean_name = customer_name or "Valued Customer"
        service = WhatsAppService(phone_number_id=phone_number_id)

        # Step 1: Multi-Tenant Isolation Check (Fail Closed)
        if company:
            context = get_business_context_for_company(company)
        else:
            context = _get_business_context(phone_number_id)

        if not context.get("is_configured") or not context.get("company"):
            logger.warning(
                f"[WhatsApp Agent] Access rejected: phone_number_id '{phone_number_id}' "
                "is not configured with an active company."
            )
            unconfigured_reply = (
                "Thank you for reaching out! This WhatsApp business line is not yet active "
                "or configured for online customer service. Please contact the business administrator."
            )
            service.send_text_message(to=sender_phone, text=unconfigured_reply)
            return {
                "success": False,
                "error": "Unconfigured WhatsApp phone_number_id",
                "reply_text": unconfigured_reply,
            }

        company_obj = context.get("company")

        # Owner AI Pause Check (Manual Takeover):
        if getattr(company_obj, "is_ai_paused", False):
            logger.info(
                f"[WhatsApp Agent] Company '{company_obj.name}' AI Agent is paused by owner. "
                f"Saving customer message from {sender_phone} to AgentConversation for manual response."
            )
            try:
                clean_name = customer_name if customer_name and customer_name != "Valued Customer" else "Customer"
                conv, _ = AgentConversation.objects.get_or_create(
                    company=company_obj,
                    customer_phone=sender_phone,
                    defaults={"customer_name": clean_name, "status": "human"},
                )
                conv.status = "human"
                conv.save(update_fields=["status", "updated_at"])
                is_voice_msg = (msg_type == "audio" or bool(media_id) or bool(audio_bytes))
                AgentMessage.objects.create(
                    conversation=conv,
                    role="user",
                    content=message_text or ("[Voice Message]" if is_voice_msg else "[Customer Message]"),
                    metadata={"is_voice": is_voice_msg, "ai_paused": True},
                )
            except Exception as e:
                logger.warning(f"[WhatsApp Agent] Failed to save paused incoming message: {e}")

            return {
                "success": True,
                "ai_paused": True,
                "reply_text": None,
                "message": "AI Agent is paused by owner; customer message logged for manual response.",
            }

        from billing.services import get_access_state, consume_company_message
        access_state = get_access_state(company_obj)
        if access_state != "ok":
            logger.warning(
                f"[WhatsApp Agent] Company '{company_obj.name}' subscription is inactive (status: {access_state}). "
                f"Rejecting message from {sender_phone}."
            )
            inactive_reply = (
                f"Thank you for contacting {company_obj.name}. Our automated assistant is currently unavailable. "
                f"Please reach out to us directly."
            )
            _dispatch_whatsapp_text(company=company_obj, phone=sender_phone, text=inactive_reply, service=service)
            return {
                "success": False,
                "error": "subscription_inactive",
                "reply_text": inactive_reply,
            }

        try:
            consume_company_message(company_obj, count=1)
        except Exception as e:
            logger.warning(
                f"[WhatsApp Agent] Company '{company_obj.name}' monthly message/voice limit reached: {e}. "
                f"Rejecting message from {sender_phone}."
            )
            limit_reply = (
                f"Thank you for contacting {company_obj.name}. Our automated voice and messaging assistant has "
                f"reached its monthly limit. Please contact us directly at {company_obj.phone or 'our official number'}."
            )
            _dispatch_whatsapp_text(company=company_obj, phone=sender_phone, text=limit_reply, service=service)
            return {
                "success": False,
                "error": "monthly_limit_reached",
                "reply_text": limit_reply,
            }

        # Step 2: Audio / Voice Message Cost & Rate Limiting Check
        is_voice_message = (msg_type == "audio" or bool(media_id) or bool(audio_bytes))
        if is_voice_message:
            allowed, limit_msg, customer = check_and_enforce_voice_limit(
                company=company_obj,
                phone=sender_phone,
                customer_name=clean_name if clean_name != "Valued Customer" else None,
            )
            if not allowed:
                logger.warning(
                    f"[WhatsApp Voice Agent] Customer {sender_phone} reached daily voice limit "
                    f"for company '{company_obj.name}'. Rejecting audio processing and dispatching warning text."
                )
                print(f"[WhatsApp Voice Agent] Customer {sender_phone} exceeded voice limit. Blocking audio processing.")
                dispatch_res = _dispatch_whatsapp_text(company=company_obj, phone=sender_phone, text=limit_msg, service=service)
                return {
                    "success": dispatch_res.get("success", False) if isinstance(dispatch_res, dict) else True,
                    "reply_text": limit_msg,
                    "rate_limited": True,
                    "dispatch_result": dispatch_res,
                }

            if audio_bytes:
                logger.info(f"[WhatsApp Voice Agent] Transcribing provided audio bytes ({len(audio_bytes)} bytes) for {sender_phone}...")
                print(f"[WhatsApp Voice Agent] Transcribing provided voice note ({len(audio_bytes)} bytes) for {sender_phone}...")
                transcription = transcribe_audio(audio_bytes, filename="audio.ogg")
                if transcription and transcription.strip():
                    message_text = transcription.strip()
                    logger.info(f"[WhatsApp Voice Agent] STT transcribed text: '{message_text}'")
                    print(f"[WhatsApp Voice Agent STT] Customer voice note transcribed: '{message_text}'")
                else:
                    logger.warning("[WhatsApp Voice Agent] Voice transcription returned empty.")
                    message_text = "I received your voice message but couldn't make out the words. Could you please send it again?"
            elif media_id:
                logger.info(f"[WhatsApp Voice Agent] Downloading audio media {media_id} for {sender_phone}...")
                print(f"[WhatsApp Voice Agent] Received voice note from {sender_phone} (Media ID: {media_id}). Downloading...")
                downloaded_audio = service.download_media_file(media_id)
                if downloaded_audio:
                    transcription = transcribe_audio(downloaded_audio, filename="audio.ogg")
                    if transcription and transcription.strip():
                        message_text = transcription.strip()
                        logger.info(f"[WhatsApp Voice Agent] STT transcribed text: '{message_text}'")
                        print(f"[WhatsApp Voice Agent STT] Customer voice note transcribed: '{message_text}'")
                    else:
                        logger.warning("[WhatsApp Voice Agent] Voice transcription returned empty.")
                        message_text = "I received your voice message but couldn't make out the words. Could you please send it again?"
                else:
                    logger.error(f"[WhatsApp Voice Agent] Failed to download audio media {media_id}.")
                    message_text = "I received your voice note, but could not download the audio file. Please try sending your message again."
            else:
                logger.error(f"[WhatsApp Voice Agent] No audio bytes or valid media ID available for {sender_phone}. Skipping audio download.")
                message_text = "I received your voice note, but could not process the audio file. Please send a text message instead."
        else:
            # Step 2b: Text Message Cost & Rate Limiting Check
            company_obj = context.get("company")
            allowed, limit_msg, customer = check_and_enforce_text_limit(
                company=company_obj,
                phone=sender_phone,
                customer_name=clean_name if clean_name != "Valued Customer" else None,
            )
            if not allowed:
                logger.warning(
                    f"[WhatsApp Text Agent] Customer {sender_phone} reached daily text limit "
                    f"for company '{company_obj.name}'. Rejecting text and triggering human handover."
                )
                print(f"[WhatsApp Text Agent] Customer {sender_phone} exceeded text limit. Bypassing LLM.")
                # Set AgentConversation status to human
                try:
                    conv = AgentConversation.objects.filter(
                        company=company_obj, customer_phone=sender_phone
                    ).order_by("id").last()
                    if conv:
                        conv.status = "human"
                        conv.save(update_fields=["status"])
                except Exception as e:
                    logger.warning(f"[WhatsApp Text Agent] Could not update conversation status: {e}")

                dispatch_res = _dispatch_whatsapp_text(company=company_obj, phone=sender_phone, text=limit_msg, service=service)
                return {
                    "success": dispatch_res.get("success", False) if isinstance(dispatch_res, dict) else True,
                    "reply_text": limit_msg,
                    "rate_limited": True,
                    "dispatch_result": dispatch_res,
                }

        from operations.audio_service import transliterate_to_roman_urdu
        message_text = transliterate_to_roman_urdu(message_text)

        logger.info(f"[WhatsApp Agent] Processing incoming message from {sender_phone} ({clean_name}): '{message_text}'")
        print(f"[WhatsApp Agent] Processing message from {sender_phone}: '{message_text}'")

        # Step 3: Dynamic LLM Generation with Tool Calling Loop
        reply_text = _generate_agent_reply(
            message_text=message_text,
            customer_name=clean_name,
            context=context,
            sender_phone=sender_phone,
            is_voice_note=is_voice_message,
        )

        # Step 4: Outbound WhatsApp dispatch (Multi-Tenant Routing: Evolution API or Meta Cloud API)
        dispatch_result = None
        is_voice_dispatched = False
        company_obj = context.get("company")

        # Voice-first response: Prioritize replying with a Voice Note (TTS) for every response
        logger.info(f"[WhatsApp Voice Agent] Voice-First Policy: Synthesizing voice reply for {sender_phone}...")
        print(f"[WhatsApp Voice Agent] Synthesizing TTS voice note for {sender_phone}...")

        from operations.audio_service import clean_text_for_tts
        tts_text = clean_text_for_tts(reply_text)

        audio_bytes = synthesize_speech(tts_text)
        if audio_bytes:
            audio_res = _dispatch_whatsapp_audio(company=company_obj, phone=sender_phone, audio_bytes=audio_bytes, service=service)
            if audio_res and audio_res.get("success"):
                dispatch_result = audio_res
                is_voice_dispatched = True

                # Optionally send a short clean text/caption ONLY when displaying structured details
                # like a menu list, order summary, or invoice reference
                lower_reply = reply_text.lower()
                has_structured_details = any(
                    marker in lower_reply for marker in [
                        "#ra-", "#ord-", "rs.", "total:", "order #", "prescription #",
                        "appointment #", "return #", "menu", "catalog", "rupees",
                        "#rx-", "#apt-", "\n-", "\n*", "\n•", "\n1.", "\n2."
                    ]
                )
                if has_structured_details:
                    logger.info(f"[WhatsApp Voice Agent] Sending accompanying structured text summary to {sender_phone}...")
                    _dispatch_whatsapp_text(company=company_obj, phone=sender_phone, text=reply_text, service=service)
            else:
                logger.warning("[WhatsApp Voice Agent] Audio dispatch failed. Falling back to text message.")
                print("[WhatsApp Voice Agent Warning] Audio dispatch failed. Falling back to text.")
        else:
            logger.info("[WhatsApp Voice Agent] TTS audio not generated or unavailable. Falling back to text message.")

        # Fallback to text message if voice response was not used or failed
        if not dispatch_result or not dispatch_result.get("success"):
            dispatch_result = _dispatch_whatsapp_text(company=company_obj, phone=sender_phone, text=reply_text, service=service)

        # Step 5: Update message metadata if audio/voice dispatched
        if is_voice_dispatched:
            try:
                conv = AgentConversation.objects.filter(company=company_obj, customer_phone=sender_phone).last()
                if conv:
                    last_msg = conv.messages.last()
                    if last_msg:
                        last_msg.metadata = dict(last_msg.metadata or {}, is_voice=True)
                        last_msg.save(update_fields=["metadata"])
            except Exception:
                pass

        logger.info(f"[WhatsApp Agent] Dispatch result for {sender_phone}: {dispatch_result.get('success')}")
        return {
            "success": dispatch_result.get("success", False),
            "reply_text": reply_text,
            "transcribed_text": message_text if is_voice_message else None,
            "is_voice_response": is_voice_dispatched,
            "dispatch_result": dispatch_result,
        }

    except Exception as e:
        logger.error(f"[WhatsApp Agent] Unhandled error processing incoming message: {e}", exc_info=True)
        print(f"[WhatsApp Agent ERROR] {e}")
        return {"success": False, "error": str(e)}

    finally:
        _safe_close_old_connections()
