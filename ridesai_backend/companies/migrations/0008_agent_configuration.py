from django.db import migrations, models
class Migration(migrations.Migration):
    dependencies=[('companies','0007_business_configuration')]
    operations=[
        migrations.AddField(model_name='company',name='agent_greeting',field=models.TextField(blank=True)),
        migrations.AddField(model_name='company',name='agent_tone',field=models.CharField(choices=[('friendly','Friendly'),('professional','Professional'),('concise','Concise')],default='friendly',max_length=20)),
        migrations.AddField(model_name='company',name='agent_support_phone',field=models.CharField(blank=True,max_length=30)),
        migrations.AddField(model_name='company',name='agent_support_email',field=models.EmailField(blank=True,max_length=254)),
    ]
