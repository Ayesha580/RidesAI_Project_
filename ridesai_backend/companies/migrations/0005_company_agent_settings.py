import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("companies", "0004_single_client_access_and_business_email")]
    operations = [
        migrations.AddField(model_name="company", name="agent_enabled", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="company", name="agent_public_id", field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False)),
        migrations.AddField(model_name="company", name="agent_allowed_actions", field=models.JSONField(blank=True, default=list)),
    ]
