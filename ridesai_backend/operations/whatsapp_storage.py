"""
Temporary file-based storage utility for WhatsApp Cloud API credentials.

This module provides thread-safe file-based persistence for WhatsApp credentials
(phone_number_id, access_token, verify_token, is_active) to avoid database migrations
ahead of the upcoming PostgreSQL migration.
"""

import json
import logging
import os
import threading
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Storage file located in operations directory
STORAGE_FILE = Path(__file__).resolve().parent / "whatsapp_config.json"
_file_lock = threading.Lock()

DEFAULT_CONFIG = {
    "phone_number_id": "",
    "access_token": "",
    "verify_token": "ridesai_default_verify_token",
    "is_active": False,
    "updated_at": "",
}


def _load_all_configs() -> dict:
    """Reads the JSON config file into a dictionary."""
    if not STORAGE_FILE.exists():
        return {"default": dict(DEFAULT_CONFIG)}

    try:
        with open(STORAGE_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return {"default": dict(DEFAULT_CONFIG)}
            data = json.loads(content)
            if not isinstance(data, dict):
                return {"default": dict(DEFAULT_CONFIG)}
            return data
    except Exception as e:
        logger.error(f"[WhatsApp Storage] Error reading config file {STORAGE_FILE}: {e}")
        return {"default": dict(DEFAULT_CONFIG)}


def _save_all_configs(configs: dict) -> bool:
    """Atomically writes the full config dictionary to the JSON file."""
    temp_file = STORAGE_FILE.with_suffix(".tmp")
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(configs, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())

        # Atomic replacement
        temp_file.replace(STORAGE_FILE)
        return True
    except Exception as e:
        logger.error(f"[WhatsApp Storage] Failed to write config file {STORAGE_FILE}: {e}")
        if temp_file.exists():
            try:
                temp_file.unlink()
            except OSError:
                pass
        return False


def get_whatsapp_config(company_id=None) -> dict:
    """
    Retrieves the WhatsApp configuration for a specific company or the default.
    """
    with _file_lock:
        configs = _load_all_configs()
        key = str(company_id) if company_id else "default"

        if key in configs and isinstance(configs[key], dict):
            cfg = dict(DEFAULT_CONFIG)
            cfg.update(configs[key])
            return cfg

        # Fallback to default if company specific doesn't exist yet
        if "default" in configs and isinstance(configs["default"], dict):
            cfg = dict(DEFAULT_CONFIG)
            cfg.update(configs["default"])
            return cfg

        return dict(DEFAULT_CONFIG)


def save_whatsapp_config(data: dict, company_id=None) -> dict:
    """
    Saves or updates the WhatsApp configuration for a company.
    """
    with _file_lock:
        configs = _load_all_configs()
        key = str(company_id) if company_id else "default"

        existing = configs.get(key, dict(DEFAULT_CONFIG))
        updated = {
            "phone_number_id": str(data.get("phone_number_id", existing.get("phone_number_id", ""))).strip(),
            "access_token": str(data.get("access_token", existing.get("access_token", ""))).strip(),
            "verify_token": str(data.get("verify_token", existing.get("verify_token", DEFAULT_CONFIG["verify_token"]))).strip(),
            "is_active": bool(data.get("is_active", existing.get("is_active", False))),
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }

        configs[key] = updated
        # Also maintain default if updating primary/default entry
        if key == "default" or len(configs) == 1:
            configs["default"] = dict(updated)

        _save_all_configs(configs)
        return updated


def is_valid_verify_token(token: str) -> bool:
    """
    Checks if a given verify token matches any active or stored token.
    Used for Meta Webhook subscription verification.
    """
    if not token:
        return False

    with _file_lock:
        configs = _load_all_configs()
        for _, cfg in configs.items():
            if isinstance(cfg, dict) and cfg.get("verify_token") == token:
                return True

    # Also match default token fallback
    return token == DEFAULT_CONFIG["verify_token"]


def get_config_by_phone_number_id(phone_number_id: str) -> dict | None:
    """
    Finds the company config matching an incoming Meta message's recipient phone number ID.
    Returns config dictionary including company_id (or None if default/unlinked).
    """
    if not phone_number_id:
        return None

    with _file_lock:
        configs = _load_all_configs()
        # Check specific company entries first
        for key, cfg in configs.items():
            if key != "default" and isinstance(cfg, dict) and cfg.get("phone_number_id") == str(phone_number_id):
                res = dict(cfg)
                res["company_id"] = key
                return res

        # Check default config
        if "default" in configs and isinstance(configs["default"], dict):
            default_cfg = configs["default"]
            if default_cfg.get("phone_number_id") == str(phone_number_id):
                res = dict(default_cfg)
                res["company_id"] = None
                return res
            if default_cfg.get("phone_number_id"):
                res = dict(default_cfg)
                res["company_id"] = None
                return res

    return None
