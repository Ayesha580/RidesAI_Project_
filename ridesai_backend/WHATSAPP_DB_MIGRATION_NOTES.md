# WhatsApp Cloud API — Database Migration Notes

## 1. Overview & Context

To support rapid development while isolating the database prior to the planned **PostgreSQL migration**, WhatsApp Cloud API credentials and webhook configuration are currently handled via a **temporary file-based storage mechanism**:
- Location: `ridesai_backend/operations/whatsapp_config.json`
- Storage Handler: `ridesai_backend/operations/whatsapp_storage.py`

> **CRITICAL**: No models or database schemas have been altered for this temporary implementation. When PostgreSQL is provisioned, these settings must be migrated to proper relational database tables.

---

## 2. Target Database Schema (PostgreSQL Migration)

During the PostgreSQL migration, add the following fields either directly to the `Company` model (`companies/models.py`) or in a dedicated one-to-one model `CompanyWhatsAppConfig`:

### Recommended Option: Direct Fields on `Company` (in `companies/models.py`)
```python
# companies/models.py

class Company(models.Model):
    ...
    # WhatsApp Cloud API Integration
    whatsapp_phone_number_id = models.CharField(
        max_length=100, 
        blank=True, 
        help_text="Meta WhatsApp Business Account Phone Number ID"
    )
    whatsapp_access_token = models.TextField(
        blank=True, 
        help_text="Permanent Meta System User Access Token"
    )
    whatsapp_verify_token = models.CharField(
        max_length=255, 
        blank=True, 
        default="ridesai_verify_token",
        help_text="Secret token for Meta hub.verify_token handshake"
    )
    whatsapp_is_active = models.BooleanField(
        default=False, 
        help_text="Whether WhatsApp messaging is actively enabled for this business"
    )
```

### Alternative Option: Dedicated `CompanyWhatsAppConfig` Model (`operations/models.py`)
```python
# operations/models.py

class CompanyWhatsAppConfig(models.Model):
    company = models.OneToOneField(
        'companies.Company', 
        on_delete=models.CASCADE, 
        related_name='whatsapp_config'
    )
    phone_number_id = models.CharField(max_length=100, blank=True)
    access_token = models.TextField(blank=True)
    verify_token = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"WhatsApp Config ({self.company.name})"
```

---

## 3. Exact Fields Specification

| Field Name | Django Model Field | DB Type (Postgres) | Null/Blank | Default | Purpose |
|---|---|---|---|---|---|
| `phone_number_id` | `models.CharField(max_length=100)` | `VARCHAR(100)` | `blank=True` | `""` | Identifies the business sender phone in Meta Cloud API. |
| `access_token` | `models.TextField()` | `TEXT` | `blank=True` | `""` | Permanent System User token with `whatsapp_business_messaging` permission. |
| `verify_token` | `models.CharField(max_length=255)` | `VARCHAR(255)` | `blank=True` | auto-generated | Secret token for Meta Webhook challenge handshake. |
| `is_active` | `models.BooleanField()` | `BOOLEAN` | `null=False` | `False` | Toggles whether incoming/outgoing messages are processed. |

---

## 4. Data Migration Procedure (File to PostgreSQL)

When creating the PostgreSQL migration:
1. Run `python manage.py makemigrations` and `python manage.py migrate`.
2. Execute a data migration script (or Django custom management command) that reads `ridesai_backend/operations/whatsapp_config.json`:
   ```python
   import json
   from pathlib import Path
   from companies.models import Company

   config_file = Path("operations/whatsapp_config.json")
   if config_file.exists():
       with open(config_file, "r", encoding="utf-8") as f:
           configs = json.load(f)

       for company_key, data in configs.items():
           if company_key == "default":
               continue
           try:
               company = Company.objects.get(id=int(company_key))
               company.whatsapp_phone_number_id = data.get("phone_number_id", "")
               company.whatsapp_access_token = data.get("access_token", "")
               company.whatsapp_verify_token = data.get("verify_token", "")
               company.whatsapp_is_active = data.get("is_active", False)
               company.save(update_fields=[
                   "whatsapp_phone_number_id", 
                   "whatsapp_access_token", 
                   "whatsapp_verify_token", 
                   "whatsapp_is_active"
               ])
           except (Company.DoesNotExist, ValueError):
               pass
   ```
3. Update `operations/views.py` to query the ORM instead of calling `whatsapp_storage.py`.
4. Safely delete `ridesai_backend/operations/whatsapp_config.json` and archive `whatsapp_storage.py`.
