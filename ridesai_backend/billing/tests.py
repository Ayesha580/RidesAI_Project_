from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.models import User
from companies.models import Company
from .services import approve_company, consume_company_message, get_access_state, sync_company_from_subscription


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class MultiBusinessBillingServiceTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Billing Test Company", email="billing@example.com", is_approved=True)
        self.owner = User.objects.create_user(
            username="billingowner", email="billing@example.com", password="StrongPass123!",
            company=self.company, role=User.ROLE_OWNER, email_verified=True,
        )

    def test_email_verification_activation_requires_plan(self):
        approve_company(self.company, start_trial=False, notify=False)
        self.company.refresh_from_db()
        self.assertTrue(self.company.is_approved)
        self.assertEqual(get_access_state(self.company), "payment_required")

    def test_trial_and_three_day_grace_period(self):
        approve_company(self.company, start_trial=True, notify=False)
        self.company.refresh_from_db()
        self.assertEqual(get_access_state(self.company), "ok")
        self.company.trial_ends_at = timezone.now() - timedelta(days=1)
        self.company.save(update_fields=["trial_ends_at"])
        self.assertEqual(get_access_state(self.company), "ok")
        self.company.refresh_from_db()
        self.assertEqual(self.company.payment_status, Company.PAYMENT_PAST_DUE)
        self.company.grace_ends_at = timezone.now() - timedelta(seconds=1)
        self.company.save(update_fields=["grace_ends_at"])
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

    def test_successful_subscription_restores_access(self):
        self.company.polar_subscription_id = "sub_test"
        self.company.payment_status = Company.PAYMENT_SUSPENDED
        self.company.grace_ends_at = timezone.now() - timedelta(days=1)
        self.company.save()
        sync_company_from_subscription(self.company, {"id": "sub_test", "status": "active"})
        self.company.refresh_from_db()
        self.assertEqual(self.company.payment_status, Company.PAYMENT_OK)
        self.assertEqual(get_access_state(self.company), "ok")


@override_settings(DEBUG=True, POLAR_MOCK_MODE=True)
class LocalMockPaymentFlowTests(TestCase):
    def setUp(self):
        from rest_framework.test import APIClient
        from companies.models import Plan
        self.client = APIClient()
        self.plan = Plan.objects.create(
            name="Test Standard", billing_cycle="monthly", price="19.00",
            currency="USD", is_active=True, polar_product_id="",
        )
        self.company = Company.objects.create(
            name="Mock Billing Company", email="mock@example.com",
            is_approved=True, plan=self.plan,
        )
        self.owner = User.objects.create_user(
            username="mockowner", email="mock@example.com", password="StrongPass123!",
            company=self.company, role=User.ROLE_OWNER, email_verified=True,
        )
        self.client.force_authenticate(self.owner)

    def test_mock_mode_lists_plans_without_polar_product_ids(self):
        public_plans = self.client.get("/api/billing/plans/")
        self.assertEqual(public_plans.status_code, 200)
        self.assertTrue(any(row["id"] == self.plan.id for row in public_plans.data))
        selected = self.client.post(
            "/api/billing/select-plan/", {"plan_id": self.plan.id}, format="json"
        )
        self.assertEqual(selected.status_code, 200)

    def test_mock_checkout_activates_subscription_without_provider_call(self):
        started = self.client.post("/api/billing/customer-session/", {}, format="json")
        self.assertEqual(started.status_code, 200)
        self.assertTrue(started.data["mock"])
        checkout_id = started.data["checkout_id"]

        completed = self.client.post(
            "/api/billing/complete-renewal/",
            {"checkout_id": checkout_id},
            format="json",
        )
        self.assertEqual(completed.status_code, 200)
        self.assertTrue(completed.data["mock"])
        self.company.refresh_from_db()
        self.assertTrue(self.company.polar_subscription_id.startswith("mock_sub_"))
        self.assertEqual(get_access_state(self.company), "ok")
        self.assertTrue(self.company.payment_transactions.filter(status="paid_test").exists())

        repeated = self.client.post(
            "/api/billing/complete-renewal/",
            {"checkout_id": checkout_id},
            format="json",
        )
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(self.company.payment_transactions.filter(status="paid_test").count(), 1)

    def test_mock_subscription_cancel_and_resume(self):
        started = self.client.post("/api/billing/customer-session/", {}, format="json")
        checkout_id = started.data["checkout_id"]
        self.client.post("/api/billing/complete-renewal/", {"checkout_id": checkout_id}, format="json")

        canceled = self.client.post("/api/billing/cancel/", {}, format="json")
        self.assertEqual(canceled.status_code, 200)
        self.assertTrue(canceled.data["mock"])
        overview = self.client.get("/api/billing/overview/")
        self.assertEqual(overview.data["status"], "canceling")

        resumed = self.client.post("/api/billing/resume/", {}, format="json")
        self.assertEqual(resumed.status_code, 200)
        self.assertTrue(resumed.data["mock"])
        overview = self.client.get("/api/billing/overview/")
        self.assertEqual(overview.data["status"], "active")
