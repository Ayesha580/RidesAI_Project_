"""
Automated WhatsApp Customer Status Notifications Service.
Dispatches transactional status alerts (order status, appointment status)
over WhatsApp via Evolution API (QR-connected instance) or Meta Cloud API.
"""

import logging
import re
from typing import Optional

from companies.models import Company
from operations import evolution_client
from operations.whatsapp_service import WhatsAppService

logger = logging.getLogger("operations.notifications")

AVAILABLE_PLACEHOLDERS = [
    {"tag": "{{customer_name}}", "description": "Customer or patient full name"},
    {"tag": "{{order_id}}", "description": "Order, appointment, or booking reference number"},
    {"tag": "{{company_name}}", "description": "Your business name"},
    {"tag": "{{total_amount}}", "description": "Total amount formatted in Rs."},
    {"tag": "{{status}}", "description": "Current order or booking status"},
    {"tag": "{{appointment_time}}", "description": "Scheduled appointment or lab test time"},
    {"tag": "{{rider_name}}", "description": "Assigned delivery rider name"},
]

DEFAULT_NOTIFICATION_TEMPLATES = {
    "order_confirmed": {
        "label": "Order Confirmed",
        "description": "Sent immediately when a new order is confirmed.",
        "subject_template": "Order #{{order_id}} Confirmed — {{company_name}}",
        "body_template": (
            "✅ *Order Confirmed!* (Order #{{order_id}})\n\n"
            "Hi {{customer_name}}, thank you for ordering with *{{company_name}}*! "
            "Your order (Total: {{total_amount}}) has been confirmed and forwarded to preparation."
        ),
    },
    "order_preparing": {
        "label": "Order Preparing",
        "description": "Sent when kitchen or fulfillment starts preparing the order.",
        "subject_template": "Your Order #{{order_id}} is Being Prepared — {{company_name}}",
        "body_template": (
            "👨‍🍳 *Order In Preparation!* (Order #{{order_id}})\n\n"
            "Hi {{customer_name}}, *{{company_name}}* is currently preparing your order with fresh care."
        ),
    },
    "out_for_delivery": {
        "label": "Out for Delivery",
        "description": "Sent when a rider picks up and dispatches the order.",
        "subject_template": "Order #{{order_id}} is Out for Delivery — {{company_name}}",
        "body_template": (
            "🛵 *Order Out for Delivery!* (Order #{{order_id}})\n\n"
            "Hi {{customer_name}}, our rider {{rider_name}} has picked up your order from *{{company_name}}* "
            "and is on the way to your delivery address."
        ),
    },
    "order_delivered": {
        "label": "Order Delivered",
        "description": "Sent when the order is successfully delivered.",
        "subject_template": "Order #{{order_id}} Delivered — {{company_name}}",
        "body_template": (
            "🎉 *Order Delivered!* (Order #{{order_id}})\n\n"
            "Hi {{customer_name}}, your order from *{{company_name}}* has been delivered. "
            "Thank you for choosing us!"
        ),
    },
    "order_cancelled": {
        "label": "Order Cancelled",
        "description": "Sent if an order is cancelled or rejected.",
        "subject_template": "Order #{{order_id}} Cancelled — {{company_name}}",
        "body_template": (
            "❌ *Order Cancelled* (Order #{{order_id}})\n\n"
            "Hi {{customer_name}}, your order from *{{company_name}}* has been cancelled. "
            "Please reply here if you have any questions."
        ),
    },
    "appointment_confirmed": {
        "label": "Appointment Confirmed",
        "description": "Sent when a clinic or hospital OPD appointment is confirmed.",
        "subject_template": "Appointment #{{order_id}} Confirmed — {{company_name}}",
        "body_template": (
            "✅ *Appointment Confirmed!* (Ref #{{order_id}})\n\n"
            "Hi {{customer_name}}, your appointment at *{{company_name}}* is confirmed for {{appointment_time}}."
        ),
    },
    "appointment_reminder": {
        "label": "Appointment Reminder",
        "description": "Reminder sent ahead of a scheduled clinic/hospital appointment.",
        "subject_template": "Reminder: Upcoming Appointment #{{order_id}} — {{company_name}}",
        "body_template": (
            "⏰ *Appointment Reminder* (Ref #{{order_id}})\n\n"
            "Hi {{customer_name}}, this is a friendly reminder for your appointment at *{{company_name}}* at {{appointment_time}}."
        ),
    },
    "lab_booking_confirmed": {
        "label": "Lab Booking Confirmed",
        "description": "Sent when a hospital diagnostic or lab test booking is scheduled.",
        "subject_template": "Lab Booking #{{order_id}} Confirmed — {{company_name}}",
        "body_template": (
            "🧪 *Lab Test Booking Confirmed!* (Ref #{{order_id}})\n\n"
            "Hi {{customer_name}}, your diagnostic booking at *{{company_name}}* is scheduled for {{appointment_time}} "
            "(Fee: {{total_amount}})."
        ),
    },
}

_PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def _safe_substitute(template_str: str, context: dict) -> str:
    """Safely substitutes {{key}} placeholders without ever raising KeyError."""
    if not template_str:
        return ""
    safe_ctx = context or {}

    def _replace(match):
        key = match.group(1)
        val = safe_ctx.get(key)
        return "" if val is None else str(val)

    return _PLACEHOLDER_RE.sub(_replace, template_str)


def _resolve_event_type(entity_type: str, new_status: str) -> Optional[str]:
    ent = (entity_type or "").strip().lower()
    st = (new_status or "").strip().lower()
    if ent == "order":
        if st in ("confirmed", "received", "new"):
            return "order_confirmed"
        if st in ("preparing", "in_kitchen"):
            return "order_preparing"
        if st in ("dispatched", "out_for_delivery", "on_the_way", "picked_up"):
            return "out_for_delivery"
        if st == "delivered":
            return "order_delivered"
        if st in ("cancelled", "rejected"):
            return "order_cancelled"
    elif ent == "appointment":
        if st in ("confirmed", "scheduled"):
            return "appointment_confirmed"
        if st == "reminder":
            return "appointment_reminder"
    elif ent == "lab_booking":
        if st in ("scheduled", "confirmed"):
            return "lab_booking_confirmed"
    return None


def render_notification_template(company: Optional[Company], event_type: str, context: Optional[dict] = None) -> dict:
    """
    Loads the company's NotificationTemplate for `event_type` (falling back to system defaults),
    safely renders subject and body placeholders, and returns toggle flags + rendered text.
    """
    from operations.models import NotificationTemplate

    defaults = DEFAULT_NOTIFICATION_TEMPLATES.get(
        event_type,
        {
            "label": _format_status_label(event_type),
            "description": "",
            "subject_template": "Update #{{order_id}} — {{company_name}}",
            "body_template": "Update from {{company_name}} (Ref #{{order_id}}): Status is {{status}}.",
        },
    )

    tpl_obj = None
    if company and getattr(company, "id", None):
        tpl_obj = NotificationTemplate.objects.filter(company=company, event_type=event_type).first()

    is_enabled = bool(tpl_obj.is_enabled) if tpl_obj else True
    whatsapp_enabled = bool(tpl_obj.whatsapp_enabled) if tpl_obj else True
    email_enabled = bool(tpl_obj.email_enabled) if tpl_obj else True
    raw_subject = (tpl_obj.subject_template if (tpl_obj and tpl_obj.subject_template.strip()) else defaults["subject_template"])
    raw_body = (tpl_obj.body_template if (tpl_obj and tpl_obj.body_template.strip()) else defaults["body_template"])

    merged_ctx = {
        "company_name": (company.name if company else "") or "Rides AI Store",
        "customer_name": "Valued Customer",
        "order_id": "",
        "total_amount": "Rs. 0",
        "status": _format_status_label(event_type),
        "appointment_time": "",
        "rider_name": "",
    }
    if context:
        for k, v in context.items():
            if v is not None and str(v).strip() != "":
                merged_ctx[k] = v

    return {
        "event_type": event_type,
        "is_enabled": is_enabled,
        "whatsapp_enabled": whatsapp_enabled,
        "email_enabled": email_enabled,
        "subject": _safe_substitute(raw_subject, merged_ctx),
        "body": _safe_substitute(raw_body, merged_ctx),
        "is_customized": bool(tpl_obj),
    }


def normalize_pakistan_phone(raw_phone: Optional[str]) -> str:
    """
    Normalizes any Pakistani or international phone number into digits-only with country code.
    E.g.:
      '03090139836'   -> '923090139836'
      '+923090139836' -> '923090139836'
      '+92 309 0139836' -> '923090139836'
      '00923090139836' -> '923090139836'
      '3090139836'     -> '923090139836'
    """
    if not raw_phone:
        return ""
    digits = re.sub(r"\D", "", str(raw_phone))
    if not digits:
        return ""
    if digits.startswith("0092"):
        digits = "92" + digits[4:]
    elif digits.startswith("03") and len(digits) == 11:
        digits = "92" + digits[1:]
    elif digits.startswith("3") and len(digits) == 10:
        digits = "92" + digits
    return digits


