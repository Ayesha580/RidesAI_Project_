import hashlib
from datetime import timedelta

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from django.utils.crypto import get_random_string
from rest_framework.test import APIClient

from .models import EmailVerificationToken, User


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="test@ridesai.local",
    SITE_URL="http://localhost:5173",
)
class EmailVerificationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="newclient",
            email="newclient@example.com",
            password="StrongPass123!",
            email_verified=False,
        )

    def make_token(self, expires_at=None):
        raw = get_random_string(64)
        EmailVerificationToken.objects.create(
            user=self.user,
            token_hash=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            expires_at=expires_at or timezone.now() + timedelta(hours=24),
        )
        return raw

    def test_unverified_user_cannot_login(self):
        response = self.client.post(
            "/api/accounts/login/",
            {"username": "newclient", "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(response.data["verification_required"])

    def test_verification_activates_email_and_token_is_single_use(self):
        raw = self.make_token()
        response = self.client.post(
            "/api/accounts/verify-email/", {"token": raw}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.email_verified)
        self.assertIn("access", response.data)

        second_response = self.client.post(
            "/api/accounts/verify-email/", {"token": raw}, format="json"
        )
        self.assertEqual(second_response.status_code, 400)

    def test_expired_verification_token_is_rejected(self):
        raw = self.make_token(expires_at=timezone.now() - timedelta(seconds=1))
        response = self.client.post(
            "/api/accounts/verify-email/", {"token": raw}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertFalse(self.user.email_verified)

    def test_resend_sends_new_link_without_exposing_account_status(self):
        response = self.client.post(
            "/api/accounts/resend-verification/",
            {"email": "newclient@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertRegex(mail.outbox[0].body, r"\b[0-9]{6}\b")

    def test_resend_cooldown_blocks_immediate_repeat(self):
        first = self.client.post(
            "/api/accounts/resend-verification/",
            {"email": "newclient@example.com"},
            format="json",
        )
        self.assertEqual(first.status_code, 200)
        second = self.client.post(
            "/api/accounts/resend-verification/",
            {"email": "newclient@example.com"},
            format="json",
        )
        self.assertEqual(second.status_code, 429)

    def test_otp_verification_requires_email_and_code_is_single_use(self):
        code = "482916"
        EmailVerificationToken.objects.create(
            user=self.user, token_hash=hashlib.sha256(code.encode()).hexdigest(),
            expires_at=timezone.now() + timedelta(minutes=5),
        )
        response = self.client.post(
            "/api/accounts/verify-email/", {"otp": code, "email": self.user.email}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.email_verified)
        reused = self.client.post(
            "/api/accounts/verify-email/", {"otp": code, "email": self.user.email}, format="json"
        )
        self.assertEqual(reused.status_code, 400)

    def test_wrong_otp_increments_attempt_count(self):
        code = "482916"
        token = EmailVerificationToken.objects.create(
            user=self.user, token_hash=hashlib.sha256(code.encode()).hexdigest(),
            expires_at=timezone.now() + timedelta(minutes=5),
        )
        response = self.client.post(
            "/api/accounts/verify-email/", {"otp": "111111", "email": self.user.email}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        token.refresh_from_db()
        self.assertEqual(token.attempts, 1)
