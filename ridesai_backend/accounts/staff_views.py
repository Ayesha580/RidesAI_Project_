import re

from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import StaffRole, User
from .modules import BUSINESS_TYPES, business_key, catalog_for, modules_for, template_for
from .permissions import IsCompanyPaymentActive, IsOwner

OWNER_PERMS = [IsAuthenticated, IsCompanyPaymentActive, IsOwner]


def _err(field, message, code=400):
    return Response({field: message}, status=code)


def _clean_modules(company, modules):
    allowed = set(modules_for(company.business_type))
    modules = list(dict.fromkeys(modules or []))
    bad = [m for m in modules if m not in allowed]
    return modules, bad


def _role_json(role):
    return {
        "id": role.id,
        "name": role.name,
        "modules": role.modules,
        "is_active": role.is_active,
        "staff_count": role.users.filter(is_active=True).count(),
    }

def _staff_json(u):
    return {
        "id": u.id,
        "username": u.username,
        "first_name": u.first_name,
        "last_name": u.last_name,
        "full_name": f"{u.first_name} {u.last_name}".strip() or u.username,
        "phone": u.phone,
        "email": u.email,
        "is_active": u.is_active,
        "role_id": u.staff_role_id,
        "role_name": u.staff_role.name if u.staff_role else None,
        "modules": u.get_modules(),
        "date_joined": u.date_joined.isoformat(),
    }

class ModuleCatalogAPIView(APIView):
    permission_classes = OWNER_PERMS

    def get(self, request):
        bt = request.user.company.business_type
        return Response({
            "modules": catalog_for(bt),
            "templates": [
                {"name": name, "modules": mods}
                for name, mods in template_for(bt).items()
            ],
            "business_label": BUSINESS_TYPES[business_key(bt)]["label"],
        })


class RoleListCreateAPIView(APIView):
    permission_classes = OWNER_PERMS

    def get(self, request):
        roles = StaffRole.objects.filter(company=request.user.company).order_by("name")
        return Response([_role_json(r) for r in roles])

    def post(self, request):
        company = request.user.company
        name = (request.data.get("name") or "").strip()
        if not name:
            return _err("name", "Role name is required.")
        if StaffRole.objects.filter(company=company, name__iexact=name).exists():
            return _err("name", "This role already exists.")

        modules, bad = _clean_modules(company, request.data.get("modules"))
        if bad:
            return _err("modules", f"Not available for your business type: {', '.join(bad)}")
        if not modules:
            return _err("modules", "Select at least one feature.")

        role = StaffRole.objects.create(company=company, name=name, modules=modules)
        return Response(_role_json(role), status=201)


class RoleDetailAPIView(APIView):
    permission_classes = OWNER_PERMS

    def _get(self, request, role_id):
        return get_object_or_404(StaffRole, pk=role_id, company=request.user.company)

    def get(self, request, role_id):
        return Response(_role_json(self._get(request, role_id)))

    def patch(self, request, role_id):
        role, d, company = self._get(request, role_id), request.data, request.user.company

        if "name" in d:
            name = (d["name"] or "").strip()
            if not name:
                return _err("name", "Role name is required.")
            if StaffRole.objects.filter(company=company, name__iexact=name).exclude(pk=role.pk).exists():
                return _err("name", "This role already exists.")
            role.name = name

        if "modules" in d:
            modules, bad = _clean_modules(company, d["modules"])
            if bad:
                return _err("modules", f"Not available for your business type: {', '.join(bad)}")
            if not modules:
                return _err("modules", "Select at least one feature.")
            role.modules = modules

        if "is_active" in d:
            role.is_active = bool(d["is_active"])

        role.save()
        return Response(_role_json(role))

    def delete(self, request, role_id):
        role = self._get(request, role_id)
        if role.users.filter(is_active=True).exists():
            return _err("error", "Is role par staff assigned hai. Pehle unka role badlein ya unhein remove karein.")
        role.delete()
        return Response(status=204)


# ------------------------------------------------------------
# STAFF (Employees): owner add / edit / remove
# ------------------------------------------------------------
class StaffAPIView(APIView):
    permission_classes = OWNER_PERMS

    def get(self, request):
        qs = (
            User.objects.filter(company=request.user.company, role=User.ROLE_STAFF)
            .select_related("staff_role")
            .order_by("-id")
        )
        return Response([_staff_json(u) for u in qs])

    def post(self, request):
        d, company = request.data, request.user.company

        role = StaffRole.objects.filter(
            pk=d.get("role_id") or 0, company=company, is_active=True
        ).first()
        if not role:
            return _err("role_id", "Valid role select karein.")

        username = (d.get("username") or "").strip()
        password = d.get("password") or ""
        first_name = (d.get("first_name") or "").strip()
        phone = (d.get("phone") or "").strip()
        email = (d.get("email") or "").strip()
        if not first_name:
            return _err("first_name", "First name is required.")
        if not username:
            return _err("username", "Username is required.")
        if len(password) < 8:
            return _err("password", "Password must be at least 8 characters.")
        if phone and not re.fullmatch(r"03\d{9}", phone):
            return _err("phone", "Phone number must be in format 03XXXXXXXXX.")
        if User.objects.filter(username__iexact=username).exists():
            return _err("username", "Username already exists.")
        if email and User.objects.filter(email__iexact=email).exists():
            return _err("email", "Email already exists.")
        user = User(
            company=company,
            role=User.ROLE_STAFF,
            staff_role=role,
            username=username,
            first_name=first_name,
            last_name=(d.get("last_name") or "").strip(),
            phone=phone,
            email = email,
            email_verified=True,  # staff accounts are provisioned by an already verified owner
            must_change_password=True,
        )
        user.set_password(password)
        user.save()
        return Response(_staff_json(user), status=201)


class StaffDetailAPIView(APIView):
    permission_classes = OWNER_PERMS

    def _get(self, request, user_id):
        return get_object_or_404(
            User, pk=user_id, company=request.user.company, role=User.ROLE_STAFF
        )

    def get(self, request, user_id):
        return Response(_staff_json(self._get(request, user_id)))

    def patch(self, request, user_id):
        user, d, company = self._get(request, user_id), request.data, request.user.company

        if "role_id" in d:
            role = StaffRole.objects.filter(pk=d["role_id"] or 0, company=company, is_active=True).first()
            if not role:
                return _err("role_id", "Valid role select karein.")
            user.staff_role = role

        for f in ("first_name", "last_name"):
            if f in d:
                setattr(user, f, (d[f] or "").strip())
        if not user.first_name:
            return _err("first_name", "First name is required.")

        if "phone" in d:
            phone = (d["phone"] or "").strip()
            if phone and not re.fullmatch(r"03\d{9}", phone):
                return _err("phone", "Phone number must be in format 03XXXXXXXXX.")
            user.phone = phone

        if "is_active" in d:
            user.is_active = bool(d["is_active"])

        if d.get("new_password"):
            if len(d["new_password"]) < 8:
                return _err("new_password", "Password must be at least 8 characters.")
            user.set_password(d["new_password"])
            user.must_change_password = True

        user.save()
        return Response(_staff_json(user))

    def delete(self, request, user_id):
        user = self._get(request, user_id)
        user.delete()
        return Response(status=204)