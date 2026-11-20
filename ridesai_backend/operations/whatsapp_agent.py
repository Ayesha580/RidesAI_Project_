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
                                "description": "Optional preparation notes (e.g. 'no onions', 'extra spicy').",
                            },
                        },
                        "required": ["item_name", "quantity"],
                    },
                },
                "customer_name": {
                    "type": "string",
                    "description": "Name of the customer placing the order.",
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

AGENT_TOOLS = [
    TOOL_GET_CATALOG_ITEMS,
    TOOL_CREATE_ORDER,
    TOOL_CHECK_ORDER_STATUS,
    TOOL_SUBMIT_PRESCRIPTION_REQUEST,
    TOOL_GET_CLINIC_DOCTORS,
    TOOL_BOOK_APPOINTMENT,
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
        "tools": [TOOL_GET_CATALOG_ITEMS, TOOL_CREATE_ORDER, TOOL_CHECK_ORDER_STATUS],
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
        "tools": [TOOL_GET_CATALOG_ITEMS, TOOL_CREATE_ORDER, TOOL_CHECK_ORDER_STATUS, TOOL_SUBMIT_PRESCRIPTION_REQUEST],
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
        "tools": [TOOL_GET_CLINIC_DOCTORS, TOOL_BOOK_APPOINTMENT, TOOL_GET_CATALOG_ITEMS, TOOL_CHECK_ORDER_STATUS],
    },
    "retail": {
        "key": "retail",
        "role_desc": "retail store assistant and product ordering support",
        "catalog_header": "STORE CATALOG & INVENTORY",
        "instructions": (
            "- Primary duty is helping shoppers explore available retail merchandise, checking product stock, "
            "and taking orders with delivery address."
        ),
        "tools": [TOOL_GET_CATALOG_ITEMS, TOOL_CREATE_ORDER, TOOL_CHECK_ORDER_STATUS],
    },
}


def get_category_agent_config(business_type: Optional[str]) -> Dict[str, Any]:
    """
    Returns the modular agent profile configuration for a business vertical.
    Resolves keywords to restaurant, pharmacy, clinic, or retail.
    """
    raw = (business_type or "").strip().lower()
    if any(k in raw for k in ("pharm", "med", "chemist", "drug")):
        return CATEGORY_AGENT_PROFILES["pharmacy"]
    if any(k in raw for k in ("clinic", "hosp", "doctor", "health", "dental", "physio")):
        return CATEGORY_AGENT_PROFILES["clinic"]
    if any(k in raw for k in ("retail", "store", "shop", "supermarket", "grocery", "mart", "general")):
        return CATEGORY_AGENT_PROFILES["retail"]
    # Default to restaurant
    return CATEGORY_AGENT_PROFILES["restaurant"]


# ============================================================================
# Tool Execution Functions (Atomic Database Transactions & Multi-Tenant Guarded)
# ============================================================================

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
) -> Dict[str, Any]:
    """
    Executes a multi-tenant isolated database transaction creating Order, OrderItem,
    and OrderEvent records with inventory deduction and audit trail.
    """
    if not items:
        return {"success": False, "error": "No items provided in order request."}
    if not delivery_address or not delivery_address.strip():
        return {"success": False, "error": "Delivery address is required to place an order."}

    clean_name = (customer_name or "").strip() or "Valued Customer"
    clean_phone = (customer_phone or "").strip()
    clean_notes = (notes or "").strip()

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

                line_total = qty * catalog_item.price
                subtotal += line_total
                resolved_items.append({
                    "catalog_item": catalog_item,
                    "item_name": catalog_item.name,
                    "quantity": qty,
                    "unit_price": catalog_item.price,
                    "line_total": line_total,
                    "inventory": inv,
                    "notes": raw_item.get("special_instructions", ""),
                })

            # Create Order
            order = Order.objects.create(
                company=company,
                customer_name=clean_name,
                customer_phone=clean_phone,
                delivery_address=delivery_address.strip(),
                status=Order.STATUS_NEW,
                subtotal=subtotal,
                delivery_fee=Decimal("0.00"),
                total=subtotal,
                notes=clean_notes,
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


# ============================================================================
# Business Context & Prompt Building (Multi-Tenant Hardened)
# ============================================================================

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
            .values("id", "name", "price", "description")[:40]
        )
        context["catalog"] = items

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

        # Fetch active delivery service areas / zones
        zones = []
        try:
            zones = list(company.service_areas.filter(is_active=True).values_list("city", flat=True))
        except Exception:
            pass
        context["delivery_zones"] = [z for z in zones if z]
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

    # Format catalog items
    catalog_lines = []
    for item in context.get("catalog", []):
        price = f"Rs. {float(item['price']):.2f}" if item.get("price") else "Price on request"
        desc = f" - {item['description']}" if item.get("description") else ""
        catalog_lines.append(f"• {item['name']}: {price}{desc}")
    
    if catalog_lines:
        catalog_str = "\n".join(catalog_lines)
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

