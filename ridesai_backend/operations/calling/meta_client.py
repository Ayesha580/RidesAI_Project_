"""
WhatsApp Business Calling API Client for Rides AI Platform.

Handles outbound call initiation, call acceptance, rejection, and termination
via Meta Graph API (v21.0+ configurable).
Endpoint: POST https://graph.facebook.com/{version}/{phone_number_id}/calls
"""

import json
import logging
import os
import requests
from typing import Optional, Dict, Any

from django.conf import settings

logger = logging.getLogger("operations.calling")
GRAPH_API_BASE_URL = "https://graph.facebook.com"


def _mask_secret(val: str) -> str:
    """Masks sensitive credentials for secure logging."""
    if not val:
        return "<EMPTY>"
    s = str(val).strip()
    return f"{s[:6]}...{s[-4:]}" if len(s) > 10 else "***"


class WhatsAppCallingClient:
    """
    Client for interacting with Meta WhatsApp Cloud Calling API.
    """

    def __init__(self, phone_number_id: str, access_token: str, graph_api_version: Optional[str] = None):
        self.phone_number_id = str(phone_number_id).strip()
        self.access_token = str(access_token).strip()
        self.graph_api_version = graph_api_version or getattr(
            settings,
            "WHATSAPP_GRAPH_API_VERSION",
            os.getenv("WHATSAPP_GRAPH_API_VERSION", "v21.0"),
        )
        self.api_url = f"{GRAPH_API_BASE_URL}/{self.graph_api_version}/{self.phone_number_id}/calls"

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "User-Agent": "RidesAI-WhatsApp-Calling/1.0",
        }

    def _dispatch_request(self, payload: Dict[str, Any], action_name: str) -> Dict[str, Any]:
        """Dispatches an HTTP POST request to Meta Calls endpoint with logging."""
        masked_token = _mask_secret(self.access_token)
        logger.info(
            f"[WhatsApp Calling] Executing '{action_name}' on {self.phone_number_id} "
            f"(Token: {masked_token}) | Payload: {json.dumps(payload)}"
        )

        try:
            response = requests.post(
                self.api_url,
                headers=self._get_headers(),
                json=payload,
                timeout=20,
            )

            if response.status_code >= 400:
                logger.error(
                    f"[WhatsApp Calling ERROR] '{action_name}' failed with HTTP {response.status_code} | "
                    f"Phone ID: {self.phone_number_id} | Response: {response.text}"
                )
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "error": response.text,
                    "details": response.json() if response.headers.get("content-type", "").startswith("application/json") else {},
                }

            res_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            logger.info(
                f"[WhatsApp Calling] '{action_name}' succeeded with HTTP {response.status_code} | Response: {res_data}"
            )
            return {
                "success": True,
                "status_code": response.status_code,
                "data": res_data,
            }

        except requests.exceptions.RequestException as e:
            err_msg = f"Network error during calling '{action_name}': {str(e)}"
            logger.error(f"[WhatsApp Calling ERROR] {err_msg}", exc_info=True)
            return {"success": False, "error": err_msg}
        except Exception as e:
            err_msg = f"Unexpected error during calling '{action_name}': {str(e)}"
            logger.error(f"[WhatsApp Calling ERROR] {err_msg}", exc_info=True)
            return {"success": False, "error": err_msg}

    def initiate_call(self, customer_number: str, sdp_offer: str) -> Dict[str, Any]:
        """
        Initiates an outbound WhatsApp voice call to a customer with an initial SDP offer.
        """
        clean_recipient = str(customer_number).replace("+", "").replace(" ", "").replace("-", "").strip()
        payload = {
            "messaging_product": "whatsapp",
            "to": clean_recipient,
            "action": "initiate",
            "session": {
                "sdp": sdp_offer,
                "type": "offer",
            },
        }
        return self._dispatch_request(payload, "initiate_call")

    def accept_call(self, call_id: str, sdp_answer: str, pre_accept: bool = False) -> Dict[str, Any]:
        """
        Accepts (or pre-accepts) an incoming WhatsApp voice call with an SDP answer.
        """
        payload = {
            "messaging_product": "whatsapp",
            "call_id": str(call_id).strip(),
            "action": "pre_accept" if pre_accept else "accept",
            "session": {
                "sdp": sdp_answer,
                "type": "answer",
            },
        }
        return self._dispatch_request(payload, "accept_call")

    def reject_call(self, call_id: str) -> Dict[str, Any]:
        """
        Rejects an incoming WhatsApp voice call.
        """
        payload = {
            "messaging_product": "whatsapp",
            "call_id": str(call_id).strip(),
            "action": "reject",
        }
        return self._dispatch_request(payload, "reject_call")

    def terminate_call(self, call_id: str) -> Dict[str, Any]:
        """
        Terminates an active WhatsApp voice call.
        """
        payload = {
            "messaging_product": "whatsapp",
            "call_id": str(call_id).strip(),
            "action": "terminate",
        }
        return self._dispatch_request(payload, "terminate_call")
