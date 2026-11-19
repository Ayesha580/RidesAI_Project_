"""
Evolution API Client for Multi-Tenant WhatsApp QR Onboarding and Messaging.

Connects to Evolution API (v1 / v2 / Baileys) for:
1. Creating instances & retrieving QR codes for WhatsApp Web login.
2. Checking instance connection status (connected / disconnected).
3. Sending outbound text messages.
4. Sending outbound audio / voice note messages (base64 encoded).
"""

import json
import logging
import requests
from typing import Optional, Dict, Any

from django.conf import settings

logger = logging.getLogger("operations.evolution")


def _get_api_url() -> str:
    return getattr(settings, "EVOLUTION_API_URL", "http://localhost:8080").rstrip("/")


def _get_api_key() -> str:
    return getattr(settings, "EVOLUTION_API_KEY", "ridesai-secret-key-123")


def _get_headers() -> Dict[str, str]:
    return {
        "apikey": _get_api_key(),
        "Content-Type": "application/json",
    }


def _clean_phone(phone: str) -> str:
    """Strips @s.whatsapp.net, +, spaces, and dashes from phone number."""
    if not phone:
        return ""
    cleaned = str(phone).replace("@s.whatsapp.net", "").replace("+", "").replace(" ", "").replace("-", "").strip()
    return cleaned


def configure_instance_settings(instance_name: str, msg_call: Optional[str] = None) -> Dict[str, Any]:
    """
    Configures settings on an Evolution API instance to automatically reject calls
    and reply with an automated message.
    """
    default_msg = "Sorry, we do not accept WhatsApp calls. Please send a text or voice note here to place your order!"
    message = msg_call if msg_call is not None else default_msg
    api_url = _get_api_url()
    url = f"{api_url}/settings/set/{instance_name}"
    payload = {
        "rejectCall": True,
        "msgCall": message,
        "groupsIgnore": True,
        "alwaysOnline": False,
        "readMessages": False,
        "readStatus": False,
        "syncFullHistory": False,
    }

    try:
        logger.info(f"[Evolution API] Configuring instance settings for '{instance_name}' at {url}")
        res = requests.post(url, headers=_get_headers(), json=payload, timeout=15)
        try:
            return res.json()
        except Exception:
            return {"status_code": res.status_code, "text": res.text}
    except Exception as e:
        logger.warning(f"[Evolution API] Failed to configure instance settings for '{instance_name}': {e}")
        return {"error": str(e), "success": False}


def create_instance(instance_name: str) -> Dict[str, Any]:
    """
    Creates or connects to an Evolution API instance and returns the QR code.
    If the instance already exists (403/409), falls back to connect endpoint to fetch fresh QR code.
    Also auto-configures instance settings to reject calls with an instant reply.
    """
    api_url = _get_api_url()
    create_url = f"{api_url}/instance/create"
    payload = {
        "instanceName": instance_name,
        "qrcode": True,
        "integration": "WHATSAPP-BAILEYS",
    }

    try:
        logger.info(f"[Evolution API] Creating instance '{instance_name}' at {create_url}")
        res = requests.post(create_url, headers=_get_headers(), json=payload, timeout=15)
        res_data = {}
        try:
            res_data = res.json()
        except Exception:
            res_data = {"raw_text": res.text}

        # If already exists (403 or 409 or message contains exists), fallback to connect
        if res.status_code in (403, 409) or "already exists" in str(res_data).lower():
            logger.info(f"[Evolution API] Instance '{instance_name}' already exists. Fetching connect QR code...")
            connect_url = f"{api_url}/instance/connect/{instance_name}"
            c_res = requests.get(connect_url, headers=_get_headers(), timeout=15)
            try:
                res_data = c_res.json()
            except Exception:
                res_data = {"raw_text": c_res.text}

        # Extract QR code base64 from possible response formats
        qrcode_base64 = None
        if isinstance(res_data, dict):
            if isinstance(res_data.get("qrcode"), dict):
                qrcode_base64 = res_data["qrcode"].get("base64")
            elif isinstance(res_data.get("qrcode"), str):
                qrcode_base64 = res_data["qrcode"]
            elif res_data.get("base64"):
                qrcode_base64 = res_data["base64"]
            elif res_data.get("code"):
                qrcode_base64 = res_data["code"]
            elif isinstance(res_data.get("instance"), dict):
                inst = res_data["instance"]
                if isinstance(inst.get("qrcode"), dict):
                    qrcode_base64 = inst["qrcode"].get("base64")
                elif inst.get("qrcode"):
                    qrcode_base64 = inst["qrcode"]

        status = "created"
        if isinstance(res_data, dict):
            status = res_data.get("instance", {}).get("status") or res_data.get("status") or "created"

        # Auto-configure call rejection & instance settings
        configure_instance_settings(instance_name)

        return {
            "instance_name": instance_name,
            "qrcode_base64": qrcode_base64,
            "status": status,
            "raw": res_data,
        }

    except requests.exceptions.RequestException as e:
        logger.error(f"[Evolution API ERROR] create_instance failed for '{instance_name}': {e}", exc_info=True)
        return {
            "instance_name": instance_name,
            "qrcode_base64": None,
            "status": "error",
            "error": str(e),
            "raw": {},
        }
    except Exception as e:
        logger.error(f"[Evolution API ERROR] Unexpected error in create_instance: {e}", exc_info=True)
        return {
            "instance_name": instance_name,
            "qrcode_base64": None,
            "status": "error",
            "error": str(e),
            "raw": {},
        }


