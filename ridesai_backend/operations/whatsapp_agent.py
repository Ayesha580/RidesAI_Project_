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
from operations.models import Customer, Order, OrderItem, OrderEvent, AgentConversation, AgentMessage
from companies.models import Company, CatalogItem, BusinessKnowledge, BusinessHours, Inventory, StockMovement

logger = logging.getLogger("operations.whatsapp")


# ============================================================================
# OpenAI / Groq Tool Schemas (Phase 3 Tool Calling)
# ============================================================================

AGENT_TOOLS = [
    {
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
                        "description": "Optional keyword or category to search for specific items (e.g. 'burger', 'drink').",
                    }
                },
                "required": [],
            },
        },
    },
    {
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
                        "description": "General delivery instructions or notes for the kitchen/staff.",
                    },
                },
                "required": ["delivery_address", "items"],
            },
        },
    },
    {
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
    },
]


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
                    stock_info = f"{inv.quantity} available"
            except Exception:
                pass

            items_list.append({
                "id": item.id,
                "name": item.name,
                "price": str(item.price),
                "category": item.category.name if item.category else "General",
                "description": item.description or "",
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
            "subtotal": f"${subtotal:.2f}",
            "total": f"${order.total:.2f}",
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
                "total": f"${o.total:.2f}",
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


def _build_system_prompt(customer_name: str, context: Dict[str, Any]) -> str:
    """
    Constructs a detailed grounding system prompt for the LLM using tenant metadata,
    catalog items, operating hours, business knowledge, and tool-calling directives.
    """
    biz_name = context.get("business_name") or "our store"
    greeting = context.get("greeting") or f"Welcome to {biz_name}!"
    tone = context.get("tone") or "friendly and helpful"
    phone = context.get("phone") or "our support team"
    address = context.get("address") or "our store location"

    # Format catalog items
    catalog_lines = []
    for item in context.get("catalog", []):
        price = f"${float(item['price']):.2f}" if item.get("price") else "Price on request"
        desc = f" - {item['description']}" if item.get("description") else ""
        catalog_lines.append(f"• {item['name']}: {price}{desc}")
    
    if catalog_lines:
        catalog_str = "\n".join(catalog_lines)
    else:
        catalog_str = (
            "No catalog items are currently active. If a customer asks to view items or order, "
            "politely inform them that the store catalog is currently being updated."
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

    return f"""You are the official AI Assistant for {biz_name} on WhatsApp.
Your primary role is to assist customers with our menu/catalog, take orders directly into our database via tools, and provide operating hours and store information.

BUSINESS DETAILS:
- Business Name: {biz_name}
- Brand Voice / Tone: {tone}
- Default Greeting: {greeting}
- Store Address: {address}
- Support Phone: {phone}
- Customer Name: {customer_name}

OPERATING HOURS:
{hours_str}

AVAILABLE MENU / CATALOG ITEMS:
{catalog_str}

FREQUENTLY ASKED QUESTIONS & POLICIES:
{kb_str}

STRICT TOOL CALLING RULES:
1. Tool `get_catalog_items`:
   - Use when the customer asks what you sell, asks to see the menu, asks for prices, or searches for a product.
2. Tool `create_order`:
   - Use ONLY when the customer has specified what they want to order AND provided their delivery address.
   - If the customer lists items to order but has NOT provided an address yet: do NOT call `create_order`. Instead, list their selected items with prices, calculate the total, and ask them: "Please provide your delivery address to confirm and place your order."
   - Once the delivery address is provided, immediately call `create_order`.
   - After `create_order` succeeds, provide a cheerful confirmation containing the *order number*, items, total, and estimated delivery time (30-45 mins).
3. Tool `check_order_status`:
   - Use when the customer asks about order status, tracking, or previous orders.

STRICT CONVERSATIONAL RULES:
- Under NO circumstances provide financial advice, programming code, political commentary, or general trivia. Politely decline and bring the conversation back to {biz_name}.
- Keep replies concise, natural, and formatted nicely for WhatsApp (*bold* for highlights/order numbers, clear line breaks, and emojis).
- Ground all facts strictly in the business context and tool outputs above. Never invent prices or items that do not exist in the store catalog.

CRITICAL COST-SAVING RULES:
- You are a voice-first agent. Humans do not want to listen to long monologues.
- NEVER use filler words, introductory pleasantries, or formatting like markdown/bullet points.
- Answer in strictly 1 to 2 short sentences. Maximum 20 words per response.
- Be highly direct and concise.
"""


def _build_fallback_reply(message_text: str, customer_name: str, context: Dict[str, Any]) -> str:
    """
    Polite fallback response if LLM API call fails or times out.
    """
    biz_name = context.get("business_name") or "our store"
    phone = context.get("phone")
    greeting = context.get("greeting") or f"Hello {customer_name}! Welcome to *{biz_name}*."
    support_line = f"\n\nFor immediate assistance, please call us directly at *{phone}*." if phone else ""

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
) -> str:
    """
    Generates a dynamic response using OpenAI's gpt-4o-mini model with full tool calling:
    1. Sends user message with registered tools (get_catalog_items, create_order, check_order_status).
    2. If the LLM requests tool execution, executes the function with multi-tenant isolation.
    3. Feeds tool outputs back into the conversation for a second pass to produce natural confirmation.

    Supports both standard call:
        _generate_agent_reply(message_text, customer_name, context, sender_phone)
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

    api_key = getattr(settings, "OPENAI_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")
    model = getattr(settings, "OPENAI_MODEL", "gpt-4o-mini")

    if api_key and len(api_key.strip()) > 10:
        try:
            client = OpenAI(api_key=api_key.strip(), timeout=25.0)
            system_prompt = _build_system_prompt(customer_name, context)

            messages: List[Dict[str, Any]] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message_text},
            ]

            llm_max_tokens = int(getattr(settings, "OPENAI_MAX_TOKENS", 50))
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=AGENT_TOOLS,
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
                    else:
                        tool_result = {"error": f"Tool '{fn_name}' is not recognized."}

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(tool_result),
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
                    record_conversation_turn(company, sender_phone, customer_name, message_text, reply)
                    return reply

            elif response_msg.content and response_msg.content.strip():
                reply = response_msg.content.strip()
                record_conversation_turn(company, sender_phone, customer_name, message_text, reply)
                return reply

        except Exception as e:
            logger.error(f"[WhatsApp Agent] OpenAI tool-calling execution error: {e}", exc_info=True)
            print(f"[WhatsApp Agent ERROR] Tool calling failed: {e}")

    # Fallback when OpenAI key is missing, invalid, or request fails
    fallback_reply = _build_fallback_reply(message_text, customer_name, context)
    record_conversation_turn(company, sender_phone, customer_name, message_text, fallback_reply)
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


def process_incoming_whatsapp_message(
    sender_phone: str,
    message_text: str,
    phone_number_id: str,
    customer_name: Optional[str] = None,
    media_id: Optional[str] = None,
    msg_type: str = "text",
) -> Dict[str, Any]:
    """
    Main background entrypoint for processing an incoming WhatsApp customer message:
    1. Multi-Tenant Guard: Validates that destination phone_number_id belongs to a registered company.
    2. Voice Rate Limit & Cost Guard: Checks customer voice usage vs max_daily_voice_notes.
    3. Voice Input (STT): If audio note (.ogg), downloads via Meta Graph API and transcribes via Groq/Whisper.
    4. Tool-Calling Agent: Runs LLM with dynamic tool calling (get_catalog_items, create_order, check_order_status).
    5. Voice Output (TTS): If customer sent audio, synthesizes speech (OpenAI tts-1) and uploads via Meta API.
    6. Dispatches reply via Meta Cloud API using WhatsAppService.
    """
    close_old_connections()
    try:
        clean_name = customer_name or "Valued Customer"
        service = WhatsAppService(phone_number_id=phone_number_id)

        # Step 1: Multi-Tenant Isolation Check (Fail Closed)
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
        is_voice_message = (msg_type == "audio" or bool(media_id))
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
                dispatch_res = service.send_text_message(to=sender_phone, text=limit_msg)
                return {
                    "success": dispatch_res.get("success", False) if isinstance(dispatch_res, dict) else True,
                    "reply_text": limit_msg,
                    "rate_limited": True,
                    "dispatch_result": dispatch_res,
                }

            if media_id:
                logger.info(f"[WhatsApp Voice Agent] Downloading audio media {media_id} for {sender_phone}...")
                print(f"[WhatsApp Voice Agent] Received voice note from {sender_phone} (Media ID: {media_id}). Downloading...")
                audio_bytes = service.download_media_file(media_id)
                if audio_bytes:
                    transcription = transcribe_audio(audio_bytes, filename="audio.ogg")
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

                dispatch_res = service.send_text_message(to=sender_phone, text=limit_msg)
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
        )

        # Step 4: Outbound WhatsApp dispatch via WhatsAppService
        dispatch_result = None
        is_voice_dispatched = False

        # Voice-first response: If customer sent a voice note, synthesize and send a voice reply
        if is_voice_message:
            logger.info(f"[WhatsApp Voice Agent] Customer sent voice note. Synthesizing voice reply for {sender_phone}...")
            print(f"[WhatsApp Voice Agent] Synthesizing TTS voice note for {sender_phone}...")

            audio_bytes = synthesize_speech(reply_text)
            if audio_bytes:
                outbound_media_id = service.upload_media(audio_bytes, mime_type="audio/ogg")
                if outbound_media_id:
                    print(f"[WhatsApp Voice Agent] Uploaded voice note (Media ID: {outbound_media_id}). Dispatching audio...")
                    audio_res = service.send_audio_message(to=sender_phone, media_id=outbound_media_id)
                    if audio_res and audio_res.get("success"):
                        dispatch_result = audio_res
                        is_voice_dispatched = True
                else:
                    logger.warning("[WhatsApp Voice Agent] Media upload failed. Falling back to text message.")
                    print("[WhatsApp Voice Agent Warning] Media upload failed. Falling back to text.")
            else:
                logger.warning("[WhatsApp Voice Agent] Speech synthesis failed. Falling back to text message.")
                print("[WhatsApp Voice Agent Warning] TTS failed. Falling back to text.")

        # Fallback to text message if voice response was not used or failed
        if not dispatch_result or not dispatch_result.get("success"):
            dispatch_result = service.send_text_message(to=sender_phone, text=reply_text)

        # Step 5: Update message metadata if audio/voice dispatched
        if is_voice_dispatched:
            try:
                company_obj = context.get("company")
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
