import json
import logging
import os
import re
import threading
from decimal import Decimal, InvalidOperation

import requests
from django.conf import settings
from django.db import transaction
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import csrf_exempt
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.throttling import AnonRateThrottle
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsCompanyPaymentActive
from billing.services import consume_company_message, get_access_state
from accounts.models import User
from accounts.business_permissions import HasBusinessPermission
from companies.models import CatalogItem, Inventory, StockMovement
from .models import (Order, OrderItem, DeliveryAssignment, OrderEvent,
                     AgentConversation, AgentMessage, AgentActionLog)
from .order_state import is_valid_order_transition, ALLOWED_ORDER_TRANSITIONS
from .whatsapp_storage import (get_whatsapp_config, save_whatsapp_config,
                               is_valid_verify_token, get_config_by_phone_number_id)
from .whatsapp_service import WhatsAppService, send_whatsapp_message
from .whatsapp_agent import process_incoming_whatsapp_message

logger = logging.getLogger(__name__)


ORDER_TRANSITIONS = ALLOWED_ORDER_TRANSITIONS


def _valid_order_transition(current, next_status):
    return is_valid_order_transition(current, next_status)


class BusinessAPIView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyPaymentActive, HasBusinessPermission]

    @property
    def company(self):
        return self.request.user.company


def _delivery_area_for_order(company, payload):
    """Return matching configured delivery area or reject an out-of-zone delivery."""
    delivery = str(payload.get("fulfillment_type", "delivery" if payload.get("delivery_address") else "collection")).lower() == "delivery"
    if not delivery:
        return None
    address = str(payload.get("delivery_address") or "").strip()
    if not address:
        raise ValueError("A complete delivery address is required.")
    city = str(payload.get("city") or "").strip().casefold()
    country = str(payload.get("country") or "").strip().casefold()
    latitude, longitude = payload.get("latitude"), payload.get("longitude")
    from companies.models import ServiceArea
    from math import radians, sin, cos, asin, sqrt
    for area in ServiceArea.objects.filter(company=company, is_active=True):
        if area.area_type == "city" and city and city == area.city.casefold() and (not area.country or country == area.country.casefold()):
            return area
        if area.area_type == "country" and country and country == area.country.casefold():
            return area
        if area.area_type == "radius" and latitude is not None and longitude is not None:
            try:
                dlat=radians(float(latitude)-float(area.center_latitude)); dlon=radians(float(longitude)-float(area.center_longitude))
                a=sin(dlat/2)**2+cos(radians(float(area.center_latitude)))*cos(radians(float(latitude)))*sin(dlon/2)**2
                if 6371*2*asin(sqrt(a)) <= float(area.radius_km): return area
            except (TypeError, ValueError):
                continue
    raise ValueError("Delivery is unavailable at this address. Please choose collection or contact the business.")


def _create_order(company, payload, actor=None, source="dashboard"):
    rows = payload.get("items") or []
    if not rows:
        raise ValueError("At least one catalogue item is required.")
    customer_name = str(payload.get("customer_name") or "").strip()
    if not customer_name:
        raise ValueError("Customer name is required.")
    delivery_area = _delivery_area_for_order(company, payload)
    with transaction.atomic():
        order = Order.objects.create(company=company, customer_name=customer_name,
            customer_email=payload.get("customer_email", ""),
            customer_phone=payload.get("customer_phone", ""),
            delivery_address=payload.get("delivery_address", ""),
            notes=payload.get("notes", ""), source=source, created_by=actor)
        subtotal = Decimal("0")
        for row in rows:
            item_id = row.get("item_id")
            if not item_id:
                raise ValueError("Select an item from this business catalogue.")
            item = CatalogItem.objects.select_for_update().get(
                pk=item_id, company=company, is_available=True)
            quantity = Decimal(str(row.get("quantity", 1)))
            if quantity <= 0:
                raise ValueError("Order quantities must be greater than zero.")
            inventory = Inventory.objects.select_for_update().filter(company=company, item=item).first()
            if inventory and not inventory.is_unlimited:
                if quantity > inventory.quantity:
                    raise ValueError(f"Not enough stock for {item.name}.")
                inventory.quantity -= quantity
                inventory.save(update_fields=["quantity", "updated_at"])
                StockMovement.objects.create(company=company, item=item, movement_type="remove",
                    quantity=quantity, note=f"Order {order.order_number}")
            line_total = quantity * item.price
            OrderItem.objects.create(order=order, item=item, item_name=item.name,
                quantity=quantity, unit_price=item.price, line_total=line_total)
            subtotal += line_total
        # Delivery fees are always derived from the matched business service area.
        # Collection orders have no delivery fee; never trust a customer-supplied fee.
        fee = Decimal(str(delivery_area.delivery_fee if delivery_area else "0"))
        if fee < 0:
            raise ValueError("Delivery fee cannot be negative.")
        order.subtotal, order.delivery_fee, order.total = subtotal, fee, subtotal + fee
        order.save(update_fields=["subtotal", "delivery_fee", "total", "updated_at"])
        OrderEvent.objects.create(company=company, order=order, actor=actor,
            event_type=f"{source}_order_created", to_status=order.status)
    return order


def _order_payload(order):
    delivery = getattr(order, "delivery", None)
    return {
        "id": order.id, "order_number": order.order_number,
        "customer_name": order.customer_name, "customer_email": order.customer_email,
        "customer_phone": order.customer_phone, "delivery_address": order.delivery_address,
        "status": order.status, "subtotal": str(order.subtotal),
        "delivery_fee": str(order.delivery_fee), "total": str(order.total),
        "notes": order.notes, "source": order.source,
        "assigned_to_id": order.assigned_to_id, "assigned_to_name": (order.assigned_to.get_full_name() or order.assigned_to.username) if order.assigned_to else None, "assigned_team": order.assigned_team,
        "created_at": order.created_at.isoformat(),
        "items": [{"id": i.id, "item_id": i.item_id, "name": i.item_name,
                   "quantity": str(i.quantity), "unit_price": str(i.unit_price),
                   "line_total": str(i.line_total)} for i in order.items.all()],
        "delivery": ({"id": delivery.id, "rider_id": delivery.rider_id,
                      "rider_name": delivery.rider.get_full_name() or delivery.rider.username,
                      "status": delivery.status} if delivery else None),
        "events": [{"type": event.event_type, "from_status": event.from_status,
                    "to_status": event.to_status, "note": event.note,
                    "actor": (event.actor.get_full_name() or event.actor.username) if event.actor else "System",
                    "created_at": event.created_at.isoformat()}
                   for event in order.events.select_related("actor").order_by("-created_at")[:20]],
    }


class OrderCatalogAPIView(BusinessAPIView):
    def get(self, request):
        if not request.user.has_business_permission("orders.create"):
            return Response({"detail": "Your role cannot create orders."}, status=403)
        rows = CatalogItem.objects.filter(company=self.company, is_available=True).select_related("inventory")[:300]
        result = []
        for item in rows:
            inventory = getattr(item, "inventory", None)
            result.append({
                "id": item.id, "name": item.name, "price": str(item.price), "unit": item.unit,
                "in_stock": (inventory.is_unlimited or inventory.quantity > 0) if inventory else True,
                "quantity": None if not inventory or inventory.is_unlimited else str(inventory.quantity),
            })
        return Response(result)


