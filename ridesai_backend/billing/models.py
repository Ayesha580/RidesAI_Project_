from django.conf import settings
from django.db import models


class CheckoutSession(models.Model):
    STATUS_CHOICES = [
        ("created", "Created"),
        ("succeeded", "Succeeded"),
        ("failed", "Failed"),
        ("expired", "Expired"),
    ]
    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, related_name="billing_checkouts")
    plan = models.ForeignKey("companies.Plan", on_delete=models.PROTECT, related_name="checkouts")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="billing_checkouts")
    polar_checkout_id = models.CharField(max_length=120, unique=True)
    checkout_url = models.URLField(max_length=1000)
    customer_email = models.EmailField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="created")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Checkout {self.polar_checkout_id} - {self.company}"


class PaymentTransaction(models.Model):
    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, related_name="payment_transactions")
    plan = models.ForeignKey("companies.Plan", on_delete=models.PROTECT, related_name="payment_transactions")
    polar_checkout_id = models.CharField(max_length=120, blank=True, db_index=True)
    polar_order_id = models.CharField(max_length=120, blank=True, unique=True, null=True)
    polar_subscription_id = models.CharField(max_length=120, blank=True, db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=10, blank=True)
    status = models.CharField(max_length=30, default="pending")
    raw_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.company} - {self.status}"


class WebhookEvent(models.Model):
    event_id = models.CharField(max_length=150, unique=True)
    event_type = models.CharField(max_length=120)
    payload = models.JSONField(default=dict, blank=True)
    processed = models.BooleanField(default=False)
    processing_error = models.TextField(blank=True)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.event_type} ({self.event_id})"


class ManualPayment(models.Model):
    STATUS_CHOICES = [("pending", "Pending review"), ("approved", "Approved"), ("rejected", "Rejected")]
    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, related_name="manual_payments")
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="manual_payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=10, default="USD")
    payment_reference = models.CharField(max_length=120, blank=True)
    proof = models.FileField(upload_to="payment_proofs/", null=True, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    admin_note = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_manual_payments")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.company.name} - {self.status} - {self.created_at:%Y-%m-%d}"
