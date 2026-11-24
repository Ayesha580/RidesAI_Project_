"""
PostgreSQL-backed storage utility for Meta WhatsApp Cloud API credentials.

All reads and writes persist strictly to the `companies.Company` model in PostgreSQL
(multi-tenant scoped per Company), replacing the legacy `whatsapp_config.json` file.
"""

import json
import logging
from pathlib import Path

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# Legacy file path retained only for optional one-time migration import.
LEGACY_STORAGE_FILE = Path(__file__).resolve().parent / "whatsapp_config.json"

DEFAULT_CONFIG = {
    "phone_number_id": "",
    "access_token": "",
    "verify_token": "ridesai_default_verify_token",
    "is_active": False,
    "updated_at": "",
}


def _company_to_config_dict(company) -> dict:
    updated_at = ""
    if getattr(company, "whatsapp_updated_at", None):
        updated_at = company.whatsapp_updated_at.isoformat()
    return {
        "phone_number_id": (company.whatsapp_phone_number_id or "").strip(),
        "access_token": (company.whatsapp_access_token or "").strip(),
        "verify_token": (company.whatsapp_verify_token or "").strip() or f"ridesai_wa_{company.id}",
        "is_active": bool(company.whatsapp_is_active),
        "updated_at": updated_at,
    }


def get_whatsapp_config(company_id=None) -> dict:
    """
    Retrieves the Meta WhatsApp Cloud API configuration for a specific company from PostgreSQL.
    Auto-generates and persists a default per-company verify_token if blank.
    """
    from companies.models import Company

    if company_id is not None:
        company = Company.objects.filter(pk=company_id).first()
        if not company:
            cfg = dict(DEFAULT_CONFIG)
            cfg["verify_token"] = f"ridesai_wa_{company_id}"
            return cfg

        if not (company.whatsapp_verify_token or "").strip():
            company.whatsapp_verify_token = f"ridesai_wa_{company.id}"
            company.save(update_fields=["whatsapp_verify_token"])

        return _company_to_config_dict(company)

    # Fallback when called without company_id: return first active configured company or defaults
    company = (
        Company.objects.filter(whatsapp_is_active=True)
        .exclude(whatsapp_phone_number_id="")
        .order_by("id")
        .first()
    )
    if company:
        return _company_to_config_dict(company)

    return dict(DEFAULT_CONFIG)


def save_whatsapp_config(data: dict, company_id=None) -> dict:
    """
    Saves or updates the Meta WhatsApp Cloud API configuration for a company in PostgreSQL.
    """
    from companies.models import Company

    if company_id is None:
        raise ValueError("company_id is required to save WhatsApp configuration in PostgreSQL.")

    company = Company.objects.filter(pk=company_id).first()
    if not company:
        raise Company.DoesNotExist(f"Company with id={company_id} does not exist.")

    existing_verify = (company.whatsapp_verify_token or "").strip() or f"ridesai_wa_{company.id}"

    if "phone_number_id" in data:
        company.whatsapp_phone_number_id = str(data.get("phone_number_id") or "").strip()
    if "access_token" in data:
        company.whatsapp_access_token = str(data.get("access_token") or "").strip()
    if "verify_token" in data:
        new_vt = str(data.get("verify_token") or "").strip()
        company.whatsapp_verify_token = new_vt or existing_verify
    elif not (company.whatsapp_verify_token or "").strip():
        company.whatsapp_verify_token = existing_verify
    if "is_active" in data:
        company.whatsapp_is_active = bool(data.get("is_active"))

    company.whatsapp_updated_at = timezone.now()
    company.save(
        update_fields=[
            "whatsapp_phone_number_id",
            "whatsapp_access_token",
            "whatsapp_verify_token",
            "whatsapp_is_active",
            "whatsapp_updated_at",
        ]
    )
    return _company_to_config_dict(company)


def is_valid_verify_token(token: str) -> bool:
    """
    Checks if a given verify token matches any company's stored verify token in PostgreSQL,
    the settings WHATSAPP_VERIFY_TOKEN, or the default fallback token.
    Used for Meta Webhook subscription verification.
    """
    if not token:
        return False

    from companies.models import Company

    clean_token = str(token).strip()
    if Company.objects.filter(whatsapp_verify_token=clean_token).exists():
        return True

    env_token = getattr(settings, "WHATSAPP_VERIFY_TOKEN", "")
    if env_token and clean_token == env_token:
        return True

    return clean_token == DEFAULT_CONFIG["verify_token"]


def get_config_by_phone_number_id(phone_number_id: str) -> dict | None:
    """
    Finds the company config matching an incoming Meta message's recipient phone_number_id
    strictly from PostgreSQL. Returns config dict including `company_id` or None if unmapped.
    """
    if not phone_number_id:
        return None

    from companies.models import Company

    clean_pid = str(phone_number_id).strip()
    if not clean_pid:
        return None

    company = Company.objects.filter(whatsapp_phone_number_id=clean_pid).order_by("id").first()
    if not company:
        return None

    res = _company_to_config_dict(company)
    res["company_id"] = str(company.id)
    return res


def import_legacy_whatsapp_config_json(json_path: Path | None = None) -> int:
    """
    Safe one-time import helper: copies entries from legacy `whatsapp_config.json`
    into PostgreSQL `Company` records ONLY where DB fields are still empty.
    Never overwrites already-populated database records.
    """
    from companies.models import Company

    path = Path(json_path) if json_path else LEGACY_STORAGE_FILE
    if not path.exists():
        return 0

    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = fh.read().strip()
            if not raw:
                return 0
            configs = json.loads(raw)
    except Exception as exc:
        logger.warning(f"[WhatsApp Migration] Could not parse legacy config file {path}: {exc}")
        return 0

    if not isinstance(configs, dict):
        return 0

    imported = 0
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
        company.whatsapp_updated_at = timezone.now()
        company.save(
            update_fields=[
                "whatsapp_phone_number_id",
                "whatsapp_access_token",
                "whatsapp_verify_token",
                "whatsapp_is_active",
                "whatsapp_updated_at",
            ]
        )
        imported += 1

    return imported