def _format_status_label(status_str: str) -> str:
    """Returns human-readable capitalized status label."""
    return status_str.replace("_", " ").title()


def build_status_message(
    company_name: str,
    entity_type: str,
    reference_id: str,
    new_status: str,
    reason: Optional[str] = None,
    replacement_order_number: Optional[str] = None,
) -> str:
    """
    Constructs a polite, professional customer status notification message in English/Roman Urdu.
    """
    status_lower = (new_status or "").strip().lower()
    comp = company_name or "Rides AI Store"

    if entity_type == "order":
        if status_lower in ("confirmed", "received", "new"):
            msg = (
                f"✅ *Order Confirmed!* (Order #{reference_id})\n\n"
                f"Thank you for ordering with *{comp}*! Your order has been confirmed and forwarded to preparation."
            )
        elif status_lower in ("preparing", "in_kitchen"):
            msg = (
                f"👨‍🍳 *Order In Preparation!* (Order #{reference_id})\n\n"
                f"Good news! *{comp}* is currently preparing your order with fresh care."
            )
        elif status_lower in ("ready", "prepared"):
            msg = (
                f"📦 *Order Ready!* (Order #{reference_id})\n\n"
                f"Your order at *{comp}* is packed and ready for pickup / delivery dispatch."
            )
        elif status_lower in ("dispatched", "out_for_delivery", "on_the_way", "picked_up"):
            msg = (
                f"🛵 *Order Out for Delivery!* (Order #{reference_id})\n\n"
                f"Our rider has picked up your order from *{comp}* and is on the way to your delivery address."
            )
        elif status_lower == "delivered":
            msg = (
                f"🎉 *Order Delivered!* (Order #{reference_id})\n\n"
                f"Your order from *{comp}* has been successfully delivered. We hope you enjoy it!\n"
                f"Thank you for choosing us."
            )
        elif status_lower in ("cancelled", "rejected"):
            reason_text = f"\n*Reason:* {reason}" if reason else ""
            msg = (
                f"❌ *Order Cancelled* (Order #{reference_id})\n\n"
                f"Your order from *{comp}* has been cancelled.{reason_text}\n"
                f"Please reply here if you have any questions."
            )
        else:
            msg = (
                f"ℹ️ *Order Update* (Order #{reference_id})\n\n"
                f"Status of your order at *{comp}* is now: *{_format_status_label(status_lower)}*."
            )
    elif entity_type == "appointment":
        if status_lower in ("confirmed", "scheduled"):
            msg = (
                f"✅ *Appointment Confirmed!* (Ref #{reference_id})\n\n"
                f"Your booking with *{comp}* has been confirmed. We look forward to seeing you."
            )
        elif status_lower in ("cancelled", "rescheduled"):
            reason_text = f"\n*Reason:* {reason}" if reason else ""
            msg = (
                f"ℹ️ *Appointment Update* (Ref #{reference_id})\n\n"
                f"Your appointment with *{comp}* is {status_lower}.{reason_text}"
            )
        elif status_lower == "completed":
            msg = (
                f"🌟 *Thank You for Visiting!* (Ref #{reference_id})\n\n"
                f"Thank you for your visit to *{comp}*. We hope you had a great experience."
            )
        else:
            msg = (
                f"ℹ️ *Appointment Update* (Ref #{reference_id})\n\n"
                f"Status at *{comp}*: *{_format_status_label(status_lower)}*."
            )
    elif entity_type in ("return", "exchange"):
        req_label = "Return" if entity_type == "return" else "Exchange"
        if status_lower == "approved":
            if entity_type == "exchange" and replacement_order_number:
                msg = (
                    f"✅ *Exchange Request Approved!* (Ref #{reference_id})\n\n"
                    f"Thank you for contacting *{comp}*. Your exchange request has been approved! "
                    f"Replacement Order *#{replacement_order_number}* has been created for doorstep swap.\n"
                    f"Our rider will deliver your replacement and collect the original item. Please keep the item ready in original packaging."
                )
            else:
                msg = (
                    f"✅ *{req_label} Request Approved!* (Ref #{reference_id})\n\n"
                    f"Thank you for contacting *{comp}*. Your {entity_type} request has been approved by our team.\n"
                    f"Please keep items in their original condition for collection/dispatch."
                )
        elif status_lower == "completed":
            if entity_type == "exchange":
                msg = (
                    f"🎉 *Exchange Completed!* (Ref #{reference_id})\n\n"
                    f"Your exchange request with *{comp}* has been successfully completed via doorstep swap.\n"
                    f"Thank you for shopping with us!"
                )
            else:
                msg = (
                    f"🎉 *Return Completed!* (Ref #{reference_id})\n\n"
                    f"Your return request with *{comp}* has been successfully processed and completed.\n"
                    f"Thank you for shopping with us!"
                )
        elif status_lower == "rejected":
            reason_text = f"\n*Reason:* {reason}" if reason else ""
            msg = (
                f"❌ *{req_label} Request Rejected* (Ref #{reference_id})\n\n"
                f"Your {entity_type} request with *{comp}* could not be approved.{reason_text}\n"
                f"Please reply here if you have any questions."
            )
        else:
            msg = (
                f"ℹ️ *{req_label} Request Update* (Ref #{reference_id})\n\n"
                f"Status at *{comp}*: *{_format_status_label(status_lower)}*."
            )
    else:
        msg = (
            f"ℹ️ *Update from {comp}* (Ref #{reference_id})\n\n"
            f"Status updated to: *{_format_status_label(status_lower)}*."
        )

    return msg


