from datetime import timedelta
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.utils import timezone
from billing.models import BillingReminder
from companies.models import Company
from billing.services import refresh_grace_state


class Command(BaseCommand):
    help = "Send once-daily subscription grace-period reminders (run daily via scheduler)."

    def handle(self, *args, **options):
        now = timezone.now()
        companies = Company.objects.exclude(email="")
        sent = 0
        for company in companies:
            refresh_grace_state(company)
            company.refresh_from_db(fields=["payment_status", "grace_ends_at"])
            if company.payment_status != Company.PAYMENT_PAST_DUE or not company.grace_ends_at:
                continue
            remaining = max(0, int((company.grace_ends_at - now).total_seconds() // 86400))
            if remaining > 3:
                continue
            reminder, created = BillingReminder.objects.get_or_create(
                company=company, period_end=company.grace_ends_at, days_remaining=remaining)
            if not created:
                continue
            subject = "RidesAI subscription payment reminder"
            if remaining == 0:
                body = (f"Your RidesAI subscription grace period has ended or is ending now. "
                        f"Renew your subscription to restore dashboard access.")
            else:
                body = (f"Your RidesAI subscription payment is overdue. You have approximately "
                        f"{remaining} day(s) remaining in your grace period. Renew before "
                        f"{company.grace_ends_at:%Y-%m-%d %H:%M} to avoid dashboard suspension.")
            try:
                send_mail(subject, body, None, [company.email], fail_silently=False)
                sent += 1
            except Exception:
                reminder.delete()
                self.stderr.write(f"Could not send reminder for company {company.pk}")
        self.stdout.write(self.style.SUCCESS(f"Sent {sent} billing reminder(s)."))
