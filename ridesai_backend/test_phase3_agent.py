"""
Phase 3 Local Terminal Test Script: AI Agent Tool-Calling & Dynamic Order Execution.

Dynamically binds to the active tenant 'burger king' to ensure strict multi-tenant
isolation matches the logged-in dashboard user.
"""

import os
import sys
from decimal import Decimal
from pathlib import Path

# Ensure ridesai_backend directory is in sys.path so script can be run from anywhere
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from companies.models import Company, CatalogItem
from operations.models import Order, AgentConversation
from operations.whatsapp_agent import _generate_agent_reply, get_business_context_for_company


def setup_test_data():
    """
    Dynamically searches for 'burger king' (case-insensitive) in the database.
    Ensures 'burger king' has active catalog items ready for tool-calling.
    """
    # 1. Search for 'burger king' company
    company = Company.objects.filter(name__iexact="burger king").first()
    if not company:
        company = Company.objects.filter(name__icontains="burger king").first()
    if not company:
        from accounts.models import User
        user = User.objects.filter(email__iexact="rubaisha1705@gmail.com").first()
        if user and user.company:
            company = user.company
    if not company:
        print("ℹ️ Creating 'burger king' company...")
        company = Company.objects.create(
            name="burger king",
            business_type="restaurant",
            status="active",
            is_approved=True,
            phone="+923001234567",
            address="Faisalabad, Pakistan",
            agent_greeting="Welcome to Burger King!",
        )

    # Ensure company status is active & approved
    company.status = "active"
    company.is_approved = True
    company.agent_greeting = "Welcome to Burger King!"
    company.save(update_fields=["status", "is_approved", "agent_greeting"])

    # 2. Ensure test catalog items exist specifically for 'burger king'
    items_to_create = [
        {"name": "Zinger Burger", "price": Decimal("650.00"), "description": "Crispy fried chicken fillet with spicy mayo & fresh lettuce"},
        {"name": "Whopper Burger", "price": Decimal("850.00"), "description": "Flame-grilled beef patty with juicy tomatoes, lettuce & mayo"},
        {"name": "French Fries", "price": Decimal("250.00"), "description": "Hot and golden salted french fries"},
        {"name": "Crispy Fries", "price": Decimal("220.00"), "description": "Crispy seasoned golden french fries"},
        {"name": "Cold Drink", "price": Decimal("150.00"), "description": "Chilled soft drink can (Coke / Sprite / Fanta)"},
    ]

    for it in items_to_create:
        CatalogItem.objects.get_or_create(
            company=company,
            name=it["name"],
            defaults={"price": it["price"], "description": it["description"], "is_available": True},
        )
        CatalogItem.objects.filter(company=company, name=it["name"]).update(is_available=True)

    return company


def run_tool_calling_test():
    print("=================================================================")
    print("🤖 Rides AI Phase 3: Tool-Calling & Order Execution Terminal Test")
    print("=================================================================")

    company = setup_test_data()
    print(f"🏢 Active Target Business: '{company.name}' (ID: {company.id})")

    # Get grounded context for the company
    context = get_business_context_for_company(company)
    catalog_names = [i["name"] for i in context.get("catalog", [])]
    print(f"📋 Available Catalog Items in DB: {', '.join(catalog_names)}")

    test_phone = "+923001234567"
    customer_name = "Ali Khan"

    # 1. Pehla sawal: Catalog inquiry (Triggers get_catalog_items tool or catalog grounding)
    print("\n-----------------------------------------------------------------")
    print("👤 Customer Inquiry 1:")
    print("   'Menu mein kya kya available hai aur prices kya hain?'")
    print("-----------------------------------------------------------------")
    reply1 = _generate_agent_reply(
        message_text="Menu mein kya kya available hai aur prices kya hain?",
        customer_name=customer_name,
        context=context,
        sender_phone=test_phone,
    )
    print(f"🤖 Agent Response:\n{reply1}")

    # 2. Doosra sawal: Order Placement with delivery address (Triggers create_order tool)
    print("\n-----------------------------------------------------------------")
    print("👤 Customer Inquiry 2 (Order Execution):")
    print("   'Mujhe 2 Zinger Burger aur 1 French Fries bhej do, address House #45, Street 2, Johar Town, Lahore hai.'")
    print("-----------------------------------------------------------------")
    reply2 = _generate_agent_reply(
        message_text="Mujhe 2 Zinger Burger aur 1 French Fries bhej do, address House #45, Street 2, Johar Town, Lahore hai.",
        customer_name=customer_name,
        context=context,
        sender_phone=test_phone,
    )
    print(f"🤖 Agent Response:\n{reply2}")

    # 3. Database Verification: Check if order was created atomically in the DB for this company
    print("\n-----------------------------------------------------------------")
    print("🔍 Database Verification for Tenant:")
    print("-----------------------------------------------------------------")
    recent_order = Order.objects.filter(company=company, customer_phone=test_phone).order_by("-created_at").first()

    if recent_order:
        print(f"✅ SUCCESS! Live Order successfully placed in database for '{company.name}'!")
        print(f"   • Order Number   : {recent_order.order_number}")
        print(f"   • Company        : {recent_order.company.name} (ID: {recent_order.company_id})")
        print(f"   • Customer Name  : {recent_order.customer_name}")
        print(f"   • Customer Phone : {recent_order.customer_phone}")
        print(f"   • Delivery Addr  : {recent_order.delivery_address}")
        print(f"   • Status         : {recent_order.status}")
        print(f"   • Source         : {recent_order.source}")
        print(f"   • Subtotal       : Rs. {recent_order.subtotal}")
        print(f"   • Total          : Rs. {recent_order.total}")

        order_items = recent_order.items.all()
        print(f"   • Items Count    : {order_items.count()}")
        for idx, item in enumerate(order_items, 1):
            print(f"     {idx}. {item.quantity}x {item.item_name} @ Rs. {item.unit_price} = Rs. {item.line_total}")

        events = recent_order.events.all()
        if events.exists():
            print(f"   • Audit Events   : {[e.event_type for e in events]}")
    else:
        print(f"❌ FAILED! AI responded but did not create an Order in the database for '{company.name}'.")

    # Check conversations
    conv = AgentConversation.objects.filter(company=company, customer_phone=test_phone).first()
    if conv:
        print(f"✅ SUCCESS! Live Conversation logged in DB for '{company.name}' with {conv.messages.count()} messages.")

    print("\n=================================================================")
    print("🏁 Test Completed.")
    print("=================================================================")


if __name__ == "__main__":
    run_tool_calling_test()
