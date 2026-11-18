from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'company', 'is_staff')
    list_filter = ('role', 'company', 'is_staff', 'is_superuser')
    
    # Adding role and company to the admin edit screen
    fieldsets = UserAdmin.fieldsets + (
        ('Platform Roles & Tenant', {'fields': ('role', 'company')}),
    )