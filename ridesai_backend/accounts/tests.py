import hashlib
from datetime import timedelta
from unittest.mock import patch

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


    def test_login_accepts_email_address_as_identifier(self):
        self.user.email_verified = True
        self.user.save(update_fields=["email_verified"])
        response = self.client.post(
            "/api/accounts/login/",
            {"username": "newclient@example.com", "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)


    @patch("accounts.views.send_mail", side_effect=RuntimeError("SMTP unavailable"))
    def test_failed_resend_reports_delivery_failure_and_allows_retry(self, mocked_send):
        failed = self.client.post(
            "/api/accounts/resend-verification/",
            {"email": "newclient@example.com"},
            format="json",
        )
        self.assertEqual(failed.status_code, 503)
        self.assertFalse(failed.data["verification_email_sent"])

        mocked_send.side_effect = None
        mocked_send.return_value = 1
        retried = self.client.post(
            "/api/accounts/resend-verification/",
            {"email": "newclient@example.com"},
            format="json",
        )
        self.assertEqual(retried.status_code, 200)
        self.assertTrue(retried.data["verification_email_sent"])

    def test_login_case_insensitive_username_email_and_field_support(self):
        self.user.email_verified = True
        self.user.save(update_fields=["email_verified"])

        # 1. Login with uppercase email
        res1 = self.client.post(
            "/api/accounts/login/",
            {"username": "NEWCLIENT@EXAMPLE.COM", "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(res1.status_code, 200)
        self.assertIn("access", res1.data)

        # 2. Login with uppercase username
        res2 = self.client.post(
            "/api/accounts/login/",
            {"username": "NEWCLIENT", "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(res2.status_code, 200)
        self.assertIn("access", res2.data)

        # 3. Login using 'email' field in payload
        res3 = self.client.post(
            "/api/accounts/login/",
            {"email": "newclient@example.com", "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(res3.status_code, 200)
        self.assertIn("access", res3.data)

        # 4. Clear error for wrong password
        res_wrong_pw = self.client.post(
            "/api/accounts/login/",
            {"username": "newclient", "password": "WrongPassword999!"},
            format="json",
        )
        self.assertEqual(res_wrong_pw.status_code, 400)
        self.assertIn("Invalid password", res_wrong_pw.data["error"])

        # 5. Clear error for non-existent account
        res_unknown = self.client.post(
            "/api/accounts/login/",
            {"username": "nonexistent_user_999@example.com", "password": "AnyPassword123!"},
            format="json",
        )
        self.assertEqual(res_unknown.status_code, 400)
        self.assertIn("No account found", res_unknown.data["error"])

    def test_forgot_password_and_reset_password_flow(self):
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes

        self.user.email_verified = True
        self.user.save(update_fields=["email_verified"])

        # 1. Request forgot password with valid email
        mail.outbox = []
        res_forgot = self.client.post(
            "/api/accounts/forgot-password/",
            {"email": "NEWCLIENT@EXAMPLE.COM"},  # Case-insensitive
            format="json",
        )
        self.assertEqual(res_forgot.status_code, 200)
        self.assertTrue(res_forgot.data["success"])
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("reset-password", mail.outbox[0].body)

        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)

        # 2. Reset password with short password fails
        res_short = self.client.post(
            "/api/accounts/reset-password/",
            {"uid": uid, "token": token, "new_password": "short"},
            format="json",
        )
        self.assertEqual(res_short.status_code, 400)
        self.assertIn("at least 8 characters", res_short.data["error"])

        # 3. Reset password with invalid token fails
        res_invalid_token = self.client.post(
            "/api/accounts/reset-password/",
            {"uid": uid, "token": "invalid-token-123", "new_password": "NewBrandPass123!"},
            format="json",
        )
        self.assertEqual(res_invalid_token.status_code, 400)

        # 4. Reset password successfully
        res_reset = self.client.post(
            "/api/accounts/reset-password/",
            {"uid": uid, "token": token, "new_password": "NewBrandPass123!"},
            format="json",
        )
        self.assertEqual(res_reset.status_code, 200)
        self.assertTrue(res_reset.data["success"])

        # 5. Old password no longer works
        res_old_login = self.client.post(
            "/api/accounts/login/",
            {"username": "newclient", "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(res_old_login.status_code, 400)

        # 6. New password works immediately
        res_new_login = self.client.post(
            "/api/accounts/login/",
            {"username": "newclient", "password": "NewBrandPass123!"},
            format="json",
        )
        self.assertEqual(res_new_login.status_code, 200)
        self.assertIn("access", res_new_login.data)
