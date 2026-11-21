"""
Dashboard API Views for Full-Stack Integration (Phase 4).

Provides endpoints for:
1. GET /api/dashboard/conversations/ (Paginated AI conversations grouped by customer phone number with full chat history)
2. GET /api/dashboard/conversations/<uuid:conversation_key>/ (Conversation detail)
3. POST /api/dashboard/conversations/<uuid:conversation_key>/reply/ (Human agent reply / handover dispatch)
4. GET /api/dashboard/orders/ (Recent database orders with line items & status)
5. PATCH /api/dashboard/orders/<int:order_id>/status/ (Order lifecycle updates)
"""

import base64
import logging
from decimal import Decimal
from typing import Optional

from django.core.paginator import Paginator, EmptyPage
from django.db.models import Q, Avg
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from companies.models import Company
from operations.models import (
    AgentConversation, AgentMessage, Order, OrderItem, OrderEvent, DeliveryAssignment,
    VoiceCall, CallEvent, OrderPrintLog
)
from operations.printing import (
    build_receipt_payload,
    build_invoice_escpos,
    build_kot_escpos,
    dispatch_to_local_printer,
)
from operations.whatsapp_service import WhatsAppService

logger = logging.getLogger("operations.dashboard")


def _get_request_company(request) -> Optional[Company]:
    """
    Resolves the company for the current authenticated request.
    Strictly isolated: returns request.user.company if available, otherwise None.
    Never falls back to unauthenticated defaults or other companies.
    """
    if getattr(request, "user", None) and request.user.is_authenticated:
        return getattr(request.user, "company", None)
    return None


def _seed_demo_conversations_if_empty(company: Company):
    """
    Populates sample customer conversation threads if database has zero conversations,
    ensuring immediate visual feedback on the frontend dashboard.
    """
    if not company:
        return
    if AgentConversation.objects.filter(company=company).exists():
        return

    demos = [
        {
            "name": "Ali Khan",
            "phone": "+923001234567",
            "status": "bot",
            "messages": [
                ("user", "Menu mein kya kya available hai aur prices kya hain?"),
                ("assistant", f"Welcome to {company.name}! 😊\n\nHere's our menu:\n• Zinger Burger: Rs. 550.00\n• Crispy Fries: Rs. 220.00\n• Cold Drink: Rs. 120.00\n\nWhat can I get for you today?"),
                ("user", "Mujhe 2 Zinger Burger aur 1 Crispy Fries bhej do, address House #45, Street 2, Johar Town, Lahore hai."),
                ("assistant", "🎉 Your order has been successfully placed, Ali Khan!\n\n*Order Number:* *RA-261117-B81503C3*\n*Items:* 2x Zinger Burger, 1x Crispy Fries\n*Total:* Rs. 1320.00\n*Estimated Delivery:* 30-45 minutes. 🍔"),
            ]
        },
        {
            "name": "Sarah Ahmed",
            "phone": "+923219876543",
            "status": "bot",
            "messages": [
                ("user", "Hi! Do you have any vegetarian or cheese burger options?"),
                ("assistant", f"Hello Sarah! Welcome to {company.name}. We have delicious Crispy Fries (Rs. 220.00) and Cold Drinks (Rs. 120.00). Our main burger is the signature Zinger Burger. Would you like fries with that?"),
                ("user", "Yes please! 2 large fries to Gulberg III, Main Market."),
                ("assistant", "Excellent! Your order has been recorded for 2x Crispy Fries. Total: Rs. 440.00. We will dispatch it shortly! 🍟"),
            ]
        },
        {
            "name": "Usman Tariq",
            "phone": "+923334567890",
            "status": "human",
            "messages": [
                ("user", "Hello, I placed an order 40 minutes ago. Where is my rider?"),
                ("assistant", "I am checking your order status right now! Please hold on a moment..."),
                ("human", "Hi Usman, our manager here. Your rider is just 2 minutes away at your gate. Thank you for your patience!"),
                ("user", "Received! Thank you so much for the quick help."),
            ]
        },
    ]

    for d in demos:
        conv = AgentConversation.objects.create(
            company=company,
            customer_name=d["name"],
            customer_phone=d["phone"],
            status=d["status"],
        )
        for role, content in d["messages"]:
            AgentMessage.objects.create(
                conversation=conv,
                role=role,
                content=content,
            )


