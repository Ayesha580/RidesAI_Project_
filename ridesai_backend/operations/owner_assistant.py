"""
Owner AI Business Manager Service (Copilot for Business Operations).
Provides authenticated, company-scoped intelligence and management actions
for Business Owners via Voice and Text in English, Urdu, and Roman Urdu.

Strict multi-tenant isolation enforced on every tool query.
"""

import base64
import json
import logging
import os
import re
from datetime import timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.db.models import Q, Sum
from django.utils import timezone

from accounts.models import User
from companies.models import CatalogItem, Company, Inventory
from operations.audio_service import synthesize_speech, transcribe_audio
from operations.models import Order

logger = logging.getLogger("operations.owner_assistant")


# ============================================================================
# Company-Scoped Business Intelligence Tools
# ============================================================================

TOOL_GET_EMPLOYEES_SUMMARY = {
    "type": "function",
    "function": {
        "name": "get_employees_summary",
        "description": (
            "Retrieves staff/employee headcount, active/inactive counts, roles breakdown, "
            "and list of employee names for this business."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}

TOOL_GET_SALES_AND_ORDERS_SUMMARY = {
    "type": "function",
    "function": {
        "name": "get_sales_and_orders_summary",
        "description": (
            "Retrieves sales revenue in Rs., total order count, and breakdown by status "
            "for a given time period ('today', 'week', 'month', 'all')."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "enum": ["today", "week", "month", "all"],
                    "description": "Time window: 'today' (default), 'week' (last 7 days), 'month' (last 30 days), 'all'.",
                }
            },
            "required": [],
        },
    },
}

