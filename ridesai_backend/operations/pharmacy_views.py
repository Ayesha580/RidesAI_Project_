"""
Pharmacy Platform API Views: MedicineBatches & Prescriptions.

Strictly multi-tenant isolated to request.user.company.
Protected by IsAuthenticated.
"""

import logging
from datetime import date, timedelta
from typing import Optional

from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from companies.models import CatalogItem
from operations.models import MedicineBatch, Prescription
from operations.notifications import send_status_notification

logger = logging.getLogger("operations.pharmacy")


def _get_request_company(request):
    if getattr(request, "user", None) and request.user.is_authenticated:
        return getattr(request.user, "company", None)
    return None


ALLOWED_PRESCRIPTION_TRANSITIONS = {
    Prescription.STATUS_PENDING: {Prescription.STATUS_APPROVED, Prescription.STATUS_REJECTED},
    Prescription.STATUS_APPROVED: {Prescription.STATUS_DISPENSED},
    Prescription.STATUS_REJECTED: set(),
    Prescription.STATUS_DISPENSED: set(),
}


def _serialize_batch(batch: MedicineBatch) -> dict:
    return {
        "id": batch.id,
        "item_id": batch.item_id,
        "item_name": batch.item.name,
        "generic_name": getattr(batch.item, "generic_name", "") or "",
        "item_price": str(batch.item.price),
        "requires_prescription": getattr(batch.item, "requires_prescription", False),
        "batch_number": batch.batch_number,
        "expiry_date": batch.expiry_date.isoformat(),
        "quantity": batch.quantity,
        "supplier_name": batch.supplier_name,
        "status": batch.status,
        "created_at": batch.created_at.isoformat(),
        "updated_at": batch.updated_at.isoformat(),
    }


def _serialize_prescription(rx: Prescription) -> dict:
    return {
        "id": rx.id,
        "prescription_number": rx.prescription_number,
        "customer_name": rx.customer_name or "Valued Customer",
        "customer_phone": rx.customer_phone,
        "requested_items_text": rx.requested_items_text,
        "prescription_image_url": rx.prescription_image_url,
        "notes": rx.notes,
        "status": rx.status,
        "status_display": rx.get_status_display(),
        "pharmacist_notes": rx.pharmacist_notes,
        "reviewed_by_name": rx.reviewed_by.get_full_name() or rx.reviewed_by.username if rx.reviewed_by else None,
        "linked_order_id": rx.linked_order_id,
        "linked_order_number": rx.linked_order.order_number if rx.linked_order else None,
        "created_at": rx.created_at.isoformat(),
        "formatted_date": rx.created_at.strftime("%b %d, %Y %I:%M %p"),
        "updated_at": rx.updated_at.isoformat(),
    }


# ============================================================================
# Medicine Batches API
# ============================================================================

class PharmacyBatchesAPIView(APIView):
    """
    GET /api/pharmacy/batches/
    POST /api/pharmacy/batches/
    Tenant-scoped list & creation for medicine batches with expiry tracking.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = _get_request_company(request)
        if not company:
            return Response({"detail": "User has no associated company."}, status=status.HTTP_403_FORBIDDEN)

        qs = MedicineBatch.objects.filter(company=company).select_related("item")

        today = date.today()
        expiring_threshold = today + timedelta(days=30)

        # Tenant-wide summary statistics
        total_batches = qs.count()
        expired_count = qs.filter(expiry_date__lt=today).count()
        expiring_soon_count = qs.filter(expiry_date__gte=today, expiry_date__lte=expiring_threshold).count()
        low_stock_count = qs.filter(quantity__lte=10).count()

        # Query filters
        status_filter = request.GET.get("status", "").strip().lower()
        if status_filter == "expired":
            qs = qs.filter(expiry_date__lt=today)
        elif status_filter == "expiring_soon":
            qs = qs.filter(expiry_date__gte=today, expiry_date__lte=expiring_threshold)
        elif status_filter == "safe":
            qs = qs.filter(expiry_date__gt=expiring_threshold)

        search = request.GET.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(batch_number__icontains=search)
                | Q(item__name__icontains=search)
                | Q(item__generic_name__icontains=search)
                | Q(supplier_name__icontains=search)
            )

        results = [_serialize_batch(b) for b in qs]

        return Response({
            "summary": {
                "total_batches": total_batches,
                "expiring_soon_count": expiring_soon_count,
                "expired_count": expired_count,
                "low_stock_count": low_stock_count,
            },
            "count": len(results),
            "results": results,
        })

    def post(self, request):
        company = _get_request_company(request)
        if not company:
            return Response({"detail": "User has no associated company."}, status=status.HTTP_403_FORBIDDEN)

        item_id = request.data.get("item_id")
        batch_number = str(request.data.get("batch_number", "")).strip()
        expiry_date = request.data.get("expiry_date")
        quantity = request.data.get("quantity", 0)
        supplier_name = str(request.data.get("supplier_name", "")).strip()

        if not item_id:
            return Response({"error": "item_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not batch_number:
            return Response({"error": "batch_number is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not expiry_date:
            return Response({"error": "expiry_date is required."}, status=status.HTTP_400_BAD_REQUEST)

        item = get_object_or_404(CatalogItem, pk=item_id, company=company)

        try:
            qty = int(quantity)
            if qty < 0:
                return Response({"error": "quantity must be non-negative."}, status=status.HTTP_400_BAD_REQUEST)
        except (ValueError, TypeError):
            return Response({"error": "Invalid quantity value."}, status=status.HTTP_400_BAD_REQUEST)

        batch, created = MedicineBatch.objects.update_or_create(
            company=company,
            item=item,
            batch_number=batch_number,
            defaults={
                "expiry_date": expiry_date,
                "quantity": qty,
                "supplier_name": supplier_name,
            },
        )

        return Response(_serialize_batch(batch), status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class PharmacyBatchDetailAPIView(APIView):
    """
    PATCH /api/pharmacy/batches/<int:batch_id>/
    DELETE /api/pharmacy/batches/<int:batch_id>/
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, batch_id):
        company = _get_request_company(request)
        if not company:
            return Response({"detail": "User has no associated company."}, status=status.HTTP_403_FORBIDDEN)

        batch = get_object_or_404(MedicineBatch, pk=batch_id, company=company)

        if "quantity" in request.data:
            try:
                qty = int(request.data["quantity"])
                if qty < 0:
                    return Response({"error": "quantity must be non-negative."}, status=status.HTTP_400_BAD_REQUEST)
                batch.quantity = qty
            except (ValueError, TypeError):
                return Response({"error": "Invalid quantity."}, status=status.HTTP_400_BAD_REQUEST)

        if "expiry_date" in request.data:
            batch.expiry_date = request.data["expiry_date"]
        if "supplier_name" in request.data:
            batch.supplier_name = str(request.data["supplier_name"]).strip()
        if "batch_number" in request.data:
            batch.batch_number = str(request.data["batch_number"]).strip()

        batch.save()
        return Response(_serialize_batch(batch))

    def delete(self, request, batch_id):
        company = _get_request_company(request)
        if not company:
            return Response({"detail": "User has no associated company."}, status=status.HTTP_403_FORBIDDEN)

        batch = get_object_or_404(MedicineBatch, pk=batch_id, company=company)
        batch.delete()
        return Response({"success": True, "id": batch_id}, status=status.HTTP_200_OK)


