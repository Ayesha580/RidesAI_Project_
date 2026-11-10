from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("companies", "0002_catalogcategory_catalogitem_deal_dealitem_deal_items_and_more")]
    operations = [
        migrations.AddField(
            model_name="plan",
            name="polar_product_id",
            field=models.CharField(blank=True, help_text="Polar product ID for this exact plan and billing cycle.", max_length=120),
        ),
        migrations.AddField(
            model_name="plan",
            name="currency",
            field=models.CharField(default="USD", max_length=10),
        ),
    ]
