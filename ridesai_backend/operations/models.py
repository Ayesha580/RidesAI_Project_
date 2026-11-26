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

    ORDER_TYPE_DELIVERY = "delivery"
    ORDER_TYPE_DINE_IN = "dine_in"
    ORDER_TYPE_TAKEAWAY = "takeaway"
    ORDER_TYPE_CHOICES = [
        (ORDER_TYPE_DELIVERY, "Delivery"),
        (ORDER_TYPE_DINE_IN, "Dine-In"),
        (ORDER_TYPE_TAKEAWAY, "Takeaway"),
    ]

    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, related_name="orders")
    order_number = models.CharField(max_length=24, unique=True, editable=False)
    order_type = models.CharField(max_length=20, choices=ORDER_TYPE_CHOICES, default=ORDER_TYPE_DELIVERY, db_index=True)
    table_number = models.CharField(max_length=40, blank=True, default="")
    table = models.ForeignKey(
        "operations.RestaurantTable",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="orders",
    )
    customer_name = models.CharField(max_length=160)
    customer_email = models.EmailField(blank=True)
    customer_phone = models.CharField(max_length=40, blank=True)
    delivery_address = models.TextField(blank=True)
    delivery_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    delivery_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_NEW, db_index=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    delivery_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    source = models.CharField(max_length=20, default="dashboard", choices=[("dashboard", "Dashboard"), ("agent", "AI Agent"), ("api", "API")])
    prep_started_at = models.DateTimeField(null=True, blank=True)
    ready_at = models.DateTimeField(null=True, blank=True)
    dispatched_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    cod_collected = models.BooleanField(default=False)
    cod_settled = models.BooleanField(default=False)
    cod_settled_at = models.DateTimeField(null=True, blank=True)
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
    selected_modifiers = models.JSONField(default=list, blank=True)
    item_notes = models.TextField(blank=True, default="")


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
    delivery_address = models.TextField(blank=True, default="")
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
    STATUS_SCHEDULED = "scheduled"
    STATUS_CONFIRMED = "confirmed"
    STATUS_CHECKED_IN = "checked_in"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"
    STATUS_NO_SHOW = "no_show"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_SCHEDULED, "Scheduled"),
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


class ReturnRequest(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_COMPLETED = "completed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_COMPLETED, "Completed"),
    ]

    TYPE_RETURN = "return"
    TYPE_EXCHANGE = "exchange"

    TYPE_CHOICES = [
        (TYPE_RETURN, "Return"),
        (TYPE_EXCHANGE, "Exchange"),
    ]

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="return_requests",
        db_index=True,
    )
    return_number = models.CharField(max_length=32, unique=True, editable=False)
    order = models.ForeignKey(
        Order,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="return_requests",
    )
    order_number = models.CharField(max_length=64, blank=True, default="")
    customer_name = models.CharField(max_length=255, blank=True, default="")
    customer_phone = models.CharField(max_length=32, db_index=True)
    item_summary = models.TextField(blank=True, default="")
    reason = models.TextField()
    request_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default=TYPE_RETURN,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    staff_notes = models.TextField(blank=True, default="")
    replacement_order = models.ForeignKey(
        Order,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="exchange_requests",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["company", "status", "-created_at"]),
            models.Index(fields=["company", "customer_phone"]),
        ]

    def save(self, *args, **kwargs):
        if not self.return_number:
            self.return_number = f"RET-{timezone.now():%y%m%d}-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.return_number} - {self.customer_name} ({self.request_type}: {self.status})"


# ============================================================================
# Hospital Vertical Models: Departments, Wards/Beds & Lab/Diagnostic Bookings
# ============================================================================

