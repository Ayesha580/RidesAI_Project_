"""
Dashboard API Views for Full-Stack Integration (Phase 4).

Provides endpoints for:
1. GET /api/dashboard/conversations/ (Paginated AI conversations grouped by customer phone number with full chat history)
2. GET /api/dashboard/conversations/<uuid:conversation_key>/ (Conversation detail)
3. POST /api/dashboard/conversations/<uuid:conversation_key>/reply/ (Human agent reply / handover dispatch)
4. GET /api/dashboard/orders/ (Recent database orders with line items & status)
5. PATCH /api/dashboard/orders/<int:order_id>/status/ (Order lifecycle updates)
"""

import logging
from decimal import Decimal
from typing import Optional

from django.core.paginator import Paginator, EmptyPage
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from companies.models import Company
from operations.models import AgentConversation, AgentMessage, Order, OrderItem, OrderEvent
from operations.whatsapp_service import WhatsAppService

logger = logging.getLogger("operations.dashboard")


def _get_request_company(request) -> Optional[Company]:
    """
    Resolves the company for the current request.
    1. If user is authenticated and attached to a company, uses user.company.
    2. If query param `company_id` is supplied, fetches that company.
    3. If header `X-Company-Id` is supplied, fetches that company.
    4. Fallback for unauthenticated dev requests:
       Matches 'burger king' or company with orders or active company.
    """
    if getattr(request, "user", None) and request.user.is_authenticated:
        company = getattr(request.user, "company", None)
        if company:
            return company

    comp_id = request.GET.get("company_id") or request.headers.get("X-Company-Id")
    if comp_id:
        try:
            c = Company.objects.filter(pk=int(comp_id)).first()
            if c:
                return c
        except Exception:
            pass

    # Prefer 'burger king' if present in DB
    bk = Company.objects.filter(name__iexact="burger king").first()
    if bk:
        return bk

    return (
        Company.objects.filter(orders__isnull=False).distinct().first()
        or Company.objects.filter(status="active").first()
        or Company.objects.filter(is_approved=True).first()
        or Company.objects.first()
    )


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
                ("assistant", f"Welcome to {company.name}! 😊\n\nHere's our menu:\n• Zinger Burger: $550.00\n• Crispy Fries: $220.00\n• Cold Drink: $120.00\n\nWhat can I get for you today?"),
                ("user", "Mujhe 2 Zinger Burger aur 1 Crispy Fries bhej do, address House #45, Street 2, Johar Town, Lahore hai."),
                ("assistant", "🎉 Your order has been successfully placed, Ali Khan!\n\n*Order Number:* *RA-261117-B81503C3*\n*Items:* 2x Zinger Burger, 1x Crispy Fries\n*Total:* $1320.00\n*Estimated Delivery:* 30-45 minutes. 🍔"),
            ]
        },
        {
            "name": "Sarah Ahmed",
            "phone": "+923219876543",
            "status": "bot",
            "messages": [
                ("user", "Hi! Do you have any vegetarian or cheese burger options?"),
                ("assistant", f"Hello Sarah! Welcome to {company.name}. We have delicious Crispy Fries ($220.00) and Cold Drinks ($120.00). Our main burger is the signature Zinger Burger. Would you like fries with that?"),
                ("user", "Yes please! 2 large fries to Gulberg III, Main Market."),
                ("assistant", "Excellent! Your order has been recorded for 2x Crispy Fries. Total: $440.00. We will dispatch it shortly! 🍟"),
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
    permission_classes = [AllowAny]

    def get(self, request):
        company = _get_request_company(request)
        if not company:
            return Response({
                "count": 0,
                "total_pages": 0,
                "current_page": 1,
                "page_size": 10,
                "results": [],
            })

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

            results.append({
                "id": conv.id,
                "conversation_key": str(conv.conversation_key),
                "customer_phone": conv.customer_phone or "Unknown Phone",
                "customer_name": conv.customer_name or "Valued Customer",
                "customer_email": conv.customer_email or "",
                "status": conv.status,
                "status_display": conv.get_status_display() if hasattr(conv, "get_status_display") else conv.status.capitalize(),
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
    permission_classes = [AllowAny]

    def get(self, request, conversation_key):
        company = _get_request_company(request)
        if not company:
            return Response({"detail": "No active company found."}, status=404)

        conv = get_object_or_404(AgentConversation, company=company, conversation_key=conversation_key)
        msgs = list(conv.messages.all().order_by("created_at"))

        return Response({
            "id": conv.id,
            "conversation_key": str(conv.conversation_key),
            "customer_phone": conv.customer_phone,
            "customer_name": conv.customer_name or "Valued Customer",
            "customer_email": conv.customer_email,
            "status": conv.status,
            "created_at": conv.created_at.isoformat(),
            "updated_at": conv.updated_at.isoformat(),
            "messages": [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
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
    permission_classes = [AllowAny]

    def post(self, request, conversation_key):
        company = _get_request_company(request)
        if not company:
            return Response({"detail": "No active company found."}, status=404)

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
    permission_classes = [AllowAny]

    def get(self, request):
        company = _get_request_company(request)
        if not company:
            return Response({
                "count": 0,
                "total_pages": 0,
                "current_page": 1,
                "page_size": 20,
                "results": [],
            })

        qs = Order.objects.filter(company=company).prefetch_related("items").order_by("-created_at")

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
    permission_classes = [AllowAny]

    def patch(self, request, order_id):
        company = _get_request_company(request)
        if not company:
            return Response({"detail": "No active company found."}, status=404)

        order = get_object_or_404(Order, company=company, pk=order_id)
        new_status = request.data.get("status")
        valid_statuses = [x[0] for x in Order.STATUS_CHOICES]

        if new_status not in valid_statuses:
            return Response({"error": f"Invalid status '{new_status}'."}, status=400)

        old_status = order.status
        order.status = new_status
        order.save(update_fields=["status", "updated_at"])

        actor = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
        OrderEvent.objects.create(
            company=company,
            order=order,
            actor=actor,
            event_type="status_change",
            from_status=old_status,
            to_status=new_status,
            note=request.data.get("note", "Updated via Dashboard"),
        )

        return Response({
            "success": True,
            "id": order.id,
            "order_number": order.order_number,
            "status": order.status,
            "status_display": order.get_status_display(),
        })
