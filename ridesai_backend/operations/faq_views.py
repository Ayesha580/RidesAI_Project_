"""
Automated AI FAQ Suggestions & Approved Knowledge Base APIs.
Strictly multi-tenant isolated by `company=request.user.company`.
"""

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from companies.models import BusinessKnowledge
from operations.models import SuggestedFAQ


def _serialize_suggestion(s: SuggestedFAQ) -> dict:
    return {
        "id": s.id,
        "question": s.question,
        "suggested_answer": s.suggested_answer,
        "source_channel": s.source_channel,
        "source_channel_label": s.get_source_channel_display(),
        "occurrence_count": s.occurrence_count,
        "status": s.status,
        "approved_knowledge_id": s.approved_knowledge_id,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


def _serialize_faq(k: BusinessKnowledge) -> dict:
    return {
        "id": k.id,
        "entry_type": k.entry_type,
        "question": k.title,
        "title": k.title,
        "answer": k.content,
        "content": k.content,
        "is_approved": k.is_approved,
        "is_active": k.is_active,
        "source": k.source,
        "created_at": k.created_at.isoformat() if k.created_at else None,
        "updated_at": k.updated_at.isoformat() if k.updated_at else None,
    }


class SuggestedFAQListAPIView(APIView):
    """GET /api/operations/faqs/suggestions/?status=pending|approved|dismissed"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        qs = SuggestedFAQ.objects.filter(company=company).order_by("-occurrence_count", "-updated_at")
        status_filter = (request.query_params.get("status") or "").strip().lower()
        if status_filter in (SuggestedFAQ.STATUS_PENDING, SuggestedFAQ.STATUS_APPROVED, SuggestedFAQ.STATUS_DISMISSED):
            qs = qs.filter(status=status_filter)

        pending_count = SuggestedFAQ.objects.filter(company=company, status=SuggestedFAQ.STATUS_PENDING).count()
        return Response({
            "pending_count": pending_count,
            "suggestions": [_serialize_suggestion(s) for s in qs[:100]],
        }, status=200)


class SuggestedFAQApproveAPIView(APIView):
    """POST /api/operations/faqs/suggestions/<pk>/approve/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)
        if request.user.role != User.ROLE_OWNER and not request.user.is_superuser:
            return Response({"detail": "Only the business owner can approve suggested FAQs."}, status=403)

        suggestion = get_object_or_404(SuggestedFAQ, pk=pk, company=company)
        question = str(request.data.get("question") or suggestion.question).strip()[:200]
        answer = str(request.data.get("answer") or suggestion.suggested_answer).strip()

        if not question or not answer:
            return Response({"detail": "Both 'question' and 'answer' are required to approve and teach the AI."}, status=400)

        with transaction.atomic():
            kb_entry = BusinessKnowledge.objects.filter(
                company=company, title__iexact=question
            ).first()
            if kb_entry:
                kb_entry.content = answer
                kb_entry.is_approved = True
                kb_entry.is_active = True
                kb_entry.save(update_fields=["content", "is_approved", "is_active", "updated_at"])
            else:
                kb_entry = BusinessKnowledge.objects.create(
                    company=company,
                    entry_type="faq",
                    title=question,
                    content=answer,
                    is_approved=True,
                    is_active=True,
                    source="suggested",
                )

            suggestion.question = question
            suggestion.suggested_answer = answer
            suggestion.status = SuggestedFAQ.STATUS_APPROVED
            suggestion.approved_knowledge = kb_entry
            suggestion.save(update_fields=["question", "suggested_answer", "status", "approved_knowledge", "updated_at"])

        return Response({
            "suggestion": _serialize_suggestion(suggestion),
            "faq": _serialize_faq(kb_entry),
        }, status=200)


class SuggestedFAQDismissAPIView(APIView):
    """POST /api/operations/faqs/suggestions/<pk>/dismiss/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)
        if request.user.role != User.ROLE_OWNER and not request.user.is_superuser:
            return Response({"detail": "Only the business owner can dismiss suggested FAQs."}, status=403)

        suggestion = get_object_or_404(SuggestedFAQ, pk=pk, company=company)
        suggestion.status = SuggestedFAQ.STATUS_DISMISSED
        suggestion.save(update_fields=["status", "updated_at"])
        return Response(_serialize_suggestion(suggestion), status=200)


class ApprovedFAQListCreateAPIView(APIView):
    """GET / POST /api/operations/faqs/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        qs = BusinessKnowledge.objects.filter(company=company, is_active=True).order_by("-updated_at")
        return Response([_serialize_faq(k) for k in qs[:100]], status=200)

    def post(self, request):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)
        if request.user.role != User.ROLE_OWNER and not request.user.is_superuser:
            return Response({"detail": "Only the business owner can add FAQs."}, status=403)

        question = str(request.data.get("question") or request.data.get("title") or "").strip()[:200]
        answer = str(request.data.get("answer") or request.data.get("content") or "").strip()
        entry_type = str(request.data.get("entry_type") or "faq").strip()
        if not question or not answer:
            return Response({"detail": "Both 'question' and 'answer' are required."}, status=400)

        kb = BusinessKnowledge.objects.create(
            company=company,
            entry_type=entry_type if entry_type in dict(BusinessKnowledge.TYPES) else "faq",
            title=question,
            content=answer,
            is_approved=True,
            is_active=True,
            source="business",
        )
        return Response(_serialize_faq(kb), status=201)


class ApprovedFAQDetailAPIView(APIView):
    """PATCH / DELETE /api/operations/faqs/<pk>/"""
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)
        if request.user.role != User.ROLE_OWNER and not request.user.is_superuser:
            return Response({"detail": "Only the business owner can edit FAQs."}, status=403)

        kb = get_object_or_404(BusinessKnowledge, pk=pk, company=company)
        if "question" in request.data or "title" in request.data:
            new_q = str(request.data.get("question") or request.data.get("title") or "").strip()[:200]
            if new_q:
                kb.title = new_q
        if "answer" in request.data or "content" in request.data:
            new_a = str(request.data.get("answer") or request.data.get("content") or "").strip()
            if new_a:
                kb.content = new_a
        if "is_active" in request.data:
            kb.is_active = bool(request.data["is_active"])
        kb.save()
        return Response(_serialize_faq(kb), status=200)

    def delete(self, request, pk):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)
        if request.user.role != User.ROLE_OWNER and not request.user.is_superuser:
            return Response({"detail": "Only the business owner can delete FAQs."}, status=403)

        kb = get_object_or_404(BusinessKnowledge, pk=pk, company=company)
        kb.delete()
        return Response(status=204)
