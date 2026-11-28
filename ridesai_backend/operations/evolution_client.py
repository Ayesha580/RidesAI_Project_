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
import time
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
    """Strips @s.whatsapp.net, @lid, @c.us, +, spaces, and dashes from phone number."""
    if not phone:
        return ""
    cleaned = (
        str(phone)
        .replace("@s.whatsapp.net", "")
        .replace("@c.us", "")
        .replace("@lid", "")
        .replace("+", "")
        .replace(" ", "")
        .replace("-", "")
        .strip()
    )
    return cleaned


def _extract_qr_base64(res_data: Any) -> Optional[str]:
    """Extracts QR code base64 from any Evolution API v1/v2 response structure."""
    if not isinstance(res_data, dict):
        return None
    if isinstance(res_data.get("qrcode"), dict):
        return res_data["qrcode"].get("base64") or res_data["qrcode"].get("code")
    if isinstance(res_data.get("qrcode"), str):
        return res_data["qrcode"]
    if res_data.get("base64"):
        return res_data["base64"]
    if res_data.get("code"):
        return res_data["code"]
    if isinstance(res_data.get("instance"), dict):
        inst = res_data["instance"]
        if isinstance(inst.get("qrcode"), dict):
            return inst["qrcode"].get("base64") or inst["qrcode"].get("code")
        if inst.get("qrcode"):
            return inst["qrcode"]
    return None


def logout_instance(instance_name: str) -> Dict[str, Any]:
    """
    Logs out / disconnects an existing WhatsApp session on Evolution API.
    Calls DELETE /instance/logout/{instance_name}.
    """
    api_url = _get_api_url()
    url = f"{api_url}/instance/logout/{instance_name}"
    try:
        logger.info(f"[Evolution API] Logging out instance '{instance_name}' at {url}")
        res = requests.delete(url, headers=_get_headers(), timeout=15)
        try:
            body = res.json()
        except Exception:
            body = {"raw_text": res.text}
        if 200 <= res.status_code < 300:
            return {"success": True, "status_code": res.status_code, "data": body}
        logger.warning(
            f"[Evolution API] logout_instance '{instance_name}' returned HTTP {res.status_code}: {body}"
        )
        return {"success": False, "status_code": res.status_code, "error": str(body), "data": body}
    except Exception as e:
        logger.warning(f"[Evolution API] logout_instance failed for '{instance_name}': {e}")
        return {"success": False, "error": str(e)}


def delete_instance(instance_name: str) -> Dict[str, Any]:
    """
    Deletes an Evolution API instance so it can be recreated cleanly with a fresh QR code.
    Calls DELETE /instance/delete/{instance_name}.
    """
    api_url = _get_api_url()
    url = f"{api_url}/instance/delete/{instance_name}"
    try:
        logger.info(f"[Evolution API] Deleting instance '{instance_name}' at {url}")
        res = requests.delete(url, headers=_get_headers(), timeout=15)
        try:
            body = res.json()
        except Exception:
            body = {"raw_text": res.text}
        return {"success": 200 <= res.status_code < 300, "status_code": res.status_code, "data": body}
    except Exception as e:
        logger.warning(f"[Evolution API] delete_instance failed for '{instance_name}': {e}")
        return {"success": False, "error": str(e)}


DEFAULT_DOCKER_WEBHOOK_URL = "http://host.docker.internal:8000/api/operations/whatsapp/evolution-webhook"


