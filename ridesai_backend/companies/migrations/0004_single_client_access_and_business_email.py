from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("companies", "0003_plan_polar_product_id_currency")]
    operations = [
        migrations.AddField(model_name="company", name="initial_access_started_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="company", name="access_expires_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="company", name="renewal_due_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="company", name="message_limit", field=models.PositiveIntegerField(default=1000)),
        migrations.AddField(model_name="company", name="messages_used", field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="company", name="message_period_started_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="company", name="business_email_address", field=models.EmailField(blank=True, max_length=254)),
        migrations.AddField(model_name="company", name="business_email_domain", field=models.CharField(blank=True, max_length=253)),
        migrations.AddField(model_name="company", name="business_email_setup_status", field=models.CharField(choices=[("not_started", "Not started"), ("in_progress", "In progress"), ("completed", "Completed")], default="not_started", max_length=20)),
    ]
