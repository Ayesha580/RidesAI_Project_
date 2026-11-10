from django.db import migrations


def update_modules(apps, schema_editor):
    StaffRole = apps.get_model("accounts", "StaffRole")
    for role in StaffRole.objects.select_related("company").all():
        name = role.name.strip().lower()
        modules = list(role.modules or [])
        if name in ("cashier", "manager", "receptionist", "waiter", "pharmacist") and "orders" not in modules:
            modules.append("orders")
        business = (role.company.business_type or "").lower()
        if name == "manager" and any(word in business for word in ("restaurant", "cafe", "food", "pharmacy", "grocery", "mart", "retail", "shop")):
            if "deliveries" not in modules:
                modules.append("deliveries")
        if modules != list(role.modules or []):
            role.modules = modules
            role.save(update_fields=["modules"])


class Migration(migrations.Migration):
    dependencies = [("accounts", "0008_seed_staff_role_permissions")]
    operations = [migrations.RunPython(update_modules, migrations.RunPython.noop)]