# ============================================================================
# Prescriptions API
# ============================================================================

class PharmacyPrescriptionsAPIView(APIView):
    """
    GET /api/pharmacy/prescriptions/
    POST /api/pharmacy/prescriptions/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = _get_request_company(request)
        if not company:
            return Response({"detail": "User has no associated company."}, status=status.HTTP_403_FORBIDDEN)

        qs = Prescription.objects.filter(company=company).select_related("reviewed_by", "linked_order")

        # Summary counts
        pending_count = qs.filter(status=Prescription.STATUS_PENDING).count()
        approved_count = qs.filter(status=Prescription.STATUS_APPROVED).count()
        rejected_count = qs.filter(status=Prescription.STATUS_REJECTED).count()
        dispensed_count = qs.filter(status=Prescription.STATUS_DISPENSED).count()

        # Query filters
        status_filter = request.GET.get("status", "").strip().lower()
        if status_filter:
            qs = qs.filter(status=status_filter)

        search = request.GET.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(prescription_number__icontains=search)
                | Q(customer_name__icontains=search)
                | Q(customer_phone__icontains=search)
                | Q(requested_items_text__icontains=search)
            )

        results = [_serialize_prescription(rx) for rx in qs]

        return Response({
            "summary": {
                "total": len(results),
                "pending": pending_count,
                "approved": approved_count,
                "rejected": rejected_count,
                "dispensed": dispensed_count,
            },
            "results": results,
        })

    def post(self, request):
        company = _get_request_company(request)
        if not company:
            return Response({"detail": "User has no associated company."}, status=status.HTTP_403_FORBIDDEN)

        cust_phone = str(request.data.get("customer_phone", "")).strip()
        if not cust_phone:
            return Response({"error": "customer_phone is required."}, status=status.HTTP_400_BAD_REQUEST)

        rx = Prescription.objects.create(
            company=company,
            customer_name=str(request.data.get("customer_name", "")).strip(),
            customer_phone=cust_phone,
            requested_items_text=str(request.data.get("requested_items_text", "")).strip(),
            prescription_image_url=str(request.data.get("prescription_image_url", "")).strip(),
            notes=str(request.data.get("notes", "")).strip(),
            status=Prescription.STATUS_PENDING,
        )

        return Response(_serialize_prescription(rx), status=status.HTTP_201_CREATED)


class PharmacyPrescriptionStatusAPIView(APIView):
    """
    PATCH /api/pharmacy/prescriptions/<int:prescription_id>/status/
    Forward-only state transition:
    - pending -> approved | rejected
    - approved -> dispensed
    Automatically triggers customer WhatsApp status notification!
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, prescription_id):
        company = _get_request_company(request)
        if not company:
            return Response({"detail": "User has no associated company."}, status=status.HTTP_403_FORBIDDEN)

        rx = get_object_or_404(Prescription, pk=prescription_id, company=company)
        new_status = str(request.data.get("status", "")).strip().lower()
        old_status = rx.status.lower()

        allowed = ALLOWED_PRESCRIPTION_TRANSITIONS.get(old_status, set())
        if new_status not in allowed:
            return Response(
                {"error": f"Invalid prescription transition from '{old_status}' to '{new_status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        pharmacist_notes = request.data.get("pharmacist_notes") or request.data.get("reason")
        if pharmacist_notes:
            rx.pharmacist_notes = str(pharmacist_notes).strip()

        rx.status = new_status
        rx.reviewed_by = request.user
        rx.save()

        # Dispatch automated WhatsApp notification
        send_status_notification(
            company=company,
            customer_phone=rx.customer_phone,
            entity_type="prescription",
            reference_id=rx.prescription_number,
            new_status=new_status,
            reason=rx.pharmacist_notes,
            previous_status=old_status,
        )

        return Response(_serialize_prescription(rx))
