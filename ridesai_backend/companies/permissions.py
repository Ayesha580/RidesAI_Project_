from rest_framework.permissions import BasePermission
from accounts.modules import business_key, modules_for


class CatalogModulePermission(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        company = getattr(user, "company", None)
        if not company:
            return False

        module_map = {
            "restaurant": "menu",
            "pharmacy": "medicines",
            "grocery": "products",
            "retail": "products",
            "clinic": "services",
            "general": "products",
        }

        key = business_key(company.business_type)
        required_module = module_map.get(key, "products")

        return required_module in modules_for(company.business_type)

class CatalogRolePermission(BasePermission):
    """Owners have full access; staff require separate view/manage grants."""
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated or not getattr(user, "company_id", None):
            return False
        company = user.company
        if user.role == "owner" or user.is_superuser:
            return True
        required = "catalog.view" if request.method in ("GET", "HEAD", "OPTIONS") else "catalog.manage"
        if not user.has_business_permission(required):
            return False
        from accounts.modules import business_key
        key = business_key(company.business_type)
        module_for_type = {"restaurant": "menu", "pharmacy": "medicines", "clinic": "services"}.get(key, "products")
        return module_for_type in user.get_modules()
