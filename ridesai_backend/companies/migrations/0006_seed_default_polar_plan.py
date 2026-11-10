from decimal import Decimal
from django.db import migrations


def seed_plan(apps, schema_editor):
    Plan = apps.get_model("companies", "Plan")
    plan, created = Plan.objects.get_or_create(
        name="Standard", billing_cycle="monthly",
        defaults={
            "price": Decimal("90.86"),
            "currency": "USD",
            "polar_product_id": "6e52f9e2-b729-4ced-a9ad-df7d58f86329",
            "is_active": True,
        },
    )
    if not created and not plan.polar_product_id:
        plan.polar_product_id = "6e52f9e2-b729-4ced-a9ad-df7d58f86329"
        plan.is_active = True
        plan.save(update_fields=["polar_product_id", "is_active"])


def reverse_seed(apps, schema_editor):
    Plan = apps.get_model("companies", "Plan")
    Plan.objects.filter(name="Standard", billing_cycle="monthly",
                        polar_product_id="6e52f9e2-b729-4ced-a9ad-df7d58f86329").delete()


class Migration(migrations.Migration):
    dependencies = [("companies", "0005_company_agent_settings")]
    operations = [migrations.RunPython(seed_plan, reverse_seed)]
