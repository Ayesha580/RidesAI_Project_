import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("companies", "0006_seed_default_polar_plan"),
    ]
    operations = [
        migrations.CreateModel(name="Order", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("order_number", models.CharField(editable=False, max_length=24, unique=True)),
            ("customer_name", models.CharField(max_length=160)), ("customer_email", models.EmailField(blank=True, max_length=254)),
            ("customer_phone", models.CharField(blank=True, max_length=40)), ("delivery_address", models.TextField(blank=True)),
            ("status", models.CharField(choices=[("new", "New"), ("confirmed", "Confirmed"), ("preparing", "Preparing"), ("ready", "Ready"), ("assigned", "Assigned"), ("picked_up", "Picked Up"), ("on_the_way", "On The Way"), ("delivered", "Delivered"), ("cancelled", "Cancelled")], db_index=True, default="new", max_length=20)),
            ("subtotal", models.DecimalField(decimal_places=2, default=0, max_digits=12)), ("delivery_fee", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
            ("total", models.DecimalField(decimal_places=2, default=0, max_digits=12)), ("notes", models.TextField(blank=True)),
            ("source", models.CharField(choices=[("dashboard", "Dashboard"), ("agent", "AI Agent"), ("api", "API")], default="dashboard", max_length=20)),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="orders", to="companies.company")),
            ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_orders", to=settings.AUTH_USER_MODEL)),
        ], options={"ordering": ("-created_at",), "indexes": [models.Index(fields=["company", "status", "-created_at"], name="op_order_comp_status_idx")]}),
        migrations.CreateModel(name="OrderItem", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("item_name", models.CharField(max_length=200)), ("quantity", models.DecimalField(decimal_places=3, default=1, max_digits=12)),
            ("unit_price", models.DecimalField(decimal_places=2, max_digits=12)), ("line_total", models.DecimalField(decimal_places=2, max_digits=12)),
            ("item", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="companies.catalogitem")),
            ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="operations.order")),
        ]),
        migrations.CreateModel(name="DeliveryAssignment", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("status", models.CharField(choices=[("new", "New"), ("confirmed", "Confirmed"), ("preparing", "Preparing"), ("ready", "Ready"), ("assigned", "Assigned"), ("picked_up", "Picked Up"), ("on_the_way", "On The Way"), ("delivered", "Delivered"), ("cancelled", "Cancelled")], default="assigned", max_length=20)),
            ("assigned_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="delivery_assignments", to="companies.company")),
            ("assigned_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="assigned_deliveries", to=settings.AUTH_USER_MODEL)),
            ("order", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="delivery", to="operations.order")),
            ("rider", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="delivery_assignments", to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.CreateModel(name="OrderEvent", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("event_type", models.CharField(max_length=60)), ("from_status", models.CharField(blank=True, max_length=20)),
            ("to_status", models.CharField(blank=True, max_length=20)), ("note", models.TextField(blank=True)),
            ("metadata", models.JSONField(blank=True, default=dict)), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="order_events", to="companies.company")),
            ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="events", to="operations.order")),
        ]),
        migrations.CreateModel(name="AgentConversation", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("conversation_key", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
            ("customer_name", models.CharField(blank=True, max_length=160)), ("customer_email", models.EmailField(blank=True, max_length=254)),
            ("status", models.CharField(choices=[("bot", "Bot"), ("human", "Human handover"), ("closed", "Closed")], default="bot", max_length=20)),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("assigned_to", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="agent_handover_conversations", to=settings.AUTH_USER_MODEL)),
            ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="agent_conversations", to="companies.company")),
        ]),
        migrations.CreateModel(name="AgentMessage", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("role", models.CharField(choices=[("user", "User"), ("assistant", "Assistant"), ("system", "System"), ("human", "Human")], max_length=20)),
            ("content", models.TextField()), ("metadata", models.JSONField(blank=True, default=dict)), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("conversation", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="messages", to="operations.agentconversation")),
        ], options={"ordering": ("created_at",)}),
        migrations.CreateModel(name="AgentActionLog", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("action", models.CharField(max_length=80)), ("allowed", models.BooleanField(default=False)),
            ("request_data", models.JSONField(blank=True, default=dict)), ("result_data", models.JSONField(blank=True, default=dict)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="agent_action_logs", to="companies.company")),
            ("conversation", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="operations.agentconversation")),
        ]),
    ]
