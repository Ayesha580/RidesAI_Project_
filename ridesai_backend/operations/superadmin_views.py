"""
Platform Owner / Super Admin Dashboard APIs (PRD §2.1 & §10).
Strictly protected by `IsAuthenticated` + `IsSuperAdminUser` (`request.user.is_superuser`).
Regular business owners and staff receive 403 Forbidden.
"""

from collections import defaultdict
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.modules import BUSINESS_TYPES, business_key
from companies.models import Company
from operations.models import (
    AgentConversation,
    Appointment,
    LabTestBooking,
    Order,
    PlatformAuditLog,
)


class IsSuperAdminUser(BasePermission):
    message = "Super Admin privileges (is_superuser) are required to access platform endpoints."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)


def _company_is_active(company: Company) -> bool:
    return company.status == Company.STATUS_ACTIVE and company.payment_status != Company.PAYMENT_SUSPENDED


class SuperAdminOverviewAPIView(APIView):
    """GET /api/superadmin/overview/"""
    permission_classes = [IsAuthenticated, IsSuperAdminUser]

    def get(self, request):
        companies = list(Company.objects.all())
        total_businesses = len(companies)
        active_businesses = sum(1 for c in companies if _company_is_active(c))
        suspended_businesses = total_businesses - active_businesses

        vertical_counts = defaultdict(int)
        total_messages_used = 0
        total_message_limit = 0
        for c in companies:
            vkey = business_key(c.business_type)
            vertical_counts[vkey] += 1
            total_messages_used += int(c.messages_used or 0)
            total_message_limit += int(c.message_limit or 0)

        vertical_breakdown = [
            {
                "key": vkey,
                "label": BUSINESS_TYPES.get(vkey, {}).get("label", vkey.title()),
                "count": vertical_counts.get(vkey, 0),
            }
            for vkey in ["restaurant", "pharmacy", "clinic", "hospital", "retail", "grocery", "general"]
            if vertical_counts.get(vkey, 0) > 0 or vkey in ("restaurant", "pharmacy", "clinic", "hospital", "retail", "grocery")
        ]

        total_users = User.objects.exclude(is_superuser=True).count()
        total_owners = User.objects.filter(role=User.ROLE_OWNER).count()
        total_staff = User.objects.filter(role__in=[User.ROLE_STAFF, User.ROLE_EMPLOYEE]).count()

        total_orders = Order.objects.count()
        total_appointments = Appointment.objects.count()
        total_lab_bookings = LabTestBooking.objects.count()
        total_ai_conversations = AgentConversation.objects.count()

        orders_gmv = (
            Order.objects.exclude(status__in=["cancelled", "rejected"])
            .aggregate(total=Sum("total"))
            .get("total")
            or Decimal("0.00")
        )
        labs_gmv = (
            LabTestBooking.objects.exclude(status=LabTestBooking.STATUS_CANCELLED)
            .aggregate(total=Sum("price"))
            .get("total")
            or Decimal("0.00")
        )
        platform_gmv = round(float(orders_gmv + labs_gmv), 2)

        top_tenants = [
            {
                "id": c.id,
                "name": c.name,
                "vertical": BUSINESS_TYPES.get(business_key(c.business_type), {}).get("label", c.business_type or "General"),
                "messages_used": int(c.messages_used or 0),
                "message_limit": int(c.message_limit or 0),
                "is_active": _company_is_active(c),
            }
            for c in sorted(companies, key=lambda x: int(x.messages_used or 0), reverse=True)[:5]
        ]

        return Response({
            "kpis": {
                "total_businesses": total_businesses,
                "active_businesses": active_businesses,
                "suspended_businesses": suspended_businesses,
                "total_users": total_users,
                "total_owners": total_owners,
                "total_staff": total_staff,
                "total_orders": total_orders,
                "total_appointments": total_appointments,
                "total_lab_bookings": total_lab_bookings,
                "total_bookings_and_orders": total_orders + total_appointments + total_lab_bookings,
                "total_ai_conversations": total_ai_conversations,
                "platform_gmv_rs": platform_gmv,
                "total_voice_messages_used": total_messages_used,
                "total_voice_message_limit": total_message_limit,
            },
            "vertical_breakdown": vertical_breakdown,
            "top_tenants": top_tenants,
        }, status=200)