class HospitalDepartment(models.Model):
    WARD_OPD = "opd"
    WARD_EMERGENCY = "emergency"
    WARD_ICU = "icu"
    WARD_GENERAL = "general_ward"
    WARD_MATERNITY = "maternity"
    WARD_DIAGNOSTICS = "diagnostics"

    WARD_TYPE_CHOICES = [
        (WARD_OPD, "OPD"),
        (WARD_EMERGENCY, "Emergency"),
        (WARD_ICU, "ICU"),
        (WARD_GENERAL, "General Ward"),
        (WARD_MATERNITY, "Maternity"),
        (WARD_DIAGNOSTICS, "Lab / Diagnostics"),
    ]

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="hospital_departments",
        db_index=True,
    )
    name = models.CharField(max_length=150)
    ward_type = models.CharField(max_length=24, choices=WARD_TYPE_CHOICES, default=WARD_OPD)
    floor_or_location = models.CharField(max_length=120, blank=True, default="")
    total_beds = models.PositiveIntegerField(default=0)
    available_beds = models.PositiveIntegerField(default=0)
    is_24_7 = models.BooleanField(default=False)
    head_doctor = models.ForeignKey(
        Doctor,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="headed_departments",
    )
    phone_extension = models.CharField(max_length=32, blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)
        indexes = [
            models.Index(fields=["company", "is_active", "ward_type"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["company", "name"], name="unique_hospital_department_per_company")
        ]

    def save(self, *args, **kwargs):
        if self.available_beds > self.total_beds:
            self.available_beds = self.total_beds
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.available_beds}/{self.total_beds} beds)"


class LabTestBooking(models.Model):
    STATUS_SCHEDULED = "scheduled"
    STATUS_CHECKED_IN = "checked_in"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_SCHEDULED, "Scheduled"),
        (STATUS_CHECKED_IN, "Checked In"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="lab_test_bookings",
        db_index=True,
    )
    booking_number = models.CharField(max_length=32, unique=True, editable=False)
    patient = models.ForeignKey(
        Patient,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="lab_bookings",
    )
    department = models.ForeignKey(
        HospitalDepartment,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="lab_bookings",
    )
    patient_name = models.CharField(max_length=255)
    patient_phone = models.CharField(max_length=32, db_index=True)
    test_name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    scheduled_date = models.DateField(null=True, blank=True)
    scheduled_time = models.CharField(max_length=50, blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SCHEDULED, db_index=True)
    notes = models.TextField(blank=True, default="")
    source = models.CharField(max_length=20, default="dashboard")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["company", "status", "-created_at"]),
            models.Index(fields=["company", "patient_phone"]),
        ]

    def save(self, *args, **kwargs):
        if not self.booking_number:
            self.booking_number = f"LAB-{timezone.now():%y%m%d}-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.booking_number} - {self.test_name} ({self.patient_name})"


# ============================================================================
# Owner-Editable Notification Templates & Per-Event Toggles (Multi-Tenant)
# ============================================================================

class NotificationTemplate(models.Model):
    EVENT_ORDER_CONFIRMED = "order_confirmed"
    EVENT_ORDER_PREPARING = "order_preparing"
    EVENT_OUT_FOR_DELIVERY = "out_for_delivery"
    EVENT_ORDER_DELIVERED = "order_delivered"
    EVENT_ORDER_CANCELLED = "order_cancelled"
    EVENT_APPOINTMENT_CONFIRMED = "appointment_confirmed"
    EVENT_APPOINTMENT_REMINDER = "appointment_reminder"
    EVENT_LAB_BOOKING_CONFIRMED = "lab_booking_confirmed"

    EVENT_TYPE_CHOICES = [
        (EVENT_ORDER_CONFIRMED, "Order Confirmed"),
        (EVENT_ORDER_PREPARING, "Order Preparing"),
        (EVENT_OUT_FOR_DELIVERY, "Out for Delivery"),
        (EVENT_ORDER_DELIVERED, "Order Delivered"),
        (EVENT_ORDER_CANCELLED, "Order Cancelled"),
        (EVENT_APPOINTMENT_CONFIRMED, "Appointment Confirmed"),
        (EVENT_APPOINTMENT_REMINDER, "Appointment Reminder"),
        (EVENT_LAB_BOOKING_CONFIRMED, "Lab Booking Confirmed"),
    ]

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="notification_templates",
        db_index=True,
    )
    event_type = models.CharField(max_length=40, choices=EVENT_TYPE_CHOICES, db_index=True)
    is_enabled = models.BooleanField(default=True)
    whatsapp_enabled = models.BooleanField(default=True)
    email_enabled = models.BooleanField(default=True)
    subject_template = models.CharField(max_length=255, blank=True, default="")
    body_template = models.TextField(blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("event_type",)
        constraints = [
            models.UniqueConstraint(
                fields=["company", "event_type"],
                name="unique_notification_template_per_company_event",
            )
        ]

    def __str__(self):
        return f"{self.company_id}:{self.event_type} (enabled={self.is_enabled})"


# ============================================================================
# Automated AI FAQ Suggestions & Continuous Learning Loop (Multi-Tenant)
# ============================================================================

class SuggestedFAQ(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_DISMISSED = "dismissed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_DISMISSED, "Dismissed"),
    ]

    CHANNEL_PUBLIC_WEB = "public_web"
    CHANNEL_WIDGET = "widget"
    CHANNEL_WHATSAPP = "whatsapp"
    CHANNEL_CHOICES = [
        (CHANNEL_PUBLIC_WEB, "Public Web"),
        (CHANNEL_WIDGET, "Website Widget"),
        (CHANNEL_WHATSAPP, "WhatsApp"),
    ]

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="suggested_faqs",
        db_index=True,
    )
    question = models.TextField()
    suggested_answer = models.TextField(blank=True, default="")
    source_channel = models.CharField(
        max_length=24,
        choices=CHANNEL_CHOICES,
        default=CHANNEL_PUBLIC_WEB,
    )
    occurrence_count = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    approved_knowledge = models.ForeignKey(
        "companies.BusinessKnowledge",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="source_suggestions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-occurrence_count", "-updated_at")
        indexes = [
            models.Index(fields=["company", "status", "-occurrence_count"]),
        ]

    def __str__(self):
        return f"[{self.company_id}] ({self.status} x{self.occurrence_count}) {self.question[:60]}"


