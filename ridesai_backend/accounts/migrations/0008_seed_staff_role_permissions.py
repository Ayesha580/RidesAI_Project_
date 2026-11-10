from django.db import migrations


ROLE_PERMISSIONS = {
    "rider": ["deliveries.view_assigned", "deliveries.update_status"],
    "delivery boy": ["deliveries.view_assigned", "deliveries.update_status"],
    "kitchen staff": ["orders.view", "orders.update_status"],
    "waiter": ["orders.view", "orders.create", "orders.update_status"],
    "cashier": ["orders.view", "orders.create", "customers.view"],
    "manager": ["orders.view", "orders.create", "orders.update_status", "deliveries.view", "deliveries.view_assigned", "deliveries.update_status", "deliveries.assign", "catalog.view", "catalog.manage", "customers.view", "agent.view", "agent.handover"],
    "pharmacist": ["orders.view", "orders.create", "orders.update_status", "catalog.view", "catalog.manage", "customers.view"],
    "doctor": ["customers.view"],
    "receptionist": ["orders.view", "orders.create", "customers.view"],
    "stock keeper": ["catalog.view", "catalog.manage"],
}


def seed_permissions(apps, schema_editor):
    StaffRole = apps.get_model("accounts", "StaffRole")
    for role in StaffRole.objects.filter(permissions=[]):
        permissions = ROLE_PERMISSIONS.get(role.name.strip().lower(), [])
        if permissions:
            role.permissions = permissions
            role.save(update_fields=["permissions"])


class Migration(migrations.Migration):
    dependencies = [("accounts", "0007_staffrole_permissions")]
    operations = [migrations.RunPython(seed_permissions, migrations.RunPython.noop)]
