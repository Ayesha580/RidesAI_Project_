from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("operations", "0001_initial")]
    operations = [
        migrations.AddField(model_name="agentconversation", name="customer_phone", field=models.CharField(blank=True, max_length=40)),
    ]
