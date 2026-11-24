"""
Owner Privacy, Data Retention Policy, Consent Ledger & Customer Erasure APIs.
Strictly multi-tenant isolated by `company=request.user.company`.
"""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from operations.models import CustomerConsentLog, DataRetentionPolicy
from operations.privacy_service import erase_customer_pii, run_company_data_purge


def _serialize_policy(policy: DataRetentionPolicy) -> dict:
    return {
        "chat_retention_days": policy.chat_retention_days,
        "order_pii_retention_days": policy.order_pii_retention_days,
        "auto_purge_enabled": policy.auto_purge_enabled,
        "last_purge_at": policy.last_purge_at.isoformat() if policy.last_purge_at else None,
        "updated_at": policy.updated_at.isoformat() if policy.updated_at else None,
    }


def _serialize_consent(c: CustomerConsentLog) -> dict:
    return {
        "id": c.id,
        "customer_identifier": c.customer_identifier,
        "consent_type": c.consent_type,
        "consent_type_label": c.get_consent_type_display(),
        "granted": c.granted,
        "channel": c.channel,
        "channel_label": c.get_channel_display(),
        "recorded_at": c.recorded_at.isoformat() if c.recorded_at else None,
    }


class DataRetentionPolicyAPIView(APIView):
    """GET / PATCH /api/operations/privacy/retention/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)
        policy, _ = DataRetentionPolicy.objects.get_or_create(company=company)
        return Response(_serialize_policy(policy), status=200)

    def patch(self, request):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)
        if request.user.role != User.ROLE_OWNER and not request.user.is_superuser:
            return Response({"detail": "Only the business owner can update retention policies."}, status=403)

        policy, _ = DataRetentionPolicy.objects.get_or_create(company=company)
        if "chat_retention_days" in request.data:
            policy.chat_retention_days = max(1, int(request.data["chat_retention_days"] or 90))
        if "order_pii_retention_days" in request.data:
            policy.order_pii_retention_days = max(1, int(request.data["order_pii_retention_days"] or 365))
        if "auto_purge_enabled" in request.data:
            policy.auto_purge_enabled = bool(request.data["auto_purge_enabled"])
        policy.save()
        return Response(_serialize_policy(policy), status=200)


class DataRetentionRunPurgeAPIView(APIView):
    """POST /api/operations/privacy/retention/run-purge/"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)
        if request.user.role != User.ROLE_OWNER and not request.user.is_superuser:
            return Response({"detail": "Only the business owner can run data purges."}, status=403)

        dry_run = bool(request.data.get("dry_run", False))
        result = run_company_data_purge(company, dry_run=dry_run)
        return Response(result, status=200)


class CustomerConsentListCreateAPIView(APIView):
    """GET / POST /api/operations/privacy/consents/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        qs = CustomerConsentLog.objects.filter(company=company).order_by("-recorded_at")[:100]
        return Response([_serialize_consent(c) for c in qs], status=200)

    def post(self, request):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        ident = str(request.data.get("customer_identifier") or "").strip()[:160]
        consent_type = str(request.data.get("consent_type") or "").strip()
        channel = str(request.data.get("channel") or "dashboard").strip()

        if not ident:
            return Response({"customer_identifier": "Customer phone, email, or ID is required."}, status=400)
        if consent_type not in {c[0] for c in CustomerConsentLog.CONSENT_TYPE_CHOICES}:
            return Response({"consent_type": "Invalid consent_type."}, status=400)
        if channel not in {c[0] for c in CustomerConsentLog.CHANNEL_CHOICES}:
            channel = "dashboard"

        entry = CustomerConsentLog.objects.create(
            company=company,
            customer_identifier=ident,
            consent_type=consent_type,
            granted=bool(request.data.get("granted", True)),
            channel=channel,
        )
        return Response(_serialize_consent(entry), status=201)


class CustomerEraseAPIView(APIView):
    """POST /api/operations/privacy/erase-customer/"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)
        if request.user.role != User.ROLE_OWNER and not request.user.is_superuser:
            return Response({"detail": "Only the business owner can erase customer data."}, status=403)

        identifier = str(request.data.get("customer_phone_or_email") or "").strip()
        if not identifier:
            return Response({"customer_phone_or_email": "Please enter a customer phone number or email."}, status=400)

        summary = erase_customer_pii(company, identifier)
        return Response(summary, status=200)
