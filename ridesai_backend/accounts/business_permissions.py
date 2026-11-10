from rest_framework.permissions import BasePermission


class HasBusinessPermission(BasePermission):
    """Use `required_business_permission` on a view or viewset."""
    message = "Your business role does not allow this action. Ask the owner to update your permissions."

    def has_permission(self, request, view):
        user = request.user
        required = getattr(view, "required_business_permission", None)
        if not required:
            return True
        return bool(user and user.is_authenticated and user.has_business_permission(required))