class DashboardConversationsAPIView(APIView):
    """
    GET /api/dashboard/conversations/
    Returns a paginated list of AI conversations grouped by customer phone number,
    including the full chat history (AgentMessage records with user/agent roles and timestamps).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = _get_request_company(request)
        if not company:
            return Response({"detail": "User has no associated company."}, status=status.HTTP_403_FORBIDDEN)

        # Seed sample conversations if this company has none
        _seed_demo_conversations_if_empty(company)

        qs = AgentConversation.objects.filter(company=company).order_by("-updated_at")

        # Filters
        search = request.GET.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(customer_phone__icontains=search)
                | Q(customer_name__icontains=search)
                | Q(messages__content__icontains=search)
            ).distinct()

        status_filter = request.GET.get("status", "").strip()
        if status_filter in ("bot", "human", "closed"):
            qs = qs.filter(status=status_filter)

        # Pagination
        try:
            page = max(1, int(request.GET.get("page", 1)))
        except (TypeError, ValueError):
            page = 1

        try:
            page_size = min(100, max(1, int(request.GET.get("page_size", 10))))
        except (TypeError, ValueError):
            page_size = 10

        paginator = Paginator(qs, page_size)
        try:
            current_page_obj = paginator.page(page)
        except EmptyPage:
            current_page_obj = []

        results = []
        for conv in current_page_obj:
            msgs = list(conv.messages.all().order_by("created_at"))
            last_msg = msgs[-1] if msgs else None
            conv_is_voice = any(
                bool((m.metadata or {}).get("is_voice"))
                for m in msgs
                if isinstance(m.metadata, dict)
            )

            results.append({
                "id": conv.id,
                "conversation_key": str(conv.conversation_key),
                "customer_phone": conv.customer_phone or "Unknown Phone",
                "customer_name": conv.customer_name or "Valued Customer",
                "customer_email": conv.customer_email or "",
                "status": conv.status,
                "status_display": conv.get_status_display() if hasattr(conv, "get_status_display") else conv.status.capitalize(),
                "is_voice": conv_is_voice,
                "last_message": last_msg.content if last_msg else "No messages yet",
                "last_message_at": (last_msg.created_at if last_msg else conv.updated_at).isoformat(),
                "created_at": conv.created_at.isoformat(),
                "updated_at": conv.updated_at.isoformat(),
                "messages_count": len(msgs),
                "messages": [
                    {
                        "id": m.id,
                        "role": m.role,  # user, assistant, human, system
                        "content": m.content,
                        "is_voice": bool((m.metadata or {}).get("is_voice")) if isinstance(m.metadata, dict) else False,
                        "metadata": m.metadata,
                        "created_at": m.created_at.isoformat(),
                        "time_formatted": m.created_at.strftime("%I:%M %p"),
                    }
                    for m in msgs
                ],
            })

        return Response({
            "count": paginator.count,
            "total_pages": paginator.num_pages,
            "current_page": page,
            "page_size": page_size,
            "results": results,
        })


class DashboardConversationDetailAPIView(APIView):
    """
    GET /api/dashboard/conversations/<uuid:conversation_key>/
    Returns full details and message history for a single conversation.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, conversation_key):
        company = _get_request_company(request)
        if not company:
            return Response({"detail": "User has no associated company."}, status=status.HTTP_403_FORBIDDEN)

        conv = get_object_or_404(AgentConversation, company=company, conversation_key=conversation_key)
        msgs = list(conv.messages.all().order_by("created_at"))
        conv_is_voice = any(
            bool((m.metadata or {}).get("is_voice"))
            for m in msgs
            if isinstance(m.metadata, dict)
        )

        return Response({
            "id": conv.id,
            "conversation_key": str(conv.conversation_key),
            "customer_phone": conv.customer_phone,
            "customer_name": conv.customer_name or "Valued Customer",
            "customer_email": conv.customer_email,
            "status": conv.status,
            "is_voice": conv_is_voice,
            "created_at": conv.created_at.isoformat(),
            "updated_at": conv.updated_at.isoformat(),
            "messages": [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "is_voice": bool((m.metadata or {}).get("is_voice")) if isinstance(m.metadata, dict) else False,
                    "metadata": m.metadata,
                    "created_at": m.created_at.isoformat(),
                    "time_formatted": m.created_at.strftime("%I:%M %p"),
                }
                for m in msgs
            ],
        })


