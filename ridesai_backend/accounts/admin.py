from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "email_verified", "role", "company", "is_active")
    list_filter = ("role", "email_verified", "is_active", "company")
    search_fields = ("username", "email", "first_name", "last_name")

    fieldsets = BaseUserAdmin.fieldsets + (
        ("Restaurant Info", {"fields": ("role", "company", "phone", "cnic", "email_verified", "must_change_password")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Restaurant Info", {"fields": ("role", "company", "phone")}),
    )