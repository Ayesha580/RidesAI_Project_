"""
AI Voice Call Guardrails & Webhook Endpoints (Part 3).

Enforces:
1. Daily call quotas (company.max_daily_calls) per customer.
2. Graceful static audio/TwiML rejection without initiating expensive AI WebSocket/Streaming connections.
3. Maximum call duration constraints (timeLimit / maxDuration) dynamically calculated
   from company.max_call_duration_minutes * 60 seconds.
"""

import logging
from typing import Optional, Tuple, Dict, Any

from django.http import HttpResponse
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from companies.models import Company
from operations.models import Customer, VoiceCall, CallEvent
from operations.whatsapp_storage import get_config_by_phone_number_id

logger = logging.getLogger("operations.calling")


def check_and_enforce_call_limit(
    company: Company,
    phone: str,
    customer_name: Optional[str] = None,
) -> Tuple[bool, Optional[str], Customer]:
    """
    Checks if a customer has reached their daily AI call quota for the company.
    Resets the count to 0 if last_call_date is older than today.
    Returns (False, rejection_msg, customer) if limit exceeded.
    Returns (True, None, customer) and increments daily_call_count if within limit.
    """
    today = timezone.now().date()
    customer, _ = Customer.objects.get_or_create(
        company=company,
        phone=phone,
        defaults={
            "name": customer_name or "",
            "daily_call_count": 0,
            "last_call_date": today,
        },
    )

    if customer.last_call_date != today:
        customer.daily_call_count = 0
        customer.last_call_date = today

    max_limit = getattr(company, "max_daily_calls", 3)
    if customer.daily_call_count >= max_limit:
        customer.save(update_fields=["daily_call_count", "last_call_date"])
        rejection_msg = "Our AI lines are currently busy. Please text your order on WhatsApp."
        return False, rejection_msg, customer

    customer.daily_call_count += 1
    customer.last_call_date = today
    customer.save(update_fields=["daily_call_count", "last_call_date"])
    return True, None, customer


class IncomingAICallWebhookView(APIView):
    """
    Primary endpoint for incoming AI calls from telephony providers (Twilio, Vapi, Bland).
    Enforces daily call rate limiting and maximum duration guardrails.
    """
    permission_classes = [AllowAny]

    def _resolve_company(self, request) -> Optional[Company]:
        data = request.data if request.method == "POST" else request.query_params

        # 1. Direct company_id
        company_id = data.get("company_id") or request.query_params.get("company_id")
        if company_id:
            comp = Company.objects.filter(id=company_id).first()
            if comp:
                return comp

        # 2. Destination phone number / phone_number_id
        to_number = str(data.get("To") or data.get("phone_number_id") or "").strip()
        if to_number:
            cfg = get_config_by_phone_number_id(to_number)
            if cfg and cfg.get("company_id"):
                comp = Company.objects.filter(id=cfg["company_id"]).first()
                if comp:
                    return comp
            comp = Company.objects.filter(phone=to_number).first()
            if comp:
                return comp

        # 3. Fallback to active company with calling enabled or first active
        return Company.objects.filter(is_calling_enabled=True).first() or Company.objects.first()

    def _handle_request(self, request):
        data = request.data if request.method == "POST" else request.query_params

        caller_phone = str(
            data.get("From") or data.get("caller") or data.get("customer_phone") or data.get("phone") or ""
        ).strip()
        call_id = str(data.get("CallSid") or data.get("call_id") or f"call_{timezone.now().timestamp()}").strip()

        company = self._resolve_company(request)
        if not company:
            # Fallback TwiML rejection if company cannot be resolved
            rejection_twiml = (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<Response>\n'
                '    <Say>Our service is currently unavailable. Please try again later.</Say>\n'
                '    <Hangup/>\n'
                '</Response>'
            )
            return HttpResponse(rejection_twiml, content_type="application/xml")

        # Check call quota
        allowed, rejection_msg, customer = check_and_enforce_call_limit(
            company=company,
            phone=caller_phone or "unknown_caller",
        )

        wants_json = (
            request.query_params.get("format") == "json"
            or "application/json" in request.headers.get("Accept", "")
            or not data.get("CallSid") and data.get("provider") in ("vapi", "bland")
        )

        # 1. Reject if call quota exceeded
        if not allowed:
            logger.warning(
                f"[AI Call Guard] Customer '{caller_phone}' reached daily call limit "
                f"for company '{company.name}' ({customer.daily_call_count}/{company.max_daily_calls}). "
                "Rejecting call without starting AI media stream."
            )

            # Record rejected call
            vcall, _ = VoiceCall.objects.get_or_create(
                call_id=call_id,
                defaults={
                    "company": company,
                    "customer_phone": caller_phone,
                    "direction": "inbound",
                    "status": "rejected",
                    "error_message": rejection_msg,
                },
            )
            CallEvent.objects.create(
                call=vcall,
                event_type="rate_limited_rejected",
                raw_payload={"reason": rejection_msg, "limit": company.max_daily_calls},
            )

            if wants_json:
                return Response(
                    {
                        "status": "rejected",
                        "rate_limited": True,
                        "message": rejection_msg,
                    },
                    status=200,
                )

            # Return TwiML static audio rejection
            rejection_twiml = (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<Response>\n'
                f'    <Say>{rejection_msg}</Say>\n'
                '    <Hangup/>\n'
                '</Response>'
            )
            return HttpResponse(rejection_twiml, content_type="application/xml")

        # 2. Allow call and dynamically inject maximum duration limit
        max_duration_minutes = getattr(company, "max_call_duration_minutes", 3)
        duration_seconds = max_duration_minutes * 60

        logger.info(
            f"[AI Call Guard] Call permitted for customer '{caller_phone}' on company '{company.name}'. "
            f"Enforcing maximum duration: {duration_seconds}s ({max_duration_minutes}m)."
        )

        # Record initiated call
        vcall, _ = VoiceCall.objects.get_or_create(
            call_id=call_id,
            defaults={
                "company": company,
                "customer_phone": caller_phone,
                "direction": "inbound",
                "status": "initiated",
            },
        )
        CallEvent.objects.create(
            call=vcall,
            event_type="call_accepted",
            raw_payload={"time_limit_seconds": duration_seconds},
        )

        if wants_json:
            return Response(
                {
                    "status": "accepted",
                    "time_limit_seconds": duration_seconds,
                    "max_duration": duration_seconds,
                    "stream_url": f"wss://ai.rides.ai/voice/stream?call_id={call_id}",
                },
                status=200,
            )

        # TwiML establishing connection with timeLimit injected
        allowed_twiml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Response>\n'
            f'    <Connect>\n'
            f'        <Stream url="wss://ai.rides.ai/voice/stream?call_id={call_id}" timeLimit="{duration_seconds}"/>\n'
            f'    </Connect>\n'
            '</Response>'
        )
        return HttpResponse(allowed_twiml, content_type="application/xml")

    def post(self, request, *args, **kwargs):
        return self._handle_request(request)

    def get(self, request, *args, **kwargs):
        return self._handle_request(request)