class OrderListCreateAPIView(BusinessAPIView):
    def get(self, request):
        if not request.user.has_business_permission("orders.view"):
            return Response({"detail": "Your role cannot view orders."}, status=403)
        qs = Order.objects.filter(company=self.company).prefetch_related("items").select_related("delivery__rider", "assigned_to")
        if request.user.role == User.ROLE_STAFF and not request.user.has_business_permission("orders.view_all"):
            team_name = getattr(getattr(request.user, "staff_role", None), "name", "")
            from django.db.models import Q
            qs = qs.filter(Q(assigned_to=request.user) | Q(assigned_team__iexact=team_name))
        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        search = request.query_params.get("q", "").strip()
        if search:
            qs = qs.filter(order_number__icontains=search) | qs.filter(customer_name__icontains=search)
        return Response([_order_payload(o) for o in qs[:250]])

    def post(self, request):
        if not request.user.has_business_permission("orders.create"):
            return Response({"detail": "Your role cannot create orders."}, status=403)
        try:
            order = _create_order(self.company, request.data, actor=request.user,
                                  source="dashboard")
        except CatalogItem.DoesNotExist:
            return Response({"items": "One or more selected items do not belong to this business or are unavailable."}, status=400)
        except (InvalidOperation, ValueError, KeyError) as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(_order_payload(order), status=201)


class OrderStatusAPIView(BusinessAPIView):
    def patch(self, request, order_id):
        order = get_object_or_404(Order, pk=order_id, company=self.company)
        next_status = request.data.get("status")
        valid = {choice[0] for choice in Order.STATUS_CHOICES}
        if next_status not in valid:
            return Response({"status": "Invalid order status."}, status=400)
        is_rider = DeliveryAssignment.objects.filter(company=self.company, order=order, rider=request.user).exists()
        if is_rider:
            if not request.user.has_business_permission("deliveries.update_status"):
                return Response({"detail": "You cannot update delivery status."}, status=403)
            next_for_current = {
                Order.STATUS_ASSIGNED: Order.STATUS_PICKED_UP,
                Order.STATUS_PICKED_UP: Order.STATUS_ON_THE_WAY,
                Order.STATUS_ON_THE_WAY: Order.STATUS_DELIVERED,
            }
            if next_for_current.get(order.status) != next_status:
                return Response({"detail": "Riders must advance delivery in order: picked up, on the way, delivered."}, status=403)
        else:
            if not request.user.has_business_permission("orders.update_status"):
                return Response({"detail": "Your role cannot update this order."}, status=403)
            if not _valid_order_transition(order.status, next_status):
                return Response({
                    "error": f"Invalid status transition from '{order.status}' to '{next_status}'.",
                    "detail": f"Invalid order transition from {order.status} to {next_status}."
                }, status=409)
        previous = order.status
        order.status = next_status
        order.save(update_fields=["status", "updated_at"])
        DeliveryAssignment.objects.filter(order=order).update(status=next_status)
        OrderEvent.objects.create(company=self.company, order=order, actor=request.user,
            event_type="status_changed", from_status=previous, to_status=next_status,
            note=str(request.data.get("note", "")))

        from operations.notifications import send_order_status_notification
        send_order_status_notification(
            order=order,
            previous_status=previous,
            new_status=next_status,
            reason=request.data.get("note"),
        )

        # Auto-complete linked exchange requests if delivered
        if next_status == Order.STATUS_DELIVERED:
            from operations.retail_views import complete_linked_exchanges_on_delivery
            complete_linked_exchanges_on_delivery(order, company=self.company)

        return Response(_order_payload(order))


class RiderDeliveryAPIView(BusinessAPIView):
    required_business_permission = "deliveries.view_assigned"

    def get(self, request):
        rows = DeliveryAssignment.objects.filter(company=self.company, rider=request.user).select_related("order").prefetch_related("order__items")
        return Response([_order_payload(row.order) for row in rows[:200]])


class DeliveryListAPIView(BusinessAPIView):
    required_business_permission = "deliveries.view"

    def get(self, request):
        rows = DeliveryAssignment.objects.filter(company=self.company).select_related("order", "rider").prefetch_related("order__items")[:250]
        return Response([{
            **_order_payload(row.order),
            "rider_id": row.rider_id,
            "rider_name": row.rider.get_full_name() or row.rider.username,
            "delivery_status": row.status,
        } for row in rows])


class DeliveryRiderListAPIView(BusinessAPIView):
    required_business_permission = "deliveries.assign"

    def get(self, request):
        riders = User.objects.filter(company=self.company, role=User.ROLE_STAFF,
            is_active=True, staff_role__is_active=True).select_related("staff_role")
        return Response([{
            "id": rider.id,
            "full_name": rider.get_full_name() or rider.username,
            "username": rider.username,
            "permissions": rider.get_permissions(),
            "modules": rider.get_modules(),
        } for rider in riders if rider.has_business_permission("deliveries.view_assigned")])


class DeliveryAssignAPIView(BusinessAPIView):
    required_business_permission = "deliveries.assign"

    def post(self, request):
        order = get_object_or_404(Order, pk=request.data.get("order_id"), company=self.company)
        if order.status not in (Order.STATUS_READY, Order.STATUS_ASSIGNED):
            return Response({"detail": "A rider can only be assigned after the order is ready."}, status=409)
        rider = get_object_or_404(User, pk=request.data.get("rider_id"), company=self.company, role=User.ROLE_STAFF, is_active=True)
        if not rider.has_business_permission("deliveries.view_assigned"):
            return Response({"detail": "Selected staff member does not have rider delivery access."}, status=400)
        assignment, created = DeliveryAssignment.objects.update_or_create(
            order=order, defaults={"company": self.company, "rider": rider,
                "assigned_by": request.user, "status": Order.STATUS_ASSIGNED})
        previous = order.status
        order.status = Order.STATUS_ASSIGNED
        order.save(update_fields=["status", "updated_at"])
        OrderEvent.objects.create(company=self.company, order=order, actor=request.user,
            event_type="rider_assigned", from_status=previous, to_status=order.status,
            metadata={"rider_id": rider.id})
        return Response({"assignment_id": assignment.id, "rider_id": rider.id,
                         "order_id": order.id, "created": created}, status=201 if created else 200)


class OrderAssignAPIView(BusinessAPIView):
    required_business_permission = "orders.assign"
    def post(self, request, order_id):
        order = get_object_or_404(Order, pk=order_id, company=self.company)
        employee_id = request.data.get("employee_id")
        team = str(request.data.get("team", "")).strip()[:80]
        employee = None
        if employee_id:
            employee = get_object_or_404(User, pk=employee_id, company=self.company, role=User.ROLE_STAFF, is_active=True)
            if not employee.has_business_permission("orders.view"):
                return Response({"detail": "Employee must have order-view permission before assignment."}, status=400)
        if not employee and not team:
            return Response({"detail": "Provide an employee_id or team."}, status=400)
        order.assigned_to = employee
        order.assigned_team = team
        order.save(update_fields=["assigned_to", "assigned_team", "updated_at"])
        OrderEvent.objects.create(company=self.company, order=order, actor=request.user,
            event_type="work_assigned", metadata={"employee_id": employee.id if employee else None, "team": team})
        return Response(_order_payload(order))


