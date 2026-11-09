from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from companies.models import Company

GRACE_DAYS = settings.BILLING_GRACE_DAYS
TRIAL_DAYS = settings.TRIAL_DAYS

ACTIVE_STATUSES = ("active", "trialing")
PAST_DUE_STATUSES = ("past_due", "unpaid")
ENDED_STATUSES = ("canceled", "cancelled", "revoked", "incomplete_expired", "ended")

UPDATE_FIELDS = [
    "payment_status",
    "payment_failed_at",
    "grace_ends_at",
    "subscription_ends_at",
]


def _parse_aware_datetime(value):
    if not value:
        return None

    parsed = value if hasattr(value, "tzinfo") else parse_datetime(str(value))
    if not parsed:
        return None

    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed

def is_billing_exempt(company):
    exempt = {e.lower() for e in getattr(settings, "BILLING_EXEMPT_EMAILS", [])}
    return bool(company and company.email and company.email.strip().lower() in exempt)

def _clear_grace(company):
    company.payment_status = Company.PAYMENT_OK
    company.payment_failed_at = None
    company.grace_ends_at = None


def sync_company_from_subscription(company, sub):
    now = timezone.now()
    sub_id = sub.get("id")
    if (
        sub_id
        and company.polar_subscription_id
        and str(sub_id) != str(company.polar_subscription_id)
    ):
        return company

    status = str(sub.get("status") or "").lower()
    end_at = _parse_aware_datetime(
        sub.get("ends_at") or sub.get("ended_at") or sub.get("current_period_end")
    )
    cancel_at_period_end = bool(sub.get("cancel_at_period_end", False))

    if status in ACTIVE_STATUSES:
        if cancel_at_period_end and end_at and end_at > now:
            company.subscription_ends_at = end_at
        else:
            company.subscription_ends_at = None
        _clear_grace(company)

    elif status in PAST_DUE_STATUSES:
        if not company.payment_failed_at or not company.grace_ends_at:
            company.payment_failed_at = now
            company.grace_ends_at = now + timedelta(days=GRACE_DAYS)

        company.payment_status = (
            Company.PAYMENT_SUSPENDED
            if now >= company.grace_ends_at
            else Company.PAYMENT_PAST_DUE
        )

    elif status in ENDED_STATUSES:
        actual_end = (
            _parse_aware_datetime(sub.get("ends_at") or sub.get("ended_at"))
            or company.subscription_ends_at
            or now
        )

        if actual_end > now:
            company.subscription_ends_at = actual_end
            _clear_grace(company)
        else:
            already_tracked = (
                company.subscription_ends_at == actual_end
                and company.grace_ends_at is not None
            )
            if not already_tracked:
                company.payment_failed_at = actual_end
                company.grace_ends_at = actual_end + timedelta(days=GRACE_DAYS)

            company.subscription_ends_at = actual_end
            company.payment_status = (
                Company.PAYMENT_SUSPENDED
                if now >= company.grace_ends_at
                else Company.PAYMENT_PAST_DUE
            )

    company.save(update_fields=UPDATE_FIELDS)
    return company


def refresh_grace_state(company):
    now = timezone.now()

    # One-client manual billing: one month of initial access, then a 3-day grace period.
    if getattr(settings, "RIDESAI_SINGLE_CLIENT_MODE", False):
        expiry = company.access_expires_at or company.trial_ends_at
        if expiry and now >= expiry and company.payment_status != Company.PAYMENT_SUSPENDED:
            if not company.payment_failed_at:
                company.payment_failed_at = expiry
                company.grace_ends_at = expiry + timedelta(days=GRACE_DAYS)
            company.payment_status = (
                Company.PAYMENT_SUSPENDED if now >= company.grace_ends_at
                else Company.PAYMENT_PAST_DUE
            )
            company.save(update_fields=["payment_status", "payment_failed_at", "grace_ends_at"])
        elif company.payment_status == Company.PAYMENT_PAST_DUE and company.grace_ends_at and now >= company.grace_ends_at:
            company.payment_status = Company.PAYMENT_SUSPENDED
            company.save(update_fields=["payment_status"])
        return company
    if (
        not company.polar_subscription_id
        and company.trial_ends_at
        and now >= company.trial_ends_at
        and company.payment_status != Company.PAYMENT_SUSPENDED
    ):
        company.payment_status = Company.PAYMENT_SUSPENDED
        company.save(update_fields=["payment_status"])
        return company
    if (
        company.payment_status == Company.PAYMENT_PAST_DUE
        and company.grace_ends_at
        and now >= company.grace_ends_at
    ):
        company.payment_status = Company.PAYMENT_SUSPENDED
        company.save(update_fields=["payment_status"])

    return company

