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

from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny

from companies.models import Company
from operations import evolution_client
from operations.whatsapp_agent import process_incoming_whatsapp_message

logger = logging.getLogger("operations.evolution")


def _build_evolution_webhook_url(request) -> str:
    """
    Returns the normalized Evolution API webhook URL with NO trailing slash,
    preventing double slashes ('//connection-update') if webhook_by_events is enabled.
    """
    configured = getattr(settings, "EVOLUTION_WEBHOOK_URL", None)
    if configured:
        return str(configured).strip().rstrip("/")
    base = request.build_absolute_uri("/api/operations/whatsapp/evolution-webhook")
    return base.rstrip("/")


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
        webhook_url = _build_evolution_webhook_url(request)
        logger.info(f"[WhatsApp QR] Generating QR code for company '{company.name}' (instance: '{instance_name}')")

        # Always sync live Evolution state instead of trusting stale DB status
        live_status = evolution_client.get_connection_status(instance_name)
        if live_status == "connected":
            if company.whatsapp_connection_status != "connected":
                company.whatsapp_connection_status = "connected"
                company.save(update_fields=["whatsapp_connection_status"])
            return Response(
                {
                    "instance_name": instance_name,
                    "qrcode_base64": None,
                    "status": "connected",
                    "details": {"state": "connected"},
                },
                status=200,
            )

        result = evolution_client.create_instance(instance_name, webhook_url=webhook_url, qrcode=True)
        qr_b64 = result.get("qrcode_base64")

        # If create_instance / get_qr_code returned no QR (e.g. stuck on 401 LOGOUT),
        # automatically hard-delete + recreate + poll via reconnect_instance()
        if not qr_b64:
            logger.warning(
                f"[WhatsApp QR] No QR returned for '{instance_name}' (likely 401/LOGOUT state). "
                "Falling back to hard-delete reconnect_instance()..."
            )
            result = evolution_client.reconnect_instance(instance_name, webhook_url=webhook_url)
            qr_b64 = result.get("qrcode_base64")

        effective_status = "disconnected"
        if company.whatsapp_connection_status != effective_status:
            company.whatsapp_connection_status = effective_status
            company.save(update_fields=["whatsapp_connection_status"])

        return Response(
            {
                "instance_name": instance_name,
                "qrcode_base64": qr_b64,
                "status": effective_status,
                "details": result,
            },
            status=200,
        )

    def get(self, request, *args, **kwargs):
        """
        Live status check endpoint — queries Evolution API connectionState directly
        and auto-syncs the PostgreSQL status if drifted.
        """
        company = self._get_company(request)
        if not company or not company.whatsapp_instance_name:
            return Response(
                {"instance_name": None, "status": "disconnected", "live_synced": True},
                status=200,
            )

        status = evolution_client.get_connection_status(company.whatsapp_instance_name)

        if status != company.whatsapp_connection_status:
            logger.info(
                f"[WhatsApp Sync] Synced company '{company.name}' status from "
                f"'{company.whatsapp_connection_status}' -> '{status}'"
            )
            company.whatsapp_connection_status = status
            company.save(update_fields=["whatsapp_connection_status"])

        return Response(
            {
                "instance_name": company.whatsapp_instance_name,
                "status": status,
                "live_synced": True,
            },
            status=200,
        )


