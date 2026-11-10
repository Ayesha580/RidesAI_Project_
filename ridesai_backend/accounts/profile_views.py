import re

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import IsOwner

PROFILE_PERMS = [IsAuthenticated, IsOwner]


def _err(field, message):
    return Response({field: message}, status=400)


def _profile_json(user):
    c = user.company
    return {
        "first_name": user.first_name,
        "last_name": user.last_name,
        "username": user.username,
        "email": user.email,
        "phone": user.phone,
        "business_name": c.name if c else "",
        "business_type": c.business_type if c else "",
        "business_email": c.email if c else "",
        "business_phone": c.phone if c else "",
        "address": c.address if c else "",
    }


class ProfileAPIView(APIView):
    permission_classes = PROFILE_PERMS

    def get(self, request):
        return Response(_profile_json(request.user))

    def patch(self, request):
        user, d = request.user, request.data

        for f in ("first_name", "last_name"):
            if f in d:
                setattr(user, f, (d[f] or "").strip())
        if not user.first_name:
            return _err("first_name", "First name is required.")

        if "phone" in d:
            phone = (d["phone"] or "").strip()
            if not re.fullmatch(r"03\d{9}", phone):
                return _err("phone", "Phone number must be in format 03XXXXXXXXX.")
            user.phone = phone

        user.save()

        c = user.company
        if c:
            fields = []
            if "address" in d:
                c.address = (d["address"] or "").strip(); fields.append("address")
            if "phone" in d:
                c.phone = user.phone; fields.append("phone")
            if "business_name" in d:
                name = (d["business_name"] or "").strip()
                if not name: return _err("business_name", "Business name is required.")
                if type(c).objects.exclude(pk=c.pk).filter(name__iexact=name).exists(): return _err("business_name", "This business name is already in use.")
                c.name = name; fields.append("name")
            if "business_type" in d:
                c.business_type = (d["business_type"] or "").strip(); fields.append("business_type")
            if "business_email" in d:
                from django.core.validators import validate_email
                from django.core.exceptions import ValidationError
                email = (d["business_email"] or "").strip()
                if email:
                    try: validate_email(email)
                    except ValidationError: return _err("business_email", "Enter a valid business email address.")
                c.email = email; fields.append("email")
            if fields: c.save(update_fields=fields)

        return Response(_profile_json(user))

class ChangePasswordAPIView(APIView):
    permission_classes = [IsAuthenticated]   # owner + employee dono

    def post(self, request):
        user, d = request.user, request.data
        if not user.check_password(d.get("current_password") or ""):
            return _err("current_password", "Current password is incorrect.")
        new = d.get("new_password") or ""
        if len(new) < 8:
            return _err("new_password", "Password must be at least 8 characters.")
        user.set_password(new)
        user.must_change_password = False
        user.save()
        return Response({"message": "Password updated."})