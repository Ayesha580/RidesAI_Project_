from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0006_emailverificationtoken_attempts")]
    operations = [
        migrations.AddField(
            model_name="staffrole",
            name="permissions",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