class ReconnectWhatsAppView(APIView):
    """
    POST /api/operations/whatsapp/reconnect/
    Force-disconnects any active/stale Evolution session and returns a fresh QR code,
    even if the DB currently believes the instance is 'connected'.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"error": "No company associated with user"}, status=400)

        if not company.whatsapp_instance_name:
            company.whatsapp_instance_name = f"company_{company.id}"
            company.save(update_fields=["whatsapp_instance_name"])

        instance_name = company.whatsapp_instance_name
        webhook_url = _build_evolution_webhook_url(request)
        logger.info(f"[WhatsApp Reconnect] Force-reconnecting '{company.name}' (instance: '{instance_name}')")

        result = evolution_client.reconnect_instance(instance_name, webhook_url=webhook_url)

        company.whatsapp_connection_status = "disconnected"
        company.save(update_fields=["whatsapp_connection_status"])

        return Response(
            {
                "instance_name": instance_name,
                "qrcode_base64": result.get("qrcode_base64"),
                "status": "disconnected",
                "details": result,
            },
            status=200,
        )


class DisconnectWhatsAppView(APIView):
    """
    POST /api/operations/whatsapp/disconnect/
    Logs out AND hard-deletes the Evolution API instance so any future reconnect starts cleanly,
    and marks the company's WhatsApp session disconnected.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"error": "No company associated with user"}, status=400)

        instance_name = company.whatsapp_instance_name
        logout_res = {}
        delete_res = {}
        if instance_name:
            logger.info(f"[WhatsApp Disconnect] Logging out & deleting '{company.name}' (instance: '{instance_name}')")
            logout_res = evolution_client.logout_instance(instance_name)
            delete_res = evolution_client.delete_instance(instance_name)

        company.whatsapp_connection_status = "disconnected"
        company.save(update_fields=["whatsapp_connection_status"])

        return Response(
            {
                "instance_name": instance_name,
                "status": "disconnected",
                "disconnected": True,
                "details": {"logout": logout_res, "delete": delete_res},
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

            # Auto-configure call rejection whenever session connects/opens
            if new_status == "connected" or str(state).lower() == "open":
                evolution_client.configure_instance_settings(instance)

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

            # Ignore group messages and broadcast status updates
            if remote_jid.endswith("@g.us") or remote_jid == "status@broadcast":
                return Response({"ignored": "group_or_status_message"}, status=200)

            # Resolve @lid JIDs (Evolution API v2 / Baileys Linked Devices) to actual phone JID when available
            if remote_jid.endswith("@lid"):
                alt_jid = str(key.get("remoteJidAlt") or key.get("participant") or "").strip()
                if alt_jid and "@s.whatsapp.net" in alt_jid:
                    remote_jid = alt_jid

            # Extract clean customer phone number
            customer_phone = (
                remote_jid.replace("@s.whatsapp.net", "")
                .replace("@c.us", "")
                .replace("@lid", "")
                .replace("+", "")
                .strip()
            )
            customer_name = data.get("pushName") or "Valued Customer"

            # Parse & unwrap nested Baileys message envelopes (ephemeral / viewOnce / etc.)
            raw_message_obj = data.get("message", {}) if isinstance(data.get("message"), dict) else {}
            message_obj = raw_message_obj
            for wrapper_key in (
                "ephemeralMessage",
                "viewOnceMessage",
                "viewOnceMessageV2",
                "viewOnceMessageV2Extension",
                "documentWithCaptionMessage",
            ):
                if wrapper_key in message_obj and isinstance(message_obj[wrapper_key], dict):
                    inner = message_obj[wrapper_key].get("message")
                    if isinstance(inner, dict):
                        message_obj = inner

            msg_type = "text"
            media_id = None
            message_text = ""
            audio_bytes = None

            # Check for audio / voice note (including PTT voice notes)
            is_audio_payload = (
                "audioMessage" in message_obj
                or str(data.get("messageType", "")).lower() == "audiomessage"
            )
            if is_audio_payload:
                import base64
                msg_type = "audio"
                audio_obj = message_obj.get("audioMessage", {}) if isinstance(message_obj.get("audioMessage"), dict) else {}
                media_id = None

                # Check all possible inline base64 locations
                raw_b64 = (
                    raw_message_obj.get("base64")
                    or message_obj.get("base64")
                    or data.get("base64")
                    or audio_obj.get("base64")
                )
                if raw_b64:
                    try:
                        if "," in str(raw_b64):
                            raw_b64 = str(raw_b64).split(",", 1)[1]
                        audio_bytes = base64.b64decode(raw_b64)
                    except Exception as e:
                        logger.warning(f"[Evolution Webhook] Failed to decode inline base64 audio: {e}")

                # If not present inline, fetch decrypted base64 from Evolution API
                if not audio_bytes:
                    audio_bytes = evolution_client.get_media_base64(instance, data)

                if not audio_bytes:
                    logger.error(
                        f"[Evolution Webhook ERROR] Failed to obtain decrypted audio bytes for instance '{instance}' "
                        f"from customer {customer_phone}. Skipping Meta download fallback to prevent missing token errors."
                    )
                    media_id = None
                else:
                    media_id = "evolution_voice_note"
            else:
                conversation = message_obj.get("conversation", "")
                extended = message_obj.get("extendedTextMessage", {}).get("text", "")
                message_text = str(conversation or extended or "").strip()

            logger.info(
                f"[Evolution Webhook] Incoming message for '{company.name}' from {customer_phone} "
                f"({customer_name}) | Type: {msg_type} | Text: '{message_text}' | Audio bytes: {len(audio_bytes) if audio_bytes else 0}"
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
                    audio_bytes=audio_bytes,
                )
                return Response({"status": "processed", "result": agent_result}, status=200)
            except Exception as e:
                logger.error(f"[Evolution Webhook ERROR] Failed processing message: {e}", exc_info=True)
                return Response({"status": "error", "error": str(e)}, status=200)

        # Fallback acknowledgment for other events (e.g. qrcode.updated, chats.set, etc.)
        return Response({"status": "acknowledged", "event": event}, status=200)