# ============================================================================
# Restaurant Visual Floor-Plan Table Layout Model (Multi-Tenant)
# ============================================================================

class RestaurantTable(models.Model):
    STATUS_AVAILABLE = "available"
    STATUS_OCCUPIED = "occupied"
    STATUS_RESERVED = "reserved"
    STATUS_CLEANING = "cleaning"
    STATUS_CHOICES = [
        (STATUS_AVAILABLE, "Available"),
        (STATUS_OCCUPIED, "Occupied"),
        (STATUS_RESERVED, "Reserved"),
        (STATUS_CLEANING, "Cleaning"),
    ]

    SECTION_INDOOR = "indoor"
    SECTION_OUTDOOR = "outdoor"
    SECTION_VIP = "vip"
    SECTION_ROOFTOP = "rooftop"
    SECTION_CHOICES = [
        (SECTION_INDOOR, "Indoor"),
        (SECTION_OUTDOOR, "Outdoor"),
        (SECTION_VIP, "VIP"),
        (SECTION_ROOFTOP, "Rooftop"),
    ]

    SHAPE_ROUND = "round"
    SHAPE_SQUARE = "square"
    SHAPE_RECT = "rect"
    SHAPE_CHOICES = [
        (SHAPE_ROUND, "Round"),
        (SHAPE_SQUARE, "Square"),
        (SHAPE_RECT, "Rectangle"),
    ]

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="restaurant_tables",
        db_index=True,
    )
    table_number = models.CharField(max_length=40)
    capacity = models.PositiveIntegerField(default=4)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_AVAILABLE, db_index=True)
    section = models.CharField(max_length=32, choices=SECTION_CHOICES, default=SECTION_INDOOR, db_index=True)
    zone = models.CharField(max_length=60, default="Main Hall", db_index=True)
    shape = models.CharField(max_length=16, choices=SHAPE_CHOICES, default=SHAPE_SQUARE)
    pos_x = models.IntegerField(default=60)
    pos_y = models.IntegerField(default=60)
    guest_name = models.CharField(max_length=160, blank=True, default="")
    guest_phone = models.CharField(max_length=40, blank=True, default="")
    reservation_time = models.CharField(max_length=60, blank=True, default="")
    active_order = models.ForeignKey(
        Order,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_tables",
    )
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("zone", "table_number")
        constraints = [
            models.UniqueConstraint(
                fields=["company", "table_number"],
                name="unique_restaurant_table_per_company",
            )
        ]

    def __str__(self):
        return f"{self.table_number} ({self.zone}) - {self.status}"


