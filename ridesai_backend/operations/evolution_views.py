"""
Evolution API Views for WhatsApp QR Onboarding and Webhook Handling.

Provides:
1. ConnectWhatsAppView:
   - POST: Initializes or retrieves an Evolution API instance and returns the QR code base64.
   - GET: Polling status check for the connected instance.
2. EvolutionWebhookView:
   - POST: Ingests Evolution API webhooks (connection.update, messages.upsert),
     updates Company connection status, and routes incoming customer messages
     directly through the existing process_incoming_whatsapp_message() pipeline.
"""

import logging
from typing import Dict, Any

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny

from companies.models import Company
from operations import evolution_client
from operations.whatsapp_agent import process_incoming_whatsapp_message

logger = logging.getLogger("operations.evolution")


class ConnectWhatsAppView(APIView):
    """
    Onboarding endpoint for connecting WhatsApp via Evolution API QR code.
    Requires authentication (Owner or staff with company context).
    """
    permission_classes = [IsAuthenticated]

    def _get_company(self, request) -> Company:
        company = getattr(request.user, "company", None)
        return company

    def post(self, request, *args, **kwargs):
        """
        Creates or retrieves an Evolution instance for the user's company
        and returns the QR code base64 for WhatsApp Web pairing.
        """
        company = self._get_company(request)
        if not company:
            return Response({"error": "No company associated with user"}, status=400)

        # Assign instance name if not yet set
        if not company.whatsapp_instance_name:
            company.whatsapp_instance_name = f"company_{company.id}"
            company.save(update_fields=["whatsapp_instance_name"])

        instance_name = company.whatsapp_instance_name
        logger.info(f"[WhatsApp QR] Generating QR code for company '{company.name}' (instance: '{instance_name}')")

        result = evolution_client.create_instance(instance_name)

        return Response(
            {
                "instance_name": instance_name,
                "qrcode_base64": result.get("qrcode_base64"),
                "status": company.whatsapp_connection_status,
                "details": result,
            },
            status=200,
        )

    def get(self, request, *args, **kwargs):
        """
        Lightweight status check endpoint for frontend polling while scanning QR code.
        """
        company = self._get_company(request)
        if not company or not company.whatsapp_instance_name:
            return Response(
                {"instance_name": None, "status": "disconnected"},
                status=200,
            )

        status = evolution_client.get_connection_status(company.whatsapp_instance_name)

        if status != company.whatsapp_connection_status:
            company.whatsapp_connection_status = status
            company.save(update_fields=["whatsapp_connection_status"])

        return Response(
            {
                "instance_name": company.whatsapp_instance_name,
                "status": status,
            },
            status=200,
        )


class EvolutionWebhookView(APIView):
    """
    Public webhook receiver for Evolution API events (connection.update, messages.upsert).
    CSRF-exempt and unauthenticated (AllowAny) to receive events from external Baileys/Evolution engine.
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        payload = request.data if isinstance(request.data, dict) else {}
        event = payload.get("event", "")
        instance = payload.get("instance", "")
        data = payload.get("data", {}) if isinstance(payload.get("data"), dict) else {}

        if not instance:
            logger.warning("[Evolution Webhook] Ignored payload without instance name")
            return Response({"ignored": "missing_instance"}, status=200)

        # Step 1: Resolve Company / Tenant Isolation
        company = Company.objects.filter(whatsapp_instance_name=instance).first()
        if not company:
            logger.warning(f"[Evolution Webhook] Ignored event for unmapped instance: '{instance}'")
            return Response({"ignored": "unknown_instance"}, status=200)

        # Step 2: Handle Connection Updates (connection.update or CONNECTION_UPDATE)
        if event in ("connection.update", "CONNECTION_UPDATE"):
            state = data.get("state") or data.get("connection") or data.get("status")
            new_status = "connected" if str(state).lower() == "open" else "disconnected"

            logger.info(
                f"[Evolution Webhook] Connection status update for '{company.name}' "
                f"(instance: '{instance}'): {state} -> {new_status}"
            )

            if company.whatsapp_connection_status != new_status:
                company.whatsapp_connection_status = new_status
                company.save(update_fields=["whatsapp_connection_status"])

            return Response(
                {
                    "status": "updated",
                    "connection_status": company.whatsapp_connection_status,
                },
                status=200,
            )

        # Step 3: Handle Incoming Messages (messages.upsert or MESSAGES_UPSERT)
        if event in ("messages.upsert", "MESSAGES_UPSERT"):
            key = data.get("key", {}) if isinstance(data.get("key"), dict) else {}

            # Ignore messages sent by the bot itself
            if key.get("fromMe") is True:
                return Response({"ignored": "from_me"}, status=200)

            remote_jid = str(key.get("remoteJid", "")).strip()

            # Ignore group messages
            if remote_jid.endswith("@g.us"):
                return Response({"ignored": "group_message"}, status=200)

            # Extract clean customer phone number
            customer_phone = remote_jid.replace("@s.whatsapp.net", "").replace("+", "").strip()
            customer_name = data.get("pushName") or "Valued Customer"

            # Parse message content
            message_obj = data.get("message", {}) if isinstance(data.get("message"), dict) else {}
            msg_type = "text"
            media_id = None
            message_text = ""

            # Check for audio / voice note
            if "audioMessage" in message_obj:
                msg_type = "audio"
                audio_obj = message_obj.get("audioMessage", {})
                media_id = audio_obj.get("url") or audio_obj.get("id") or "evolution_voice_note"
            else:
                conversation = message_obj.get("conversation", "")
                extended = message_obj.get("extendedTextMessage", {}).get("text", "")
                message_text = str(conversation or extended or "").strip()

            logger.info(
                f"[Evolution Webhook] Incoming message for '{company.name}' from {customer_phone} "
                f"({customer_name}) | Type: {msg_type} | Text: '{message_text}'"
            )

            # Route directly into the existing AI agent processing pipeline
            try:
                agent_result = process_incoming_whatsapp_message(
                    sender_phone=customer_phone,
                    message_text=message_text,
                    phone_number_id=instance,
                    customer_name=customer_name,
                    media_id=media_id,
                    msg_type=msg_type,
                    company=company,
                )
                return Response({"status": "processed", "result": agent_result}, status=200)
            except Exception as e:
                logger.error(f"[Evolution Webhook ERROR] Failed processing message: {e}", exc_info=True)
                return Response({"status": "error", "error": str(e)}, status=200)

        # Fallback acknowledgment for other events (e.g. qrcode.updated, chats.set, etc.)
        return Response({"status": "acknowledged", "event": event}, status=200)
