import os
import sys
from decimal import Decimal

# Setup Django environment
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from django.contrib.auth import get_user_model
from companies.models import (
    Company,
    CatalogCategory,
    CatalogItem,
    Inventory,
    ServiceArea,
    BusinessKnowledge,
)
from operations.models import Order, OrderItem, ReturnRequest, OrderEvent
from accounts.models import StaffRole

User = get_user_model()


def seed():
    print("=== Seeding UrbanMart Retail Test Data ===")

    # 1. Company Creation & Activation
    company = Company.objects.filter(name__icontains="UrbanMart").first()
    if not company:
        company = Company.objects.create(
            name="UrbanMart Retail",
            business_type="retail",
            address="D-Ground, Peoples Colony No. 1, Faisalabad",
            email="info@urbanmart.pk",
            phone="03007654321",
            status="active",
            is_approved=True,
            subscription_status="active",
            is_manual_override=True,
            agent_enabled=True,
            is_calling_enabled=True,
            whatsapp_instance_name="urbanmart_retail_inst",
            whatsapp_connection_status="connected",
            agent_greeting="Welcome to UrbanMart Retail! How can I assist you today with electronics and lifestyle shopping?",
            currency_symbol="Rs.",
        )
        print("Created new UrbanMart Retail company.")
    else:
        company.business_type = "retail"
        company.status = "active"
        company.is_approved = True
        company.subscription_status = "active"
        company.is_manual_override = True
        company.agent_enabled = True
        company.is_calling_enabled = True
        company.whatsapp_instance_name = "urbanmart_retail_inst"
        company.whatsapp_connection_status = "connected"
        company.currency_symbol = "Rs."
        company.save()
        print(f"Found and updated UrbanMart Retail (ID: {company.id}).")

    # Service Delivery Area for Faisalabad (Rs. 150)
    ServiceArea.objects.get_or_create(
        company=company,
        name="Faisalabad City Zone",
        defaults={
            "area_type": "city",
            "city": "Faisalabad",
            "country": "Pakistan",
            "delivery_fee": Decimal("150.00"),
            "is_active": True,
        },
    )

    # 2. Staff Roles & Users
    # Role: Packer
    packer_role, _ = StaffRole.objects.get_or_create(
        company=company,
        name="Packer",
        defaults={
            "modules": ["fulfillment", "orders"],
            "permissions": ["orders.view", "orders.update_status"],
        },
    )
    packer_role.modules = ["fulfillment", "orders"]
    packer_role.permissions = ["orders.view", "orders.update_status"]
    packer_role.is_active = True
    packer_role.save()

    # Owner: owner@urbanmart.pk
    owner, _ = User.objects.get_or_create(
        email="owner@urbanmart.pk",
        defaults={
            "username": "owner@urbanmart.pk",
            "company": company,
            "role": User.ROLE_OWNER,
            "email_verified": True,
        },
    )
    owner.company = company
    owner.role = User.ROLE_OWNER
    owner.email_verified = True
    owner.is_active = True
    owner.set_password("Password123!")
    owner.save()
    print("Configured Owner: owner@urbanmart.pk")

    # Packer: packer@urbanmart.pk
    packer, _ = User.objects.get_or_create(
        email="packer@urbanmart.pk",
        defaults={
            "username": "packer@urbanmart.pk",
            "company": company,
            "role": User.ROLE_STAFF,
            "staff_role": packer_role,
            "email_verified": True,
        },
    )
    packer.company = company
    packer.role = User.ROLE_STAFF
    packer.staff_role = packer_role
    packer.is_active = True
    packer.email_verified = True
    packer.set_password("Password123!")
    packer.save()
    print("Configured Packer: packer@urbanmart.pk")

    # Rider: rider@urbanmart.pk
    rider, _ = User.objects.get_or_create(
        email="rider@urbanmart.pk",
        defaults={
            "username": "rider@urbanmart.pk",
            "company": company,
            "role": User.ROLE_RIDER,
            "email_verified": True,
        },
    )
    rider.company = company
    rider.role = User.ROLE_RIDER
    rider.modules = ["my_deliveries"]
    rider.email_verified = True
    rider.set_password("Password123!")
    rider.save()
    print("Configured Rider: rider@urbanmart.pk")

    # 3. Categories & Catalog Items
    electronics_cat, _ = CatalogCategory.objects.get_or_create(
        company=company,
        name="Electronics & Gadgets",
        defaults={"description": "Audio, chargers, smart wearables"},
    )
    accessories_cat, _ = CatalogCategory.objects.get_or_create(
        company=company,
        name="Accessories & Bags",
        defaults={"description": "Bags, backpacks, and daily carry"},
    )

    items_data = [
        {
            "name": "Wireless Earbuds Pro",
            "sku": "UBM-EAR-001",
            "brand": "SoundPulse",
            "price": Decimal("4500.00"),
            "cost_price": Decimal("3200.00"),
            "category": electronics_cat,
            "description": "Active noise cancelling wireless earbuds with 24hr battery life.",
            "stock_qty": Decimal("25"),
            "threshold": Decimal("5"),
            "is_available": True,
        },
        {
            "name": "Smart Watch Series 9",
            "sku": "UBM-WCH-002",
            "brand": "AeroTech",
            "price": Decimal("8500.00"),
            "cost_price": Decimal("6500.00"),
            "category": electronics_cat,
            "description": "AMOLED display smartwatch with heart-rate and SpO2 tracking.",
            "stock_qty": Decimal("8"),  # Low stock (< 10)
            "threshold": Decimal("10"),
            "is_available": True,
        },
        {
            "name": "USB-C Fast Charger 65W",
            "sku": "UBM-CHG-003",
            "brand": "PowerVolt",
            "price": Decimal("2200.00"),
            "cost_price": Decimal("1400.00"),
            "category": electronics_cat,
            "description": "GaN fast charger with dual Type-C ports for laptops and phones.",
            "stock_qty": Decimal("0"),  # Out of stock
            "threshold": Decimal("5"),
            "is_available": False,
        },
        {
            "name": "Laptop Backpack Waterproof",
            "sku": "UBM-BAG-004",
            "brand": "UrbanGear",
            "price": Decimal("3800.00"),
            "cost_price": Decimal("2600.00"),
            "category": accessories_cat,
            "description": "Water-resistant 15.6 inch laptop backpack with USB charging port.",
            "stock_qty": Decimal("15"),
            "threshold": Decimal("5"),
            "is_available": True,
        },
    ]

    catalog_map = {}
    for it in items_data:
        prod, _ = CatalogItem.objects.update_or_create(
            company=company,
            sku=it["sku"],
            defaults={
                "name": it["name"],
                "brand": it["brand"],
                "price": it["price"],
                "cost_price": it["cost_price"],
                "category": it["category"],
                "description": it["description"],
                "item_type": "product",
                "is_available": it["is_available"],
            },
        )
        catalog_map[it["sku"]] = prod

        Inventory.objects.update_or_create(
            company=company,
            item=prod,
            defaults={
                "is_unlimited": False,
                "quantity": it["stock_qty"],
                "low_stock_threshold": it["threshold"],
            },
        )
        print(f"Catalog Item: {prod.name} (Stock: {it['stock_qty']})")

    # 4. Orders
    # Order 1: To Pack (New)
    earbuds = catalog_map["UBM-EAR-001"]
    o1 = Order.objects.filter(company=company, customer_name="Hamza Sheikh").first()
    if not o1:
        o1 = Order.objects.create(
            company=company,
            customer_name="Hamza Sheikh",
            customer_phone="+923001234567",
            customer_email="hamza@example.pk",
            delivery_address="House #12, Kohinoor City, Faisalabad",
            status=Order.STATUS_NEW,
            subtotal=Decimal("4500.00"),
            delivery_fee=Decimal("150.00"),
            total=Decimal("4650.00"),
            notes="Please pack carefully in bubble wrap.",
            source="agent",
        )
        OrderItem.objects.create(
            order=o1,
            item=earbuds,
            item_name=earbuds.name,
            quantity=Decimal("1"),
            unit_price=earbuds.price,
            line_total=earbuds.price,
        )
        OrderEvent.objects.create(
            company=company,
            order=o1,
            event_type="agent_order_created",
            to_status=o1.status,
            note="Order created via WhatsApp AI Agent",
        )
        print(f"Created Order 1: {o1.order_number} (Status: {o1.status})")

    # Order 2: Ready
    backpack = catalog_map["UBM-BAG-004"]
    o2 = Order.objects.filter(company=company, customer_name="Zainab Bibi").first()
    if not o2:
        o2 = Order.objects.create(
            company=company,
            customer_name="Zainab Bibi",
            customer_phone="+923217654321",
            customer_email="zainab@example.pk",
            delivery_address="Plot #45, Susan Road, Faisalabad",
            status=Order.STATUS_READY,
            subtotal=Decimal("3800.00"),
            delivery_fee=Decimal("150.00"),
            total=Decimal("3950.00"),
            notes="Ready for rider pickup.",
            source="dashboard",
            assigned_to=packer,
            assigned_rider=rider,
        )
        OrderItem.objects.create(
            order=o2,
            item=backpack,
            item_name=backpack.name,
            quantity=Decimal("1"),
            unit_price=backpack.price,
            line_total=backpack.price,
        )
        print(f"Created Order 2: {o2.order_number} (Status: {o2.status})")

    # 5. Return / Exchange Request
    ret = ReturnRequest.objects.filter(company=company, customer_name="Bilal Farooq").first()
    if not ret:
        ret = ReturnRequest.objects.create(
            company=company,
            customer_name="Bilal Farooq",
            customer_phone="+923339876543",
            order_number=o1.order_number if o1 else "",
            order=o1,
            item_summary="1x Wireless Earbuds Pro",
            reason="Defective left earbud audio crackling",
            request_type=ReturnRequest.TYPE_RETURN,
            status=ReturnRequest.STATUS_PENDING,
            staff_notes="Customer reported within 24 hours of delivery.",
        )
        print(f"Created Return Request: {ret.return_number} (Status: {ret.status})")

    # 6. Business Knowledge Base FAQs
    BusinessKnowledge.objects.get_or_create(
        company=company,
        title="What is your return and exchange policy?",
        defaults={
            "entry_type": "faq",
            "content": "We offer a 7-day return and exchange policy for items in original condition with packaging.",
            "is_approved": True,
            "is_active": True,
        },
    )
    BusinessKnowledge.objects.get_or_create(
        company=company,
        title="What are your delivery charges and timings?",
        defaults={
            "entry_type": "faq",
            "content": "Delivery across Faisalabad is Rs. 150. Same-day delivery takes 2 to 4 hours.",
            "is_approved": True,
            "is_active": True,
        },
    )
    print("Seeded Business Knowledge FAQs.")
    print("=== UrbanMart Retail Seeding Completed Successfully! ===")


if __name__ == "__main__":
    seed()
