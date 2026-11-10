from django.db import migrations

def add_permissions(apps, schema_editor):
    StaffRole = apps.get_model('accounts', 'StaffRole')
    for role in StaffRole.objects.all():
        if role.name.strip().lower() == 'manager':
            perms = list(role.permissions or [])
            for value in ('orders.assign', 'orders.view_all'):
                if value not in perms: perms.append(value)
            role.permissions = perms
            role.save(update_fields=['permissions'])

def reverse_permissions(apps, schema_editor):
    StaffRole = apps.get_model('accounts', 'StaffRole')
    for role in StaffRole.objects.all():
        if role.name.strip().lower() == 'manager':
            role.permissions = [p for p in (role.permissions or []) if p not in ('orders.assign','orders.view_all')]
            role.save(update_fields=['permissions'])

class Migration(migrations.Migration):
    dependencies=[('accounts','0009_add_orders_to_existing_roles')]
    operations=[migrations.RunPython(add_permissions, reverse_permissions)]
