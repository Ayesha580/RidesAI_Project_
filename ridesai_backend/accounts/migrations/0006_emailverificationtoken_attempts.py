from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("accounts", "0005_email_verification")]
    operations = [migrations.AddField(model_name="emailverificationtoken", name="attempts", field=models.PositiveSmallIntegerField(default=0))]
