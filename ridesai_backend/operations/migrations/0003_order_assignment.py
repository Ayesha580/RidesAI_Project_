import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('operations','0002_agentconversation_customer_phone'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AddField(model_name='order', name='assigned_team', field=models.CharField(blank=True, max_length=80)),
        migrations.AddField(model_name='order', name='assigned_to', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_business_orders', to=settings.AUTH_USER_MODEL)),
    ]
