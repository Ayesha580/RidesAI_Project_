from django.contrib.auth.models import AbstractUser
from django.db import models

from companies.models import Company
from .modules import modules_for, template_for, business_key

class StaffRole(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="staff_roles")
    name = models.CharField(max_length=60)
    modules = models.JSONField(default=list, blank=True)   # dashboard modules
    permissions = models.JSONField(default=list, blank=True)  # granular API actions
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("company", "name")

    def __str__(self):
        return f"{self.name} - {self.company}"


def seed_default_roles(company):
    permission_templates = {
        "rider": ["deliveries.view_assigned", "deliveries.update_status"],
        "delivery boy": ["deliveries.view_assigned", "deliveries.update_status"],
        "kitchen staff": ["orders.view", "orders.update_status"],
        "waiter": ["orders.view", "orders.create", "orders.update_status"],
        "cashier": ["orders.view", "orders.create", "customers.view"],
        "manager": ["orders.view", "orders.view_all", "orders.create", "orders.update_status", "orders.assign", "deliveries.view", "deliveries.view_assigned", "deliveries.update_status", "deliveries.assign", "catalog.view", "catalog.manage", "customers.view", "agent.view", "agent.handover"],
        "pharmacist": ["orders.view", "orders.create", "orders.update_status", "catalog.view", "catalog.manage", "customers.view"],
        "doctor": ["customers.view"],
        "receptionist": ["orders.view", "orders.create", "customers.view"],
        "stock keeper": ["catalog.view", "catalog.manage"],
    }
    for name, mods in template_for(company.business_type).items():
        key = name.strip().lower()
        permissions = permission_templates.get(key, [])
        StaffRole.objects.get_or_create(company=company, name=name,
            defaults={"modules": mods, "permissions": permissions})


class User(AbstractUser):
    ROLE_OWNER = "owner"
    ROLE_STAFF = "Employee"
    ROLE_SUPERADMIN = "superadmin"
    ROLE_MANAGER = "manager"
    ROLE_KITCHEN = "kitchen"
    ROLE_EMPLOYEE = "employee"

    ROLE_CHOICES = [
        (ROLE_OWNER, "Business Owner"),
        (ROLE_STAFF, "Employee"),
        (ROLE_MANAGER, "Manager (legacy)"),
        (ROLE_KITCHEN, "Kitchen Staff (legacy)"),
        (ROLE_EMPLOYEE, "Employee (legacy)"),
        (ROLE_SUPERADMIN, "Super Admin"),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_STAFF)
    staff_role = models.ForeignKey(
        StaffRole, null=True, blank=True, on_delete=models.SET_NULL, related_name="users"
    )
    company = models.ForeignKey(
        Company, null=True, blank=True, on_delete=models.SET_NULL, related_name="users"
    )
    phone = models.CharField(max_length=30, blank=True)
    cnic = models.CharField(max_length=20, unique=True, null=True, blank=True)
    profile_image = models.ImageField(upload_to="profile_images/", null=True, blank=True)
    must_change_password = models.BooleanField(default=False)
    # New registrations must verify their email before checkout or login.
    email_verified = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.role = self.ROLE_SUPERADMIN
        super().save(*args, **kwargs)

    def get_permissions(self):
        if not self.company:
            return []
        if self.role == self.ROLE_OWNER:
            return ["*"]
        if self.role == self.ROLE_STAFF and self.staff_role and self.staff_role.is_active:
            return list(self.staff_role.permissions or [])
        return []

    def has_business_permission(self, permission):
        granted = self.get_permissions()
        if "*" in granted:
            return True
        implied = {
            "orders.view": {"orders.create", "orders.update_status"},
            "catalog.view": {"catalog.manage"},
            "deliveries.view": {"deliveries.assign"},
        }
        if permission not in granted and not (implied.get(permission, set()) & set(granted)):
            return False
        if permission.startswith("orders."):
            required_module = "orders"
        elif permission in ("deliveries.view", "deliveries.assign"):
            required_module = "deliveries"
        elif permission in ("deliveries.view_assigned", "deliveries.update_status"):
            required_module = "my_deliveries"
        elif permission.startswith("catalog."):
            from .modules import business_key
            required_module = {"restaurant": "menu", "pharmacy": "medicines", "clinic": "services"}.get(business_key(self.company.business_type), "products")
        elif permission == "customers.view":
            required_module = "customers"
        elif permission.startswith("agent."):
            required_module = "orders"
        else:
            required_module = None
        return required_module is None or required_module in self.get_modules()

    def get_modules(self):
        if not self.company:
            return []
        allowed = modules_for(self.company.business_type)
        if self.role == self.ROLE_OWNER:
            return allowed
        if self.role == self.ROLE_STAFF and self.staff_role and self.staff_role.is_active:
            modules = [m for m in self.staff_role.modules if m in allowed]
            grants = set(self.staff_role.permissions or [])
            if "orders" in modules and not grants.intersection({"orders.view", "orders.create", "orders.update_status", "agent.view", "agent.handover"}):
                modules.remove("orders")
            if "deliveries" in modules and not grants.intersection({"deliveries.view", "deliveries.assign"}):
                modules.remove("deliveries")
            if "my_deliveries" in modules and "deliveries.view_assigned" not in grants:
                modules.remove("my_deliveries")
            catalog_module = {"restaurant": "menu", "pharmacy": "medicines", "clinic": "services"}.get(business_key(self.company.business_type), "products")
            if catalog_module in modules and not grants.intersection({"catalog.view", "catalog.manage"}):
                modules.remove(catalog_module)
            return modules
        return []

    def __str__(self):
        label = self.staff_role.name if self.staff_role else self.get_role_display()
        return f"{self.username} ({label})"

class EmailVerificationToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="email_verification_tokens")
    token_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"Email verification for {self.user.email}"