class AgentSettingsAPIView(BusinessAPIView):
    def get(self, request):
        if request.user.role != User.ROLE_OWNER:
            return Response({"detail": "Only the business owner can configure the AI Agent."}, status=403)
        return Response({
            "enabled": self.company.agent_enabled,
            "is_ai_paused": self.company.is_ai_paused,
            "allowed_actions": self.company.agent_allowed_actions,
            "greeting": self.company.agent_greeting,
            "tone": self.company.agent_tone,
            "support_phone": self.company.agent_support_phone,
            "support_email": self.company.agent_support_email,
            "public_id": str(self.company.agent_public_id),
        })

    def patch(self, request):
        if request.user.role != User.ROLE_OWNER:
            return Response({"detail": "Only the business owner can configure the AI Agent."}, status=403)
        allowed = {"create_order", "update_order_status", "lookup_order", "handover"}
        actions = list(dict.fromkeys(request.data.get("allowed_actions", self.company.agent_allowed_actions) or []))
        if set(actions) - allowed:
            return Response({"allowed_actions": "Contains unsupported actions."}, status=400)
        self.company.agent_enabled = bool(request.data.get("enabled", self.company.agent_enabled))
        if "is_ai_paused" in request.data:
            self.company.is_ai_paused = bool(request.data["is_ai_paused"])
        self.company.agent_allowed_actions = actions
        self.company.agent_greeting = str(request.data.get("greeting", self.company.agent_greeting))[:2000]
        tone = request.data.get("tone", self.company.agent_tone)
        if tone not in ("friendly", "professional", "concise"):
            return Response({"tone": "Choose friendly, professional or concise."}, status=400)
        self.company.agent_tone = tone
        self.company.agent_support_phone = str(request.data.get("support_phone", self.company.agent_support_phone))[:30]
        self.company.agent_support_email = str(request.data.get("support_email", self.company.agent_support_email))[:254]
        self.company.save(update_fields=[
            "agent_enabled", "is_ai_paused", "agent_allowed_actions", "agent_greeting",
            "agent_tone", "agent_support_phone", "agent_support_email"
        ])
        return Response({
            "enabled": self.company.agent_enabled,
            "is_ai_paused": self.company.is_ai_paused,
            "allowed_actions": actions,
            "greeting": self.company.agent_greeting,
            "tone": self.company.agent_tone,
            "support_phone": self.company.agent_support_phone,
            "support_email": self.company.agent_support_email,
            "public_id": str(self.company.agent_public_id),
        })


class AgentTogglePauseAPIView(BusinessAPIView):
    def post(self, request):
        if request.user.role != User.ROLE_OWNER:
            return Response({"detail": "Only the business owner can pause or resume the AI Agent."}, status=403)
        if "is_ai_paused" in request.data:
            self.company.is_ai_paused = bool(request.data["is_ai_paused"])
        else:
            self.company.is_ai_paused = not self.company.is_ai_paused
        self.company.save(update_fields=["is_ai_paused"])
        return Response({
            "success": True,
            "is_ai_paused": self.company.is_ai_paused,
            "message": "AI Voice Agent paused." if self.company.is_ai_paused else "AI Voice Agent resumed."
        })


