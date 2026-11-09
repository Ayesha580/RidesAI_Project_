from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.models import User
from companies.models import Company
from .models import ManualPayment
from .services import approve_company, approve_manual_payment, consume_company_message, get_access_state


@override_settings(RIDESAI_SINGLE_CLIENT_MODE=True, DEFAULT_CLIENT_MESSAGE_LIMIT=5, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class SingleClientBillingServiceTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Billing Test Company", email="billing@example.com")
        self.owner = User.objects.create_user(
            username="billingowner", email="billing@example.com", password="StrongPass123!",
            company=self.company, role=User.ROLE_OWNER, email_verified=True,
        )

    def test_approval_starts_30_day_access_and_message_period(self):
        approve_company(self.company)
        self.company.refresh_from_db()
        self.assertTrue(self.company.is_approved)
        self.assertEqual(self.company.status, Company.STATUS_ACTIVE)
        self.assertAlmostEqual(
            (self.company.access_expires_at - timezone.now()).total_seconds(),
            30 * 24 * 60 * 60, delta=10,
        )
        self.assertEqual(self.company.message_limit, 5)
        self.assertEqual(self.company.messages_used, 0)

    def test_grace_period_then_suspension(self):
        self.company.is_approved = True
        self.company.access_expires_at = timezone.now() - timedelta(days=1)
        self.company.save()
        self.assertEqual(get_access_state(self.company), "ok")
        self.company.refresh_from_db()
        self.assertEqual(self.company.payment_status, Company.PAYMENT_PAST_DUE)

        self.company.access_expires_at = timezone.now() - timedelta(days=4)
        self.company.payment_failed_at = self.company.access_expires_at
        self.company.grace_ends_at = self.company.access_expires_at + timedelta(days=3)
        self.company.payment_status = Company.PAYMENT_PAST_DUE
        self.company.save()
        self.assertEqual(get_access_state(self.company), "suspended")

    def test_message_quota_is_consumed_and_limit_rejected(self):
        self.company.message_limit = 2
        self.company.messages_used = 0
        self.company.message_period_started_at = timezone.now()
        self.company.save()
        consume_company_message(self.company)
        consume_company_message(self.company)
        with self.assertRaises(ValidationError):
            consume_company_message(self.company)
        self.company.refresh_from_db()
        self.assertEqual(self.company.messages_used, 2)

    def test_manual_payment_approval_renews_access_and_resets_usage(self):
        self.company.messages_used = 4
        self.company.message_period_started_at = timezone.now() - timedelta(days=31)
        self.company.access_expires_at = timezone.now() - timedelta(days=5)
        self.company.payment_status = Company.PAYMENT_SUSPENDED
        self.company.save()
        payment = ManualPayment.objects.create(
            company=self.company, submitted_by=self.owner,
            amount=Decimal("100.00"), currency="USD", payment_reference="TEST-REF-001",
        )
        approve_manual_payment(payment, reviewer=self.owner)
        self.company.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(payment.status, "approved")
        self.assertEqual(self.company.payment_status, Company.PAYMENT_OK)
        self.assertEqual(self.company.messages_used, 0)
        self.assertGreater(self.company.access_expires_at, timezone.now())
