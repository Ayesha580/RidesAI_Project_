"""
WhatsApp AI Agent & Dynamic Order Processing Workflow.

Dynamically parses customer inquiries and order requests using the OpenAI API (gpt-4o-mini).
Grounds responses in tenant-specific business data (Company, CatalogItem, BusinessKnowledge,
and BusinessHours), and dispatches responses via Meta WhatsApp Cloud API using WhatsAppService.
"""

import json
import logging
import os
from typing import Optional, Dict, Any, List

from django.conf import settings
from django.db import close_old_connections
from openai import OpenAI

from .whatsapp_service import WhatsAppService
from .whatsapp_storage import get_config_by_phone_number_id

logger = logging.getLogger("operations.whatsapp")


def _get_business_context(phone_number_id: str) -> Dict[str, Any]:
    """
    Retrieves the tenant business context (company, catalog, FAQs, hours)
    matching the destination WhatsApp phone_number_id.
    """
    context = {
        "company": None,
        "company_id": None,
        "business_name": "Rides AI Store",
        "greeting": "Welcome to our store!",
        "tone": "friendly",
        "phone": "",
        "address": "",
        "catalog": [],
        "knowledge": [],
        "hours": [],
    }

    try:
        from companies.models import Company, CatalogItem, BusinessKnowledge, BusinessHours

        cfg = get_config_by_phone_number_id(phone_number_id)
        company = None
        if cfg and cfg.get("company_id"):
            try:
                company = Company.objects.filter(pk=cfg["company_id"]).first()
            except Exception:
                company = None

        if not company:
            # Fallback to the first active/approved company in the system
            company = (
                Company.objects.filter(status="active").first()
                or Company.objects.filter(is_approved=True).first()
                or Company.objects.first()
            )

        if company:
            context["company"] = company
            context["company_id"] = company.id
            context["business_name"] = company.name or "Rides AI Store"
            context["greeting"] = company.agent_greeting or f"Welcome to {company.name}!"
            context["tone"] = company.agent_tone or "friendly and helpful"
            context["phone"] = company.phone or company.agent_support_phone or ""
            context["address"] = company.address or ""

            # Fetch active catalog items
            items = list(
                CatalogItem.objects.filter(company=company, is_available=True)
                .values("id", "name", "price", "description")[:30]
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
        logger.warning(f"[WhatsApp Agent] Could not load DB business context: {e}", exc_info=True)

    # Sensible defaults for restaurants/retail if catalog is empty
    if not context["catalog"]:
        context["catalog"] = [
            {"name": "Classic Beef Burger", "price": "8.99", "description": "Grilled beef patty, cheddar, lettuce & secret sauce"},
            {"name": "Crispy Chicken Burger", "price": "7.99", "description": "Crispy fried chicken breast, pickles & spicy mayo"},
            {"name": "Truffle Mushroom Burger", "price": "9.99", "description": "Swiss cheese, sautéed mushrooms & truffle aioli"},
            {"name": "French Fries (Large)", "price": "3.50", "description": "Crispy golden salted fries"},
            {"name": "Soft Drink (Can)", "price": "1.99", "description": "Coke, Sprite, or Fanta"},
        ]

    return context


def _build_system_prompt(customer_name: str, context: Dict[str, Any]) -> str:
    """
    Constructs a detailed grounding system prompt for the LLM using tenant metadata,
    catalog items, operating hours, and business knowledge base.
    """
    biz_name = context.get("business_name") or "our store"
    greeting = context.get("greeting") or f"Welcome to {biz_name}!"
    tone = context.get("tone") or "friendly and helpful"
    phone = context.get("phone") or "our main support desk"
    address = context.get("address") or "our central store location"

    # Format catalog items
    catalog_lines = []
    for item in context.get("catalog", []):
        price = f"${float(item['price']):.2f}" if item.get("price") else "Price on request"
        desc = f" - {item['description']}" if item.get("description") else ""
        catalog_lines.append(f"• {item['name']}: {price}{desc}")
    catalog_str = "\n".join(catalog_lines) if catalog_lines else "No specific catalog items available."

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
Your ONLY goal is to assist customers with the menu, ordering, catalog items, and business hours provided in your context.

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

STRICT CONVERSATIONAL RULES & GUARDRAILS:
1. Identity & Role:
   - You are exclusively the official customer service assistant for {biz_name}.
   - Your primary responsibility is assisting customers with viewing the menu/catalog, answering store inquiries, taking orders, and providing operating hours.

2. Handling Greetings & Small Talk:
   - If the customer greets you (e.g., "Hi", "Hello", "Hey", "Good morning") or asks "How are you?":
     Respond warmly and politely, state that you are doing well, and immediately ask how you can assist them with {biz_name}'s services or menu today.

3. Out-Of-Domain (OOD) Guardrails (STRICT):
   - Under NO circumstances should you provide financial advice, coding help, technical programming assistance, political opinions, homework answers, poems, or general trivia/knowledge answers.
   - If a customer asks an unrelated or out-of-domain question (e.g., "how to save money", "write a python script", "what is the capital of France", "write a poem"):
     Politely decline by stating that you are an AI assistant tailored specifically for {biz_name}, and immediately pivot the conversation back to {biz_name}'s menu, products, or services.
     (Example: "I am specifically designed to assist with {biz_name}. I can't assist with general topics, but I'd be happy to show you our menu or help you place an order! What can I get for you today?")

4. Tone & Anti-Hallucination:
   - Keep all responses concise, friendly, and strictly professional.
   - Keep answers compact and easily readable on a mobile screen.
   - Ground all statements strictly in the provided catalog and FAQs above. Never invent or hallucinate items, prices, discounts, or policies that are not explicitly listed in your context.

5. WhatsApp Formatting:
   - Format text with WhatsApp markdown (*bold* for items/prices/emphasis, _italics_ where helpful, clean line breaks, bullet points, and appropriate emojis).

6. Ordering & Handover Workflow:
   - When a customer wants to place an order, list the items with prices, state the estimated total, and ask them to reply with *CONFIRM <Delivery Address>*.
   - When a confirmation with address is received, confirm the order enthusiastically with an estimated 30-45 min delivery time.
   - If the customer asks for a human manager or has an unresolved issue, provide the support phone: {phone}.
"""


def _build_fallback_reply(message_text: str, customer_name: str, context: Dict[str, Any]) -> str:
    """
    Polite fallback response if OpenAI API call fails or times out.
    """
    biz_name = context.get("business_name") or "our store"
    phone = context.get("phone")
    greeting = context.get("greeting") or f"Hello {customer_name}! Welcome to *{biz_name}*."

    support_line = f"\n\nIf you need immediate support, feel free to call us at *{phone}*." if phone else ""

    return (
        f"{greeting}\n\n"
        f"Thank you for contacting *{biz_name}*! We have received your message:\n"
        f"_{message_text}_\n\n"
        f"Our team is currently reviewing your inquiry and will reply shortly.{support_line}"
    )


def _generate_agent_reply(message_text: str, customer_name: str, context: Dict[str, Any]) -> str:
    """
    Generates a dynamic response using OpenAI's gpt-4o-mini model grounded in tenant data.
    Falls back gracefully to a polite static message if the API fails or is not configured.
    """
    api_key = getattr(settings, "OPENAI_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")
    model = getattr(settings, "OPENAI_MODEL", "gpt-4o-mini")

    if api_key and len(api_key.strip()) > 10:
        try:
            client = OpenAI(api_key=api_key.strip(), timeout=20.0)
            system_prompt = _build_system_prompt(customer_name, context)

            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message_text},
                ],
                temperature=0.3,
                max_tokens=350,
            )

            ai_reply = response.choices[0].message.content
            if ai_reply and ai_reply.strip():
                return ai_reply.strip()

        except Exception as e:
            logger.error(f"[WhatsApp Agent] OpenAI dynamic generation error: {e}", exc_info=True)
            print(f"[WhatsApp Agent ERROR] OpenAI generation failed: {e}")

    # Fallback when OpenAI key is missing, invalid, or request fails
    return _build_fallback_reply(message_text, customer_name, context)


def process_incoming_whatsapp_message(
    sender_phone: str,
    message_text: str,
    phone_number_id: str,
    customer_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Main background entrypoint for processing an incoming WhatsApp customer message:
    1. Loads tenant business context matching phone_number_id.
    2. Generates dynamic AI Agent reply using OpenAI (gpt-4o-mini).
    3. Sends reply via Meta Cloud API using WhatsAppService.
    """
    close_old_connections()
    try:
        clean_name = customer_name or "Valued Customer"
        logger.info(f"[WhatsApp Agent] Processing incoming message from {sender_phone} ({clean_name}): '{message_text}'")
        print(f"[WhatsApp Agent] Processing message from {sender_phone}: '{message_text}'")

        # Step 1: Load tenant context
        context = _get_business_context(phone_number_id)

        # Step 2: Dynamic LLM Generation
        reply_text = _generate_agent_reply(message_text, clean_name, context)

        # Step 3: Outbound WhatsApp dispatch via WhatsAppService
        service = WhatsAppService(phone_number_id=phone_number_id)
        dispatch_result = service.send_text_message(to=sender_phone, text=reply_text)

        logger.info(f"[WhatsApp Agent] Dispatch result for {sender_phone}: {dispatch_result.get('success')}")
        return {
            "success": dispatch_result.get("success", False),
            "reply_text": reply_text,
            "dispatch_result": dispatch_result
        }

    except Exception as e:
        logger.error(f"[WhatsApp Agent] Unhandled error processing incoming message: {e}", exc_info=True)
        print(f"[WhatsApp Agent ERROR] {e}")
        return {"success": False, "error": str(e)}

    finally:
        close_old_connections()
