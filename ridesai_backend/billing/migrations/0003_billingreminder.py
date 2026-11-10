from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("billing", "0002_manual_payment"), ("companies", "0004_single_client_access_and_business_email")]
    operations = [
        migrations.CreateModel(name="BillingReminder", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("period_end", models.DateTimeField()), ("days_remaining", models.PositiveSmallIntegerField()),
            ("sent_at", models.DateTimeField(auto_now_add=True)),
            ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="billing_reminders", to="companies.company")),
        ]),
        migrations.AddConstraint(model_name="billingreminder", constraint=models.UniqueConstraint(fields=("company", "period_end", "days_remaining"), name="unique_company_billing_reminder")),
    ]
