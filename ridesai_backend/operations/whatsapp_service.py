"""
Outgoing WhatsApp Service module for Meta WhatsApp Cloud API (v21.0).

Handles sending outbound WhatsApp messages, credentials retrieval from
file-based storage (whatsapp_config.json), and comprehensive error logging.
"""

import json
import logging
import requests
from typing import Optional, Dict, Any

from .whatsapp_storage import get_whatsapp_config, get_config_by_phone_number_id

logger = logging.getLogger("operations.whatsapp")
GRAPH_API_VERSION = "v21.0"
GRAPH_API_BASE_URL = "https://graph.facebook.com"


class WhatsAppServiceError(Exception):
    """Custom exception for WhatsApp outbound messaging failures."""
    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class WhatsAppService:
    """
    Service client for sending messages via Meta WhatsApp Cloud API.
    """

    def __init__(self, phone_number_id: Optional[str] = None, access_token: Optional[str] = None, company_id: Optional[Any] = None):
        if phone_number_id and access_token:
            self.phone_number_id = str(phone_number_id).strip()
            self.access_token = str(access_token).strip()
        elif phone_number_id:
            # FIX: Look up by phone_number_id first for incoming webhooks!
            cfg = get_config_by_phone_number_id(phone_number_id) or {}
            self.phone_number_id = str(phone_number_id).strip()
            self.access_token = str(cfg.get("access_token", "")).strip()
        else:
            cfg = get_whatsapp_config(company_id=company_id)
            self.phone_number_id = str(cfg.get("phone_number_id", "")).strip()
            self.access_token = str(cfg.get("access_token", "")).strip()

        self.api_url = f"{GRAPH_API_BASE_URL}/{GRAPH_API_VERSION}/{self.phone_number_id}/messages"

    def is_configured(self) -> bool:
        """Checks whether necessary credentials are present."""
        return bool(self.phone_number_id and self.access_token)

    def send_text_message(self, to: str, text: str) -> Dict[str, Any]:
        """
        Sends a plain or markdown text message to a WhatsApp user.

        :param to: Recipient phone number in E.164 format (e.g. '15551234567' or '+15551234567')
        :param text: Message text body to send
        :return: Dict containing success boolean, message_id, and response data
        """
        clean_recipient = str(to).replace("+", "").replace(" ", "").replace("-", "").strip()

        if not clean_recipient:
            err_msg = "Recipient phone number is required."
            logger.error(f"[WhatsApp Outbound] Validation error: {err_msg}")
            return {"success": False, "error": err_msg}

        if not text or not str(text).strip():
            err_msg = "Message body cannot be empty."
            logger.error(f"[WhatsApp Outbound] Validation error: {err_msg}")
            return {"success": False, "error": err_msg}

        if not self.is_configured():
            err_msg = (
                f"WhatsApp Cloud API credentials not configured. "
                f"Missing phone_number_id ('{self.phone_number_id}') or access_token."
            )
            logger.error(f"[WhatsApp Outbound] Credential error: {err_msg}")
            print(f"[WhatsApp Service Error] {err_msg}")
            return {"success": False, "error": err_msg}

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": clean_recipient,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": text.strip()
            }
        }

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        logger.info(f"[WhatsApp Outbound] Sending message to {clean_recipient} via Phone ID {self.phone_number_id}...")
        print(f"[WhatsApp Outbound] Sending to {clean_recipient} via Phone ID {self.phone_number_id} | Text: '{text[:60]}...'")

        try:
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=20
            )

            # Detailed logging on failure to prevent silent errors
            if response.status_code >= 400:
                logger.error(
                    f"[WhatsApp Outbound] Meta API Error! "
                    f"Status: {response.status_code} | "
                    f"Response: {response.text} | "
                    f"Payload: {json.dumps(payload)}"
                )
                print(f"[WhatsApp Outbound ERROR] Meta API returned HTTP {response.status_code}:\n{response.text}")
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "error": response.text,
                    "details": response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                }

            data = response.json()
            message_id = data.get("messages", [{}])[0].get("id") if data.get("messages") else None

            logger.info(f"[WhatsApp Outbound] Message successfully sent! Meta Message ID: {message_id}")
            print(f"[WhatsApp Outbound] Message delivered to Meta. ID: {message_id}")

            return {
                "success": True,
                "status_code": response.status_code,
                "message_id": message_id,
                "data": data
            }

        except requests.exceptions.Timeout:
            err_msg = "Timeout while connecting to Meta WhatsApp API."
            logger.error(f"[WhatsApp Outbound] {err_msg}")
            print(f"[WhatsApp Outbound ERROR] {err_msg}")
            return {"success": False, "error": err_msg}

        except requests.exceptions.RequestException as e:
            err_msg = f"Network or HTTP error communicating with Meta API: {str(e)}"
            logger.error(f"[WhatsApp Outbound] {err_msg}", exc_info=True)
            print(f"[WhatsApp Outbound ERROR] {err_msg}")
            return {"success": False, "error": err_msg}

        except Exception as e:
            err_msg = f"Unexpected error during WhatsApp outbound dispatch: {str(e)}"
            logger.error(f"[WhatsApp Outbound] {err_msg}", exc_info=True)
            print(f"[WhatsApp Outbound ERROR] {err_msg}")
            return {"success": False, "error": err_msg}


def send_whatsapp_message(
    to: str,
    text: str,
    phone_number_id: Optional[str] = None,
    access_token: Optional[str] = None,
    company_id: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Convenience functional wrapper to dispatch a WhatsApp text message.
    """
    service = WhatsAppService(phone_number_id=phone_number_id, access_token=access_token, company_id=company_id)
    return service.send_text_message(to=to, text=text)