def approve_company(company, start_trial=True, notify=True):
    now = timezone.now()

    company.is_approved = True
    company.approved_at = now
    company.status = Company.STATUS_ACTIVE
    company.payment_status = Company.PAYMENT_OK
    fields = ["is_approved", "approved_at", "status", "payment_status"]

    if getattr(settings, "RIDESAI_SINGLE_CLIENT_MODE", False):
        if not company.initial_access_started_at:
            company.initial_access_started_at = now
            company.access_expires_at = now + timedelta(days=TRIAL_DAYS)
            company.renewal_due_at = company.access_expires_at
            company.message_limit = getattr(settings, "DEFAULT_CLIENT_MESSAGE_LIMIT", 1000)
            company.message_period_started_at = now
            fields.extend(["initial_access_started_at", "access_expires_at", "renewal_due_at", "message_limit", "message_period_started_at"])
    elif start_trial and not company.polar_subscription_id and not company.trial_ends_at:
        company.trial_ends_at = now + timedelta(days=TRIAL_DAYS)
        fields.append("trial_ends_at")

    company.save(update_fields=fields)

    if notify and company.email:
        send_mail(
            subject=f"Your business '{company.name}' has been approved.",
            message=f"Your business '{company.name}' has been approved. You can now login to your dashboard.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[company.email],
            fail_silently=True,
        )

    return company
def get_access_state(company):
    if not company.is_approved:
        return "pending_approval"

    if is_billing_exempt(company):
        return "ok"

    refresh_grace_state(company)

    if company.payment_status == Company.PAYMENT_SUSPENDED:
        return "suspended"

    if (
        not getattr(settings, "RIDESAI_SINGLE_CLIENT_MODE", False)
        and not company.polar_subscription_id
        and not company.trial_ends_at
    ):
        return "payment_required"   
    return "ok"

def approve_manual_payment(payment, reviewer=None):
    """Approve a manual payment and grant the next 30-day access period."""
    from django.db import transaction
    now = timezone.now()
    company = payment.company
    with transaction.atomic():
        payment.status = "approved"
        payment.reviewed_by = reviewer
        payment.reviewed_at = now
        payment.save(update_fields=["status", "reviewed_by", "reviewed_at"])
        company.payment_status = Company.PAYMENT_OK
        company.payment_failed_at = None
        company.grace_ends_at = None
        company.access_expires_at = now + timedelta(days=30)
        company.renewal_due_at = company.access_expires_at
        company.messages_used = 0
        company.message_period_started_at = now
        company.save(update_fields=["payment_status", "payment_failed_at", "grace_ends_at", "access_expires_at", "renewal_due_at", "messages_used", "message_period_started_at"])
    return company


def refresh_message_period(company):
    """Keep the displayed monthly message balance current even before the next agent call."""
    now = timezone.now()
    if not company.message_period_started_at or (now - company.message_period_started_at).days >= 30:
        company.messages_used = 0
        company.message_period_started_at = now
        company.save(update_fields=["messages_used", "message_period_started_at"])
    return company


def consume_company_message(company, count=1):
    """Atomically consume message quota; call this before processing each AI message."""
    from django.db import transaction
    from django.db.models import F
    from rest_framework.exceptions import ValidationError
    now = timezone.now()
    with transaction.atomic():
        company = Company.objects.select_for_update().get(pk=company.pk)
        start = company.message_period_started_at
        if not start or (now - start).days >= 30:
            company.messages_used = 0
            company.message_period_started_at = now
            company.save(update_fields=["messages_used", "message_period_started_at"])
        if company.messages_used + count > company.message_limit:
            raise ValidationError({"code": "message_limit_reached", "detail": "Your monthly message limit has been reached. Please contact support."})
        Company.objects.filter(pk=company.pk).update(messages_used=F("messages_used") + count)
        company.refresh_from_db(fields=["messages_used", "message_limit", "message_period_started_at"])
    return company
