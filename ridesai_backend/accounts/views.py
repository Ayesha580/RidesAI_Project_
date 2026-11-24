import hashlib
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from billing.services import approve_company, get_access_state
from companies.models import Company

from .models import EmailVerificationToken, User, seed_default_roles
from .modules import BUSINESS_TYPES, business_key, owner_nav_for
from .serializers import MeSerializer, RegisterSerializer, UserListSerializer

logger = logging.getLogger(__name__)

REDIRECT_MAP = {
    User.ROLE_OWNER: "/owner/dashboard",
    User.ROLE_STAFF: "/staff/dashboard",
    User.ROLE_MANAGER: "/manager/dashboard",
    User.ROLE_KITCHEN: "/kitchen/dashboard",
    User.ROLE_RIDER: "/rider/dashboard",
    User.ROLE_EMPLOYEE: "/staff/dashboard",
}
EMAIL_VERIFICATION_REDIRECT = "/login"
SELECT_PLAN_REDIRECT = "/select-plan"
SUSPENDED_REDIRECT = "/billing"
STAFF_SUSPENDED_REDIRECT = "/account-suspended"


def _field_error(field, message):
    return Response({field: message}, status=status.HTTP_400_BAD_REQUEST)


def _role_name(user):
    return user.staff_role.name if user.staff_role else user.get_role_display()


def _role_label(user):
    return "Employee" if user.role == User.ROLE_STAFF else user.get_role_display()


def _resolve_redirect(user):
    if user.is_superuser or user.role == User.ROLE_SUPERADMIN:
        return "disabled", "/login"
    if not user.company:
        return "disabled", "/login"

    state = get_access_state(user.company)

    if state == "email_verification_required":
        return state, EMAIL_VERIFICATION_REDIRECT
    if state == "payment_required":
        if user.role == User.ROLE_OWNER:
            return state, SELECT_PLAN_REDIRECT
        return state, STAFF_SUSPENDED_REDIRECT
    if state == "suspended":
        if user.role == User.ROLE_OWNER:
            return state, SUSPENDED_REDIRECT
        return state, STAFF_SUSPENDED_REDIRECT
    if getattr(user, "is_kitchen", False):
        return state, "/kitchen/dashboard"
    if getattr(user, "is_rider", False):
        return state, "/rider/dashboard"
    if user.staff_role and "packer" in user.staff_role.name.lower():
        return state, "/staff/fulfillment"
    if user.role in (User.ROLE_STAFF, User.ROLE_EMPLOYEE):
        mods = user.get_modules()
        if "fulfillment" in mods:
            return state, "/staff/fulfillment"
        return state, "/staff/dashboard"
    return state, REDIRECT_MAP.get(user.role, "/dashboard")


def _business_info(user):
    if not user.company:
        return {"owner_nav": [], "business_label": ""}
    c = user.company
    bt = c.business_type
    return {
        "owner_nav": owner_nav_for(bt),
        "business_label": BUSINESS_TYPES[business_key(bt)]["label"],
        "business_type": bt,
        "subscription_status": c.subscription_status,
        "trial_ends_at": c.trial_ends_at,
        "is_manual_override": c.is_manual_override,
        "manual_override_expires_at": c.manual_override_expires_at,
        "stripe_customer_id": c.stripe_customer_id,
        "stripe_subscription_id": c.stripe_subscription_id,
        "grace_period_ends_at": c.grace_period_ends_at,
    }


def _generate_otp():
    return f"{secrets.randbelow(1_000_000):06d}"


def _hash_otp(otp):
    return hashlib.sha256(otp.encode("utf-8")).hexdigest()


class RegisterAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        business_name = d["business_name"].strip()
        username = d["username"].strip()
        email = d["email"].strip()
        cnic = d["cnic"].strip()

        if Company.objects.filter(name__iexact=business_name).exists():
            return _field_error("business_name", "Company name already exists.")
        if User.objects.filter(username__iexact=username).exists():
            return _field_error("username", "Username already exists.")
        if User.objects.filter(email__iexact=email).exists():
            return _field_error("email", "Email already exists.")
        if User.objects.filter(cnic=cnic).exists():
            return _field_error("cnic", "CNIC already exists.")

        plan = None
        plan_id = d.get("plan_id")
        if plan_id:
            from companies.models import Plan

            plan = Plan.objects.filter(pk=plan_id, is_active=True).first()
            if not plan:
                return _field_error("plan_id", "Please select a valid, active subscription plan.")
            if not plan.polar_product_id:
                return _field_error("plan_id", "This plan is not configured for online checkout yet. Please contact support.")

        try:
            with transaction.atomic():
                from billing.services import is_billing_exempt_email
                is_exempt = is_billing_exempt_email(email)
                now = timezone.now()
                company = Company.objects.create(
                    name=business_name,
                    business_type=d.get("business_type", ""),
                    address=d.get("business_address", ""),
                    is_registered=d.get("is_registered", False),
                    registration_number=d.get("registration_number", ""),
                    cnic=cnic,
                    email=email,
                    phone=d["phone"],
                    plan=plan,
                    message_limit=getattr(settings, "DEFAULT_CLIENT_MESSAGE_LIMIT", getattr(settings, "DEFAULT_MESSAGE_LIMIT", 1000)),
                    business_registration_document=d.get("business_registration_document"),
                    cnic_front=d["cnic_front"],
                    cnic_back=d["cnic_back"],
                    passport_size_photo=d["passport_size_photo"],
                    status=Company.STATUS_ACTIVE if is_exempt else Company.STATUS_PENDING,
                    is_approved=True if is_exempt else False,
                    approved_at=now if is_exempt else None,
                    subscription_status="trial" if is_exempt else Company.SUBSCRIPTION_TRIAL,
                    trial_ends_at=now + timedelta(days=30) if is_exempt else None,
                    is_manual_override=False,
                )

                user = User(
                    company=company,
                    role=User.ROLE_OWNER,
                    first_name=d["first_name"],
                    username=username,
                    email=email,
                    phone=d["phone"],
                    cnic=cnic,
                    email_verified=False,
                )
                user.set_password(d["password"])
                user.save()
                seed_default_roles(company)
        except IntegrityError as e:
            return Response(
                {"error": "Some information already exists.", "details": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        otp = _generate_otp()
        verification_token = EmailVerificationToken.objects.create(
            user=user,
            token_hash=_hash_otp(otp),
            expires_at=timezone.now() + timedelta(minutes=5),
        )
        try:
            send_mail(
                subject="Verify Your RidesAI Business Account",
                message=(
                    f"Hello {user.first_name},\n\nThank you for registering {company.name} with RidesAI.\n\n"
                    f"Your six-digit email verification code is: {otp}\n\nThis code expires in 5 minutes. Please do not share it.\n"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )
        except Exception:
            logger.exception("Failed to send verification email for user %s", user.pk)
            verification_token.used_at = timezone.now()
            verification_token.save(update_fields=["used_at"])
            return Response(
                {
                    "message": "Your account was created, but we could not send the verification email. Please use resend verification after email delivery is configured.",
                    "email": user.email,
                    "verification_required": True,
                    "verification_email_sent": False,
                },
                status=status.HTTP_201_CREATED,
            )

        return Response(
            {
                "message": "Registration received. Enter the six-digit code sent to your email to verify your address.",
                "email": user.email,
                "verification_required": True,
                "verification_email_sent": True,
            },
            status=status.HTTP_201_CREATED,
        )


class VerifyEmailAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        raw_token = str(request.data.get("token") or request.data.get("otp") or "").strip()
        if not raw_token:
            return Response({"error": "Six-digit verification code is required."}, status=400)

        email = str(request.data.get("email") or "").strip()
        now = timezone.now()
        verification_query = EmailVerificationToken.objects.select_related("user").filter(
            token_hash=_hash_otp(raw_token),
            used_at__isnull=True,
            expires_at__gt=now,
            attempts__lt=5,
        )
        if request.data.get("otp"):
            verification_query = verification_query.filter(user__email__iexact=email)
        verification = verification_query.first()

        if not verification and request.data.get("otp"):
            candidate = EmailVerificationToken.objects.filter(
                user__email__iexact=email,
                used_at__isnull=True,
                expires_at__gt=now,
                attempts__lt=5,
            ).first()
            if candidate:
                candidate.attempts += 1
                candidate.save(update_fields=["attempts"])

        if not verification:
            return Response(
                {"error": "This verification code is invalid, expired, or already used. Please request a new one."},
                status=400,
            )

        with transaction.atomic():
            verification.used_at = timezone.now()
            verification.save(update_fields=["used_at"])

            user = verification.user
            user.email_verified = True
            user.save(update_fields=["email_verified"])

            company = user.company
            if company:
                from billing.services import is_billing_exempt_email
                is_exempt = is_billing_exempt_email(user.email) or is_billing_exempt_email(company.email)
                if is_exempt:
                    now = timezone.now()
                    company.is_approved = True
                    company.approved_at = now
                    company.status = Company.STATUS_ACTIVE
                    company.subscription_status = "trial"
                    company.trial_ends_at = now + timedelta(days=30)
                    company.payment_status = Company.PAYMENT_OK
                    company.is_manual_override = False
                    company.save(update_fields=["is_approved", "approved_at", "status", "subscription_status", "trial_ends_at", "payment_status", "is_manual_override"])
                elif not company.is_approved:
                    approve_company(company, start_trial=False, notify=False)

            EmailVerificationToken.objects.filter(
                user=user,
                used_at__isnull=True,
            ).exclude(pk=verification.pk).update(used_at=timezone.now())

        if user.company:
            user.company.refresh_from_db()

        access_state, redirect = _resolve_redirect(user)
        refresh = RefreshToken.for_user(user)

        return Response({
            "message": (
                "Email verified successfully. Your business access has been activated."
                if access_state == "ok"
                else "Email verified successfully. Please choose a plan to continue."
            ),
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "email": user.email,
            "company_id": user.company_id,
            "access_state": access_state,
            "redirect": redirect,
        })


class ResendVerificationEmailAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        email = str(request.data.get("email") or "").strip().lower()
        generic = {"message": "If this email belongs to an unverified account, a new six-digit code has been sent."}
        user = User.objects.filter(email__iexact=email, is_active=True, email_verified=False).first()
        if not user:
            return Response(generic)

        latest = EmailVerificationToken.objects.filter(
            user=user, used_at__isnull=True
        ).order_by("-created_at").first()
        if latest and latest.created_at > timezone.now() - timedelta(seconds=60):
            return Response(
                {"message": "Please wait 60 seconds between verification code requests."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        otp = _generate_otp()
        EmailVerificationToken.objects.filter(user=user, used_at__isnull=True).update(used_at=timezone.now())
        verification_token = EmailVerificationToken.objects.create(
            user=user,
            token_hash=_hash_otp(otp),
            expires_at=timezone.now() + timedelta(minutes=5),
        )
        try:
            send_mail(
                "Verify Your RidesAI Business Account",
                f"Hello {user.first_name},\n\nYour RidesAI six-digit verification code is {otp}.\nIt expires in 5 minutes. Do not share it.",
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
        except Exception:
            logger.exception("Failed to resend verification email for user %s", user.pk)
            verification_token.used_at = timezone.now()
            verification_token.save(update_fields=["used_at"])
            return Response(
                {
                    "message": "We could not deliver the verification email. Please check the SMTP configuration and try again.",
                    "verification_email_sent": False,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({
            "message": "A new verification email has been sent.",
            "verification_email_sent": True,
        })


class LoginAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        login_identifier = str(request.data.get("username") or request.data.get("email") or "").strip()
        password = str(request.data.get("password") or "")

        if not login_identifier or not password:
            return Response(
                {"error": "Please provide both username/email and password."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Support login cleanly by either email, username, or full name (case-insensitive)
        matched_user = (
            User.objects.filter(email__iexact=login_identifier).first()
            or User.objects.filter(username__iexact=login_identifier).first()
            or User.objects.filter(email__istartswith=login_identifier + "@").first()
        )
        if not matched_user:
            # Check if login_identifier matches first_name (e.g. "mashail munir") or split first + last
            matched_user = User.objects.filter(first_name__iexact=login_identifier).first()
            if not matched_user:
                parts = login_identifier.split()
                if len(parts) == 2:
                    matched_user = User.objects.filter(first_name__iexact=parts[0], last_name__iexact=parts[1]).first()
                elif len(parts) == 1:
                    matched_user = User.objects.filter(first_name__iexact=parts[0]).first()

        if not matched_user:
            return Response(
                {"error": "No account found with this username or email."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not matched_user.is_active:
            return Response(
                {"error": "This account has been deactivated. Please contact support."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Check password cleanly with specific error
        if not matched_user.check_password(password):
            return Response(
                {"error": "Invalid password. Please check your credentials or reset your password."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(
            request,
            username=matched_user.username,
            password=password,
        )

        if not user:
            user = matched_user

        if user.is_superuser or user.role == User.ROLE_SUPERADMIN:
            return Response({"error": "Platform-admin access is not part of the RidesAI business application."}, status=403)

        if not user.email_verified:
            return Response(
                {
                    "error": "Please verify your email address before logging in.",
                    "verification_required": True,
                    "email": user.email,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Ensure company is active/approved if user has a company
        if user.company:
            if not user.company.is_approved:
                if user.company.is_manual_override or user.company.subscription_status == "active":
                    user.company.is_approved = True
                    user.company.save(update_fields=["is_approved"])
                else:
                    return Response(
                        {"error": "Your company registration is pending approval by Rides Technologies admin."},
                        status=status.HTTP_403_FORBIDDEN,
                    )

        access_state, redirect = _resolve_redirect(user)
        refresh = RefreshToken.for_user(user)

        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "redirect": redirect,
            "access_state": access_state,
            "user": {
                "id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "role_name": _role_name(user),
                "modules": user.get_modules(),
                "permissions": user.get_permissions(),
                "company_name": user.company.name if user.company else "",
                "plan": user.company.plan.name if user.company and user.company.plan else None,
                **_business_info(user),
            },
        })


class ForgotPasswordAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        email = str(request.data.get("email") or "").strip().lower()
        if not email:
            return Response(
                {"error": "Please provide your email address."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Case-insensitive lookup by email or username
        user = (
            User.objects.filter(email__iexact=email, is_active=True).first()
            or User.objects.filter(username__iexact=email, is_active=True).first()
        )

        generic_response = {
            "message": "If an account exists with this email, a password reset link has been sent.",
            "success": True,
        }

        if not user:
            return Response(generic_response, status=status.HTTP_200_OK)

        # Generate secure uid and time-limited reset token
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        frontend_base = getattr(settings, "SITE_URL", "http://localhost:5173").rstrip("/")
        reset_url = f"{frontend_base}/reset-password/{uid}/{token}"

        subject = "Reset Your RidesAI Password"
        recipient_name = user.first_name or user.username
        message = (
            f"Hello {recipient_name},\n\n"
            f"We received a request to reset the password for your RidesAI business account.\n"
            f"Please click the link below to set a new password:\n\n"
            f"{reset_url}\n\n"
            f"This link is valid for 1 hour. If you did not request a password reset, you can safely ignore this email.\n\n"
            f"— The Rides Technologies Team"
        )

        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
            logger.info("Password reset email sent to %s", user.email)
        except Exception as exc:
            logger.warning("Failed to send password reset email to %s: %s", user.email, exc)
            if getattr(settings, "DEBUG", False):
                logger.info("[DEBUG] Password reset link for %s: %s", user.email, reset_url)

        resp_data = dict(generic_response)
        if getattr(settings, "DEBUG", False):
            resp_data["debug_reset_url"] = reset_url
            resp_data["debug_uid"] = uid
            resp_data["debug_token"] = token

        return Response(resp_data, status=status.HTTP_200_OK)


class ResetPasswordAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        uid = str(request.data.get("uid") or "").strip()
        token = str(request.data.get("token") or "").strip()
        new_password = str(request.data.get("new_password") or "").strip()

        if not uid or not token or not new_password:
            return Response(
                {"error": "uid, token, and new_password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(new_password) < 8:
            return Response(
                {"error": "Password must be at least 8 characters long."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user_pk = force_str(urlsafe_base64_decode(uid))
            user = User.objects.filter(pk=user_pk, is_active=True).first()
        except Exception:
            user = None

        if not user or not default_token_generator.check_token(user, token):
            return Response(
                {"error": "Invalid or expired password reset link. Please request a new one."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        if hasattr(user, "must_change_password"):
            user.must_change_password = False
        user.save()

        logger.info("Password successfully reset for user %s (%s)", user.id, user.email)

        return Response(
            {
                "message": "Your password has been successfully reset. You can now sign in with your new password.",
                "success": True,
            },
            status=status.HTTP_200_OK,
        )


class MeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = MeSerializer(request.user).data
        access_state, redirect = _resolve_redirect(request.user)
        data["access_state"] = access_state
        data["redirect"] = redirect
        data["role_name"] = _role_name(request.user)
        data["role_label"] = _role_label(request.user)
        data["must_change_password"] = request.user.must_change_password
        data["is_superuser"] = bool(request.user.is_superuser)
        data["modules"] = request.user.get_modules()
        data["permissions"] = request.user.get_permissions()
        data.update(_business_info(request.user))
        data["company_name"] = request.user.company.name if request.user.company else ""
        return Response(data)


class UserListAPIView(APIView):
    def get(self, request):
        users = User.objects.filter(
            company=request.user.company, is_active=True
        ).exclude(id=request.user.id)
        return Response(UserListSerializer(users, many=True).data)


class PublicBusinessesAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        companies = (
            Company.objects.filter(is_approved=True)
            .exclude(status=Company.STATUS_REJECTED)
            .order_by("-approved_at")[:24]
        )
        return Response([
            {
                "id": c.id,
                "name": c.name,
                "business_type": c.business_type,
                "address": c.address,
            }
            for c in companies
        ])