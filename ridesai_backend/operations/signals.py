"""
Signals for Operations App.
Handles non-blocking zero-click auto-printing of receipts (KOT and Customer Invoice)
upon order creation and confirmation.
"""

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Order
from .printing.printer_service import trigger_auto_print_for_order

logger = logging.getLogger("operations.signals")


@receiver(post_save, sender=Order)
def order_auto_print_on_save(sender, instance, created, **kwargs):
    """
    Non-blocking auto-print hook on Order save.
    Fires ONLY when:
    1. created is True (new order placed by AI agent or dashboard), OR
    2. Order status is 'confirmed' and zero prior print logs exist for this order
       (prevents duplicate prints on subsequent status updates).
    """
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
