import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone


class Order(models.Model):
    STATUS_NEW = "new"
    STATUS_PENDING = "pending"
    STATUS_CONFIRMED = "confirmed"
    STATUS_PREPARING = "preparing"
    STATUS_PREPARED = "prepared"
    STATUS_READY = "ready"
    STATUS_ASSIGNED = "assigned"
    STATUS_PICKED_UP = "picked_up"
    STATUS_ON_THE_WAY = "on_the_way"
    STATUS_OUT_FOR_DELIVERY = "out_for_delivery"
    STATUS_DELIVERED = "delivered"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [(x, x.replace("_", " ").title()) for x in (
        STATUS_NEW, STATUS_PENDING, STATUS_CONFIRMED, STATUS_PREPARING,
        STATUS_PREPARED, STATUS_READY, STATUS_ASSIGNED, STATUS_PICKED_UP,
        STATUS_ON_THE_WAY, STATUS_OUT_FOR_DELIVERY, STATUS_DELIVERED, STATUS_CANCELLED,
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
    assigned_rider = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_deliveries",
    )
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
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="dispatched_deliveries")
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


class Customer(models.Model):
    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, related_name="customers")
    phone = models.CharField(max_length=40, db_index=True)
    name = models.CharField(max_length=160, blank=True)
    daily_voice_count = models.IntegerField(default=0)
    last_voice_date = models.DateField(null=True, blank=True)
    daily_text_count = models.IntegerField(default=0)
    last_text_date = models.DateField(null=True, blank=True)
    daily_call_count = models.IntegerField(default=0)
    last_call_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("company", "phone")
        indexes = [
            models.Index(fields=["company", "phone"], name="op_cust_comp_phone_idx"),
        ]

    def __str__(self):
        return f"{self.name or self.phone} ({self.company.name})"


class AgentConversation(models.Model):
    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, related_name="agent_conversations")
    conversation_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    customer_name = models.CharField(max_length=160, blank=True)
    customer_email = models.EmailField(blank=True)
    customer_phone = models.CharField(max_length=40, blank=True)
    daily_voice_count = models.IntegerField(default=0)
    last_voice_date = models.DateField(null=True, blank=True)
    daily_text_count = models.IntegerField(default=0)
    last_text_date = models.DateField(null=True, blank=True)
    daily_call_count = models.IntegerField(default=0)
    last_call_date = models.DateField(null=True, blank=True)
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
        ordering = ("created_at", "id")


class AgentActionLog(models.Model):
    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, related_name="agent_action_logs")
    conversation = models.ForeignKey(AgentConversation, null=True, blank=True, on_delete=models.SET_NULL)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=80)
    allowed = models.BooleanField(default=False)
    request_data = models.JSONField(default=dict, blank=True)
    result_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


# ============================================================================
# Phase 2: WhatsApp Live Calling Models
# ============================================================================

class VoiceCall(models.Model):
    DIRECTION_CHOICES = [
        ("inbound", "Inbound"),
        ("outbound", "Outbound"),
    ]
    STATUS_CHOICES = [
        ("initiated", "Initiated"),
        ("ringing", "Ringing"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
        ("terminated", "Terminated"),
        ("failed", "Failed"),
    ]

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="voice_calls",
    )
    call_id = models.CharField(max_length=128, unique=True, db_index=True)
    customer_phone = models.CharField(max_length=32, db_index=True)
    direction = models.CharField(max_length=16, choices=DIRECTION_CHOICES, default="inbound")
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default="initiated")
    sdp_offer = models.TextField(blank=True, default="")
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(default=0)
    error_code = models.CharField(max_length=32, blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["company", "status", "-created_at"], name="op_call_comp_status_idx"),
            models.Index(fields=["customer_phone", "-created_at"], name="op_call_phone_idx"),
        ]

    def __str__(self):
        return f"Call {self.call_id} ({self.status}) - {self.customer_phone}"


class CallPermission(models.Model):
    PERMISSION_TYPE_CHOICES = [
        ("template_request", "Template Request"),
        ("profile_opt_in", "Profile Opt-In"),
        ("inbound_call", "Inbound Call"),
    ]

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="call_permissions",
    )
    customer_phone = models.CharField(max_length=32, db_index=True)
    permission_type = models.CharField(
        max_length=32,
        choices=PERMISSION_TYPE_CHOICES,
        default="template_request",
    )
    is_granted = models.BooleanField(default=False)
    granted_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("company", "customer_phone")
        ordering = ("-created_at",)

    def __str__(self):
        status_text = "Granted" if self.is_granted else "Denied"
        return f"CallPermission {self.customer_phone} ({status_text}) - {self.company.name}"


class CallEvent(models.Model):
    call = models.ForeignKey(VoiceCall, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=64)
    raw_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "id")

    def __str__(self):
        return f"CallEvent {self.event_type} on {self.call.call_id} @ {self.created_at}"


