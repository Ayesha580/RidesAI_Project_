from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("companies", "0003_plan_polar_product_id_currency"),
    ]
    operations = [
        migrations.CreateModel(
            name="CheckoutSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("polar_checkout_id", models.CharField(max_length=120, unique=True)),
                ("checkout_url", models.URLField(max_length=1000)),
                ("customer_email", models.EmailField(max_length=254)),
                ("status", models.CharField(choices=[("created", "Created"), ("succeeded", "Succeeded"), ("failed", "Failed"), ("expired", "Expired")], default="created", max_length=20)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="billing_checkouts", to="companies.company")),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="checkouts", to="companies.plan")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="billing_checkouts", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="PaymentTransaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("polar_checkout_id", models.CharField(blank=True, db_index=True, max_length=120)),
                ("polar_order_id", models.CharField(blank=True, max_length=120, null=True, unique=True)),
                ("polar_subscription_id", models.CharField(blank=True, db_index=True, max_length=120)),
                ("amount", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("currency", models.CharField(blank=True, max_length=10)),
                ("status", models.CharField(default="pending", max_length=30)),
                ("raw_payload", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="payment_transactions", to="companies.company")),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payment_transactions", to="companies.plan")),
            ],
        ),
        migrations.CreateModel(
            name="WebhookEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_id", models.CharField(max_length=150, unique=True)),
                ("event_type", models.CharField(max_length=120)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("processed", models.BooleanField(default=False)),
                ("processing_error", models.TextField(blank=True)),
                ("received_at", models.DateTimeField(auto_now_add=True)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
            ],
        ),
    ]