class AgentChatAPIView(BusinessAPIView):
    """Authenticated, tenant-scoped AI chat. Agent actions are explicit and separately authorized."""
    required_business_permission = "agent.view"
    def post(self, request):
        company = self.company
        if not company:
            return Response({"detail": "Business account is not linked."}, status=400)
        if not company.agent_enabled:
            return Response({"detail": "The AI Agent is disabled for this business."}, status=403)
        message = (request.data.get("message") or "").strip()
        if not message:
            return Response({"message": "A message is required."}, status=400)
        try:
            company = consume_company_message(company)
        except Exception as exc:
            return Response({"detail": str(exc)}, status=429)
        conversation = None
        conversation_id = request.data.get("conversation_id")
        if conversation_id:
            conversation = get_object_or_404(AgentConversation, conversation_key=conversation_id, company=company)
        else:
            conversation = AgentConversation.objects.create(company=company,
                customer_name=request.data.get("customer_name", ""),
                customer_email=request.data.get("customer_email", ""),
                customer_phone=request.data.get("customer_phone", ""))
        AgentMessage.objects.create(conversation=conversation, role="user", content=message)

        action = request.data.get("action") or {}
        action_result = None
        if action:
            action_result = self._perform_action(request, conversation, action)

        context = self._business_context(company, conversation)
        history = list(conversation.messages.order_by("-created_at").values("role", "content")[:12])[::-1]
        answer = self._generate_answer(company, context, history, action_result)
        AgentMessage.objects.create(conversation=conversation, role="assistant", content=answer,
                                    metadata={"action_result": action_result or {}})
        return Response({"conversation_id": str(conversation.conversation_key),
                          "answer": answer, "status": conversation.status,
                          "action_result": action_result})

    def _business_context(self, company, conversation, include_customer_orders=True):
        catalog = []
        for item in CatalogItem.objects.filter(company=company, is_available=True).select_related("inventory")[:80]:
            inventory = getattr(item, "inventory", None)
            catalog.append({
                "id": item.id, "name": item.name, "description": item.description,
                "price": str(item.price), "unit": item.unit,
                "in_stock": (inventory.is_unlimited or inventory.quantity > 0) if inventory else True,
                "quantity": None if not inventory or inventory.is_unlimited else str(inventory.quantity),
            })
        orders = []
        if include_customer_orders and (conversation.customer_email or conversation.customer_phone or conversation.customer_name):
            qs = Order.objects.filter(company=company)
            if conversation.customer_email:
                qs = qs.filter(customer_email__iexact=conversation.customer_email)
            elif conversation.customer_phone:
                qs = qs.filter(customer_phone=conversation.customer_phone)
            elif conversation.customer_name:
                qs = qs.filter(customer_name__iexact=conversation.customer_name)
            orders = list(qs.values("order_number", "status", "total", "created_at",
                "delivery__status", "delivery__rider__first_name", "delivery__rider__last_name")[:10])
        from companies.models import BusinessKnowledge, BusinessHours, BusinessLocation
        knowledge = list(BusinessKnowledge.objects.filter(company=company, is_active=True, is_approved=True).values("entry_type", "title", "content")[:100])
        hours = list(BusinessHours.objects.filter(company=company).values("day_of_week", "opens_at", "closes_at", "is_closed"))
        locations = list(BusinessLocation.objects.filter(company=company, is_active=True).values("name", "address", "city", "country", "phone"))
        service_areas = list(company.service_areas.filter(is_active=True).values("name", "area_type", "city", "country", "radius_km", "delivery_fee"))
        return {"business": company.name, "business_type": company.business_type,
                "business_address": company.address, "business_phone": company.phone,
                "locations": locations, "operating_hours": hours, "service_areas": service_areas, "approved_knowledge": knowledge,
                "catalog": catalog, "customer_orders": orders}

    def _perform_action(self, request, conversation, action):
        name = action.get("type")
        enabled = set(request.user.company.agent_allowed_actions or [])
        permission_by_action = {
            "create_order": "orders.create",
            "lookup_order": "orders.view",
            "update_order_status": "orders.update_status",
            "handover": "agent.handover",
        }
        required = permission_by_action.get(name)
        permitted = bool(name in enabled and required and request.user.has_business_permission(required))
        result = {"success": False, "error": "This action is not enabled or authorized."}
        if permitted and name == "create_order":
            if action.get("confirmed") is not True:
                result["error"] = "Customer confirmation is required before creating an order."
                AgentActionLog.objects.create(company=request.user.company, conversation=conversation,
                    actor=request.user, action=str(name), allowed=False,
                    request_data=action, result_data=result)
                return result
            payload = action.get("data") or {}
            payload.setdefault("customer_name", conversation.customer_name)
            payload.setdefault("customer_email", conversation.customer_email)
            payload.setdefault("customer_phone", conversation.customer_phone)
            try:
                order = _create_order(request.user.company, payload, actor=request.user, source="agent")
                result = {"success": True, "order": _order_payload(order)}
            except (CatalogItem.DoesNotExist, InvalidOperation, ValueError, KeyError) as exc:
                result["error"] = str(exc)
        elif permitted and name == "lookup_order":
            order = Order.objects.filter(company=request.user.company,
                order_number=action.get("order_number", "")).first()
            if order:
                result = {"success": True, "order": _order_payload(order)}
            else:
                result["error"] = "Order not found for this business."
        elif permitted and name == "update_order_status":
            order = Order.objects.filter(company=request.user.company, pk=action.get("order_id")).first()
            next_status = action.get("status")
            valid = {choice[0] for choice in Order.STATUS_CHOICES}
            if order and next_status in valid and _valid_order_transition(order.status, next_status):
                old = order.status
                order.status = next_status
                order.save(update_fields=["status", "updated_at"])
                DeliveryAssignment.objects.filter(order=order).update(status=next_status)
                OrderEvent.objects.create(company=request.user.company, order=order, actor=request.user,
                    event_type="agent_status_update", from_status=old, to_status=next_status)
                result = {"success": True, "order_number": order.order_number, "status": next_status}
            else:
                result["error"] = "Order not found or the requested status transition is not allowed."
        elif name == "handover" and "handover" in enabled and request.user.has_business_permission("agent.handover"):
            conversation.status = "human"
            conversation.save(update_fields=["status", "updated_at"])
            result = {"success": True, "status": "human", "message": "Conversation handed over to the business team."}
        AgentActionLog.objects.create(company=request.user.company, conversation=conversation,
            actor=request.user, action=str(name or "unknown"), allowed=bool(result.get("success")),
            request_data=action, result_data=result)
        return result

    def _generate_answer(self, company, context, history, action_result):
        api_key = getattr(settings, "OPENAI_API_KEY", "")
        model = getattr(settings, "OPENAI_MODEL", "gpt-4o-mini")
        if not api_key:
            if action_result and action_result.get("success"):
                order_number = action_result.get("order_number") or (action_result.get("order") or {}).get("order_number")
                order_status = action_result.get("status") or (action_result.get("order") or {}).get("status")
                delivery_status = action_result.get("delivery_status")
                rider_name = action_result.get("rider_name")
                total = action_result.get("total") or (action_result.get("order") or {}).get("total")
                if order_number and order_status:
                    extra = f" Delivery status: {delivery_status.replace('_', ' ')}" if delivery_status else ""
                    if rider_name:
                        extra += f". Rider: {rider_name}"
                    return f"Order {order_number} is currently {order_status.replace('_', ' ')}.{extra}"
                if order_number and total:
                    return f"Your order {order_number} has been placed. Total: {total}."
                return "The requested action has been completed in the business system."
            return (f"I can help with {company.name}. I have access to the business catalogue and order records, "
                    "but the AI language model is not configured yet. Please configure OPENAI_API_KEY to enable natural-language answers.")
        tone = getattr(company, "agent_tone", "friendly")
        system = ("You are the customer support assistant for this business. Answer only from the supplied business context. "
                  "Never invent stock, prices, order statuses, policies, operating hours or business capabilities. If information is missing, say you cannot confirm it and offer the configured support contact or human handover. "
                  "Ask concise follow-up questions when order details are missing. Clearly label recommendations as optional, base them only on available catalogue items and never add them without customer confirmation. "
                  "For health-related statements, do not diagnose, prescribe, or claim food/products are medically safe; use cautious wording and recommend a qualified professional. Respect customer choice and do not pressure purchases. "
                  "Do not claim an action was completed unless the action result confirms success. Business tone: " + tone + ". Greeting: " + (company.agent_greeting or "") + ". Support phone: " + (company.agent_support_phone or "not supplied") + ". Support email: " + (company.agent_support_email or "not supplied") + ". Context: " + json.dumps(context, default=str))
        messages = [{"role": "system", "content": system}]
        for row in history:
            role = row["role"] if row["role"] in ("user", "assistant") else "assistant"
            messages.append({"role": role, "content": row["content"]})
        if action_result:
            messages.append({"role": "system", "content": "Backend action result: " + json.dumps(action_result, default=str)})
        try:
            response = requests.post("https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": model, "messages": messages, "temperature": 0.2}, timeout=25)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
        except (requests.RequestException, KeyError, IndexError, ValueError):
            return "I’m having trouble responding right now. I can hand this conversation over to the business team."


class PublicAgentThrottle(AnonRateThrottle):
    scope = "agent_public"
    rate = "120/minute"

    def get_rate(self):
        try:
            return super().get_rate()
        except Exception:
            return "120/minute"


@method_decorator(xframe_options_exempt, name="dispatch")
class PublicAgentCatalogAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PublicAgentThrottle]

    def get(self, request, public_id):
        from companies.models import Company, ServiceArea
        from billing.services import get_access_state, check_company_monthly_limit
        from operations.whatsapp_agent import get_effective_service_areas
        company = get_object_or_404(Company, agent_public_id=public_id)
        if not company.agent_enabled or get_access_state(company) != "ok":
            return Response({"detail": "This business catalogue is not currently available."}, status=404)
        has_quota, _ = check_company_monthly_limit(company)
        rows = CatalogItem.objects.filter(company=company, is_available=True).select_related("inventory")[:300]
        result = []
        for item in rows:
            inventory = getattr(item, "inventory", None)
            result.append({
                "id": item.id, "name": item.name, "description": item.description,
                "price": str(item.price), "unit": item.unit,
                "in_stock": (inventory.is_unlimited or inventory.quantity > 0) if inventory else True,
            })
        areas = list(ServiceArea.objects.filter(company=company, is_active=True).values("name", "area_type", "city", "country", "radius_km", "delivery_fee"))
        if not areas:
            for zone_city in get_effective_service_areas(company):
                areas.append({
                    "name": zone_city,
                    "area_type": "city",
                    "city": zone_city,
                    "country": "Pakistan",
                    "radius_km": None,
                    "delivery_fee": "0.00",
                })
        return Response({
            "business": company.name,
            "items": result,
            "service_areas": areas,
            "can_order": "create_order" in (company.agent_allowed_actions or []),
            "can_handover": "handover" in (company.agent_allowed_actions or []),
            "monthly_limit_reached": not has_quota,
            "messages_used": company.messages_used,
            "message_limit": company.message_limit,
            "ai_paused": getattr(company, "is_ai_paused", False),
        })


