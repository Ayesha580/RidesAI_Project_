"""
Outgoing WhatsApp Service module for Meta WhatsApp Cloud API (v21.0).

Handles sending outbound WhatsApp messages, credentials retrieval from
file-based storage (whatsapp_config.json), and comprehensive error logging.
"""

import json
import logging
import os
import requests
from typing import Optional, Dict, Any

from django.conf import settings
from .whatsapp_storage import get_whatsapp_config, get_config_by_phone_number_id

logger = logging.getLogger("operations.whatsapp")
GRAPH_API_VERSION = getattr(
    settings,
    "WHATSAPP_GRAPH_API_VERSION",
    os.getenv("WHATSAPP_GRAPH_API_VERSION", "v21.0")
)
GRAPH_API_BASE_URL = "https://graph.facebook.com"


def _mask_secret(val: str) -> str:
    """Masks sensitive credentials in logs."""
    if not val:
        return "<EMPTY>"
    s = str(val).strip()
    return f"{s[:6]}...{s[-4:]}" if len(s) > 10 else "***"


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

    def download_media_file(self, media_id: str) -> Optional[bytes]:
        """
        Downloads a media file (such as incoming audio .ogg) from Meta WhatsApp Cloud API.
        Step 1: Queries Meta Graph API to retrieve the temporary download URL for media_id.
        Step 2: Downloads and returns the binary audio payload.

        :param media_id: The WhatsApp media ID from the incoming webhook payload.
        :return: Binary bytes of the media file, or None if failed.
        """
        if not media_id or not str(media_id).strip():
            logger.error("[WhatsApp Media] media_id is required.")
            return None

        if not self.access_token:
            logger.error("[WhatsApp Media] Cannot download media: missing access_token.")
            return None

        clean_media_id = str(media_id).strip()
        media_url = f"{GRAPH_API_BASE_URL}/{GRAPH_API_VERSION}/{clean_media_id}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "User-Agent": "RidesAI-WhatsApp-Client/1.0",
        }

        try:
            logger.info(f"[WhatsApp Media] Fetching media metadata for {clean_media_id}...")
            meta_resp = requests.get(media_url, headers=headers, timeout=15)
            if meta_resp.status_code != 200:
                logger.error(
                    f"[WhatsApp Media ERROR] Failed to fetch media info ({meta_resp.status_code}): {meta_resp.text}"
                )
                return None

            meta_data = meta_resp.json()
            download_url = meta_data.get("url")
            if not download_url:
                logger.error(f"[WhatsApp Media ERROR] No 'url' in media response: {meta_data}")
                return None

            logger.info(f"[WhatsApp Media] Downloading binary media from {download_url[:60]}...")
            file_resp = requests.get(download_url, headers=headers, timeout=30)
            if file_resp.status_code != 200:
                logger.error(
                    f"[WhatsApp Media ERROR] Failed to download binary file ({file_resp.status_code}): {file_resp.text}"
                )
                return None

            binary_payload = file_resp.content
            logger.info(f"[WhatsApp Media] Successfully downloaded {len(binary_payload)} bytes for media {clean_media_id}")
            return binary_payload

        except requests.exceptions.RequestException as e:
            logger.error(f"[WhatsApp Media ERROR] Network error downloading media {clean_media_id}: {e}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"[WhatsApp Media ERROR] Unexpected error downloading media {clean_media_id}: {e}", exc_info=True)
            return None

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

    def upload_media(
        self,
        file_bytes: bytes,
        mime_type: str = "audio/ogg",
        filename: str = "voice_note.ogg"
    ) -> Optional[str]:
        """
        Uploads binary media (e.g. .ogg Opus voice note) to Meta WhatsApp Cloud API media endpoint.
        URL: https://graph.facebook.com/v21.0/{phone_number_id}/media

        :param file_bytes: Binary bytes of the media file.
        :param mime_type: MIME type of the file (defaults to 'audio/ogg').
        :param filename: Filename for multipart upload (defaults to 'voice_note.ogg').
        :return: String media_id returned by Meta on success, or None on failure.
        """
        if not file_bytes or len(file_bytes) < 50:
            logger.error("[WhatsApp Media Upload] file_bytes payload is empty or too small.")
            return None

        if not self.is_configured():
            logger.error(
                f"[WhatsApp Media Upload] Credentials missing: phone_number_id='{self.phone_number_id}'"
            )
            return None

        media_upload_url = f"{GRAPH_API_BASE_URL}/{GRAPH_API_VERSION}/{self.phone_number_id}/media"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "User-Agent": "RidesAI-WhatsApp-Client/1.0",
        }

        data = {
            "messaging_product": "whatsapp",
            "type": mime_type,
        }
        files = {
            "file": (filename, file_bytes, mime_type),
        }

        masked_token = _mask_secret(self.access_token)
        logger.info(
            f"[WhatsApp Media Upload] Uploading {len(file_bytes)} bytes ({mime_type}) "
            f"to {self.phone_number_id} (Token: {masked_token})..."
        )

        try:
            response = requests.post(
                media_upload_url,
                headers=headers,
                data=data,
                files=files,
                timeout=30
            )

            if response.status_code >= 400:
                logger.error(
                    f"[WhatsApp Media Upload ERROR] Meta returned HTTP {response.status_code} | "
                    f"Phone ID: {self.phone_number_id} | Response: {response.text}"
                )
                print(f"[WhatsApp Media Upload ERROR] HTTP {response.status_code}: {response.text}")
                return None

            res_json = response.json()
            media_id = res_json.get("id")
            if media_id:
                logger.info(
                    f"[WhatsApp Media Upload] Successfully uploaded media! "
                    f"Status: HTTP {response.status_code} | Media ID: {media_id} | Phone ID: {self.phone_number_id}"
                )
                print(f"[WhatsApp Media Upload] Uploaded media ID: {media_id}")
                return str(media_id).strip()

            logger.error(f"[WhatsApp Media Upload ERROR] 'id' missing in response: {res_json}")
            return None

        except requests.exceptions.RequestException as e:
            logger.error(f"[WhatsApp Media Upload ERROR] Network error: {e}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"[WhatsApp Media Upload ERROR] Unexpected error: {e}", exc_info=True)
            return None

    def send_audio_message(self, to: str, media_id: str) -> Dict[str, Any]:
        """
        Sends an outbound audio voice note to a WhatsApp recipient using an uploaded media_id.

        :param to: Recipient phone number in E.164 format.
        :param media_id: Media ID returned by upload_media().
        :return: Dict containing success boolean, message_id, and response data.
        """
        clean_recipient = str(to).replace("+", "").replace(" ", "").replace("-", "").strip()

        if not clean_recipient:
            err_msg = "Recipient phone number is required."
            logger.error(f"[WhatsApp Audio Outbound] {err_msg}")
            return {"success": False, "error": err_msg}

        if not media_id or not str(media_id).strip():
            err_msg = "Media ID is required to send audio message."
            logger.error(f"[WhatsApp Audio Outbound] {err_msg}")
            return {"success": False, "error": err_msg}

        if not self.is_configured():
            err_msg = f"Credentials missing: phone_number_id='{self.phone_number_id}' or access_token."
            logger.error(f"[WhatsApp Audio Outbound] {err_msg}")
            return {"success": False, "error": err_msg}

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": clean_recipient,
            "type": "audio",
            "audio": {
                "id": str(media_id).strip(),
                "voice": True,
            }
        }

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "User-Agent": "RidesAI-WhatsApp-Client/1.0",
        }

        masked_token = _mask_secret(self.access_token)
        logger.info(
            f"[WhatsApp Audio Outbound] Sending audio voice note (Media ID: {media_id}) "
            f"to {clean_recipient} via Phone ID {self.phone_number_id} (Token: {masked_token})..."
        )
        print(f"[WhatsApp Audio Outbound] Dispatching voice note to {clean_recipient} (Media: {media_id})...")

        try:
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=20
            )

            if response.status_code >= 400:
                logger.error(
                    f"[WhatsApp Audio Outbound ERROR] Meta API Error! "
                    f"Status: HTTP {response.status_code} | To: {clean_recipient} | "
                    f"Phone ID: {self.phone_number_id} | Response: {response.text}"
                )
                print(f"[WhatsApp Audio Outbound ERROR] HTTP {response.status_code}: {response.text}")
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "error": response.text,
                }

            res_data = response.json()
            message_id = None
            if "messages" in res_data and len(res_data["messages"]) > 0:
                message_id = res_data["messages"][0].get("id")

            logger.info(
                f"[WhatsApp Audio Outbound] Voice note accepted by Meta! "
                f"Status: HTTP {response.status_code} | Meta ID: {message_id} | "
                f"To: {clean_recipient} | Response: {response.text}"
            )
            print(f"[WhatsApp Audio Outbound] Voice note delivered to Meta. Message ID: {message_id}")

            return {
                "success": True,
                "status_code": response.status_code,
                "message_id": message_id,
                "data": res_data
            }

        except requests.exceptions.RequestException as e:
            err_msg = f"Network error during audio dispatch: {str(e)}"
            logger.error(f"[WhatsApp Audio Outbound] {err_msg}", exc_info=True)
            return {"success": False, "error": err_msg}
        except Exception as e:
            err_msg = f"Unexpected error during audio dispatch: {str(e)}"
            logger.error(f"[WhatsApp Audio Outbound] {err_msg}", exc_info=True)
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
