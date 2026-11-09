from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from billing.services import get_access_state
from .models import User


class IsCompanyPaymentActive(BasePermission):
    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        if user.is_superuser or user.role == User.ROLE_SUPERADMIN:
            return True

        company = user.company
        if not company:
            return False

        state = get_access_state(company)

        if state == "pending_approval":
            raise PermissionDenied({
                "detail": "Your account is waiting for admin approval.",
                "code": "pending_approval",
            })

        if state == "payment_required":
            is_owner = user.role == User.ROLE_OWNER
            raise PermissionDenied({
                "detail": "Please choose a plan and complete payment to activate your account.",
                "code": "payment_required",
                "can_pay": is_owner,
            })

        if state == "suspended":
            is_owner = user.role == User.ROLE_OWNER
            raise PermissionDenied({
                "detail": (
                    "Your trial/subscription has ended. Please pay to restore access."
                    if is_owner
                    else "Your company's subscription has ended. Please ask the business owner to renew it."
                ),
                "code": "payment_required",
                "can_pay": is_owner,
            })

        return True


def HasModule(module_key):
    class _HasModule(BasePermission):
        def has_permission(self, request, view):
            u = request.user
            return bool(u and u.is_authenticated and module_key in u.get_modules())
    return _HasModule


class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and (u.role == User.ROLE_SUPERADMIN or u.is_superuser))


def _role_permission(*roles):
    class _RolePermission(BasePermission):
        def has_permission(self, request, view):
            u = request.user
            return bool(u and u.is_authenticated and u.role in roles)
    return _RolePermission


IsOwner = _role_permission(User.ROLE_OWNER)
IsStaff = _role_permission(User.ROLE_STAFF)
IsManager = _role_permission(User.ROLE_MANAGER)
IsKitchen = _role_permission(User.ROLE_KITCHEN)
IsEmployee = _role_permission(User.ROLE_EMPLOYEE)
IsOwnerOrManager = _role_permission(User.ROLE_OWNER, User.ROLE_MANAGER)