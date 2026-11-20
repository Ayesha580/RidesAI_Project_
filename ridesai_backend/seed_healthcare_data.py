import os
import sys
from datetime import date, timedelta
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
from operations.models import MedicineBatch
from accounts.models import StaffRole

User = get_user_model()

def seed():
    print("=== Seeding HealthCare Pharmacy Test Data ===")

    # 1. Company Verification & Activation
    company = Company.objects.filter(name__icontains="HealthCare").first()
    if not company:
        company = Company.objects.create(
            name="HealthCare",
            business_type="pharmacy",
            address="Jaranwala Road, Kohinoor City, Faisalabad",
            email="info@healthcare.pk",
            phone="03001234567",
            status="active",
            is_approved=True,
            subscription_status="active",
            is_manual_override=True,
        )
        print("Created new HealthCare company.")
    else:
        company.business_type = "pharmacy"
        company.status = "active"
        company.is_approved = True
        company.subscription_status = "active"
        company.is_manual_override = True
        company.save()
        print(f"Found and activated HealthCare company (ID: {company.id}).")

    # 2. Delivery Zone (ServiceArea)
    service_area, sa_created = ServiceArea.objects.get_or_create(
        company=company,
        name="Faisalabad Delivery Zone",
        defaults={
            "area_type": "city",
            "city": "Faisalabad",
            "country": "Pakistan",
            "delivery_fee": Decimal("100.00"),
            "is_active": True,
        }
    )
    if not sa_created:
        service_area.area_type = "city"
        service_area.city = "Faisalabad"
        service_area.delivery_fee = Decimal("100.00")
        service_area.is_active = True
        service_area.save()
    print(f"Delivery Zone: {service_area.name} (Fee: Rs. {service_area.delivery_fee})")

    # 3. Categories
    category_names = ["Pain Relief", "Antibiotics", "Vitamins & Supplements"]
    categories = {}
    for cname in category_names:
        cat, _ = CatalogCategory.objects.get_or_create(
            company=company,
            name=cname,
            defaults={"is_active": True}
        )
        categories[cname] = cat
        print(f"Category: {cat.name}")

    # 4. Medicines & Inventory
    medicines_spec = [
        {
            "name": "Panadol 500mg",
            "generic_name": "Paracetamol",
            "price": Decimal("50.00"),
            "cost_price": Decimal("35.00"),
            "category": categories["Pain Relief"],
            "requires_prescription": False,
            "stock": Decimal("100.00"),
            "unit": "pack",
        },
        {
            "name": "Brufen 400mg",
            "generic_name": "Ibuprofen",
            "price": Decimal("120.00"),
            "cost_price": Decimal("85.00"),
            "category": categories["Pain Relief"],
            "requires_prescription": False,
            "stock": Decimal("80.00"),
            "unit": "pack",
        },
        {
            "name": "Augmentin 625mg",
            "generic_name": "Amoxicillin + Clavulanic Acid",
            "price": Decimal("450.00"),
            "cost_price": Decimal("340.00"),
            "category": categories["Antibiotics"],
            "requires_prescription": True,
            "stock": Decimal("50.00"),
            "unit": "box",
        },
        {
            "name": "Cac-1000 Plus",
            "generic_name": "Calcium + Vitamin C",
            "price": Decimal("320.00"),
            "cost_price": Decimal("240.00"),
            "category": categories["Vitamins & Supplements"],
            "requires_prescription": False,
            "stock": Decimal("60.00"),
            "unit": "tube",
        },
    ]

    items_dict = {}
    for med in medicines_spec:
        item, _ = CatalogItem.objects.get_or_create(
            company=company,
            name=med["name"],
            defaults={
                "generic_name": med["generic_name"],
                "price": med["price"],
                "cost_price": med["cost_price"],
                "category": med["category"],
                "requires_prescription": med["requires_prescription"],
                "unit": med["unit"],
                "item_type": "product",
                "is_available": True,
            }
        )
        item.generic_name = med["generic_name"]
        item.price = med["price"]
        item.cost_price = med["cost_price"]
        item.category = med["category"]
        item.requires_prescription = med["requires_prescription"]
        item.unit = med["unit"]
        item.is_available = True
        item.save()

        # Update Inventory
        inv, _ = Inventory.objects.get_or_create(
            company=company,
            item=item,
            defaults={
                "is_unlimited": False,
                "quantity": med["stock"],
                "low_stock_threshold": Decimal("10.00"),
            }
        )
        inv.is_unlimited = False
        inv.quantity = med["stock"]
        inv.low_stock_threshold = Decimal("10.00")
        inv.save()

        items_dict[med["name"]] = item
        rx_label = "Rx" if item.requires_prescription else "OTC"
        print(f"Medicine: {item.name} | Generic: {item.generic_name} | Price: Rs. {item.price} | Stock: {inv.quantity} | {rx_label}")

    # 5. Medicine Batches
    today = date.today()
    batches_spec = [
        {
            "item_name": "Panadol 500mg",
            "batch_number": "PAN-2027A",
            "expiry_date": date(2027, 8, 15),
            "quantity": 100,
            "supplier_name": "GSK Pakistan",
        },
        {
            "item_name": "Brufen 400mg",
            "batch_number": "BRU-2026B",
            "expiry_date": today + timedelta(days=15),
            "quantity": 8,
            "supplier_name": "Abbott Labs",
        },
        {
            "item_name": "Augmentin 625mg",
            "batch_number": "AUG-2025X",
            "expiry_date": today - timedelta(days=30),
            "quantity": 12,
            "supplier_name": "GSK Pakistan",
        },
    ]

    for b in batches_spec:
        item = items_dict[b["item_name"]]
        batch, _ = MedicineBatch.objects.get_or_create(
            company=company,
            item=item,
            batch_number=b["batch_number"],
            defaults={
                "expiry_date": b["expiry_date"],
                "quantity": b["quantity"],
                "supplier_name": b["supplier_name"],
            }
        )
        batch.expiry_date = b["expiry_date"]
        batch.quantity = b["quantity"]
        batch.supplier_name = b["supplier_name"]
        batch.save()
        print(f"Batch: {batch.batch_number} ({b['item_name']}) | Expiry: {batch.expiry_date} | Qty: {batch.quantity} | Status: {batch.status}")

    # 6. Staff Roles & Employees
    # Role: Pharmacist
    pharmacist_role, _ = StaffRole.objects.get_or_create(
        company=company,
        name="Pharmacist",
        defaults={
            "modules": [
                "orders",
                "medicines",
                "prescriptions",
                "expiry_tracking",
                "controlled_drugs",
                "inventory",
                "pos",
                "customers",
            ],
            "permissions": [
                "orders.view",
                "orders.create",
                "orders.update_status",
                "catalog.view",
                "catalog.manage",
                "prescriptions.view",
                "prescriptions.manage",
                "batches.view",
                "batches.manage",
                "customers.view",
                "agent.view",
                "agent.handover",
            ],
            "is_active": True,
        }
    )
    pharmacist_role.modules = [
        "orders",
        "medicines",
        "prescriptions",
        "expiry_tracking",
        "controlled_drugs",
        "inventory",
        "pos",
        "customers",
    ]
    pharmacist_role.permissions = [
        "orders.view",
        "orders.create",
        "orders.update_status",
        "catalog.view",
        "catalog.manage",
        "prescriptions.view",
        "prescriptions.manage",
        "batches.view",
        "batches.manage",
        "customers.view",
        "agent.view",
        "agent.handover",
    ]
    pharmacist_role.save()

    # User: pharmacist@healthcare.pk
    pharmacist_user, p_created = User.objects.get_or_create(
        email="pharmacist@healthcare.pk",
        defaults={
            "username": "pharmacist@healthcare.pk",
            "company": company,
            "role": User.ROLE_STAFF,
            "staff_role": pharmacist_role,
            "email_verified": True,
        }
    )
    pharmacist_user.company = company
    pharmacist_user.role = User.ROLE_STAFF
    pharmacist_user.staff_role = pharmacist_role
    pharmacist_user.email_verified = True
    pharmacist_user.set_password("Password123!")
    pharmacist_user.save()
    print(f"Employee (Pharmacist): {pharmacist_user.email} (Password: Password123!)")

    # Role: Delivery Rider
    rider_role, _ = StaffRole.objects.get_or_create(
        company=company,
        name="Delivery Rider",
        defaults={
            "modules": ["my_deliveries"],
            "permissions": ["deliveries.view_assigned", "deliveries.update_status"],
            "is_active": True,
        }
    )
    rider_role.modules = ["my_deliveries"]
    rider_role.permissions = ["deliveries.view_assigned", "deliveries.update_status"]
    rider_role.save()

    # User: rider@healthcare.pk
    rider_user, r_created = User.objects.get_or_create(
        email="rider@healthcare.pk",
        defaults={
            "username": "rider@healthcare.pk",
            "company": company,
            "role": User.ROLE_RIDER,
            "staff_role": rider_role,
            "email_verified": True,
        }
    )
    rider_user.company = company
    rider_user.role = User.ROLE_RIDER
    rider_user.staff_role = rider_role
    rider_user.email_verified = True
    rider_user.set_password("Password123!")
    rider_user.save()
    print(f"Employee (Rider): {rider_user.email} (Password: Password123!)")

    # 7. Knowledge Base FAQs
    faqs = [
        {
            "title": "Delivery Policy",
            "content": "We deliver across Faisalabad for Rs. 100. Free delivery on orders above Rs. 1500.",
            "entry_type": "policy",
        },
        {
            "title": "Prescription Policy",
            "content": "Prescription medicines (Rx) such as antibiotics require pharmacist verification before dispensing.",
            "entry_type": "policy",
        },
    ]

    for faq in faqs:
        kb, _ = BusinessKnowledge.objects.get_or_create(
            company=company,
            title=faq["title"],
            defaults={
                "content": faq["content"],
                "entry_type": faq["entry_type"],
                "is_approved": True,
                "is_active": True,
                "source": "business",
            }
        )
        kb.content = faq["content"]
        kb.entry_type = faq["entry_type"]
        kb.is_approved = True
        kb.is_active = True
        kb.source = "business"
        kb.save()
        print(f"Knowledge FAQ: '{kb.title}' -> '{kb.content}'")

    print("\n=== Seeding Finished Successfully! ===")

if __name__ == "__main__":
    seed()
