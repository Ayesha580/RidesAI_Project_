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