class TableReservation(models.Model):
    STATUS_PENDING = "pending"
    STATUS_CONFIRMED = "confirmed"
    STATUS_SEATED = "seated"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"
    STATUS_NO_SHOW = "no_show"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_SEATED, "Seated"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_NO_SHOW, "No Show"),
    ]

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="table_reservations",
        db_index=True,
    )
    table = models.ForeignKey(
        RestaurantTable,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reservations",
    )
    customer_name = models.CharField(max_length=160)
    customer_phone = models.CharField(max_length=40, blank=True, default="")
    party_size = models.PositiveIntegerField(default=2)
    reservation_date = models.DateField(db_index=True)
    reservation_time = models.TimeField()
    reserved_at = models.DateTimeField(db_index=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_CONFIRMED,
        db_index=True,
    )
    special_requests = models.TextField(blank=True, default="")
    source = models.CharField(
        max_length=20,
        default="dashboard",
        choices=[("dashboard", "Dashboard"), ("agent", "AI Agent"), ("web", "Web")],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("reserved_at", "id")
        indexes = [
            models.Index(fields=["company", "reservation_date", "status"], name="op_res_comp_date_st_idx"),
            models.Index(fields=["company", "table", "reserved_at"], name="op_res_comp_tbl_dt_idx"),
        ]

    def __str__(self):
        tbl = self.table.table_number if self.table else "Unassigned"
        return f"{self.customer_name} ({self.party_size}p) @ {self.reservation_date} {self.reservation_time} [{tbl}]"


# ============================================================================
# Restaurant Ingredient Inventory, Dish Recipes & Stock Movement Logs
# ============================================================================

class RestaurantIngredient(models.Model):
    UNIT_CHOICES = [
        ("pcs", "Pieces (pcs)"),
        ("kg", "Kilograms (kg)"),
        ("g", "Grams (g)"),
        ("l", "Liters (l)"),
        ("ml", "Milliliters (ml)"),
        ("packs", "Packs"),
    ]

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="restaurant_ingredients",
        db_index=True,
    )
    name = models.CharField(max_length=160)
    sku = models.CharField(max_length=80, blank=True, default="")
    unit = models.CharField(max_length=16, choices=UNIT_CHOICES, default="pcs")
    current_stock = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"))
    low_stock_threshold = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("5"))
    cost_per_unit = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    supplier_name = models.CharField(max_length=160, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=["company", "name"],
                name="unique_rest_ingredient_per_company",
            )
        ]

    @property
    def stock_status(self) -> str:
        if self.current_stock <= 0:
            return "out_of_stock"
        if self.current_stock <= self.low_stock_threshold:
            return "low_stock"
        return "in_stock"

    def __str__(self):
        return f"{self.name} ({self.current_stock} {self.unit})"


class MenuItemRecipe(models.Model):
    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="menu_item_recipes",
        db_index=True,
    )
    catalog_item = models.ForeignKey(
        "companies.CatalogItem",
        on_delete=models.CASCADE,
        related_name="recipe_ingredients",
    )
    ingredient = models.ForeignKey(
        RestaurantIngredient,
        on_delete=models.CASCADE,
        related_name="used_in_recipes",
    )
    quantity_required = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("1"))

    class Meta:
        ordering = ("ingredient__name",)
        constraints = [
            models.UniqueConstraint(
                fields=["catalog_item", "ingredient"],
                name="unique_recipe_ingredient_per_dish",
            )
        ]

    def __str__(self):
        return f"{self.catalog_item.name} -> {self.ingredient.name} ({self.quantity_required})"


class IngredientStockMovement(models.Model):
    MOVEMENT_ORDER_DEDUCTION = "order_deduction"
    MOVEMENT_ORDER_CANCEL_RESTORE = "order_cancellation_restore"
    MOVEMENT_RESTOCK = "restock"
    MOVEMENT_WASTE = "waste"
    MOVEMENT_MANUAL_ADJUSTMENT = "manual_adjustment"
    MOVEMENT_CHOICES = [
        (MOVEMENT_ORDER_DEDUCTION, "Order Deduction"),
        (MOVEMENT_ORDER_CANCEL_RESTORE, "Order Cancellation Restore"),
        (MOVEMENT_RESTOCK, "Restock"),
        (MOVEMENT_WASTE, "Waste / Spoilage"),
        (MOVEMENT_MANUAL_ADJUSTMENT, "Manual Adjustment"),
    ]

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="ingredient_stock_movements",
        db_index=True,
    )
    ingredient = models.ForeignKey(
        RestaurantIngredient,
        on_delete=models.CASCADE,
        related_name="movements",
    )
    movement_type = models.CharField(max_length=32, choices=MOVEMENT_CHOICES, db_index=True)
    quantity_delta = models.DecimalField(max_digits=12, decimal_places=3)
    stock_after = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"))
    reason = models.CharField(max_length=255, blank=True, default="")
    order = models.ForeignKey(
        Order,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ingredient_movements",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=["company", "ingredient", "-created_at"], name="op_ing_mov_comp_ing_idx"),
        ]

    def __str__(self):
        return f"{self.ingredient.name} {self.quantity_delta:+} ({self.movement_type})"


