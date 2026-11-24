"""
Multi-Tenant Data Retention Purge & Right-to-Erasure Service (PRD §12).
Every operation is strictly scoped to a single `Company` and preserves
financial order totals so revenue analytics remain intact.
"""

from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from operations.models import (
    AgentConversation,
    AgentMessage,
    Appointment,
    Customer,
    CustomerConsentLog,
    DataRetentionPolicy,
    LabTestBooking,
    Order,
    Patient,
)


def run_company_data_purge(company, dry_run: bool = False) -> dict:
    """
    Purges expired AgentMessage rows older than `chat_retention_days` and
    anonymizes customer PII on completed/cancelled Orders older than
    `order_pii_retention_days` while preserving financial totals.
    """
    policy, _ = DataRetentionPolicy.objects.get_or_create(company=company)
    now = timezone.now()
    chat_cutoff = now - timedelta(days=int(policy.chat_retention_days or 90))
    order_cutoff = now - timedelta(days=int(policy.order_pii_retention_days or 365))

    expired_msgs_qs = AgentMessage.objects.filter(
        conversation__company=company,
        created_at__lt=chat_cutoff,
    )
    expired_orders_qs = Order.objects.filter(
        company=company,
        status__in=[Order.STATUS_DELIVERED, Order.STATUS_CANCELLED, "completed", "rejected"],
        created_at__lt=order_cutoff,
    ).exclude(customer_name="Anonymized", customer_phone="", delivery_address="")

    purged_messages = expired_msgs_qs.count()
    anonymized_orders = expired_orders_qs.count()

    if not dry_run:
        with transaction.atomic():
            if purged_messages > 0:
                expired_msgs_qs.delete()
            if anonymized_orders > 0:
                expired_orders_qs.update(
                    customer_name="Anonymized",
                    customer_phone="",
                    customer_email="",
                    delivery_address="",
                    delivery_lat=None,
                    delivery_lng=None,
                )
            policy.last_purge_at = now
            policy.save(update_fields=["last_purge_at", "updated_at"])

    return {
        "company_id": company.id,
        "company_name": company.name,
        "dry_run": dry_run,
        "purged_messages": purged_messages,
        "anonymized_orders": anonymized_orders,
        "last_purge_at": policy.last_purge_at.isoformat() if policy.last_purge_at else None,
    }


def erase_customer_pii(company, identifier: str) -> dict:
    """
    Right-to-Erasure workflow: anonymizes a customer's PII across all tables
    strictly within `company` while preserving financial order totals.
    """
    clean_id = str(identifier or "").strip()
    if not clean_id:
        raise ValueError("Customer phone or email is required.")

    with transaction.atomic():
        orders_qs = Order.objects.filter(company=company).filter(
            Q(customer_phone__iexact=clean_id) | Q(customer_email__iexact=clean_id)
        )
        orders_count = orders_qs.update(
            customer_name="Anonymized",
            customer_phone="",
            customer_email="",
            delivery_address="",
            delivery_lat=None,
            delivery_lng=None,
        )

        appts_qs = Appointment.objects.filter(company=company, patient_phone__iexact=clean_id)
        appts_count = appts_qs.update(patient_name="Anonymized", patient_phone="")

        labs_qs = LabTestBooking.objects.filter(company=company, patient_phone__iexact=clean_id)
        labs_count = labs_qs.update(patient_name="Anonymized", patient_phone="")

        convs_qs = AgentConversation.objects.filter(company=company).filter(
            Q(customer_phone__iexact=clean_id) | Q(customer_email__iexact=clean_id)
        )
        msgs_count = AgentMessage.objects.filter(conversation__in=convs_qs).delete()[0]
        convs_count = convs_qs.update(
            customer_name="Anonymized",
            customer_phone="",
            customer_email="",
        )

        patients_count = Patient.objects.filter(company=company, phone__iexact=clean_id).update(
            name="Anonymized",
            notes="",
        )
        customers_count = Customer.objects.filter(company=company, phone__iexact=clean_id).update(
            name="Anonymized",
        )
        consents_count = CustomerConsentLog.objects.filter(
            company=company,
            customer_identifier__iexact=clean_id,
        ).update(customer_identifier="Anonymized")

    return {
        "company_id": company.id,
        "anonymized_orders": orders_count,
        "anonymized_appointments": appts_count,
        "anonymized_lab_bookings": labs_count,
        "anonymized_conversations": convs_count,
        "purged_messages": msgs_count,
        "anonymized_patients": patients_count,
        "anonymized_customers": customers_count,
        "anonymized_consents": consents_count,
    }
