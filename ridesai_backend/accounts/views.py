import hashlib
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from billing.services import approve_company, get_access_state, is_billing_exempt
from companies.models import Company

from .models import EmailVerificationToken, User, seed_default_roles
from .modules import BUSINESS_TYPES, business_key, owner_nav_for
from .serializers import MeSerializer, RegisterSerializer, UserListSerializer

logger = logging.getLogger(__name__)

REDIRECT_MAP = {
    User.ROLE_OWNER: "/owner/dashboard",
    User.ROLE_STAFF: "/staff/dashboard",
    User.ROLE_SUPERADMIN: "/admin/dashboard",
    User.ROLE_MANAGER: "/manager/dashboard",
    User.ROLE_KITCHEN: "/kitchen/dashboard",
    User.ROLE_EMPLOYEE: "/employee/dashboard",
}
PENDING_APPROVAL_REDIRECT = "/pending-approval"
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
    if user.is_superuser or user.role == User.ROLE_SUPERADMIN or not user.company:
        return "ok", REDIRECT_MAP.get(user.role, "/dashboard")

    state = get_access_state(user.company)

    if state == "pending_approval":
        return state, PENDING_APPROVAL_REDIRECT
    if state == "payment_required":
        if user.role == User.ROLE_OWNER:
            return state, SELECT_PLAN_REDIRECT
        return state, STAFF_SUSPENDED_REDIRECT
    if state == "suspended":
        if user.role == User.ROLE_OWNER:
            return state, SUSPENDED_REDIRECT
        return state, STAFF_SUSPENDED_REDIRECT
    return state, REDIRECT_MAP.get(user.role, "/dashboard")


def _business_info(user):
    if not user.company:
        return {"owner_nav": [], "business_label": ""}
    bt = user.company.business_type
    return {
        "owner_nav": owner_nav_for(bt),
        "business_label": BUSINESS_TYPES[business_key(bt)]["label"],
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
        if plan_id and not getattr(settings, "RIDESAI_SINGLE_CLIENT_MODE", False):
            from companies.models import Plan

            plan = Plan.objects.filter(pk=plan_id, is_active=True).first()
            if not plan:
                return _field_error("plan_id", "Please select a valid, active subscription plan.")
            if not plan.polar_product_id:
                return _field_error("plan_id", "This plan is not configured for online checkout yet. Please contact support.")

        try:
            with transaction.atomic():
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
                    message_limit=getattr(settings, "DEFAULT_CLIENT_MESSAGE_LIMIT", 1000),
                    business_registration_document=d.get("business_registration_document"),
                    cnic_front=d["cnic_front"],
                    cnic_back=d["cnic_back"],
                    passport_size_photo=d["passport_size_photo"],
                    status=Company.STATUS_PENDING,
                    is_approved=False,
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
        EmailVerificationToken.objects.create(
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
            if company and not company.is_approved:
                approve_company(company, start_trial=False, notify=is_billing_exempt(company))

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

        latest = EmailVerificationToken.objects.filter(user=user).order_by("-created_at").first()
        if latest and latest.created_at > timezone.now() - timedelta(seconds=60):
            return Response(
                {"message": "Please wait 60 seconds between verification code requests."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        otp = _generate_otp()
        EmailVerificationToken.objects.filter(user=user, used_at__isnull=True).update(used_at=timezone.now())
        EmailVerificationToken.objects.create(
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
        return Response(generic)


class LoginAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        user = authenticate(
            request,
            username=request.data.get("username"),
            password=request.data.get("password"),
        )

        if not user:
            return Response(
                {"error": "Invalid username or password."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not user.is_active:
            return Response(
                {"error": "This account has been deactivated."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not user.email_verified:
            return Response(
                {
                    "error": "Please verify your email address before logging in.",
                    "verification_required": True,
                    "email": user.email,
                },
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
                "company_name": user.company.name if user.company else "",
                "plan": user.company.plan.name if user.company and user.company.plan else None,
                **_business_info(user),
            },
        })


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
        data["modules"] = request.user.get_modules()
        data.update(_business_info(request.user))
        data["company_name"] = request.user.company.name if request.user.company else ""
        return Response(data)


class UserListAPIView(APIView):
    def get(self, request):
        users = User.objects.filter(
            company=request.user.company, is_active=True
        ).exclude(id=request.user.id)
        return Response(UserListSerializer(users, many=True).data)


class AdminLoginAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        user = authenticate(
            username=request.data.get("username"),
            password=request.data.get("password"),
        )

        if user is None:
            return Response({"detail": "Invalid username or password."}, status=401)
        if not user.is_superuser:
            return Response({"detail": "Only admin can login here."}, status=403)
        if not user.is_active:
            return Response({"detail": "Admin account is inactive."}, status=403)

        refresh = RefreshToken.for_user(user)
        return Response({
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "username": user.username,
            "is_superuser": True,
            "role_name": _role_name(user),
            "role_label": _role_label(user),
            "must_change_password": user.must_change_password,
        })


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