# ============================================================================
# Privacy, Data Retention & Customer Consent Ledger (PRD §12 — Multi-Tenant)
# ============================================================================

class DataRetentionPolicy(models.Model):
    company = models.OneToOneField(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="retention_policy",
    )
    chat_retention_days = models.PositiveIntegerField(default=90)
    order_pii_retention_days = models.PositiveIntegerField(default=365)
    auto_purge_enabled = models.BooleanField(default=False)
    last_purge_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"RetentionPolicy(company={self.company_id}, chat={self.chat_retention_days}d, pii={self.order_pii_retention_days}d)"


class CustomerConsentLog(models.Model):
    CONSENT_VOICE_AI = "voice_ai_recording"
    CONSENT_WHATSAPP = "whatsapp_notifications"
    CONSENT_DATA_PROC = "data_processing"
    CONSENT_MARKETING = "marketing_upsell"
    CONSENT_TYPE_CHOICES = [
        (CONSENT_VOICE_AI, "Voice AI Recording & Processing"),
        (CONSENT_WHATSAPP, "WhatsApp Notifications"),
        (CONSENT_DATA_PROC, "Order & Data Processing"),
        (CONSENT_MARKETING, "Marketing & Upsell Offers"),
    ]

    CHANNEL_CHOICES = [
        ("public_web", "Public Web"),
        ("widget", "Website Widget"),
        ("whatsapp", "WhatsApp"),
        ("dashboard", "Dashboard"),
    ]

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="customer_consents",
        db_index=True,
    )
    customer_identifier = models.CharField(max_length=160, db_index=True)
    consent_type = models.CharField(max_length=40, choices=CONSENT_TYPE_CHOICES)
    granted = models.BooleanField(default=True)
    channel = models.CharField(max_length=24, choices=CHANNEL_CHOICES, default="public_web")
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-recorded_at",)
        indexes = [
            models.Index(fields=["company", "customer_identifier", "-recorded_at"]),
        ]

    def __str__(self):
        return f"[{self.company_id}] {self.customer_identifier} - {self.consent_type} ({self.granted})"


# ============================================================================
# Platform Owner / Super Admin Audit Log (PRD §2.1 & §10)
# ============================================================================

class PlatformAuditLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="platform_audit_actions",
    )
    actor_email = models.CharField(max_length=254, blank=True, default="")
    action = models.CharField(max_length=80, db_index=True)
    target_company = models.ForeignKey(
        "companies.Company",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="platform_audit_logs",
    )
    target_company_name = models.CharField(max_length=200, blank=True, default="")
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["action", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.action} -> {self.target_company_name} by {self.actor_email}"


# ============================================================================
# Staff Attendance & Suppliers Management (PRD §3 / §9 — Multi-Tenant)
# ============================================================================

class StaffAttendance(models.Model):
    STATUS_PRESENT = "present"
    STATUS_ABSENT = "absent"
    STATUS_LATE = "late"
    STATUS_HALF_DAY = "half_day"
    STATUS_ON_LEAVE = "on_leave"
    STATUS_CHOICES = [
        (STATUS_PRESENT, "Present"),
        (STATUS_ABSENT, "Absent"),
        (STATUS_LATE, "Late"),
        (STATUS_HALF_DAY, "Half Day"),
        (STATUS_ON_LEAVE, "On Leave"),
    ]

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="staff_attendances",
        db_index=True,
    )
    staff_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )
    date = models.DateField(db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PRESENT)
    check_in_time = models.TimeField(null=True, blank=True)
    check_out_time = models.TimeField(null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-date", "staff_user_id")
        constraints = [
            models.UniqueConstraint(
                fields=["company", "staff_user", "date"],
                name="unique_staff_attendance_per_company_day",
            )
        ]

    def __str__(self):
        return f"{self.staff_user_id} ({self.date}) - {self.status}"


class Supplier(models.Model):
    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="suppliers",
        db_index=True,
    )
    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=160, blank=True, default="")
    phone = models.CharField(max_length=40, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    category = models.CharField(max_length=100, blank=True, default="")
    address = models.TextField(blank=True, default="")
    payment_terms = models.CharField(max_length=80, blank=True, default="")
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)
        indexes = [
            models.Index(fields=["company", "is_active", "category"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.category or 'General'})"












