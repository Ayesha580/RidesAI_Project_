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
import re
import threading
import time
from typing import Dict, Any, Optional

from django.conf import settings
from django.core.cache import cache
from django.db import close_old_connections
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny

from companies.models import Company
from operations import evolution_client
from operations.whatsapp_agent import process_incoming_whatsapp_message

logger = logging.getLogger("operations.evolution")

EVOLUTION_DEDUP_TTL_SECONDS = 600   # 10 minutes
EVOLUTION_STALE_MAX_AGE_SECONDS = 120


def _resolve_company_for_instance(instance: str) -> Optional[Company]:
    """
    Resolves a Company tenant from an Evolution instance name:
    1. Exact / case-insensitive match on whatsapp_instance_name
    2. Fallback for standard 'company_<id>' instance naming (auto-persisting the field)
    """
    clean = str(instance or "").strip()
    if not clean:
        return None
    company = (
        Company.objects.filter(whatsapp_instance_name=clean).first()
        or Company.objects.filter(whatsapp_instance_name__iexact=clean).first()
    )
    if company:
        return company
    m = re.match(r"^company_(\d+)$", clean, flags=re.IGNORECASE)
    if m:
        company = Company.objects.filter(pk=int(m.group(1))).first()
        if company and not company.whatsapp_instance_name:
            company.whatsapp_instance_name = clean
            company.save(update_fields=["whatsapp_instance_name"])
        return company
    return None


def _parse_message_timestamp(raw_ts: Any) -> Optional[float]:
    """Parses Evolution/Baileys messageTimestamp (int/str/ms or Long dict {'low': ...}) into UNIX seconds."""
    if raw_ts is None or raw_ts == "":
        return None
    val = raw_ts
    if isinstance(val, dict):
        val = val.get("low") or val.get("seconds")
    try:
        ts = float(val)
    except (TypeError, ValueError):
        return None
    if ts <= 0:
        return None
    if ts > 10_000_000_000:
        ts = ts / 1000.0
    return ts


def _safe_close_old_connections() -> None:
    """Closes stale DB connections in background threads without disrupting active atomic blocks."""
    from django.db import connection
    if not connection.in_atomic_block:
        close_old_connections()