class DashboardConversationReplyAPIView(APIView):
    """
    POST /api/dashboard/conversations/<uuid:conversation_key>/reply/
    Allows a human manager to reply directly to the customer or toggle handover status.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, conversation_key):
        company = _get_request_company(request)
        if not company:
            return Response({"detail": "User has no associated company."}, status=status.HTTP_403_FORBIDDEN)

        conv = get_object_or_404(AgentConversation, company=company, conversation_key=conversation_key)
        message_text = str(request.data.get("message") or "").strip()
        new_status = request.data.get("status")

        if new_status and new_status in ("bot", "human", "closed"):
            conv.status = new_status
            conv.save(update_fields=["status", "updated_at"])

        created_msg = None
        if message_text:
            conv.status = "human"
            conv.save(update_fields=["status", "updated_at"])

            created_msg = AgentMessage.objects.create(
                conversation=conv,
                role="human",
                content=message_text,
            )

            # Optional dispatch via WhatsApp Cloud API if credentials exist
            try:
                service = WhatsAppService()
                if service.is_configured and conv.customer_phone:
                    service.send_text_message(to=conv.customer_phone, text=message_text)
            except Exception as e:
                logger.warning(f"[Dashboard Reply] WhatsApp outbound dispatch failed: {e}")

        return Response({
            "success": True,
            "conversation_key": str(conv.conversation_key),
            "status": conv.status,
            "message": {
                "id": created_msg.id if created_msg else None,
                "role": created_msg.role if created_msg else None,
                "content": created_msg.content if created_msg else None,
                "created_at": created_msg.created_at.isoformat() if created_msg else None,
            } if created_msg else None,
        })


class DashboardOrdersAPIView(APIView):
    """
    GET /api/dashboard/orders/
    Returns a list of recent database orders with items, delivery address, subtotal, and status.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = _get_request_company(request)
        if not company:
            return Response({"detail": "User has no associated company."}, status=status.HTTP_403_FORBIDDEN)

        qs = Order.objects.filter(company=company).select_related("assigned_rider").prefetch_related("items").order_by("-created_at")

        # Filters
        search = request.GET.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(order_number__icontains=search)
                | Q(customer_name__icontains=search)
                | Q(customer_phone__icontains=search)
                | Q(delivery_address__icontains=search)
            )

        status_filter = request.GET.get("status", "").strip()
        if status_filter:
            qs = qs.filter(status=status_filter)

        # Pagination
        try:
            page = max(1, int(request.GET.get("page", 1)))
        except (TypeError, ValueError):
            page = 1

        try:
            page_size = min(100, max(1, int(request.GET.get("page_size", 20))))
        except (TypeError, ValueError):
            page_size = 20

        paginator = Paginator(qs, page_size)
        try:
            current_page_obj = paginator.page(page)
        except EmptyPage:
            current_page_obj = []

        results = []
        for o in current_page_obj:
            items_list = [
                {
                    "id": item.id,
                    "item_name": item.item_name,
                    "quantity": str(item.quantity),
                    "unit_price": str(item.unit_price),
                    "line_total": str(item.line_total),
                }
                for item in o.items.all()
            ]

            results.append({
                "id": o.id,
                "order_number": o.order_number,
                "customer_name": o.customer_name or "Customer",
                "customer_phone": o.customer_phone or "N/A",
                "customer_email": o.customer_email or "",
                "delivery_address": o.delivery_address or "Collection / No Address",
                "status": o.status,
                "status_display": o.get_status_display(),
                "subtotal": str(o.subtotal),
                "delivery_fee": str(o.delivery_fee),
                "total": str(o.total),
                "notes": o.notes or "",
                "source": o.source,
                "created_at": o.created_at.isoformat(),
                "formatted_date": o.created_at.strftime("%b %d, %Y %I:%M %p"),
                "items": items_list,
                "items_count": len(items_list),
                "assigned_rider": {
                    "id": o.assigned_rider.id,
                    "name": o.assigned_rider.get_full_name() or o.assigned_rider.username,
                    "phone": o.assigned_rider.phone or "",
                } if o.assigned_rider else None,
            })

        return Response({
            "count": paginator.count,
            "total_pages": paginator.num_pages,
            "current_page": page,
            "page_size": page_size,
            "results": results,
        })


