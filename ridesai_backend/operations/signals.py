"""
Signals for Operations App.
Handles non-blocking zero-click auto-printing of receipts (KOT and Customer Invoice)
upon order creation and confirmation.
"""

import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Order
from .printing.printer_service import trigger_auto_print_for_order
from .services.dispatch_service import assign_best_rider

logger = logging.getLogger("operations.signals")


@receiver(pre_save, sender=Order)
def order_pre_save_track_status(sender, instance, **kwargs):
    """Caches previous order status before saving to detect status transitions."""
    if kwargs.get("raw"):
        return
    if instance.pk:
        try:
            old = Order.objects.get(pk=instance.pk)
            instance._previous_status = old.status
        except Order.DoesNotExist:
            instance._previous_status = None
    else:
        instance._previous_status = None


@receiver(post_save, sender=Order)
def order_auto_assign_rider_on_save(sender, instance, created, **kwargs):
    """
    Auto-assigns the best available delivery rider when an order status
    transitions to 'prepared' (or 'ready') if not already assigned.
    """
    if kwargs.get("raw"):
        return
    prev_status = getattr(instance, "_previous_status", None)
    is_prepared_status = instance.status in (Order.STATUS_PREPARED, Order.STATUS_READY)

    # Trigger when transitioning from preparing to prepared, or when marked prepared without a rider
    if is_prepared_status and not instance.assigned_rider:
        if prev_status == Order.STATUS_PREPARING or not prev_status or not instance.assigned_rider:
            try:
                assign_best_rider(instance)
            except Exception as exc:
                logger.error(
                    f"[Auto-Assign Signal Error] Failed to auto-assign rider for Order #{instance.order_number}: {exc}",
                    exc_info=True,
                )


@receiver(post_save, sender=Order)
def order_auto_print_on_save(sender, instance, created, **kwargs):
    """
    Non-blocking auto-print hook on Order save.
    Fires ONLY when:
    1. created is True (new order placed by AI agent or dashboard), OR
    2. Order status is 'confirmed' and zero prior print logs exist for this order
       (prevents duplicate prints on subsequent status updates).
    """
    if kwargs.get("raw"):
        return
    company = getattr(instance, "company", None)
    if not company:
        return

    # Check if either auto-print setting is enabled for this company
    auto_kot = getattr(company, "auto_print_kot", False)
    auto_invoice = getattr(company, "auto_print_invoice", False)
    if not (auto_kot or auto_invoice):
        return

    should_print = False
    if created:
        should_print = True
    elif instance.status == "confirmed" and not instance.print_logs.exists():
        should_print = True

    if should_print:
        try:
            trigger_auto_print_for_order(instance)
        except Exception as exc:
            logger.error(
                f"[Auto-Print Signal Error] Failed to trigger auto-print for Order #{instance.order_number}: {exc}",
                exc_info=True,
            )