def _process_evolution_message_worker(
    *,
    company_id: int,
    instance: str,
    customer_phone: str,
    customer_name: str,
    msg_type: str,
    message_text: str,
    is_audio_payload: bool,
    inline_audio_bytes: Optional[bytes],
    raw_event_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Runs the full WhatsApp AI pipeline (media download -> STT -> LLM -> TTS -> Evolution send)
    in a daemon background thread so EvolutionWebhookView returns 200 OK immediately.
    """
    _safe_close_old_connections()
    try:
        company = Company.objects.filter(pk=company_id).first()
        if not company:
            logger.warning(f"[Evolution Worker] Company id={company_id} not found; aborting.")
            return {"success": False, "error": "company_not_found"}

        audio_bytes = inline_audio_bytes
        media_id = None
        if is_audio_payload:
            if not audio_bytes:
                audio_bytes = evolution_client.get_media_base64(instance, raw_event_data)
            if not audio_bytes:
                logger.error(
                    f"[Evolution Worker ERROR] Failed to obtain decrypted audio bytes for instance '{instance}' "
                    f"from customer {customer_phone}."
                )
                media_id = None
            else:
                media_id = "evolution_voice_note"

        logger.info(
            f"[Evolution Worker] Processing message for '{company.name}' from {customer_phone} "
            f"({customer_name}) | Type: {msg_type} | Text: '{message_text}' | "
            f"Audio bytes: {len(audio_bytes) if audio_bytes else 0}"
        )

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
        logger.info(
            f"[Evolution Worker] Completed for '{company.name}' -> {customer_phone} | "
            f"success={agent_result.get('success')} | error={agent_result.get('error')} | "
            f"reply_preview='{str(agent_result.get('reply_text') or '')[:80]}'"
        )
        return agent_result
    except Exception as e:
        logger.error(f"[Evolution Worker ERROR] Unhandled error for '{instance}' -> {customer_phone}: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
    finally:
        _safe_close_old_connections()


def _dispatch_evolution_worker(**kwargs) -> None:
    """Spawns a daemon background thread to process an Evolution WhatsApp message non-blockingly."""
    t = threading.Thread(
        target=_process_evolution_message_worker,
        kwargs=kwargs,
        daemon=True,
        name=f"evo-wa-{kwargs.get('instance', 'inst')}",
    )
    t.start()


def _build_evolution_webhook_url(request) -> str:
    """
    Returns the normalized Evolution API webhook URL with NO trailing slash,
    automatically rewriting 127.0.0.1 / localhost to host.docker.internal so
    Dockerized Evolution API reaches the host Django server cleanly.
    """
    configured = getattr(settings, "EVOLUTION_WEBHOOK_URL", None)
    if configured:
        return evolution_client._normalize_webhook_url(configured) or evolution_client.DEFAULT_DOCKER_WEBHOOK_URL
    base = request.build_absolute_uri("/api/operations/whatsapp/evolution-webhook")
    return evolution_client._normalize_webhook_url(base) or evolution_client.DEFAULT_DOCKER_WEBHOOK_URL


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

        # Assign instance name and auto-enable AI agent out-of-the-box for any connecting tenant
        update_fields = []
        if not company.whatsapp_instance_name:
            company.whatsapp_instance_name = f"company_{company.id}"
            update_fields.append("whatsapp_instance_name")
        if not getattr(company, "agent_enabled", False):
            company.agent_enabled = True
            update_fields.append("agent_enabled")
        if update_fields:
            company.save(update_fields=update_fields)

        instance_name = company.whatsapp_instance_name
        webhook_url = _build_evolution_webhook_url(request)
        logger.info(f"[WhatsApp QR] Generating QR code for company '{company.name}' (instance: '{instance_name}')")

        # Always sync live Evolution state instead of trusting stale DB status
        live_status = evolution_client.get_connection_status(instance_name)
        if live_status == "connected":
            if company.whatsapp_connection_status != "connected":
                company.whatsapp_connection_status = "connected"
                company.save(update_fields=["whatsapp_connection_status"])
            # Ensure existing connected instance uses the normalized host.docker.internal webhook URL
            evolution_client.set_instance_webhook(instance_name, webhook_url=webhook_url)
            return Response(
                {
                    "instance_name": instance_name,
                    "qrcode_base64": None,
                    "status": "connected",
                    "webhook_url": webhook_url,
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

        webhook_synced = None
        if status == "connected":
            webhook_url = _build_evolution_webhook_url(request)
            sync_res = evolution_client.set_instance_webhook(
                company.whatsapp_instance_name, webhook_url=webhook_url
            )
            webhook_synced = sync_res.get("webhook_url")

        return Response(
            {
                "instance_name": company.whatsapp_instance_name,
                "status": status,
                "live_synced": True,
                "webhook_url": webhook_synced,
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
        event_slug = str(kwargs.get("event_slug") or "").strip()
        raw_event = payload.get("event") or event_slug or ""
        event_norm = str(raw_event).strip().lower().replace("-", ".").replace("_", ".")
        instance = str(payload.get("instance") or "").strip()
        raw_data = payload.get("data")
        if isinstance(raw_data, list):
            data = raw_data[0] if (raw_data and isinstance(raw_data[0], dict)) else {}
        elif isinstance(raw_data, dict):
            if "key" not in raw_data and isinstance(raw_data.get("messages"), list) and raw_data["messages"]:
                first_msg = raw_data["messages"][0]
                data = first_msg if isinstance(first_msg, dict) else raw_data
            else:
                data = raw_data
        else:
            data = {}

        if not instance:
            logger.warning(f"[Evolution Webhook] Ignored payload without instance name (event='{raw_event}', slug='{event_slug}')")
            return Response({"ignored": "missing_instance"}, status=200)

        # Step 1: Resolve Company / Tenant Isolation
        company = _resolve_company_for_instance(instance)
        if not company:
            logger.warning(f"[Evolution Webhook] Ignored event='{raw_event}' for unmapped instance: '{instance}'")
            return Response({"ignored": "unknown_instance"}, status=200)

        logger.info(
            f"[Evolution Webhook] Received event='{raw_event}' (norm='{event_norm}', slug='{event_slug}') "
            f"instance='{instance}' -> company='{company.name}' (id={company.id}, vertical='{company.business_type}')"
        )

        # Step 2: Handle Connection Updates (connection.update / CONNECTION_UPDATE / connection-update)
        if event_norm == "connection.update":
            state = data.get("state") or data.get("connection") or data.get("status")
            new_status = "connected" if str(state).lower() == "open" else "disconnected"

            logger.info(
                f"[Evolution Webhook] Connection status update for '{company.name}' "
                f"(instance: '{instance}'): {state} -> {new_status}"
            )

            update_fields = []
            if company.whatsapp_connection_status != new_status:
                company.whatsapp_connection_status = new_status
                update_fields.append("whatsapp_connection_status")
            if new_status == "connected" and not getattr(company, "agent_enabled", False):
                company.agent_enabled = True
                update_fields.append("agent_enabled")
            if update_fields:
                company.save(update_fields=update_fields)

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

        # Step 3: Handle Incoming Messages (messages.upsert / MESSAGES_UPSERT / messages-upsert)
        if event_norm == "messages.upsert":
            key = data.get("key", {}) if isinstance(data.get("key"), dict) else {}

            # Ignore messages sent by the bot itself
            if key.get("fromMe") is True:
                logger.info(f"[Evolution Webhook] Skipping fromMe=True message for '{company.name}' ({instance})")
                return Response({"ignored": "from_me"}, status=200)

            remote_jid = str(key.get("remoteJid", "")).strip()

            # Ignore group messages and broadcast status updates
            if not remote_jid or remote_jid.endswith("@g.us") or remote_jid == "status@broadcast":
                logger.info(f"[Evolution Webhook] Skipping group/status/empty JID '{remote_jid}' for '{company.name}'")
                return Response({"ignored": "group_or_status_message"}, status=200)

            # Stale message guard (> 120s old): prevents reconnect/restart floods
            msg_ts = _parse_message_timestamp(data.get("messageTimestamp"))
            if msg_ts is not None:
                age_seconds = time.time() - msg_ts
                if age_seconds > EVOLUTION_STALE_MAX_AGE_SECONDS:
                    logger.info(
                        f"[Evolution Webhook] Ignoring stale message (age={int(age_seconds)}s > "
                        f"{EVOLUTION_STALE_MAX_AGE_SECONDS}s) for '{company.name}' ({instance})"
                    )
                    return Response({"ignored": "stale_message"}, status=200)

            # Deduplicate by Evolution message_id (10-minute TTL) to block webhook retry floods
            message_id = str(key.get("id") or "").strip()
            if message_id:
                dedup_key = f"evo_msg_seen:{instance}:{message_id}"
                if not cache.add(dedup_key, 1, timeout=EVOLUTION_DEDUP_TTL_SECONDS):
                    logger.info(
                        f"[Evolution Webhook] Ignoring duplicate message_id='{message_id}' "
                        f"for '{company.name}' ({instance})"
                    )
                    return Response({"ignored": "duplicate_message"}, status=200)

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
            message_text = ""
            inline_audio_bytes = None

            # Check for audio / voice note (including PTT voice notes)
            is_audio_payload = (
                "audioMessage" in message_obj
                or str(data.get("messageType", "")).lower() == "audiomessage"
            )
            if is_audio_payload:
                import base64
                msg_type = "audio"
                audio_obj = message_obj.get("audioMessage", {}) if isinstance(message_obj.get("audioMessage"), dict) else {}
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
                        inline_audio_bytes = base64.b64decode(raw_b64)
                    except Exception as e:
                        logger.warning(f"[Evolution Webhook] Failed to decode inline base64 audio: {e}")
            else:
                conversation = message_obj.get("conversation", "")
                extended = (
                    message_obj.get("extendedTextMessage", {}).get("text", "")
                    if isinstance(message_obj.get("extendedTextMessage"), dict)
                    else ""
                )
                img_caption = (
                    message_obj.get("imageMessage", {}).get("caption", "")
                    if isinstance(message_obj.get("imageMessage"), dict)
                    else ""
                )
                vid_caption = (
                    message_obj.get("videoMessage", {}).get("caption", "")
                    if isinstance(message_obj.get("videoMessage"), dict)
                    else ""
                )
                btn_reply = (
                    message_obj.get("buttonsResponseMessage", {}).get("selectedDisplayText", "")
                    if isinstance(message_obj.get("buttonsResponseMessage"), dict)
                    else ""
                )
                list_reply = (
                    message_obj.get("listResponseMessage", {}).get("title", "")
                    if isinstance(message_obj.get("listResponseMessage"), dict)
                    else ""
                )
                message_text = str(
                    conversation or extended or img_caption or vid_caption or btn_reply or list_reply or ""
                ).strip()

                if not message_text:
                    logger.info(
                        f"[Evolution Webhook] Skipping non-text/empty message for '{company.name}' from {customer_phone} "
                        f"(message keys: {list(message_obj.keys())})"
                    )
                    return Response({"ignored": "empty_message"}, status=200)

            logger.info(
                f"[Evolution Webhook] Queuing background AI processing for '{company.name}' "
                f"from {customer_phone} ({customer_name}) | msg_id='{message_id}' | Type={msg_type}"
            )

            # Dispatch non-blockingly in a daemon thread and return 200 OK immediately
            _dispatch_evolution_worker(
                company_id=company.id,
                instance=instance,
                customer_phone=customer_phone,
                customer_name=customer_name,
                msg_type=msg_type,
                message_text=message_text,
                is_audio_payload=is_audio_payload,
                inline_audio_bytes=inline_audio_bytes,
                raw_event_data=data,
            )
            return Response({"status": "queued", "message_id": message_id}, status=200)

        # Fallback acknowledgment for other events (e.g. qrcode.updated, chats.update, messages.update)
        logger.info(
            f"[Evolution Webhook] Acknowledged non-actionable event='{raw_event}' (norm='{event_norm}') "
            f"for '{company.name}' ({instance})"
        )
        return Response({"status": "acknowledged", "event": raw_event}, status=200)