class OrderPrintLog(models.Model):
    SLIP_INVOICE = "invoice"
    SLIP_KOT = "kot"
    SLIP_CHOICES = [
        (SLIP_INVOICE, "Customer Invoice"),
        (SLIP_KOT, "Kitchen Order Ticket"),
    ]

    MODE_BROWSER = "browser"
    MODE_ESCPOS_LOCAL = "escpos_local"
    MODE_CHOICES = [
        (MODE_BROWSER, "Browser Print"),
        (MODE_ESCPOS_LOCAL, "Local ESC/POS Spooler"),
    ]

    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
    ]

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="order_print_logs",
    )
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="print_logs",
    )
    slip_type = models.CharField(max_length=20, choices=SLIP_CHOICES, default=SLIP_INVOICE)
    print_mode = models.CharField(max_length=20, choices=MODE_CHOICES, default=MODE_BROWSER)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SUCCESS)
    error_message = models.TextField(blank=True, default="")
    printed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="order_prints",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"PrintLog #{self.order.order_number} [{self.slip_type.upper()}] ({self.status})"


class MedicineBatch(models.Model):
    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="medicine_batches",
        db_index=True,
    )
    item = models.ForeignKey(
        "companies.CatalogItem",
        on_delete=models.CASCADE,
        related_name="medicine_batches",
    )
    batch_number = models.CharField(max_length=100)
    expiry_date = models.DateField()
    quantity = models.PositiveIntegerField(default=0)
    supplier_name = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("expiry_date",)
        indexes = [
            models.Index(fields=["company", "expiry_date"]),
            models.Index(fields=["company", "batch_number"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "item", "batch_number"],
                name="unique_pharmacy_batch_per_item",
            )
        ]

    @property
    def status(self) -> str:
        from datetime import date, timedelta
        today = date.today()
        if self.expiry_date < today:
            return "expired"
        elif self.expiry_date <= today + timedelta(days=30):
            return "expiring_soon"
        return "safe"

    def __str__(self):
        return f"Batch {self.batch_number} - {self.item.name} ({self.status})"


class Prescription(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_DISPENSED = "dispensed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending Review"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_DISPENSED, "Dispensed"),
    ]

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="prescriptions",
        db_index=True,
    )
    prescription_number = models.CharField(max_length=32, unique=True, editable=False)
    customer_name = models.CharField(max_length=255, blank=True, default="")
    customer_phone = models.CharField(max_length=32, db_index=True)
    requested_items_text = models.TextField(blank=True, default="")
    prescription_image_url = models.TextField(blank=True, default="")
    notes = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    pharmacist_notes = models.TextField(blank=True, default="")
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_prescriptions",
    )
    linked_order = models.ForeignKey(
        Order,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="prescriptions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["company", "status", "-created_at"]),
        ]

    def save(self, *args, **kwargs):
        if not self.prescription_number:
            self.prescription_number = f"RX-{timezone.now():%y%m%d}-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.prescription_number} ({self.customer_phone}) - {self.status}"


# ============================================================================
# Phase 3: Clinic & Hospital Models
# ============================================================================

class Doctor(models.Model):
    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="doctors",
        db_index=True,
    )
    name = models.CharField(max_length=255)
    specialty = models.CharField(max_length=150)
    qualification = models.CharField(max_length=255, blank=True, default="")
    consultation_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    available_days = models.CharField(max_length=255, default="Mon-Sat")
    available_hours = models.CharField(max_length=150, default="10:00 AM - 06:00 PM")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)
        indexes = [
            models.Index(fields=["company", "is_active", "specialty"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.specialty})"


class Patient(models.Model):
    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="patients",
        db_index=True,
    )
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=32, db_index=True)
    age = models.PositiveIntegerField(null=True, blank=True)
    gender = models.CharField(max_length=20, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["company", "phone"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["company", "phone"], name="unique_patient_phone_per_company")
        ]

    def __str__(self):
        return f"{self.name} ({self.phone})"


class Appointment(models.Model):
    STATUS_PENDING = "pending"
    STATUS_CONFIRMED = "confirmed"
    STATUS_CHECKED_IN = "checked_in"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"
    STATUS_NO_SHOW = "no_show"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_CHECKED_IN, "Checked In"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_NO_SHOW, "No Show"),
    ]

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="appointments",
        db_index=True,
    )
    appointment_number = models.CharField(max_length=32, unique=True, editable=False)
    doctor = models.ForeignKey(
        Doctor,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="appointments",
    )
    patient = models.ForeignKey(
        Patient,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="appointments",
    )
    patient_name = models.CharField(max_length=255)
    patient_phone = models.CharField(max_length=32, db_index=True)
    appointment_date = models.DateField(null=True, blank=True)
    appointment_time = models.CharField(max_length=50, blank=True, default="")
    reason = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    staff_notes = models.TextField(blank=True, default="")
    source = models.CharField(max_length=50, default="dashboard")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["company", "status", "-created_at"]),
            models.Index(fields=["company", "appointment_date"]),
        ]

    def save(self, *args, **kwargs):
        if not self.appointment_number:
            self.appointment_number = f"APT-{timezone.now():%y%m%d}-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        doc = self.doctor.name if self.doctor else "Unassigned"
        return f"{self.appointment_number} - {self.patient_name} with {doc} ({self.status})"




