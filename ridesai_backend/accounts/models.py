from django.contrib.auth.models import AbstractUser
from django.db import models

from companies.models import Company
from .modules import modules_for, template_for

class StaffRole(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="staff_roles")
    name = models.CharField(max_length=60)
    modules = models.JSONField(default=list, blank=True)   # ["orders", "kitchen_display"]
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("company", "name")

    def __str__(self):
        return f"{self.name} - {self.company}"


def seed_default_roles(company):
    for name, mods in template_for(company.business_type).items():
        StaffRole.objects.get_or_create(company=company, name=name, defaults={"modules": mods})


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

    def get_modules(self):
        if not self.company:
            return []
        allowed = modules_for(self.company.business_type)
        if self.role == self.ROLE_OWNER:
            return allowed
        if self.role == self.ROLE_STAFF and self.staff_role and self.staff_role.is_active:
            return [m for m in self.staff_role.modules if m in allowed]
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