def get_connection_status(instance_name: str) -> str:
    """
    Checks the connection state of the instance.
    Returns 'connected' if open, else 'disconnected'.
    """
    api_url = _get_api_url()
    url = f"{api_url}/instance/connectionState/{instance_name}"

    try:
        logger.info(f"[Evolution API] Checking connection status for '{instance_name}' at {url}")
        res = requests.get(url, headers=_get_headers(), timeout=15)
        if res.status_code != 200:
            logger.warning(f"[Evolution API] connectionState returned HTTP {res.status_code}")
            return "disconnected"

        data = res.json()
        state = None
        if isinstance(data, dict):
            state = (
                data.get("instance", {}).get("state")
                or data.get("state")
                or data.get("connectionState", {}).get("state")
                or data.get("status")
            )

        if str(state).lower() in ("open", "connected"):
            return "connected"
        return "disconnected"

    except Exception as e:
        logger.warning(f"[Evolution API] Could not retrieve connection state for '{instance_name}': {e}")
        return "disconnected"


def send_text_message(instance_name: str, phone: str, text: str) -> Dict[str, Any]:
    """
    Sends an outbound text message via Evolution API.
    """
    cleaned_phone = _clean_phone(phone)
    api_url = _get_api_url()
    url = f"{api_url}/message/sendText/{instance_name}"
    payload = {
        "number": cleaned_phone,
        "text": text,
    }

    try:
        logger.info(f"[Evolution API] Sending text message to {cleaned_phone} via '{instance_name}'")
        res = requests.post(url, headers=_get_headers(), json=payload, timeout=15)
        try:
            return res.json()
        except Exception:
            return {"status_code": res.status_code, "text": res.text}
    except Exception as e:
        logger.error(f"[Evolution API ERROR] Failed to send text message to {cleaned_phone}: {e}", exc_info=True)
        return {"error": str(e), "success": False}


def send_audio_message(instance_name: str, phone: str, audio_base64: str) -> Dict[str, Any]:
    """
    Sends an outbound audio (voice note) via Evolution API using base64.
    """
    cleaned_phone = _clean_phone(phone)
    api_url = _get_api_url()
    url = f"{api_url}/message/sendWhatsAppAudio/{instance_name}"
    payload = {
        "number": cleaned_phone,
        "audio": audio_base64,
    }

    try:
        logger.info(f"[Evolution API] Sending audio voice note to {cleaned_phone} via '{instance_name}'")
        res = requests.post(url, headers=_get_headers(), json=payload, timeout=15)
        try:
            return res.json()
        except Exception:
            return {"status_code": res.status_code, "text": res.text}
    except Exception as e:
        logger.error(f"[Evolution API ERROR] Failed to send audio message to {cleaned_phone}: {e}", exc_info=True)
        return {"error": str(e), "success": False}


def get_media_base64(instance_name: str, message_data: dict) -> Optional[bytes]:
    """
    Retrieves and decodes base64 media from an Evolution API message.
    Calls POST {EVOLUTION_API_URL}/chat/getBase64FromMediaMessage/{instance_name}
    with {"message": {"key": message_data.get("key", {})}, "convertToMp4": False}.
    Returns decoded raw bytes or None.
    """
    import base64
    api_url = _get_api_url()
    url = f"{api_url}/chat/getBase64FromMediaMessage/{instance_name}"

    key = message_data.get("key", {}) if isinstance(message_data, dict) else {}
    if not key and isinstance(message_data, dict) and ("id" in message_data or "remoteJid" in message_data):
        key = message_data

    payload = {
        "message": {
            "key": key
        },
        "convertToMp4": False,
    }

    try:
        logger.info(f"[Evolution API] Fetching media base64 for instance '{instance_name}' at {url}")
        res = requests.post(url, headers=_get_headers(), json=payload, timeout=20)
        if not (200 <= res.status_code < 300):
            logger.error(
                f"[Evolution API ERROR] getBase64FromMediaMessage failed for '{instance_name}' "
                f"with HTTP {res.status_code}: {res.text}"
            )
            return None

        data = res.json()
        b64_str = None
        if isinstance(data, dict):
            b64_str = data.get("base64") or (data.get("media", {}).get("base64") if isinstance(data.get("media"), dict) else None)
        elif isinstance(data, str):
            b64_str = data

        if b64_str:
            if "," in b64_str:
                b64_str = b64_str.split(",", 1)[1]
            return base64.b64decode(b64_str)

        logger.error(
            f"[Evolution API ERROR] getBase64FromMediaMessage for '{instance_name}' "
            f"returned 200 but no base64 string found in response: {data}"
        )
        return None
    except Exception as e:
        logger.error(f"[Evolution API ERROR] Failed get_media_base64 for '{instance_name}': {e}", exc_info=True)
        return None