@method_decorator(xframe_options_exempt, name="dispatch")
class PublicAgentChatAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PublicAgentThrottle]

    def post(self, request, public_id):
        import base64
        from companies.models import Company, CatalogItem
        from billing.services import get_access_state, consume_company_message
        from operations.audio_service import transcribe_audio, synthesize_speech, clean_text_for_tts, transliterate_to_roman_urdu
        from operations.whatsapp_agent import _generate_agent_reply, get_business_context_for_company

        company = get_object_or_404(Company, agent_public_id=public_id)
        if not company.agent_enabled:
            return Response(
                {
                    "error": "agent_disabled",
                    "detail": "This business assistant is not currently available.",
                    "message": "This business assistant is not currently available.",
                },
                status=404,
            )

        # Owner AI Pause Check
        if getattr(company, "is_ai_paused", False):
            return Response(
                {
                    "error": "ai_paused",
                    "detail": "This business's AI Voice Agent is currently paused by the owner. Please contact the business directly.",
                    "message": "This business's AI Voice Agent is currently paused by the owner. Please contact the business directly.",
                },
                status=403,
            )

        # 1. Billing access state check BEFORE calling STT/LLM/TTS
        if get_access_state(company) != "ok":
            return Response(
                {
                    "error": "subscription_inactive",
                    "detail": "This business's AI Voice Agent is temporarily unavailable due to an inactive subscription. Please contact the business directly.",
                    "message": "This business's AI Voice Agent is temporarily unavailable due to an inactive subscription. Please contact the business directly.",
                },
                status=402,
            )

        # 2. Monthly voice/message quota check & atomic consumption BEFORE STT/LLM/TTS
        try:
            consume_company_message(company)
        except Exception:
            return Response(
                {
                    "error": "monthly_limit_reached",
                    "detail": "This business's AI Voice Agent has reached its monthly usage limit. Please contact the business directly.",
                    "message": "This business's AI Voice Agent has reached its monthly usage limit. Please contact the business directly.",
                },
                status=402,
            )

        # 3. Accept customer audio (base64 or file upload) or speech-to-text transcript
        raw_audio = request.data.get("audio") or request.data.get("audio_base64") or request.FILES.get("audio")
        message = (request.data.get("message") or "").strip()
        transcript = None

        if raw_audio:
            audio_bytes = None
            if hasattr(raw_audio, "read"):
                audio_bytes = raw_audio.read()
            elif isinstance(raw_audio, str):
                if "," in raw_audio:
                    raw_audio = raw_audio.split(",", 1)[1]
                try:
                    audio_bytes = base64.b64decode(raw_audio)
                except Exception:
                    pass
            if audio_bytes and len(audio_bytes) > 50:
                transcript = transcribe_audio(audio_bytes, filename="voice.webm")
                if transcript and transcript.strip():
                    message = transcript.strip()

        if not message:
            return Response({"message": "A voice message or speech transcript is required."}, status=400)

        message = transliterate_to_roman_urdu(message)

        key = request.data.get("conversation_id")
        if key:
            conversation = get_object_or_404(AgentConversation, conversation_key=key, company=company)
        else:
            conversation = AgentConversation.objects.create(
                company=company,
                customer_name=str(request.data.get("customer_name", ""))[:160],
                customer_email=request.data.get("customer_email", ""),
                customer_phone=request.data.get("customer_phone", "")
            )

        AgentMessage.objects.create(
            conversation=conversation,
            role="user",
            content=message,
            metadata={"is_voice": True, "has_audio": bool(raw_audio)}
        )

        if conversation.status == "human":
            answer = "Your conversation has been handed to the business team. A team member will reply here."
            result = None
            return Response({
                "business": company.name,
                "conversation_id": str(conversation.conversation_key),
                "transcript": message,
                "reply_text": answer,
                "answer": answer,
                "status": conversation.status,
                "action_result": result,
                "menu_items": [],
                "order_summary": None,
                "audio_base64": None,
                "audio_url": None,
            })

        action = request.data.get("action") or {}
        if not action:
            match = re.search(r"\bRA-\d{6}-[A-F0-9]{8}\b", message, re.IGNORECASE)
            if match:
                action = {
                    "type": "lookup_order",
                    "order_number": match.group(0),
                    "customer_phone": conversation.customer_phone,
                    "customer_email": conversation.customer_email
                }

        result = self._public_action(company, conversation, action) if action else None

        biz_context = get_business_context_for_company(company)
        if result:
            biz_context["action_result"] = result

        if result and result.get("status") == "human":
            answer = "I’ve passed your conversation to the business team. A team member will reply here."
        else:
            # Shared multi-tenant category-aware AI agent
            api_key = getattr(settings, "OPENAI_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")
            if api_key and len(api_key.strip()) > 10:
                answer = _generate_agent_reply(
                    message_text=message,
                    customer_name=conversation.customer_name or "Valued Customer",
                    context=biz_context,
                    sender_phone=conversation.customer_phone or "",
                    is_voice_note=True,
                    record_turn=False,
                    conversation_obj=conversation,
                )
            else:
                helper = AgentChatAPIView()
                context = helper._business_context(company, conversation, include_customer_orders=False)
                history = list(conversation.messages.order_by("-created_at").values("role", "content")[:12])[::-1]
                answer = helper._generate_answer(company, context, history, result)

        # Extract structured details for read-only customer screen
        menu_items = []
        lower_ans = answer.lower()
        lower_msg = message.lower()

        is_asking_menu = any(
            kw in lower_msg for kw in [
                "menu", "catalog", "rate list", "price list", "kya items", "what do you have",
                "show items", "list items", "what's available", "what is available", "kya mil",
                "prices", "cost"
            ]
        )
        is_order_confirmation_or_address = any(
            kw in lower_ans for kw in [
                "address", "confirm your order", "placed your order", "order #", "order number",
                "order has been", "delivery address", "total is", "total is rs"
            ]
        ) or any(
            kw in lower_msg for kw in [
                "confirm", "hanjee", "bhej do", "yes", "my address", "deliver to", "phone"
            ]
        )

        should_return_menu = (
            is_asking_menu or (
                (lower_ans.count("rs.") >= 2 or lower_ans.count("rupees") >= 2 or lower_ans.count("•") >= 2)
            )
        ) and not is_order_confirmation_or_address

        if should_return_menu:
            catalog_rows = CatalogItem.objects.filter(company=company, is_available=True).select_related("inventory")[:8]
            for itm in catalog_rows:
                inventory = getattr(itm, "inventory", None)
                in_stock = (inventory.is_unlimited or inventory.quantity > 0) if inventory else True
                menu_items.append({
                    "id": itm.id,
                    "name": itm.name,
                    "price": str(itm.price),
                    "unit": itm.unit or "",
                    "description": itm.description or "",
                    "in_stock": in_stock,
                })

        order_summary = None
        if result and result.get("success") and result.get("order_number"):
            order_summary = {
                "order_number": result.get("order_number"),
                "total": str(result.get("total", "0.00")),
                "status": result.get("status", "confirmed"),
            }
        elif biz_context.get("order_summary"):
            order_summary = biz_context.get("order_summary")

        # Synthesize TTS voice reply
        audio_base64 = None
        audio_url = None
        tts_bytes = synthesize_speech(clean_text_for_tts(answer))
        if tts_bytes:
            audio_base64 = base64.b64encode(tts_bytes).decode("utf-8")
            audio_url = f"data:audio/mp3;base64,{audio_base64}"

        AgentMessage.objects.create(
            conversation=conversation,
            role="assistant",
            content=answer,
            metadata={
                "is_voice": True,
                "has_audio": bool(audio_base64),
                "action_result": result or {},
                "menu_items": menu_items,
                "order_summary": order_summary,
            }
        )

        return Response({
            "business": company.name,
            "conversation_id": str(conversation.conversation_key),
            "transcript": message,
            "reply_text": answer,
            "answer": answer,
            "audio_base64": audio_base64,
            "audio_url": audio_url,
            "menu_items": menu_items,
            "order_summary": order_summary,
            "status": conversation.status,
            "action_result": result,
        })

    def _public_action(self, company, conversation, action):
        name = action.get("type")
        enabled = set(company.agent_allowed_actions or [])
        result = {"success": False, "error": "This action is not enabled for this business."}
        if name == "create_order" and name in enabled:
            if action.get("confirmed") is not True:
                result["error"] = "Customer confirmation is required before creating an order."
                AgentActionLog.objects.create(company=company, conversation=conversation,
                    action=str(name), allowed=False, request_data=action, result_data=result)
                return result
            payload = action.get("data") or {}
            payload.setdefault("customer_name", conversation.customer_name)
            payload.setdefault("customer_email", conversation.customer_email)
            payload.setdefault("customer_phone", conversation.customer_phone)
            try:
                order = _create_order(company, payload, actor=None, source="agent")
                result = {"success": True, "order_number": order.order_number, "total": str(order.total)}
            except (CatalogItem.DoesNotExist, InvalidOperation, ValueError, KeyError) as exc:
                result = {"success": False, "error": str(exc)}
        elif name == "lookup_order" and name in enabled:
            number = str(action.get("order_number", "")).upper()
            contact = str(action.get("customer_phone", ""))
            email = str(action.get("customer_email", ""))
            qs = Order.objects.filter(company=company, order_number=number)
            if contact: qs = qs.filter(customer_phone=contact)
            elif email: qs = qs.filter(customer_email__iexact=email)
            else: qs = qs.none()
            order = qs.first()
            if order:
                delivery = getattr(order, "delivery", None)
                result = {"success": True, "order_number": order.order_number, "status": order.status,
                    "delivery_status": delivery.status if delivery else None,
                    "rider_name": (delivery.rider.get_full_name() or delivery.rider.username) if delivery else None}
            else:
                result = {"success": False, "error": "Order not found. Verify your order number and contact details."}
        elif name == "handover" and name in enabled:
            conversation.status = "human"
            conversation.save(update_fields=["status", "updated_at"])
            result = {"success": True, "status": "human"}
        AgentActionLog.objects.create(company=company, conversation=conversation,
            action=str(name or "unknown"), allowed=bool(result.get("success")),
            request_data=action, result_data=result)
        return result


class PublicAgentConversationAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PublicAgentThrottle]

    def get(self, request, public_id, conversation_id):
        from companies.models import Company
        company = get_object_or_404(Company, agent_public_id=public_id)
        if not company.agent_enabled or get_access_state(company) != "ok":
            return Response({"detail": "This business assistant is not currently available."}, status=404)
        conversation = get_object_or_404(AgentConversation, company=company, conversation_key=conversation_id)
        return Response({
            "status": conversation.status,
            "messages": [
                {
                    "role": message.role,
                    "content": message.content,
                    "created_at": message.created_at,
                    "metadata": message.metadata or {},
                }
                for message in conversation.messages.all()[:100]
            ]
        })


class AgentConversationListAPIView(BusinessAPIView):
    required_business_permission = "agent.view"

    def get(self, request):
        rows = AgentConversation.objects.filter(company=self.company).prefetch_related("messages").select_related("assigned_to")[:100]
        return Response([{
            "id": str(row.conversation_key), "customer_name": row.customer_name,
            "customer_email": row.customer_email, "customer_phone": row.customer_phone, "status": row.status,
            "assigned_to": row.assigned_to.get_full_name() if row.assigned_to else None,
            "created_at": row.created_at.isoformat(),
            "messages": [{"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()} for m in row.messages.all()],
        } for row in rows])

    def patch(self, request):
        key = request.data.get("conversation_id")
        row = get_object_or_404(AgentConversation, company=self.company, conversation_key=key)
        if not request.user.has_business_permission("agent.handover"):
            return Response({"detail": "Your role cannot manage handovers."}, status=403)
        new_status = request.data.get("status", "human")
        if new_status not in ("human", "bot", "closed"):
            return Response({"status": "Invalid conversation status."}, status=400)
        row.status = new_status
        row.assigned_to = request.user if new_status == "human" else None
        row.save(update_fields=["status", "assigned_to", "updated_at"])
        human_message = str(request.data.get("message", "")).strip()
        if human_message:
            AgentMessage.objects.create(conversation=row, role="human", content=human_message)
        AgentActionLog.objects.create(company=self.company, conversation=row, actor=request.user,
            action="conversation_handover", allowed=True, request_data={"status": new_status},
            result_data={"status": row.status})
        return Response({"id": str(row.conversation_key), "status": row.status})


@method_decorator(csrf_exempt, name="dispatch")
class WhatsAppWebhookAPIView(APIView):
    """
    Public webhook endpoint for Meta WhatsApp Cloud API.
    Handles verification handshake (GET) and incoming message dispatch (POST).
    URL: /api/operations/whatsapp/webhook/
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        """
        Meta Webhook verification handshake.
        Meta passes: hub.mode, hub.verify_token, hub.challenge
        """
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")

        logger.info(f"[WhatsApp Webhook Handshake] Received mode={mode}, token={token}, challenge={challenge}")

        # Check against Django settings, environment variable, or stored tenant tokens
        configured_token = getattr(settings, "WHATSAPP_VERIFY_TOKEN", None) or os.getenv(
            "WHATSAPP_VERIFY_TOKEN", "rides_default_verify_token"
        )
        is_token_valid = (token == configured_token) or is_valid_verify_token(token)

        if mode == "subscribe" and challenge and is_token_valid:
            logger.info("[WhatsApp Webhook] Handshake verified successfully.")
            return HttpResponse(challenge, content_type="text/plain", status=200)

        logger.warning(f"[WhatsApp Webhook] Handshake rejected for token: {token}, mode: {mode}")
        return HttpResponseForbidden("Verification failed")

    def post(self, request):
        """
        Receives incoming WhatsApp messages and notifications from Meta.
        Parses customer inquiries/order requests, triggers background AI agent processing,
        and returns an immediate HTTP 200 response to Meta.
        """
        try:
            if isinstance(request.data, dict):
                payload = request.data
            else:
                payload = json.loads(request.body.decode("utf-8"))
        except Exception as e:
            logger.error(f"[WhatsApp Webhook] Error parsing request JSON: {e}", exc_info=True)
            return JsonResponse({"status": "error", "message": "Invalid JSON"}, status=400)

        logger.info(f"[WhatsApp Webhook] Received event payload: {payload}")

        try:
            entries = payload.get("entry", []) if isinstance(payload, dict) else []
            for entry in entries:
                changes = entry.get("changes", [])
                for change in changes:
                    field = change.get("field", "messages")
                    value = change.get("value", {})
                    metadata = value.get("metadata", {})
                    phone_number_id = str(metadata.get("phone_number_id", "")).strip()

                    # Phase 2 Calling Webhook: route field == "calls"
                    if field == "calls":
                        from .calling import handle_calling_webhook_event
                        from companies.models import Company
                        cfg = get_config_by_phone_number_id(phone_number_id) or {}
                        company_id = cfg.get("company_id")
                        company_obj = Company.objects.filter(id=company_id).first() if company_id else None
                        handle_calling_webhook_event(value, company=company_obj)
                        continue

                    # Process status delivery events (sent, delivered, read, failed)
                    statuses = value.get("statuses", [])
                    if statuses:
                        for st in statuses:
                            wamid = st.get("id", "unknown_wamid")
                            st_val = st.get("status", "unknown")
                            recipient_id = str(st.get("recipient_id", "")).strip()
                            masked_recipient = f"...{recipient_id[-4:]}" if len(recipient_id) >= 4 else recipient_id

                            if st_val == "failed":
                                errors = st.get("errors", [])
                                logger.error(
                                    f"[WhatsApp Webhook Status ERROR] Message delivery failed! "
                                    f"wamid={wamid} | Recipient={masked_recipient} | Errors={json.dumps(errors)}"
                                )
                                print(
                                    f"[WhatsApp Delivery FAILED] wamid={wamid} | "
                                    f"Recipient={masked_recipient} | Errors={json.dumps(errors)}"
                                )
                            else:
                                logger.info(
                                    f"[WhatsApp Webhook Status] Message status update: "
                                    f"wamid={wamid} | Status={st_val} | Recipient={masked_recipient}"
                                )
                                print(
                                    f"[WhatsApp Status] wamid={wamid} | Status={st_val} | Recipient={masked_recipient}"
                                )

                    # If this payload contains only status updates and no messages, continue to next change
                    if "statuses" in value and "messages" not in value:
                        continue

                    messages = value.get("messages", [])
                    contacts = value.get("contacts", [])
                    sender_name = contacts[0].get("profile", {}).get("name", "Customer") if contacts else "Customer"

                    for msg in messages:
                        sender_phone = str(msg.get("from", "")).strip()
                        msg_type = msg.get("type")

                        # Extract content from text, interactive choices, or audio/voice media
                        content = ""
                        media_id = None
                        if msg_type == "text":
                            content = msg.get("text", {}).get("body", "").strip()
                        elif msg_type == "interactive":
                            interactive = msg.get("interactive", {})
                            content = (
                                interactive.get("button_reply", {}).get("title")
                                or interactive.get("list_reply", {}).get("title")
                                or ""
                            )
                        elif msg_type == "audio":
                            audio_data = msg.get("audio", {})
                            media_id = str(audio_data.get("id", "")).strip()
                            mime_type = audio_data.get("mime_type", "audio/ogg")
                            logger.info(
                                f"[WhatsApp Webhook Audio] Inbound voice note id={media_id}, mime={mime_type} "
                                f"from {sender_name} ({sender_phone})"
                            )
                            content = "[Voice Note]"
                        else:
                            content = f"[{msg_type} message]"

                        logger.info(
                            f"[WhatsApp Message] Phone ID: {phone_number_id} | Type: {msg_type} | "
                            f"From: {sender_name} ({sender_phone}) | Content: '{content}' | Media: {media_id}"
                        )

                        # Trigger background processing so Meta receives instant HTTP 200 within timeout window
                        if sender_phone and (content or media_id):
                            worker = threading.Thread(
                                target=process_incoming_whatsapp_message,
                                args=(sender_phone, content, phone_number_id, sender_name),
                                kwargs={"media_id": media_id, "msg_type": msg_type},
                                daemon=True,
                            )
                            worker.start()

        except Exception as e:
            logger.error(f"[WhatsApp Webhook] Error processing incoming payload: {e}", exc_info=True)

        return JsonResponse({"status": "success"}, status=200)


class WhatsAppSettingsAPIView(BusinessAPIView):
    """
    Authenticated settings endpoint for business owners to view and update
    their WhatsApp Cloud API credentials using temporary file storage.
    Handles missing settings gracefully for newly registered companies.
    URL: /api/operations/agent/whatsapp-settings/
    """
    permission_classes = [IsAuthenticated]

    def _is_authorized_owner(self, user):
        if not user or not user.is_authenticated:
            return False
        if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
            return True
        role = str(getattr(user, "role", "")).strip().lower()
        if role in (User.ROLE_OWNER.lower(), User.ROLE_SUPERADMIN.lower(), "owner", "admin"):
            return True
        if hasattr(user, "has_business_permission") and user.has_business_permission("can_manage_integrations"):
            return True
        return False

    def get(self, request):
        if not self._is_authorized_owner(request.user):
            return Response({"detail": "Only business owners can configure WhatsApp settings."}, status=403)

        company = getattr(request.user, "company", None)
        company_id = company.id if company else None

        try:
            config = get_whatsapp_config(company_id=company_id)
        except Exception as e:
            logger.warning(f"[WhatsApp Config] Error loading config for company {company_id}: {e}")
            config = {}

        if not config:
            config = {}

        verify_token = config.get("verify_token") or f"ridesai_wa_{company_id or 'default'}"

        return Response({
            "phone_number_id": config.get("phone_number_id", ""),
            "access_token": config.get("access_token", ""),
            "verify_token": verify_token,
            "is_active": config.get("is_active", False),
            "updated_at": config.get("updated_at", ""),
        }, status=200)

    def post(self, request):
        if not self._is_authorized_owner(request.user):
            return Response({"detail": "Only business owners can configure WhatsApp settings."}, status=403)

        # Basic input validation — phone_number_id and access_token are required
        phone_number_id = str(request.data.get("phone_number_id", "")).strip()
        access_token = str(request.data.get("access_token", "")).strip()

        if not phone_number_id or not access_token:
            return Response(
                {"status": "error", "message": "Both 'phone_number_id' and 'access_token' are required fields."},
                status=400,
            )

        company = getattr(request.user, "company", None)
        company_id = company.id if company else None

        try:
            updated = save_whatsapp_config(request.data, company_id=company_id)
        except Exception as e:
            logger.error(f"[WhatsApp Config] Failed to save config for company {company_id}: {e}", exc_info=True)
            return Response(
                {"status": "error", "message": "Failed to save WhatsApp configuration. Please try again."},
                status=500,
            )

        return Response({
            "status": "success",
            "message": "WhatsApp settings updated successfully.",
            "data": updated,
        }, status=200)


@method_decorator(xframe_options_exempt, name="dispatch")
class PublicAgentWidgetScriptAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, public_id):
        from companies.models import Company
        company = get_object_or_404(Company, agent_public_id=public_id)

        frontend_url = os.environ.get("FRONTEND_URL") or getattr(settings, "FRONTEND_URL", None) or getattr(settings, "SITE_URL", "http://localhost:5173")
        frontend_url = frontend_url.rstrip("/")
        iframe_url = f"{frontend_url}/agent/{company.agent_public_id}?embed=1"
        safe_biz_name = (company.name or "Store").replace("\\", "\\\\").replace('"', '\\"').replace("'", "\\'")

        js_content = f"""(function() {{
    if (window.__RIDES_AI_WIDGET_LOADED__) return;
    window.__RIDES_AI_WIDGET_LOADED__ = true;

    var iframeUrl = "{iframe_url}";
    var bizName = "{safe_biz_name}";

    var container = document.createElement("div");
    container.id = "rides-ai-widget-root";
    container.style.cssText = "position:fixed;bottom:20px;right:20px;z-index:999999;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;";

    var tooltip = document.createElement("div");
    tooltip.id = "rides-ai-widget-tooltip";
    tooltip.innerHTML = '<span>Talk to ' + bizName + ' AI 🎤</span>';
    tooltip.style.cssText = "position:absolute;bottom:70px;right:0;background:#ffffff;color:#1e293b;padding:8px 14px;border-radius:20px;box-shadow:0 4px 16px rgba(0,0,0,0.12);border:1px solid #ff77ff;font-size:13px;font-weight:600;white-space:nowrap;pointer-events:none;transition:all 0.3s ease;opacity:1;transform:translateY(0);display:flex;align-items:center;gap:6px;";

    var btn = document.createElement("button");
    btn.id = "rides-ai-widget-btn";
    btn.setAttribute("aria-label", "Open " + bizName + " Voice Assistant");
    btn.innerHTML = '<span id="rides-ai-icon-mic" style="font-size:26px;line-height:1;">🎤</span><span id="rides-ai-icon-close" style="font-size:24px;line-height:1;display:none;color:#ffffff;">✕</span>';
    btn.style.cssText = "width:60px;height:60px;border-radius:50%;background:#ff77ff;border:none;box-shadow:0 6px 20px rgba(255,119,255,0.45);cursor:pointer;display:flex;align-items:center;justify-content:center;transition:transform 0.2s cubic-bezier(0.34,1.56,0.64,1),box-shadow 0.2s;outline:none;";
    btn.onmouseenter = function() {{ btn.style.transform = "scale(1.08)"; }};
    btn.onmouseleave = function() {{ btn.style.transform = "scale(1)"; }};

    var popup = document.createElement("div");
    popup.id = "rides-ai-widget-popup";
    popup.style.cssText = "display:none;position:absolute;bottom:75px;right:0;width:380px;height:600px;max-width:calc(100vw - 32px);max-height:calc(100vh - 100px);background:#ffffff;border-radius:20px;box-shadow:0 12px 40px rgba(0,0,0,0.18);border:1px solid rgba(255,119,255,0.3);overflow:hidden;flex-direction:column;transition:opacity 0.25s ease,transform 0.25s ease;transform:translateY(10px);opacity:0;";

    var styleTag = document.createElement("style");
    styleTag.textContent = "@media (max-width: 480px) {{ #rides-ai-widget-popup {{ width: 100vw !important; height: 92vh !important; max-width: 100vw !important; max-height: 92vh !important; bottom: 0 !important; right: 0 !important; border-radius: 20px 20px 0 0 !important; position: fixed !important; }} #rides-ai-widget-root {{ bottom: 16px !important; right: 16px !important; }} }}";
    document.head.appendChild(styleTag);

    var header = document.createElement("div");
    header.style.cssText = "height:48px;background:linear-gradient(135deg,#ff77ff 0%,#ff55bb 100%);color:#ffffff;display:flex;align-items:center;justify-content:space-between;padding:0 16px;box-shadow:0 2px 8px rgba(0,0,0,0.06);";
    header.innerHTML = '<div style="display:flex;align-items:center;gap:8px;font-weight:600;font-size:14px;"><span>🎤</span><span>' + bizName + '</span></div>';

    var closeHeaderBtn = document.createElement("button");
    closeHeaderBtn.innerHTML = "✕";
    closeHeaderBtn.setAttribute("aria-label", "Close Voice Assistant");
    closeHeaderBtn.style.cssText = "background:none;border:none;color:#ffffff;font-size:18px;cursor:pointer;padding:4px 8px;border-radius:4px;";
    header.appendChild(closeHeaderBtn);

    var iframe = document.createElement("iframe");
    iframe.src = iframeUrl;
    iframe.allow = "microphone; autoplay";
    iframe.style.cssText = "width:100%;height:calc(100% - 48px);border:none;background:#fafafa;";

    popup.appendChild(header);
    popup.appendChild(iframe);

    container.appendChild(tooltip);
    container.appendChild(popup);
    container.appendChild(btn);
    document.body.appendChild(container);

    var isOpen = false;
    function setWidgetOpen(open) {{
        isOpen = open;
        var micIcon = document.getElementById("rides-ai-icon-mic");
        var closeIcon = document.getElementById("rides-ai-icon-close");
        if (isOpen) {{
            popup.style.display = "flex";
            setTimeout(function() {{
                popup.style.transform = "translateY(0)";
                popup.style.opacity = "1";
            }}, 10);
            if (tooltip) tooltip.style.display = "none";
            if (micIcon) micIcon.style.display = "none";
            if (closeIcon) closeIcon.style.display = "block";
            btn.style.background = "#475569";
        }} else {{
            popup.style.transform = "translateY(10px)";
            popup.style.opacity = "0";
            setTimeout(function() {{
                popup.style.display = "none";
            }}, 250);
            if (micIcon) micIcon.style.display = "block";
            if (closeIcon) closeIcon.style.display = "none";
            btn.style.background = "#ff77ff";
        }}
    }}

    btn.addEventListener("click", function() {{ setWidgetOpen(!isOpen); }});
    closeHeaderBtn.addEventListener("click", function() {{ setWidgetOpen(false); }});

    window.RidesAIWidget = {{
        open: function() {{ setWidgetOpen(true); }},
        close: function() {{ setWidgetOpen(false); }},
        toggle: function() {{ setWidgetOpen(!isOpen); }}
    }};
}})();
"""
        response = HttpResponse(js_content, content_type="application/javascript; charset=utf-8")
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response["Access-Control-Allow-Headers"] = "*"
        return response


class OrderAutoAssignRiderAPIView(BusinessAPIView):
    required_business_permission = None

    def post(self, request, order_id):
        order = get_object_or_404(Order, pk=order_id, company=self.company)

        from django.db.models import Q
        from accounts.models import User
        from operations.services.dispatch_service import assign_best_rider

        rider_filter = (
            Q(role="rider")
            | Q(staff_role__name__iexact="rider")
            | Q(staff_role__name__iexact="delivery boy")
            | Q(staff_role__name__iexact="delivery")
        )
        has_riders = User.objects.filter(company=self.company, is_active=True).filter(rider_filter).exists()
        if not has_riders:
            return Response(
                {
                    "error": "No active riders available. Please add a rider in Employees.",
                    "detail": "No active riders available. Please add a rider in Employees.",
                },
                status=400,
            )

        rider = assign_best_rider(order)
        if not rider:
            return Response(
                {
                    "error": "No active riders available. Please add a rider in Employees.",
                    "detail": "No active riders available. Please add a rider in Employees.",
                },
                status=400,
            )

        assignment, _ = DeliveryAssignment.objects.update_or_create(
            order=order,
            defaults={
                "company": self.company,
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
        }, status=200)