TOOL_GET_INVENTORY_AND_CATALOG_SUMMARY = {
    "type": "function",
    "function": {
        "name": "get_inventory_and_catalog_summary",
        "description": (
            "Retrieves inventory health, catalog item counts, out-of-stock items, "
            "and low-stock alerts across products/medicines/services."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}

TOOL_GET_DELIVERIES_AND_RIDERS_STATUS = {
    "type": "function",
    "function": {
        "name": "get_deliveries_and_riders_status",
        "description": (
            "Retrieves delivery rider workload, active deliveries per rider, "
            "and unassigned orders awaiting dispatch."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}

TOOL_GET_BILLING_AND_AI_USAGE = {
    "type": "function",
    "function": {
        "name": "get_billing_and_ai_usage",
        "description": (
            "Retrieves the business's monthly AI voice message usage meter, limit, "
            "AI paused state, and subscription status."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}

TOOL_TOGGLE_CUSTOMER_AI_AGENT = {
    "type": "function",
    "function": {
        "name": "toggle_customer_ai_agent",
        "description": (
            "Pauses or resumes the customer-facing AI Assistant across WhatsApp, "
            "Website Widget, and Public link. Pass pause=true to pause, pause=false to resume."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "pause": {
                    "type": "boolean",
                    "description": "True to pause automated customer replies; False to resume.",
                }
            },
            "required": ["pause"],
        },
    },
}

OWNER_TOOLS = [
    TOOL_GET_EMPLOYEES_SUMMARY,
    TOOL_GET_SALES_AND_ORDERS_SUMMARY,
    TOOL_GET_INVENTORY_AND_CATALOG_SUMMARY,
    TOOL_GET_DELIVERIES_AND_RIDERS_STATUS,
    TOOL_GET_BILLING_AND_AI_USAGE,
    TOOL_TOGGLE_CUSTOMER_AI_AGENT,
]


# ============================================================================
# Tool Implementations (Strictly Multi-Tenant Isolated)
# ============================================================================

def execute_get_employees_summary(company: Company) -> Dict[str, Any]:
    """Strictly scoped employee summary for the authenticated company."""
    if not company:
        return {"error": "Company not found."}

    qs = User.objects.filter(company=company).exclude(role=User.ROLE_SUPERADMIN).exclude(is_superuser=True)
    staff_qs = qs.exclude(role=User.ROLE_OWNER)
    total_staff = staff_qs.count()
    active_staff = staff_qs.filter(is_active=True).count()
    inactive_staff = total_staff - active_staff

    role_counts: Dict[str, int] = {}
    employees_list: List[Dict[str, Any]] = []

    for u in staff_qs.select_related("staff_role").order_by("-is_active", "first_name", "username")[:50]:
        r_name = getattr(u.staff_role, "name", "") or u.get_role_display() or u.role
        role_counts[r_name] = role_counts.get(r_name, 0) + 1
        employees_list.append({
            "id": u.id,
            "name": u.get_full_name() or u.username,
            "role": r_name,
            "phone": getattr(u, "phone", "") or "",
            "is_active": u.is_active,
        })

    return {
        "company_name": company.name,
        "total_employees": total_staff,
        "active_employees": active_staff,
        "inactive_employees": inactive_staff,
        "role_breakdown": role_counts,
        "employees": employees_list,
    }


def execute_get_sales_and_orders_summary(company: Company, period: str = "today") -> Dict[str, Any]:
    """Strictly scoped sales & orders analysis for the authenticated company."""
    if not company:
        return {"error": "Company not found."}

    now = timezone.now()
    qs = Order.objects.filter(company=company)
    period_clean = (period or "today").lower().strip()

    if period_clean == "today":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        qs = qs.filter(created_at__gte=start_date)
        period_label = "Today"
    elif period_clean == "week":
        start_date = now - timedelta(days=7)
        qs = qs.filter(created_at__gte=start_date)
        period_label = "Last 7 Days"
    elif period_clean == "month":
        start_date = now - timedelta(days=30)
        qs = qs.filter(created_at__gte=start_date)
        period_label = "Last 30 Days"
    else:
        period_label = "All Time"

    total_orders = qs.count()
    cancelled_orders = qs.filter(status=Order.STATUS_CANCELLED).count()
    delivered_orders = qs.filter(status=Order.STATUS_DELIVERED).count()
    pending_orders = qs.exclude(status__in=[Order.STATUS_DELIVERED, Order.STATUS_CANCELLED]).count()

    non_cancelled = qs.exclude(status=Order.STATUS_CANCELLED)
    total_sales = non_cancelled.aggregate(s=Sum("total"))["s"] or Decimal("0.00")

    status_counts: Dict[str, int] = {}
    for s_choice in Order.STATUS_CHOICES:
        c = qs.filter(status=s_choice[0]).count()
        if c > 0:
            status_counts[s_choice[0]] = c

    avg_ticket = (total_sales / non_cancelled.count()) if non_cancelled.count() > 0 else Decimal("0.00")

    return {
        "company_name": company.name,
        "period": period_label,
        "total_orders": total_orders,
        "total_sales_pkr": float(total_sales),
        "average_order_value_pkr": float(round(avg_ticket, 2)),
        "pending_orders": pending_orders,
        "delivered_orders": delivered_orders,
        "cancelled_orders": cancelled_orders,
        "status_breakdown": status_counts,
    }


def execute_get_inventory_and_catalog_summary(company: Company) -> Dict[str, Any]:
    """Strictly scoped inventory & catalog summary for the authenticated company."""
    if not company:
        return {"error": "Company not found."}

    catalog_items = CatalogItem.objects.filter(company=company)
    total_catalog_items = catalog_items.count()
    active_available_items = catalog_items.filter(is_available=True).count()
    unavailable_items = catalog_items.filter(is_available=False).count()

    low_stock_records = []
    out_of_stock_records = []
    inventories = Inventory.objects.filter(company=company, is_unlimited=False).select_related("item")
    for inv in inventories:
        qty = inv.quantity
        thresh = inv.low_stock_threshold or 5
        item_name = inv.item.name if inv.item else f"Item #{inv.item_id}"
        if qty <= 0:
            out_of_stock_records.append({"item_name": item_name, "quantity": float(qty)})
        elif qty <= thresh:
            low_stock_records.append({
                "item_name": item_name,
                "quantity": float(qty),
                "threshold": float(thresh),
            })

    expired_batches_count = 0
    near_expiry_batches = 0
    if company.business_type == "pharmacy":
        try:
            from operations.models import MedicineBatch
            today = timezone.now().date()
            expired_batches_count = MedicineBatch.objects.filter(
                company=company, expiry_date__lt=today, quantity__gt=0
            ).count()
            near_expiry_batches = MedicineBatch.objects.filter(
                company=company,
                expiry_date__gte=today,
                expiry_date__lte=today + timedelta(days=30),
                quantity__gt=0,
            ).count()
        except Exception:
            pass

    return {
        "company_name": company.name,
        "business_type": company.business_type,
        "total_catalog_items": total_catalog_items,
        "active_available_items": active_available_items,
        "unavailable_items": unavailable_items,
        "out_of_stock_items": out_of_stock_records[:15],
        "out_of_stock_count": len(out_of_stock_records),
        "low_stock_items": low_stock_records[:15],
        "low_stock_count": len(low_stock_records),
        "expired_batches_count": expired_batches_count,
        "near_expiry_batches_count": near_expiry_batches,
    }


def execute_get_deliveries_and_riders_status(company: Company) -> Dict[str, Any]:
    """Strictly scoped deliveries & rider status for the authenticated company."""
    if not company:
        return {"error": "Company not found."}

    rider_filter = (
        Q(role="rider")
        | Q(staff_role__name__iexact="rider")
        | Q(staff_role__name__iexact="delivery boy")
        | Q(staff_role__name__iexact="delivery")
    )
    riders = list(User.objects.filter(company=company, is_active=True).filter(rider_filter).order_by("id"))

    active_statuses = [
        Order.STATUS_PREPARED,
        Order.STATUS_READY,
        Order.STATUS_OUT_FOR_DELIVERY,
        Order.STATUS_ON_THE_WAY,
        Order.STATUS_PICKED_UP,
        Order.STATUS_ASSIGNED,
    ]

    riders_status = []
    for r in riders:
        active_count = Order.objects.filter(company=company, assigned_rider=r, status__in=active_statuses).count()
        delivered_count = Order.objects.filter(company=company, assigned_rider=r, status=Order.STATUS_DELIVERED).count()
        riders_status.append({
            "rider_id": r.id,
            "name": r.get_full_name() or r.username,
            "phone": getattr(r, "phone", "") or "",
            "active_orders": active_count,
            "delivered_orders": delivered_count,
        })

    unassigned_orders = Order.objects.filter(
        company=company,
        assigned_rider__isnull=True,
        status__in=[
            Order.STATUS_NEW,
            Order.STATUS_PENDING,
            Order.STATUS_CONFIRMED,
            Order.STATUS_PREPARING,
            Order.STATUS_PREPARED,
            Order.STATUS_READY,
        ],
    ).count()

    return {
        "company_name": company.name,
        "total_active_riders": len(riders),
        "unassigned_orders_count": unassigned_orders,
        "riders": riders_status,
    }


def execute_get_billing_and_ai_usage(company: Company) -> Dict[str, Any]:
    """Strictly scoped billing and voice limit state for the authenticated company."""
    if not company:
        return {"error": "Company not found."}

    msg_used = int(company.messages_used or 0)
    msg_limit = int(company.message_limit or 0)
    limit_reached = bool(msg_limit > 0 and msg_used >= msg_limit)
    plan_name = getattr(company.plan, "name", "Standard") if hasattr(company, "plan") and company.plan else "Active Business"

    return {
        "company_name": company.name,
        "subscription_status": company.subscription_status,
        "plan_name": plan_name,
        "messages_used": msg_used,
        "message_limit": msg_limit,
        "monthly_limit_reached": limit_reached,
        "is_ai_paused": bool(company.is_ai_paused),
    }


def execute_toggle_customer_ai_agent(company: Company, pause: bool) -> Dict[str, Any]:
    """Safely toggles customer-facing AI agent automated replies for this company."""
    if not company:
        return {"error": "Company not found."}

    company.is_ai_paused = bool(pause)
    company.save(update_fields=["is_ai_paused"])
    action_str = "PAUSED" if company.is_ai_paused else "RESUMED (Active)"

    return {
        "success": True,
        "is_ai_paused": company.is_ai_paused,
        "message": f"Customer AI Agent has been {action_str} across WhatsApp, Public Link, and Website Widget.",
    }


# ============================================================================
# Executive Assistant System Prompt & Query Dispatcher
# ============================================================================

def _build_owner_system_prompt(company: Company, owner_user: User) -> str:
    biz_name = company.name or "Your Business"
    owner_name = owner_user.get_full_name() or owner_user.username
    biz_type = getattr(company, "business_type", "restaurant")

    return f"""You are the official Rides AI Business Manager & Executive Copilot for {biz_name}.
You are speaking directly with the business owner, {owner_name}.

YOUR ROLE & CAPABILITIES:
- You help the business owner manage and monitor their {biz_type} operations in real-time.
- You have direct tool access to live store data:
  1. `get_employees_summary`: Staff headcount, roles, active/inactive staff.
  2. `get_sales_and_orders_summary`: Live revenue (Rs.), total orders, order statuses (today, this week, this month).
  3. `get_inventory_and_catalog_summary`: Catalog items, out-of-stock, and low-stock alerts.
  4. `get_deliveries_and_riders_status`: Rider active workloads and unassigned delivery orders.
  5. `get_billing_and_ai_usage`: Monthly AI voice usage meter, message limit, subscription plan.
  6. `toggle_customer_ai_agent`: Pause or resume the customer-facing AI assistant.

STRICT OPERATIONAL RULES:
1. ALWAYS CALL TOOLS FOR LIVE NUMBERS: Never guess or invent employee names, sales revenue, order counts, or inventory levels. Call the appropriate tool and use its output to answer.
2. MULTILINGUAL FLUENCY:
   - If the owner speaks or types in Roman Urdu or Urdu (e.g., 'kitne employees hain?', 'aaj ki sales kitni hui?', 'riders free hain kya?', 'stock check karo'), reply in natural, polite Pakistani Roman Urdu.
   - If the owner speaks or types in English, reply in concise, professional English.
3. CURRENCY: Always format prices in Pakistani Rupees using `Rs.` (e.g. `Rs. 14,500`).
4. FORMATTING: Use bolding, bullet points, and clean line breaks so key numbers and names are easy for an executive to scan.
5. CONCISE & ACTION-ORIENTED: Be direct, helpful, and executive-friendly.
"""


def _format_fallback_response(query: str, company: Company) -> str:
    """Smart deterministic rule-based fallback when external LLM APIs are offline."""
    q_low = query.lower()

    if any(k in q_low for k in ["employee", "staff", "mulazim", "worker", "team"]):
        data = execute_get_employees_summary(company)
        roles_str = ", ".join([f"{k}: {v}" for k, v in data["role_breakdown"].items()]) or "None"
        names_str = ", ".join([e["name"] for e in data["employees"][:5]])
        return (
            f"👥 **Employee Summary ({company.name})**\n\n"
            f"• **Total Staff:** {data['total_employees']} ({data['active_employees']} active, {data['inactive_employees']} inactive)\n"
            f"• **Role Breakdown:** {roles_str}\n"
            f"• **Staff Members:** {names_str if names_str else 'No employees registered yet'}"
        )

    if any(k in q_low for k in ["sale", "order", "revenue", "kamai", "aaj"]):
        period = "today"
        if "week" in q_low or "hafte" in q_low:
            period = "week"
        elif "month" in q_low or "mahine" in q_low:
            period = "month"
        elif "all" in q_low or "total" in q_low:
            period = "all"
        data = execute_get_sales_and_orders_summary(company, period=period)
        return (
            f"📊 **Sales & Orders Report ({data['period']})**\n\n"
            f"• **Total Revenue:** Rs. {data['total_sales_pkr']:,.2f}\n"
            f"• **Total Orders:** {data['total_orders']}\n"
            f"• **Pending Orders:** {data['pending_orders']}\n"
            f"• **Delivered Orders:** {data['delivered_orders']}\n"
            f"• **Average Ticket Size:** Rs. {data['average_order_value_pkr']:,.2f}"
        )

    if any(k in q_low for k in ["inventory", "stock", "saman", "item", "catalog"]):
        data = execute_get_inventory_and_catalog_summary(company)
        low_items_str = ", ".join([f"{it['item_name']} ({it['quantity']})" for it in data["low_stock_items"][:5]]) or "None"
        return (
            f"📦 **Inventory & Stock Health**\n\n"
            f"• **Total Catalog Items:** {data['total_catalog_items']}\n"
            f"• **Active Available:** {data['active_available_items']}\n"
            f"• **Out of Stock:** {data['out_of_stock_count']} items\n"
            f"• **Low Stock Alerts:** {data['low_stock_count']} items ({low_items_str})"
        )

    if any(k in q_low for k in ["rider", "delivery", "dispatch"]):
        data = execute_get_deliveries_and_riders_status(company)
        riders_str = "\n".join([f"  - **{r['name']}**: {r['active_orders']} active orders ({r['delivered_orders']} completed)" for r in data["riders"]]) or "  No active delivery riders."
        return (
            f"🛵 **Delivery & Rider Status**\n\n"
            f"• **Active Riders:** {data['total_active_riders']}\n"
            f"• **Unassigned Orders:** {data['unassigned_orders_count']}\n"
            f"• **Rider Workload:**\n{riders_str}"
        )

    if any(k in q_low for k in ["billing", "usage", "limit", "quota", "plan"]):
        data = execute_get_billing_and_ai_usage(company)
        ai_state = "PAUSED (Manual Mode)" if data["is_ai_paused"] else "ACTIVE (Responding to Customers)"
        return (
            f"💳 **AI Usage & Billing Overview**\n\n"
            f"• **Plan Status:** {data['subscription_status'].upper()} ({data['plan_name']})\n"
            f"• **Monthly AI Voice Usage:** {data['messages_used']} / {data['message_limit']} messages\n"
            f"• **Limit Reached:** {'YES ⚠️' if data['monthly_limit_reached'] else 'No'}\n"
            f"• **Customer AI Agent Status:** {ai_state}"
        )

    if "pause" in q_low or "rok do" in q_low or "band kar" in q_low:
        res = execute_toggle_customer_ai_agent(company, pause=True)
        return f"⏸️ {res['message']}"

    if "resume" in q_low or "chala do" in q_low or "start" in q_low or "activate" in q_low:
        res = execute_toggle_customer_ai_agent(company, pause=False)
        return f"▶️ {res['message']}"

    return (
        f"Assalam-o-Alaikum! Main aapka **Rides AI Business Manager** hoon. "
        f"Aap mujh se apne employees, aaj ki sales, pending orders, rider deliveries, ya inventory ke baare mein poochna chahte hain?"
    )


def process_owner_assistant_query(
    company: Company,
    owner_user: User,
    message: Optional[str] = None,
    audio_base64: Optional[str] = None,
    history: Optional[List[Dict[str, str]]] = None,
    want_voice_reply: bool = False,
) -> Dict[str, Any]:
    """
    Processes an authenticated business owner's query (voice or text),
    dispatches scoped tool calls, and returns structured text + optional voice audio.
    """
    user_text = (message or "").strip()

    # 1. Voice transcription if audio_base64 provided
    if audio_base64 and audio_base64.strip():
        try:
            raw_b64 = audio_base64.strip()
            if "," in raw_b64:
                raw_b64 = raw_b64.split(",", 1)[1]
            audio_bytes = base64.b64decode(raw_b64)
            transcribed = transcribe_audio(audio_bytes, filename="owner_voice.webm")
            if transcribed and transcribed.strip():
                user_text = transcribed.strip()
        except Exception as e:
            logger.warning(f"[Owner Assistant] Voice transcription failed: {e}")

    if not user_text:
        return {
            "transcript": "",
            "reply": "I couldn't hear or read your question. Please speak clearly or type your question.",
            "audio_base64": None,
            "tools_used": [],
        }

    tools_used: List[str] = []
    reply_text = ""

    api_key = getattr(settings, "OPENAI_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")
    model = getattr(settings, "OPENAI_MODEL", "gpt-4o-mini")

    if api_key and len(api_key.strip()) > 10:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=api_key.strip(), timeout=25.0)
            system_prompt = _build_owner_system_prompt(company, owner_user)

            messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]

            # Add recent conversation history if provided
            if history and isinstance(history, list):
                for h in history[-8:]:
                    r = h.get("role")
                    c = (h.get("content") or "").strip()
                    if r in ("user", "assistant") and c:
                        messages.append({"role": r, "content": c})

            messages.append({"role": "user", "content": user_text})

            response = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=OWNER_TOOLS,
                tool_choice="auto",
                temperature=0.2,
                max_tokens=400,
            )

            response_msg = response.choices[0].message
            tool_calls = getattr(response_msg, "tool_calls", None)

            if tool_calls:
                messages.append(response_msg)
                for tc in tool_calls:
                    fn_name = tc.function.name
                    raw_args = tc.function.arguments or "{}"
                    try:
                        fn_args = json.loads(raw_args)
                    except Exception:
                        fn_args = {}

                    tools_used.append(fn_name)
                    tool_result: Dict[str, Any] = {}

                    if fn_name == "get_employees_summary":
                        tool_result = execute_get_employees_summary(company=company)
                    elif fn_name == "get_sales_and_orders_summary":
                        tool_result = execute_get_sales_and_orders_summary(
                            company=company, period=fn_args.get("period", "today")
                        )
                    elif fn_name == "get_inventory_and_catalog_summary":
                        tool_result = execute_get_inventory_and_catalog_summary(company=company)
                    elif fn_name == "get_deliveries_and_riders_status":
                        tool_result = execute_get_deliveries_and_riders_status(company=company)
                    elif fn_name == "get_billing_and_ai_usage":
                        tool_result = execute_get_billing_and_ai_usage(company=company)
                    elif fn_name == "toggle_customer_ai_agent":
                        tool_result = execute_toggle_customer_ai_agent(
                            company=company, pause=bool(fn_args.get("pause", False))
                        )
                    else:
                        tool_result = {"error": f"Tool '{fn_name}' not recognized."}

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(tool_result),
                    })

                # Follow-up completion pass with tool outputs
                second_response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.2,
                    max_tokens=400,
                )
                final_content = second_response.choices[0].message.content
                if final_content and final_content.strip():
                    reply_text = final_content.strip()

            elif response_msg.content and response_msg.content.strip():
                reply_text = response_msg.content.strip()

        except Exception as e:
            logger.warning(f"[Owner Assistant] LLM tool-calling error: {e}")

    # Fallback response if LLM was unreachable or returned empty
    if not reply_text:
        reply_text = _format_fallback_response(user_text, company)

    # Optional Voice Reply (TTS)
    reply_audio_b64: Optional[str] = None
    if want_voice_reply and reply_text:
        try:
            tts_bytes = synthesize_speech(reply_text, voice="alloy")
            if tts_bytes:
                reply_audio_b64 = "data:audio/mp3;base64," + base64.b64encode(tts_bytes).decode("ascii")
        except Exception as e:
            logger.warning(f"[Owner Assistant] TTS synthesis failed: {e}")

    return {
        "transcript": user_text,
        "reply": reply_text,
        "audio_base64": reply_audio_b64,
        "tools_used": tools_used,
    }
