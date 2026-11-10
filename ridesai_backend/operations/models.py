import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone


class Order(models.Model):
    STATUS_NEW = "new"
    STATUS_CONFIRMED = "confirmed"
    STATUS_PREPARING = "preparing"
    STATUS_READY = "ready"
    STATUS_ASSIGNED = "assigned"
    STATUS_PICKED_UP = "picked_up"
    STATUS_ON_THE_WAY = "on_the_way"
    STATUS_DELIVERED = "delivered"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [(x, x.replace("_", " ").title()) for x in (
        STATUS_NEW, STATUS_CONFIRMED, STATUS_PREPARING, STATUS_READY,
        STATUS_ASSIGNED, STATUS_PICKED_UP, STATUS_ON_THE_WAY,
        STATUS_DELIVERED, STATUS_CANCELLED,
    )]

    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, related_name="orders")
    order_number = models.CharField(max_length=24, unique=True, editable=False)
    customer_name = models.CharField(max_length=160)
    customer_email = models.EmailField(blank=True)
    customer_phone = models.CharField(max_length=40, blank=True)
    delivery_address = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_NEW, db_index=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    delivery_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    source = models.CharField(max_length=20, default="dashboard", choices=[("dashboard", "Dashboard"), ("agent", "AI Agent"), ("api", "API")])
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_orders")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_business_orders")
    assigned_team = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["company", "status", "-created_at"], name="op_order_comp_status_idx")]

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = f"RA-{timezone.now():%y%m%d}-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.order_number


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    item = models.ForeignKey("companies.CatalogItem", null=True, blank=True, on_delete=models.SET_NULL)
    item_name = models.CharField(max_length=200)
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)


class DeliveryAssignment(models.Model):
    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, related_name="delivery_assignments")
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="delivery")
    rider = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="delivery_assignments")
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_deliveries")
    status = models.CharField(max_length=20, choices=Order.STATUS_CHOICES, default=Order.STATUS_ASSIGNED)
    assigned_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class OrderEvent(models.Model):
    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, related_name="order_events")
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    event_type = models.CharField(max_length=60)
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20, blank=True)
    note = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class AgentConversation(models.Model):
    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, related_name="agent_conversations")
    conversation_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    customer_name = models.CharField(max_length=160, blank=True)
    customer_email = models.EmailField(blank=True)
    customer_phone = models.CharField(max_length=40, blank=True)
    status = models.CharField(max_length=20, choices=[("bot", "Bot"), ("human", "Human handover"), ("closed", "Closed")], default="bot")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="agent_handover_conversations")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class AgentMessage(models.Model):
    conversation = models.ForeignKey(AgentConversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=20, choices=[("user", "User"), ("assistant", "Assistant"), ("system", "System"), ("human", "Human")])
    content = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)


class AgentActionLog(models.Model):
    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, related_name="agent_action_logs")
    conversation = models.ForeignKey(AgentConversation, null=True, blank=True, on_delete=models.SET_NULL)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=80)
    allowed = models.BooleanField(default=False)
    request_data = models.JSONField(default=dict, blank=True)
    result_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
