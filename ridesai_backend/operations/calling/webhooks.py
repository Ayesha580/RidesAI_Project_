"""
Webhook parser and state manager for WhatsApp Business Calling API.

Handles incoming calls webhook events from Meta:
- 'connect' / 'offer' (Inbound call initiated with SDP offer)
- 'ringing' (Handset ringing confirmation)
- 'accepted' / 'answered' (Call connected)
- 'rejected' (Call declined)
- 'terminate' / 'ended' (Call finished, duration calculated)
- 'failed' (Call error)
"""

import json
import logging
from typing import Optional, Dict, Any

from django.utils import timezone
from companies.models import Company
from operations.models import VoiceCall, CallEvent
from operations.whatsapp_storage import get_config_by_phone_number_id

logger = logging.getLogger("operations.calling")


def handle_calling_webhook_event(value: Dict[str, Any], company: Optional[Company] = None) -> Dict[str, Any]:
    """
    Safely parses and processes Meta 'calls' webhook changes.

    :param value: The 'value' dictionary from Meta entry.changes[].value
    :param company: Optional pre-resolved Company instance for tenant isolation
    :return: Dict summarizing processing result
    """
    metadata = value.get("metadata", {}) if isinstance(value, dict) else {}
    phone_number_id = str(metadata.get("phone_number_id", "")).strip()

    # Step 1: Resolve Company / Tenant boundary
    if not company and phone_number_id:
        cfg = get_config_by_phone_number_id(phone_number_id) or {}
        company_id = cfg.get("company_id")
        if company_id:
            company = Company.objects.filter(id=company_id).first()

    if not company:
        logger.warning(
            f"[WhatsApp Calling] Received calling event for unmapped phone_number_id '{phone_number_id}'. "
            "Cannot isolate tenant. Skipping."
        )
        return {"success": False, "error": "Company not resolved"}

    # Step 2: Tenant Calling Feature Flag Verification
    if not getattr(company, "is_calling_enabled", False):
        logger.warning(
            f"[WhatsApp Calling] Calling feature is disabled for tenant '{company.name}' (ID: {company.id}). "
            f"Event skipped."
        )
        return {"success": False, "error": "Calling disabled for company"}

    # Step 3: Extract call items from payload
    # Meta format: value["calls"] = [ { "id": "...", "event": "...", "from": "...", ... } ]
    calls_data = value.get("calls", [])
    if isinstance(calls_data, dict):
        calls_data = [calls_data]
    elif not isinstance(calls_data, list):
        calls_data = []

    # Fallback: if value itself represents a single call object
    if not calls_data and value.get("id") and (value.get("event") or value.get("status")):
        calls_data = [value]

    processed_calls = []

    for item in calls_data:
        call_id = str(item.get("id") or item.get("call_id") or "").strip()
        if not call_id:
            logger.warning(f"[WhatsApp Calling] Skipping calling event without call_id: {item}")
            continue

        raw_event = str(item.get("event") or item.get("status") or "connect").strip().lower()
        customer_phone = str(item.get("from") or item.get("customer_phone") or item.get("to") or "").strip()
        direction = str(item.get("direction", "inbound")).lower()
        if direction not in ("inbound", "outbound"):
            direction = "inbound"

        session = item.get("session", {}) if isinstance(item.get("session"), dict) else {}
        sdp_offer = session.get("sdp", "") or item.get("sdp", "")

        error_obj = item.get("error", {}) if isinstance(item.get("error"), dict) else {}
        error_code = str(error_obj.get("code") or "")
        error_message = str(error_obj.get("message") or "")

        logger.info(
            f"[WhatsApp Calling Event] Tenant: {company.name} | Call ID: {call_id} | "
            f"Event: {raw_event} | From: {customer_phone}"
        )

        # Get or create the VoiceCall record
        voice_call, created = VoiceCall.objects.get_or_create(
            call_id=call_id,
            defaults={
                "company": company,
                "customer_phone": customer_phone,
                "direction": direction,
                "status": "initiated",
                "sdp_offer": sdp_offer,
            },
        )

        now = timezone.now()

        # Update customer_phone or sdp_offer if missing initially
        if customer_phone and not voice_call.customer_phone:
            voice_call.customer_phone = customer_phone
        if sdp_offer and not voice_call.sdp_offer:
            voice_call.sdp_offer = sdp_offer

        # State Transitions
        if raw_event in ("connect", "offer", "initiated"):
            voice_call.status = "initiated"

        elif raw_event == "ringing":
            voice_call.status = "ringing"

        elif raw_event in ("accepted", "answered"):
            voice_call.status = "accepted"
            if not voice_call.started_at:
                voice_call.started_at = now

        elif raw_event in ("rejected", "declined"):
            voice_call.status = "rejected"
            if not voice_call.ended_at:
                voice_call.ended_at = now

        elif raw_event in ("terminate", "terminated", "ended", "hangup"):
            voice_call.status = "terminated"
            if not voice_call.ended_at:
                voice_call.ended_at = now
            if voice_call.started_at and voice_call.ended_at:
                seconds = int((voice_call.ended_at - voice_call.started_at).total_seconds())
                voice_call.duration_seconds = max(0, seconds)

        elif raw_event in ("failed", "error"):
            voice_call.status = "failed"
            if not voice_call.ended_at:
                voice_call.ended_at = now
            voice_call.error_code = error_code
            voice_call.error_message = error_message

        voice_call.save()

        # Create audit CallEvent
        CallEvent.objects.create(
            call=voice_call,
            event_type=raw_event,
            raw_payload=item,
        )

        processed_calls.append({
            "call_id": call_id,
            "status": voice_call.status,
            "event": raw_event,
        })

    return {
        "success": True,
        "processed_count": len(processed_calls),
        "calls": processed_calls,
    }