STRICT TOOL CALLING RULES:
1. Tool `get_catalog_items`:
   - Use when the customer asks what you sell, asks to see the menu/catalog, asks for prices, or searches for a product/service.
2. Tool `create_order`:
   - Active for ordering verticals. Use ONLY when the customer has specified what they want to order AND provided their delivery address.
   - If the customer lists items to order but has NOT provided an address yet: do NOT call `create_order`. Instead, list their selected items with prices in Rs., calculate the total in Rs., and ask them: "Please provide your delivery address to confirm and place your order."
   - If items and address are already discussed, ask the customer for final confirmation or confirm the order.
   - When the customer confirms (e.g., 'hanjee', 'hanjee krden', 'ji kar dein', 'haan', 'done', 'ok', 'confirm', 'yes', 'bhej do'): IMMEDIATELY call `create_order` using the items and address from the conversation history, and return the confirmation.
   - After `create_order` succeeds, provide a cheerful confirmation containing the *order number*, items, total in Pakistani Rupees (e.g., *Total:* Rs. 850.00), and estimated delivery time (30-45 mins).
3. Tool `check_order_status`:
   - Use when the customer asks about order status, tracking, or previous orders.

STRICT CONVERSATIONAL & LOCALIZATION RULES:
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

    # Multi-turn memory: Load recent conversation history (last 10 messages from past 24 hours)
    history_messages: List[Dict[str, str]] = []
    has_prior_history = False
    if company and sender_phone:
        try:
            from operations.models import AgentConversation
            from datetime import timedelta
            conv = AgentConversation.objects.filter(company=company, customer_phone=sender_phone).last()
            if conv:
                recent_msgs = list(
                    conv.messages.filter(created_at__gte=timezone.now() - timedelta(hours=24))
                    .order_by("-created_at")[:10]
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
            active_tools = cat_cfg.get("tools") or AGENT_TOOLS

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
                    elif fn_name == "create_order":
                        tool_result = execute_create_order(
                            company=company,
                            customer_name=fn_args.get("customer_name") or customer_name,
                            customer_phone=fn_args.get("customer_phone") or sender_phone,
                            items=fn_args.get("items", []),
                            delivery_address=fn_args.get("delivery_address", ""),
                            notes=fn_args.get("notes", ""),
                        )
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
                    record_conversation_turn(company, sender_phone, customer_name, message_text, reply, is_voice=is_voice_note)
                    return reply

            elif response_msg.content and response_msg.content.strip():
                reply = response_msg.content.strip()
                record_conversation_turn(company, sender_phone, customer_name, message_text, reply, is_voice=is_voice_note)
                return reply

        except Exception as e:
            logger.error(f"[WhatsApp Agent] OpenAI tool-calling execution error: {e}", exc_info=True)
            print(f"[WhatsApp Agent ERROR] Tool calling failed: {e}")

    # Fallback when OpenAI key is missing, invalid, or request fails
    fallback_reply = _build_fallback_reply(message_text, customer_name, context)
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
        success = bool(res and not res.get("error"))
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
        success = bool(res and not res.get("error"))
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
    close_old_connections()
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

        # Step 2: Audio / Voice Message Cost & Rate Limiting Check
        is_voice_message = (msg_type == "audio" or bool(media_id) or bool(audio_bytes))
        if is_voice_message:
            company_obj = context.get("company")
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

        # Voice-first response: If customer sent a voice note, synthesize and send a voice reply
        if is_voice_message:
            logger.info(f"[WhatsApp Voice Agent] Customer sent voice note. Synthesizing voice reply for {sender_phone}...")
            print(f"[WhatsApp Voice Agent] Synthesizing TTS voice note for {sender_phone}...")

            from operations.audio_service import clean_text_for_tts
            tts_text = clean_text_for_tts(reply_text)

            audio_bytes = synthesize_speech(tts_text)
            if audio_bytes:
                audio_res = _dispatch_whatsapp_audio(company=company_obj, phone=sender_phone, audio_bytes=audio_bytes, service=service)
                if audio_res and audio_res.get("success"):
                    dispatch_result = audio_res
                    is_voice_dispatched = True
                else:
                    logger.warning("[WhatsApp Voice Agent] Audio dispatch failed. Falling back to text message.")
                    print("[WhatsApp Voice Agent Warning] Audio dispatch failed. Falling back to text.")
            else:
                logger.warning("[WhatsApp Voice Agent] Speech synthesis failed. Falling back to text message.")
                print("[WhatsApp Voice Agent Warning] TTS failed. Falling back to text.")

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
        close_old_connections()
