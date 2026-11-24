"""
Owner-Editable Notification Templates & Per-Event Toggles API.
Strictly multi-tenant isolated by `company=request.user.company`.
"""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from operations.models import NotificationTemplate
from operations.notifications import (
    AVAILABLE_PLACEHOLDERS,
    DEFAULT_NOTIFICATION_TEMPLATES,
)


def _serialize_template(event_type: str, tpl_obj: NotificationTemplate | None) -> dict:
    meta = DEFAULT_NOTIFICATION_TEMPLATES[event_type]
    return {
        "event_type": event_type,
        "label": meta["label"],
        "description": meta["description"],
        "is_enabled": bool(tpl_obj.is_enabled) if tpl_obj else True,
        "whatsapp_enabled": bool(tpl_obj.whatsapp_enabled) if tpl_obj else True,
        "email_enabled": bool(tpl_obj.email_enabled) if tpl_obj else True,
        "subject_template": (
            tpl_obj.subject_template if (tpl_obj and tpl_obj.subject_template.strip()) else meta["subject_template"]
        ),
        "body_template": (
            tpl_obj.body_template if (tpl_obj and tpl_obj.body_template.strip()) else meta["body_template"]
        ),
        "is_customized": bool(tpl_obj),
        "updated_at": tpl_obj.updated_at.isoformat() if (tpl_obj and tpl_obj.updated_at) else None,
    }


class NotificationTemplateListAPIView(APIView):
    """GET /api/operations/notifications/templates/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        existing = {
            t.event_type: t
            for t in NotificationTemplate.objects.filter(company=company)
        }
        templates = [
            _serialize_template(event_type, existing.get(event_type))
            for event_type in DEFAULT_NOTIFICATION_TEMPLATES.keys()
        ]
        return Response({
            "company_name": company.name,
            "placeholders": AVAILABLE_PLACEHOLDERS,
            "templates": templates,
        }, status=200)


class NotificationTemplateDetailAPIView(APIView):
    """PATCH /api/operations/notifications/templates/<event_type>/"""
    permission_classes = [IsAuthenticated]

    def patch(self, request, event_type):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)
        if request.user.role != User.ROLE_OWNER and not request.user.is_superuser:
            return Response({"detail": "Only the business owner can edit notification templates."}, status=403)

        if event_type not in DEFAULT_NOTIFICATION_TEMPLATES:
            return Response({"event_type": f"Unsupported notification event '{event_type}'."}, status=400)

        meta = DEFAULT_NOTIFICATION_TEMPLATES[event_type]
        tpl, _ = NotificationTemplate.objects.get_or_create(
            company=company,
            event_type=event_type,
            defaults={
                "is_enabled": True,
                "whatsapp_enabled": True,
                "email_enabled": True,
                "subject_template": meta["subject_template"],
                "body_template": meta["body_template"],
            },
        )

        if "is_enabled" in request.data:
            tpl.is_enabled = bool(request.data["is_enabled"])
        if "whatsapp_enabled" in request.data:
            tpl.whatsapp_enabled = bool(request.data["whatsapp_enabled"])
        if "email_enabled" in request.data:
            tpl.email_enabled = bool(request.data["email_enabled"])
        if "subject_template" in request.data:
            tpl.subject_template = str(request.data["subject_template"] or "").strip()[:255]
        if "body_template" in request.data:
            tpl.body_template = str(request.data["body_template"] or "").strip()[:4000]

        tpl.save()
        return Response(_serialize_template(event_type, tpl), status=200)


class NotificationTemplateResetAPIView(APIView):
    """POST /api/operations/notifications/templates/<event_type>/reset/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, event_type):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)
        if request.user.role != User.ROLE_OWNER and not request.user.is_superuser:
            return Response({"detail": "Only the business owner can reset notification templates."}, status=403)

        if event_type not in DEFAULT_NOTIFICATION_TEMPLATES:
            return Response({"event_type": f"Unsupported notification event '{event_type}'."}, status=400)

        NotificationTemplate.objects.filter(company=company, event_type=event_type).delete()
        return Response(_serialize_template(event_type, None), status=200)