class SuperAdminCompaniesAPIView(APIView):
    """GET /api/superadmin/companies/?search=...&vertical=...&status=active|suspended"""
    permission_classes = [IsAuthenticated, IsSuperAdminUser]

    def get(self, request):
        search = (request.query_params.get("search") or "").strip()
        vertical = (request.query_params.get("vertical") or "").strip().lower()
        status_filter = (request.query_params.get("status") or "").strip().lower()

        qs = Company.objects.annotate(
            orders_count=Count("orders", distinct=True),
            conversations_count=Count("agent_conversations", distinct=True),
        ).order_by("-created_at")

        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(email__icontains=search)
                | Q(phone__icontains=search)
                | Q(business_type__icontains=search)
            )

        # Map owner emails in bulk
        owner_emails = {}
        for u in User.objects.filter(role=User.ROLE_OWNER, company__isnull=False).only("company_id", "email"):
            owner_emails.setdefault(u.company_id, u.email)

        rows = []
        for c in qs:
            vkey = business_key(c.business_type)
            is_act = _company_is_active(c)
            if vertical and vertical != "all" and vkey != vertical:
                continue
            if status_filter == "active" and not is_act:
                continue
            if status_filter == "suspended" and is_act:
                continue

            rows.append({
                "id": c.id,
                "name": c.name,
                "owner_email": owner_emails.get(c.id) or c.email or "",
                "business_type": c.business_type or "general",
                "vertical_key": vkey,
                "vertical_label": BUSINESS_TYPES.get(vkey, {}).get("label", vkey.title()),
                "is_active": is_act,
                "status": c.status,
                "payment_status": c.payment_status,
                "orders_count": int(getattr(c, "orders_count", 0) or 0),
                "conversations_count": int(getattr(c, "conversations_count", 0) or 0),
                "messages_used": int(c.messages_used or 0),
                "message_limit": int(c.message_limit or 0),
                "created_at": c.created_at.isoformat() if c.created_at else None,
            })

        return Response(rows, status=200)


class SuperAdminCompanyStatusAPIView(APIView):
    """PATCH /api/superadmin/companies/<int:pk>/status/"""
    permission_classes = [IsAuthenticated, IsSuperAdminUser]

    def patch(self, request, pk):
        company = get_object_or_404(Company, pk=pk)
        if "is_active" not in request.data:
            return Response({"is_active": "Boolean field 'is_active' is required."}, status=400)

        target_active = bool(request.data["is_active"])
        reason = str(request.data.get("reason") or "").strip()[:300]
        prev_active = _company_is_active(company)

        if target_active:
            company.status = Company.STATUS_ACTIVE
            company.is_approved = True
            company.payment_status = Company.PAYMENT_OK
            company.subscription_status = Company.SUBSCRIPTION_ACTIVE
            action = "company_activated"
        else:
            company.payment_status = Company.PAYMENT_SUSPENDED
            company.subscription_status = Company.SUBSCRIPTION_PAST_DUE
            action = "company_suspended"

        company.save(update_fields=["status", "is_approved", "payment_status", "subscription_status"])

        log = PlatformAuditLog.objects.create(
            actor=request.user,
            actor_email=request.user.email or request.user.username,
            action=action,
            target_company=company,
            target_company_name=company.name,
            details={
                "previous_active": prev_active,
                "new_active": target_active,
                "reason": reason,
            },
        )

        return Response({
            "id": company.id,
            "name": company.name,
            "is_active": _company_is_active(company),
            "status": company.status,
            "payment_status": company.payment_status,
            "audit_log_id": log.id,
        }, status=200)


class SuperAdminAuditLogsAPIView(APIView):
    """GET /api/superadmin/audit-logs/"""
    permission_classes = [IsAuthenticated, IsSuperAdminUser]

    def get(self, request):
        logs = PlatformAuditLog.objects.select_related("target_company", "actor").order_by("-created_at")[:100]
        return Response([
            {
                "id": entry.id,
                "action": entry.action,
                "actor_email": entry.actor_email,
                "target_company_id": entry.target_company_id,
                "target_company_name": entry.target_company_name or (entry.target_company.name if entry.target_company else ""),
                "details": entry.details or {},
                "created_at": entry.created_at.isoformat() if entry.created_at else None,
            }
            for entry in logs
        ], status=200)
