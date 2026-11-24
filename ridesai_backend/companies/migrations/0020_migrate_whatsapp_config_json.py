"""
One-time safe data migration: imports existing Meta WhatsApp Cloud API credentials
from legacy `operations/whatsapp_config.json` into `companies.Company` in PostgreSQL.
Never overwrites already-populated database records.
"""

import json
from pathlib import Path

from django.db import migrations
from django.utils import timezone


def migrate_whatsapp_config_json(apps, schema_editor):
    Company = apps.get_model("companies", "Company")
    json_path = Path(__file__).resolve().parent.parent.parent / "operations" / "whatsapp_config.json"
    if not json_path.exists():
        return

    try:
        raw = json_path.read_text(encoding="utf-8").strip()
        if not raw:
            return
        configs = json.loads(raw)
    except Exception:
        return

    if not isinstance(configs, dict):
        return

    now = timezone.now()
    for key, cfg in configs.items():
        if key == "default" or not isinstance(cfg, dict):
            continue
        try:
            company_id = int(key)
        except (TypeError, ValueError):
            continue

        company = Company.objects.filter(pk=company_id).first()
        if not company:
            continue

        # Never overwrite already-populated DB records
        if (company.whatsapp_phone_number_id or "").strip() or (company.whatsapp_access_token or "").strip():
            continue

        pid = str(cfg.get("phone_number_id") or "").strip()
        tok = str(cfg.get("access_token") or "").strip()
        vtok = str(cfg.get("verify_token") or "").strip()
        active = bool(cfg.get("is_active", False))

        if not (pid or tok or vtok):
            continue

        company.whatsapp_phone_number_id = pid
        company.whatsapp_access_token = tok
        if vtok and not (company.whatsapp_verify_token or "").strip():
            company.whatsapp_verify_token = vtok
        company.whatsapp_is_active = active
        company.whatsapp_updated_at = now
        company.save(
            update_fields=[
                "whatsapp_phone_number_id",
                "whatsapp_access_token",
                "whatsapp_verify_token",
                "whatsapp_is_active",
                "whatsapp_updated_at",
            ]
        )


class Migration(migrations.Migration):
    dependencies = [
        ("companies", "0019_company_whatsapp_cloud_fields"),
    ]

    operations = [
        migrations.RunPython(migrate_whatsapp_config_json, migrations.RunPython.noop),
    ]