def _normalize_webhook_url(webhook_url: Optional[str]) -> Optional[str]:
    """
    Normalizes an Evolution API webhook URL:
    1. Strips trailing slashes so webhook_by_events never produces '//event'.
    2. Rewrites localhost / 127.0.0.1 to host.docker.internal so Dockerized Evolution API
       reaches the host Django server instead of posting to itself.
    """
    if not webhook_url:
        return None
    import re
    cleaned = str(webhook_url).strip().rstrip("/")
    if not cleaned:
        return None
    cleaned = re.sub(
        r"^(https?://)(?:127\.0\.0\.1|localhost)(?=[:/]|$)",
        r"\1host.docker.internal",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned


def set_instance_webhook(instance_name: str, webhook_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Updates/syncs the webhook URL on an existing Evolution API instance (POST /webhook/set/{instance_name})
    without deleting or disconnecting the WhatsApp session.
    """
    api_url = _get_api_url()
    url = f"{api_url}/webhook/set/{instance_name}"
    clean_webhook = _normalize_webhook_url(
        webhook_url or getattr(settings, "EVOLUTION_WEBHOOK_URL", None) or DEFAULT_DOCKER_WEBHOOK_URL
    )
    payload = {
        "webhook": {
            "enabled": True,
            "url": clean_webhook,
            "webhookByEvents": False,
            "byEvents": False,
            "webhookBase64": True,
            "base64": True,
            "events": ["MESSAGES_UPSERT", "CONNECTION_UPDATE"],
        }
    }
    try:
        logger.info(f"[Evolution API] Syncing webhook for '{instance_name}' -> {clean_webhook}")
        res = requests.post(url, headers=_get_headers(), json=payload, timeout=15)
        try:
            body = res.json()
        except Exception:
            body = {"status_code": res.status_code, "text": res.text}
        if 200 <= res.status_code < 300:
            return {"success": True, "webhook_url": clean_webhook, "data": body}
        # Fallback for Evolution v1 flat payload format
        flat_payload = {
            "enabled": True,
            "url": clean_webhook,
            "webhook_by_events": False,
            "webhook_base64": True,
            "events": ["MESSAGES_UPSERT", "CONNECTION_UPDATE"],
        }
        res2 = requests.post(url, headers=_get_headers(), json=flat_payload, timeout=15)
        try:
            body2 = res2.json()
        except Exception:
            body2 = {"status_code": res2.status_code, "text": res2.text}
        return {"success": 200 <= res2.status_code < 300, "webhook_url": clean_webhook, "data": body2}
    except Exception as e:
        logger.warning(f"[Evolution API] Failed to sync webhook for '{instance_name}': {e}")
        return {"success": False, "error": str(e), "webhook_url": clean_webhook}


def _is_valid_qr_base64(qr: Optional[str]) -> bool:
    if not qr or not isinstance(qr, str):
        return False
    val = qr.strip()
    return val.startswith("data:image/") or len(val) > 80


def get_qr_code(instance_name: str, retries: int = 4, delay_seconds: float = 1.5) -> Dict[str, Any]:
    """
    Polls GET /instance/connect/{instance_name} up to `retries` times (`delay_seconds` apart)
    until a valid base64 QR image is returned.
    """
    api_url = _get_api_url()
    connect_url = f"{api_url}/instance/connect/{instance_name}"
    last_data: Dict[str, Any] = {}

    for attempt in range(1, max(1, retries) + 1):
        try:
            logger.info(
                f"[Evolution API] Fetching QR for '{instance_name}' (attempt {attempt}/{retries}) at {connect_url}"
            )
            c_res = requests.get(connect_url, headers=_get_headers(), timeout=15)
            try:
                last_data = c_res.json()
            except Exception:
                last_data = {"raw_text": c_res.text, "status_code": c_res.status_code}

            qr = _extract_qr_base64(last_data)
            if _is_valid_qr_base64(qr):
                return {
                    "instance_name": instance_name,
                    "qrcode_base64": qr,
                    "status": "disconnected",
                    "raw": last_data,
                }
        except Exception as e:
            logger.warning(f"[Evolution API] get_qr_code attempt {attempt} failed for '{instance_name}': {e}")
            last_data = {"error": str(e)}

        if attempt < retries and delay_seconds > 0:
            time.sleep(delay_seconds)

    return {
        "instance_name": instance_name,
        "qrcode_base64": None,
        "status": "disconnected",
        "raw": last_data,
    }


def reconnect_instance(instance_name: str, webhook_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Hard-resets an Evolution API instance (handles 401/LOGOUT & stale connected sessions):
    1. Logs out the active/stale Baileys session (ignoring errors).
    2. Hard-deletes the instance (DELETE /instance/delete/{instance_name}).
    3. Sleeps 1.5s for Evolution API v2 to release Baileys state.
    4. Recreates the instance with qrcode=True and polls /instance/connect/{instance_name}
       up to 4 times (1.5s apart) if the QR is not returned immediately.
    """
    logger.info(f"[Evolution API] Force-reconnecting (hard-delete + recreate) instance '{instance_name}'...")

    try:
        logout_instance(instance_name)
    except Exception as e:
        logger.warning(f"[Evolution API] Ignoring logout error during reconnect for '{instance_name}': {e}")

    delete_instance(instance_name)
    time.sleep(1.5)

    created = create_instance(instance_name, webhook_url=webhook_url, qrcode=True)
    created["status"] = "disconnected"
    return created


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


def create_instance(
    instance_name: str,
    webhook_url: Optional[str] = None,
    qrcode: bool = True,
) -> Dict[str, Any]:
    """
    Creates or connects to an Evolution API instance and returns the QR code.
    - Strips any trailing slash from `webhook_url` before registering with Evolution API.
    - If the instance already exists (403/409), falls back to connect endpoint.
    - If `create_instance` does not immediately return a valid base64 QR, polls
      GET /instance/connect/{instance_name} up to 4 times (1.5s apart).
    - Auto-configures instance settings to reject calls with an instant reply.
    """
    api_url = _get_api_url()
    create_url = f"{api_url}/instance/create"
    clean_webhook = _normalize_webhook_url(
        webhook_url or getattr(settings, "EVOLUTION_WEBHOOK_URL", None) or DEFAULT_DOCKER_WEBHOOK_URL
    )
    payload: Dict[str, Any] = {
        "instanceName": instance_name,
        "qrcode": bool(qrcode),
        "integration": "WHATSAPP-BAILEYS",
    }
    if clean_webhook:
        payload["webhook"] = {
            "url": clean_webhook,
            "byEvents": False,
            "base64": True,
            "events": ["CONNECTION_UPDATE", "MESSAGES_UPSERT", "QRCODE_UPDATED"],
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

        qrcode_base64 = _extract_qr_base64(res_data)

        # Poll /instance/connect/{instance_name} up to 4 times (1.5s apart) if QR not ready immediately
        if qrcode and not _is_valid_qr_base64(qrcode_base64):
            polled = get_qr_code(instance_name, retries=4, delay_seconds=1.5)
            if _is_valid_qr_base64(polled.get("qrcode_base64")):
                qrcode_base64 = polled["qrcode_base64"]
                res_data = polled.get("raw", res_data)

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


def send_text_message(instance_name: str, phone: str = "", text: str = "", to: str = "") -> Dict[str, Any]:
    """
    Sends an outbound text message via Evolution API.
    Supports either `phone` or `to` parameter for caller flexibility.
    Strictly checks HTTP status codes and logs Evolution API errors clearly.
    """
    target_phone = phone or to or ""
    cleaned_phone = _clean_phone(target_phone)
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
            body = res.json()
        except Exception:
            body = {"status_code": res.status_code, "text": res.text}

        if not (200 <= res.status_code < 300):
            logger.error(
                f"[Evolution API ERROR] sendText failed for '{instance_name}' -> {cleaned_phone} "
                f"(HTTP {res.status_code}): {body}"
            )
            return {
                "success": False,
                "error": f"Evolution API HTTP {res.status_code}: {body}",
                "status_code": res.status_code,
                "raw": body,
            }

        if isinstance(body, dict):
            return {"success": True, **body}
        return {"success": True, "data": body}
    except Exception as e:
        logger.error(f"[Evolution API ERROR] Failed to send text message to {cleaned_phone}: {e}", exc_info=True)
        return {"error": str(e), "success": False}


def send_audio_message(instance_name: str, phone: str, audio_base64: str) -> Dict[str, Any]:
    """
    Sends an outbound audio (voice note) via Evolution API using base64.
    Strictly checks HTTP status codes and logs Evolution API errors clearly.
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
        res = requests.post(url, headers=_get_headers(), json=payload, timeout=45)
        try:
            body = res.json()
        except Exception:
            body = {"status_code": res.status_code, "text": res.text}

        if not (200 <= res.status_code < 300):
            logger.error(
                f"[Evolution API ERROR] sendWhatsAppAudio failed for '{instance_name}' -> {cleaned_phone} "
                f"(HTTP {res.status_code}): {body}"
            )
            return {
                "success": False,
                "error": f"Evolution API HTTP {res.status_code}: {body}",
                "status_code": res.status_code,
                "raw": body,
            }

        if isinstance(body, dict):
            return {"success": True, **body}
        return {"success": True, "data": body}
    except Exception as e:
        logger.error(f"[Evolution API ERROR] Failed to send audio message to {cleaned_phone}: {e}", exc_info=True)
        return {"error": str(e), "success": False}


def get_media_base64(instance_name: str, message_data: dict) -> Optional[bytes]:
    """
    Retrieves and decodes base64 media from an Evolution API message.
    Calls POST {EVOLUTION_API_URL}/chat/getBase64FromMediaMessage/{instance_name}
    passing both `key` and `message` (when available) for Evolution API v2 compatibility.
    Returns decoded raw bytes or None.
    """
    import base64
    api_url = _get_api_url()
    url = f"{api_url}/chat/getBase64FromMediaMessage/{instance_name}"

    key = message_data.get("key", {}) if isinstance(message_data, dict) else {}
    if not key and isinstance(message_data, dict) and ("id" in message_data or "remoteJid" in message_data):
        key = message_data

    msg_inner = message_data.get("message") if isinstance(message_data, dict) else None
    msg_envelope: Dict[str, Any] = {"key": key}
    if isinstance(msg_inner, dict) and msg_inner:
        msg_envelope["message"] = msg_inner

    payload = {
        "message": msg_envelope,
        "convertToMp4": False,
    }

    try:
        logger.info(f"[Evolution API] Fetching media base64 for instance '{instance_name}' at {url}")
        res = requests.post(url, headers=_get_headers(), json=payload, timeout=45)
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

