import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('companies', '0006_seed_default_polar_plan')]
    operations = [
        migrations.CreateModel(name='BusinessLocation', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('name', models.CharField(max_length=150)), ('address', models.TextField()),
            ('city', models.CharField(blank=True, max_length=100)), ('country', models.CharField(blank=True, max_length=100)),
            ('phone', models.CharField(blank=True, max_length=30)),
            ('latitude', models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
            ('longitude', models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
            ('is_primary', models.BooleanField(default=False)), ('is_active', models.BooleanField(default=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='locations', to='companies.company')),
        ], options={'ordering': ['-is_primary', 'name']}),
        migrations.CreateModel(name='BusinessHours', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('day_of_week', models.PositiveSmallIntegerField(choices=[(0,'Monday'),(1,'Tuesday'),(2,'Wednesday'),(3,'Thursday'),(4,'Friday'),(5,'Saturday'),(6,'Sunday')])),
            ('opens_at', models.TimeField(blank=True, null=True)), ('closes_at', models.TimeField(blank=True, null=True)),
            ('is_closed', models.BooleanField(default=False)),
            ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='business_hours', to='companies.company')),
            ('location', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='hours', to='companies.businesslocation')),
        ], options={'ordering': ['day_of_week']}),
        migrations.AddConstraint(model_name='businesshours', constraint=models.UniqueConstraint(fields=('company','location','day_of_week'), name='unique_business_hours_day')),
        migrations.CreateModel(name='ServiceArea', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('name', models.CharField(max_length=150)), ('area_type', models.CharField(choices=[('city','City'),('country','Country'),('radius','Radius')], default='city', max_length=20)),
            ('city', models.CharField(blank=True, max_length=100)), ('country', models.CharField(blank=True, max_length=100)),
            ('center_latitude', models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
            ('center_longitude', models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
            ('radius_km', models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
            ('delivery_fee', models.DecimalField(decimal_places=2, default=0, max_digits=10)), ('is_active', models.BooleanField(default=True)),
            ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='service_areas', to='companies.company')),
        ], options={'ordering': ['name']}),
        migrations.CreateModel(name='BusinessKnowledge', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('entry_type', models.CharField(choices=[('faq','FAQ'),('policy','Policy'),('procedure','Procedure'),('approved_response','Approved response'),('support','Support contact')], default='faq', max_length=30)),
            ('title', models.CharField(max_length=200)), ('content', models.TextField()),
            ('is_approved', models.BooleanField(default=True)), ('is_active', models.BooleanField(default=True)),
            ('source', models.CharField(choices=[('business','Business supplied'),('suggested','AI suggested')], default='business', max_length=30)),
            ('created_at', models.DateTimeField(auto_now_add=True)), ('updated_at', models.DateTimeField(auto_now=True)),
            ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='knowledge_entries', to='companies.company')),
        ], options={'ordering': ['entry_type', 'title']}),
    ]
