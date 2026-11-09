from django.db import models
from django.db.models import Q
from django.core.validators import MinValueValidator
from decimal import Decimal

class Plan(models.Model):
    MONTHLY = "monthly"
    YEARLY = "yearly"
    BILLING_CHOICES = [(MONTHLY, "Monthly"), (YEARLY, "Yearly")]

    name = models.CharField(max_length=50)
    billing_cycle = models.CharField(max_length=10, choices=BILLING_CHOICES, default=MONTHLY)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    polar_product_id = models.CharField(max_length=120, blank=True, help_text="Polar product ID for this exact plan and billing cycle.")
    currency = models.CharField(max_length=10, default="USD")

    class Meta:
        unique_together = ("name", "billing_cycle")

    def __str__(self):
        return f"{self.name} ({self.billing_cycle})"


class Company(models.Model):
    STATUS_PENDING = "pending"
    STATUS_ACTIVE = "active"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_REJECTED, "Rejected"),
    ]

    PAYMENT_OK = "ok"
    PAYMENT_PAST_DUE = "past_due"
    PAYMENT_SUSPENDED = "suspended"
    PAYMENT_CHOICES = [
        (PAYMENT_OK, "OK"),
        (PAYMENT_PAST_DUE, "Past due"),
        (PAYMENT_SUSPENDED, "Suspended"),
    ]

    # Business
    name = models.CharField(max_length=200, unique=True)
    business_type = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    is_registered = models.BooleanField(default=False)
    registration_number = models.CharField(max_length=100, blank=True)

    # Owner contact
    cnic = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)

    # Documents (admin approval ke waqt dekhe jate hain)
    business_registration_document = models.FileField(upload_to="company_docs/", null=True, blank=True)
    cnic_front = models.FileField(upload_to="company_docs/", null=True, blank=True)
    cnic_back = models.FileField(upload_to="company_docs/", null=True, blank=True)
    passport_size_photo = models.ImageField(upload_to="company_docs/", null=True, blank=True)

    # Plan + approval + trial
    plan = models.ForeignKey(Plan, null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    is_approved = models.BooleanField(default=False)
    approved_at = models.DateTimeField(null=True, blank=True)
    trial_ends_at = models.DateTimeField(null=True, blank=True)

    # Billing (Polar)
    polar_subscription_id = models.CharField(max_length=100, blank=True)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default=PAYMENT_OK)
    payment_failed_at = models.DateTimeField(null=True, blank=True)
    grace_ends_at = models.DateTimeField(null=True, blank=True)
    subscription_ends_at = models.DateTimeField(null=True, blank=True)

    # Single-client manual access and usage controls.
    initial_access_started_at = models.DateTimeField(null=True, blank=True)
    access_expires_at = models.DateTimeField(null=True, blank=True)
    renewal_due_at = models.DateTimeField(null=True, blank=True)
    message_limit = models.PositiveIntegerField(default=1000)
    messages_used = models.PositiveIntegerField(default=0)
    message_period_started_at = models.DateTimeField(null=True, blank=True)

    # Business-owned Gmail / Google Workspace setup details (credentials are never stored).
    business_email_address = models.EmailField(blank=True)
    business_email_domain = models.CharField(max_length=253, blank=True)
    business_email_setup_status = models.CharField(
        max_length=20,
        choices=[("not_started", "Not started"), ("in_progress", "In progress"), ("completed", "Completed")],
        default="not_started",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name



class CatalogCategory(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="catalog_categories")
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["company", "name"], name="unique_catalog_category_per_company")
        ]

    def __str__(self):
        return self.name


class CatalogItem(models.Model):
    ITEM_TYPES = [
        ("product", "Product"),
        ("service", "Service"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="catalog_items")
    category = models.ForeignKey(CatalogCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name="items")
    name = models.CharField(max_length=200)
    item_type = models.CharField(max_length=20, choices=ITEM_TYPES, default="product")
    description = models.TextField(blank=True)
    sku = models.CharField(max_length=100, blank=True)
    barcode = models.CharField(max_length=100, blank=True)
    brand = models.CharField(max_length=150, blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(Decimal("0"))])
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(Decimal("0"))])
    unit = models.CharField(max_length=50, blank=True)
    image = models.ImageField(upload_to="catalog/", null=True, blank=True)
    attributes = models.JSONField(default=dict, blank=True)
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["company", "sku"], condition=~Q(sku=""), name="unique_catalog_sku_per_company"),
            models.UniqueConstraint(fields=["company", "barcode"], condition=~Q(barcode=""), name="unique_catalog_barcode_per_company"),
        ]

    def __str__(self):
        return self.name


class ItemVariant(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="catalog_variants")
    item = models.ForeignKey(CatalogItem, on_delete=models.CASCADE, related_name="variants")
    name = models.CharField(max_length=150)
    sku = models.CharField(max_length=100, blank=True)
    attributes = models.JSONField(default=dict, blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    is_available = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["item", "name"], name="unique_variant_name_per_item")
        ]

    def __str__(self):
        return f"{self.item.name} - {self.name}"


class Inventory(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="catalog_inventory")
    item = models.OneToOneField(CatalogItem, on_delete=models.CASCADE, related_name="inventory")
    is_unlimited = models.BooleanField(default=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0, validators=[MinValueValidator(Decimal("0"))])
    low_stock_threshold = models.DecimalField(max_digits=12, decimal_places=3, default=5)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def in_stock(self):
        return self.is_unlimited or self.quantity > 0


class StockMovement(models.Model):
    MOVEMENT_TYPES = [
        ("add", "Stock Added"),
        ("remove", "Stock Removed"),
        ("adjustment", "Stock Adjusted"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="stock_movements")
    item = models.ForeignKey(CatalogItem, on_delete=models.CASCADE, related_name="stock_movements")
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ItemBatch(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="item_batches")
    item = models.ForeignKey(CatalogItem, on_delete=models.CASCADE, related_name="batches")
    batch_number = models.CharField(max_length=100)
    expiry_date = models.DateField(null=True, blank=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["item", "batch_number"], name="unique_batch_per_item")
        ]


class Deal(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="catalog_deals")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0"))])
    items = models.ManyToManyField(CatalogItem, through="DealItem", related_name="deals")
    image = models.ImageField(upload_to="catalog/deals/", null=True, blank=True)
    is_active = models.BooleanField(default=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class DealItem(models.Model):
    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name="deal_items")
    item = models.ForeignKey(CatalogItem, on_delete=models.CASCADE, related_name="deal_items")
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["deal", "item"], name="unique_item_per_deal")
        ]