class DashboardOrderStatusAPIView(APIView):
    """
    PATCH /api/dashboard/orders/<int:order_id>/status/
    Updates the status of an existing order and records an OrderEvent.
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, order_id):
        company = _get_request_company(request)
        if not company:
            return Response({"detail": "User has no associated company."}, status=status.HTTP_403_FORBIDDEN)

        order = get_object_or_404(Order, company=company, pk=order_id)
        new_status = (request.data.get("status") or "").strip().lower()
        valid_statuses = [x[0] for x in Order.STATUS_CHOICES]

        if new_status not in valid_statuses:
            return Response({"error": f"Invalid status '{new_status}'."}, status=400)

        old_status = order.status
        from operations.order_state import is_valid_order_transition
        if not is_valid_order_transition(old_status, new_status):
            return Response(
                {"error": f"Invalid status transition from '{old_status}' to '{new_status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        order.status = new_status
        order.save(update_fields=["status", "updated_at"])

        actor = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
        note_text = request.data.get("note") or request.data.get("reason") or "Updated via Dashboard"
        OrderEvent.objects.create(
            company=company,
            order=order,
            actor=actor,
            event_type="status_change",
            from_status=old_status,
            to_status=new_status,
            note=note_text,
        )

        from operations.notifications import send_order_status_notification
        send_order_status_notification(
            order=order,
            previous_status=old_status,
            new_status=new_status,
            reason=request.data.get("reason") or request.data.get("note"),
        )

        # Auto-complete linked exchange requests if delivered
        if new_status == Order.STATUS_DELIVERED:
            from operations.retail_views import complete_linked_exchanges_on_delivery
            complete_linked_exchanges_on_delivery(order, company=company)

        return Response({
            "success": True,
            "id": order.id,
            "order_number": order.order_number,
            "status": order.status,
            "status_display": order.get_status_display(),
        })


class DashboardOrderAutoAssignRiderAPIView(APIView):
    """
    POST /api/dashboard/orders/<int:order_pk>/auto-assign-rider/
    Auto-assigns the least busy active delivery rider to the order.
    Strict tenant isolation enforced.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, order_pk):
        company = _get_request_company(request)
        if not company:
            return Response({"detail": "User has no associated company."}, status=status.HTTP_403_FORBIDDEN)

        order = get_object_or_404(Order, pk=order_pk, company=company)

        from django.db.models import Q
        from accounts.models import User
        from operations.services.dispatch_service import assign_best_rider

        rider_filter = (
            Q(role="rider")
            | Q(staff_role__name__iexact="rider")
            | Q(staff_role__name__iexact="delivery boy")
            | Q(staff_role__name__iexact="delivery")
        )
        has_riders = User.objects.filter(company=company, is_active=True).filter(rider_filter).exists()
        if not has_riders:
            return Response(
                {
                    "error": "No active riders available. Please add a rider in Employees.",
                    "detail": "No active riders available. Please add a rider in Employees.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        rider = assign_best_rider(order)
        if not rider:
            return Response(
                {
                    "error": "No active riders available. Please add a rider in Employees.",
                    "detail": "No active riders available. Please add a rider in Employees.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        assignment, _ = DeliveryAssignment.objects.update_or_create(
            order=order,
            defaults={
                "company": company,
                "rider": rider,
                "assigned_by": request.user,
                "status": Order.STATUS_ASSIGNED,
            },
        )
        order.assigned_rider = rider
        if order.status in (
            Order.STATUS_NEW,
            Order.STATUS_PENDING,
            Order.STATUS_CONFIRMED,
            Order.STATUS_PREPARING,
            Order.STATUS_PREPARED,
            Order.STATUS_READY,
        ):
            order.status = Order.STATUS_ASSIGNED
        order.save(update_fields=["assigned_rider", "status", "updated_at"])

        return Response({
            "success": True,
            "order_id": order.id,
            "order_number": order.order_number,
            "status": order.status,
            "rider": {
                "id": rider.id,
                "name": rider.get_full_name() or rider.username,
                "phone": getattr(rider, "phone", "") or "",
            },
            "message": f"Successfully auto-assigned to {rider.get_full_name() or rider.username}.",
        }, status=status.HTTP_200_OK)


class DashboardCallsAPIView(APIView):
    """
    GET /api/dashboard/calls/
    Returns tenant-scoped WhatsApp voice calls and aggregated KPI statistics.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = _get_request_company(request)
        if not company:
            return Response({"detail": "User has no associated company."}, status=status.HTTP_403_FORBIDDEN)

        base_qs = VoiceCall.objects.filter(company=company)

        # Tenant-wide KPI stats
        total_calls = base_qs.count()
        active_calls = base_qs.filter(status__in=["initiated", "ringing", "accepted"]).count()
        missed_or_failed = base_qs.filter(status__in=["rejected", "failed"]).count()
        avg_dur_val = base_qs.filter(status="terminated").aggregate(avg=Avg("duration_seconds"))["avg"]
        avg_duration_seconds = round(avg_dur_val, 1) if avg_dur_val is not None else 0

        qs = base_qs.order_by("-created_at")

        # Filters
        status_filter = request.GET.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter.strip().lower())

        direction_filter = request.GET.get("direction")
        if direction_filter:
            qs = qs.filter(direction=direction_filter.strip().lower())

        search_query = request.GET.get("search", "").strip()
        if search_query:
            qs = qs.filter(
                Q(customer_phone__icontains=search_query) |
                Q(call_id__icontains=search_query)
            )

        calls_list = []
        for c in qs:
            calls_list.append({
                "id": c.id,
                "call_id": c.call_id,
                "customer_phone": c.customer_phone,
                "direction": c.direction,
                "status": c.status,
                "status_display": c.get_status_display(),
                "duration_seconds": c.duration_seconds,
                "started_at": c.started_at.isoformat() if c.started_at else None,
                "ended_at": c.ended_at.isoformat() if c.ended_at else None,
                "error_code": c.error_code,
                "error_message": c.error_message,
                "created_at": c.created_at.isoformat(),
                "formatted_date": c.created_at.strftime("%b %d, %Y %I:%M %p"),
            })

        return Response({
            "is_calling_enabled": bool(company.is_calling_enabled),
            "stats": {
                "active_calls": active_calls,
                "total_calls": total_calls,
                "missed_or_failed": missed_or_failed,
                "avg_duration_seconds": avg_duration_seconds,
            },
            "calls": calls_list,
        })


class DashboardCallEventsAPIView(APIView):
    """
    GET /api/dashboard/calls/<int:call_pk>/events/
    Returns chronological CallEvents for a specific tenant-owned VoiceCall.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, call_pk):
        company = _get_request_company(request)
        if not company:
            return Response({"detail": "User has no associated company."}, status=status.HTTP_403_FORBIDDEN)

        call_obj = get_object_or_404(VoiceCall, pk=call_pk, company=company)
        events = call_obj.events.all().order_by("created_at")

        events_list = [
            {
                "id": ev.id,
                "event_type": ev.event_type,
                "raw_payload": ev.raw_payload,
                "created_at": ev.created_at.isoformat(),
                "formatted_date": ev.created_at.strftime("%b %d, %Y %I:%M:%S %p"),
            }
            for ev in events
        ]

        return Response({
            "call": {
                "id": call_obj.id,
                "call_id": call_obj.call_id,
                "customer_phone": call_obj.customer_phone,
                "direction": call_obj.direction,
                "status": call_obj.status,
                "status_display": call_obj.get_status_display(),
                "duration_seconds": call_obj.duration_seconds,
                "started_at": call_obj.started_at.isoformat() if call_obj.started_at else None,
                "ended_at": call_obj.ended_at.isoformat() if call_obj.ended_at else None,
                "error_code": call_obj.error_code,
                "error_message": call_obj.error_message,
                "created_at": call_obj.created_at.isoformat(),
                "formatted_date": call_obj.created_at.strftime("%b %d, %Y %I:%M %p"),
            },
            "events": events_list,
        })


class DashboardOrderReceiptAPIView(APIView):
    """
    GET /api/dashboard/orders/<int:order_pk>/receipt/?type=invoice|kot
    Returns formatted 80mm thermal receipt data and pre-generated ESC/POS binary stream.
    Strict tenant isolation enforced.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, order_pk):
        company = _get_request_company(request)
        if not company:
            return Response({"detail": "User has no associated company."}, status=status.HTTP_403_FORBIDDEN)

        order = get_object_or_404(Order, pk=order_pk, company=company)
        slip_type = request.GET.get("type", "invoice").lower()
        if slip_type not in ("invoice", "kot"):
            slip_type = "invoice"

        # 1. Build structured payload
        payload = build_receipt_payload(order, company=company, slip_type=slip_type)

        # 2. Build ESC/POS bytes (80mm / SpeedX SP-200U)
        if slip_type == "kot":
            escpos_bytes = build_kot_escpos(order, company=company)
        else:
            escpos_bytes = build_invoice_escpos(order, company=company)

        escpos_base64 = base64.b64encode(escpos_bytes).decode("ascii")

        # 3. Print audit info
        print_logs = order.print_logs.all()
        print_count = print_logs.filter(status=OrderPrintLog.STATUS_SUCCESS).count()
        last_log = print_logs.first()

        return Response({
            "slip_type": slip_type,
            "receipt": payload,
            "printer_name": getattr(company, "printer_name", "SpeedX SP-200U") or "SpeedX SP-200U",
            "currency_symbol": getattr(company, "currency_symbol", "Rs.") or "Rs.",
            "auto_print_kot": getattr(company, "auto_print_kot", False),
            "auto_print_invoice": getattr(company, "auto_print_invoice", False),
            "print_count": print_count,
            "last_printed_at": last_log.created_at.isoformat() if last_log else None,
            "escpos_base64": escpos_base64,
        })


class DashboardOrderPrintAPIView(APIView):
    """
    POST /api/dashboard/orders/<int:order_pk>/print/
    Dispatches print job to local Windows ESC/POS spooler or records browser print audit.
    Body: {"slip_type": "invoice"|"kot", "mode": "browser"|"escpos_local"}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, order_pk):
        company = _get_request_company(request)
        if not company:
            return Response({"detail": "User has no associated company."}, status=status.HTTP_403_FORBIDDEN)

        order = get_object_or_404(Order, pk=order_pk, company=company)
        slip_type = request.data.get("slip_type", "invoice").lower()
        if slip_type not in ("invoice", "kot"):
            slip_type = "invoice"

        mode = request.data.get("mode", "browser").lower()
        if mode not in ("browser", "escpos_local"):
            mode = "browser"

        user = request.user if request.user and request.user.is_authenticated else None

        if mode == "escpos_local":
            if slip_type == "kot":
                raw_bytes = build_kot_escpos(order, company=company)
            else:
                raw_bytes = build_invoice_escpos(order, company=company)

            printer_name = getattr(company, "printer_name", "SpeedX SP-200U")
            dispatch_result = dispatch_to_local_printer(raw_bytes, printer_name)

            log_status = OrderPrintLog.STATUS_SUCCESS if dispatch_result.get("success") else OrderPrintLog.STATUS_FAILED
            OrderPrintLog.objects.create(
                company=company,
                order=order,
                slip_type=slip_type,
                print_mode=OrderPrintLog.MODE_ESCPOS_LOCAL,
                status=log_status,
                error_message=dispatch_result.get("error", "") or "",
                printed_by=user,
            )

            print_count = order.print_logs.filter(status=OrderPrintLog.STATUS_SUCCESS).count()

            return Response({
                "success": dispatch_result.get("success", False),
                "mode": "escpos_local",
                "slip_type": slip_type,
                "printer": dispatch_result.get("printer", printer_name),
                "bytes_sent": dispatch_result.get("bytes_sent", 0),
                "simulated": dispatch_result.get("simulated", False),
                "error": dispatch_result.get("error"),
                "print_count": print_count,
            }, status=status.HTTP_200_OK if dispatch_result.get("success") else status.HTTP_200_OK)

        else:
            # Browser print audit logging
            OrderPrintLog.objects.create(
                company=company,
                order=order,
                slip_type=slip_type,
                print_mode=OrderPrintLog.MODE_BROWSER,
                status=OrderPrintLog.STATUS_SUCCESS,
                printed_by=user,
            )
            print_count = order.print_logs.filter(status=OrderPrintLog.STATUS_SUCCESS).count()

            return Response({
                "success": True,
                "mode": "browser",
                "slip_type": slip_type,
                "print_count": print_count,
            }, status=status.HTTP_200_OK)


