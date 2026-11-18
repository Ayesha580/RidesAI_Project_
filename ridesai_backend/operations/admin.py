from django.contrib import admin
from .models import (
    Order, OrderItem, DeliveryAssignment, OrderEvent,
    AgentConversation, AgentMessage, AgentActionLog,
    VoiceCall, CallPermission, CallEvent, OrderPrintLog
)


@admin.register(VoiceCall)
class VoiceCallAdmin(admin.ModelAdmin):
    list_display = ("call_id", "company", "customer_phone", "direction", "status", "duration_seconds", "created_at")
    list_filter = ("status", "direction", "company")
    search_fields = ("call_id", "customer_phone")
    readonly_fields = ("created_at", "updated_at")


@admin.register(CallPermission)
class CallPermissionAdmin(admin.ModelAdmin):
    list_display = ("company", "customer_phone", "permission_type", "is_granted", "granted_at", "expires_at")
    list_filter = ("is_granted", "permission_type", "company")
    search_fields = ("customer_phone",)


@admin.register(CallEvent)
class CallEventAdmin(admin.ModelAdmin):
    list_display = ("call", "event_type", "created_at")
    list_filter = ("event_type",)
    search_fields = ("call__call_id", "event_type")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "company", "customer_name", "customer_phone", "status", "assigned_rider", "total", "source", "created_at")
    list_filter = ("status", "source", "company", "assigned_rider")
    search_fields = ("order_number", "customer_name", "customer_phone", "assigned_rider__username")


@admin.register(AgentConversation)
class AgentConversationAdmin(admin.ModelAdmin):
    list_display = ("conversation_key", "company", "customer_name", "customer_phone", "status", "created_at")
    list_filter = ("status", "company")
    search_fields = ("customer_phone", "customer_name")


@admin.register(OrderPrintLog)
class OrderPrintLogAdmin(admin.ModelAdmin):
    list_display = ("order", "company", "slip_type", "print_mode", "status", "printed_by", "created_at")
    list_filter = ("slip_type", "print_mode", "status", "company")
    search_fields = ("order__order_number", "company__name")
    readonly_fields = ("created_at",)