def send_status_notification(
    company: Company,
    customer_phone: Optional[str] = None,
    entity_type: str = "order",
    reference_id: str = "",
    new_status: str = "",
    reason: Optional[str] = None,
    previous_status: Optional[str] = None,
    phone: Optional[str] = None,
    replacement_order_number: Optional[str] = None,
    **kwargs,
) -> bool:
    """
    Sends an automated WhatsApp status notification to the customer.

    - Idempotent: Skips if previous_status equals new_status.
    - Phone normalization: Converts 03xx local format or messy phones to standard 923xxxxxxxxx.
    - Multi-tenant routing: Prefers Evolution API instance if configured, falls back to Meta Cloud API.
    - Fault-tolerant: Never raises exceptions to the caller; logs detailed diagnostics.
    """
    target_phone = customer_phone or phone or kwargs.get("customer_phone") or kwargs.get("phone")
    if not target_phone:
        logger.warning("[Notification] No customer phone provided for %s #%s; skipping.", entity_type, reference_id)
        return False

    prev = (previous_status or "").strip().lower()
    curr = (new_status or "").strip().lower()

    if prev and curr and prev == curr:
        logger.info(
            "[Notification] Idempotent skip: %s #%s status unchanged (%s -> %s)",
            entity_type, reference_id, prev, curr
        )
        return False

    rep_order_num = replacement_order_number or kwargs.get("replacement_order_number")
    comp_name = company.name if company else "Rides AI Store"

    # Check per-company NotificationTemplate & toggles
    event_type = _resolve_event_type(entity_type, curr)
    tpl_result = None
    if event_type and company:
        tpl_ctx = {
            "company_name": comp_name,
            "customer_name": kwargs.get("customer_name") or "Valued Customer",
            "order_id": str(reference_id),
            "total_amount": kwargs.get("total_amount") or "",
            "status": _format_status_label(curr),
            "appointment_time": kwargs.get("appointment_time") or "",
            "rider_name": kwargs.get("rider_name") or "",
        }
        tpl_result = render_notification_template(company, event_type, tpl_ctx)
        if not tpl_result["is_enabled"]:
            logger.info("[Notification] Event '%s' disabled for company '%s'; skipping.", event_type, comp_name)
            return False

        # Optional email dispatch if enabled and customer_email provided
        customer_email = (kwargs.get("customer_email") or "").strip()
        if tpl_result["email_enabled"] and customer_email:
            try:
                from django.conf import settings as django_settings
                from django.core.mail import send_mail
                send_mail(
                    subject=tpl_result["subject"],
                    message=tpl_result["body"],
                    from_email=getattr(django_settings, "DEFAULT_FROM_EMAIL", "noreply@example.com"),
                    recipient_list=[customer_email],
                    fail_silently=True,
                )
            except Exception:
                pass

        if not tpl_result["whatsapp_enabled"]:
            logger.info("[Notification] WhatsApp channel disabled for event '%s' on company '%s'; skipping WA.", event_type, comp_name)
            return False

    if tpl_result and tpl_result["is_customized"]:
        message_text = tpl_result["body"]
    else:
        message_text = build_status_message(
            company_name=comp_name,
            entity_type=entity_type,
            reference_id=str(reference_id),
            new_status=curr,
            reason=reason,
            replacement_order_number=rep_order_num,
        )

    clean_phone = normalize_pakistan_phone(target_phone)
    if not clean_phone:
        logger.warning(
            "[Notification] Could not normalize customer phone '%s' for %s #%s; skipping.",
            target_phone, entity_type, reference_id
        )
        return False

    logger.info(
        "[Notification] Preparing status notification for %s #%s (%s -> %s) to %s (raw: %s)",
        entity_type, reference_id, prev or "initial", curr, clean_phone, target_phone
    )

    try:
        # Route 1: Evolution API QR-connected instance
        instance_name = getattr(company, "whatsapp_instance_name", None)
        if instance_name:
            logger.info(
                "[Notification] Attempting Evolution API dispatch via instance '%s' to '%s'",
                instance_name, clean_phone
            )
            print(f"[WhatsApp Status Notification] Sending {entity_type} #{reference_id} status '{curr}' to {clean_phone} via instance '{instance_name}'")
            res = evolution_client.send_text_message(
                instance_name=instance_name,
                phone=clean_phone,
                to=clean_phone,
                text=message_text,
            )
            if isinstance(res, dict) and (res.get("error") or res.get("success") is False):
                logger.error(
                    "[Notification ERROR] Evolution API failed for %s #%s to %s (instance '%s'): %s. "
                    "Verify WhatsApp session is connected or reconnect QR.",
                    entity_type, reference_id, clean_phone, instance_name, res
                )
                return False

            logger.info(
                "[Notification] Evolution API result for %s #%s to %s (instance '%s'): %s",
                entity_type, reference_id, clean_phone, instance_name, res
            )
            print(f"[Evolution API Response] Instance '{instance_name}' -> {clean_phone}: {res}")
            return True

        # Route 2: Meta Cloud API fallback
        meta_service = WhatsAppService()
        if meta_service.is_configured:
            logger.info(
                "[Notification] Attempting Meta Cloud API dispatch to '%s'",
                clean_phone
            )
            print(f"[WhatsApp Status Notification] Sending {entity_type} #{reference_id} status '{curr}' to {clean_phone} via Meta Cloud API")
            res = meta_service.send_text_message(to=clean_phone, text=message_text)
            logger.info(
                "[Notification] Sent %s #%s (%s) via Meta Cloud API to %s: %s",
                entity_type, reference_id, curr, clean_phone, res
            )
            print(f"[Meta Cloud API Response] Sent to {clean_phone}: {res}")
            return True

        logger.warning(
            "[Notification] Neither Evolution API (instance: %s) nor Meta Cloud API configured for company '%s' (ID: %s); notification dropped.",
            instance_name, comp_name, getattr(company, "id", None)
        )
        return False

    except Exception as exc:
        logger.exception(
            "[Notification] Failed to send %s status notification for #%s to %s: %s",
            entity_type, reference_id, clean_phone, exc
        )
        return False


def send_order_status_notification(
    order,
    previous_status: Optional[str] = None,
    new_status: Optional[str] = None,
    reason: Optional[str] = None,
) -> bool:
    """
    Convenience wrapper for dispatching an order status notification from an Order model instance.
    """
    if not order:
        return False

    status_to_notify = new_status or order.status
    ref_id = getattr(order, "order_number", None) or str(order.id)
    cust_phone = getattr(order, "customer_phone", None)
    company = getattr(order, "company", None)

    rider_obj = getattr(order, "assigned_rider", None)
    rider_name = ""
    if rider_obj:
        rider_name = (rider_obj.get_full_name() or rider_obj.username or "").strip()
    total_val = getattr(order, "total", None)
    total_str = f"Rs. {float(total_val):.2f}" if total_val is not None else ""

    return send_status_notification(
        company=company,
        customer_phone=cust_phone,
        entity_type="order",
        reference_id=ref_id,
        new_status=status_to_notify,
        reason=reason,
        previous_status=previous_status,
        customer_name=getattr(order, "customer_name", None),
        customer_email=getattr(order, "customer_email", None),
        total_amount=total_str,
        rider_name=rider_name,
    )
