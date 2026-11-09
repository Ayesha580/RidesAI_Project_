import re

from rest_framework import serializers

from .models import User


class MeSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name", read_only=True)
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "username", "email", "first_name", "last_name", "full_name",
            "role", "company", "company_name", "phone", "email_verified",
        ]

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username


class UserListSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "username", "first_name", "last_name", "full_name", "role")

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username


class RegisterSerializer(serializers.Serializer):
    # SaaS mode requires a plan; the one-client build disables plan selection.
    plan_id = serializers.IntegerField(min_value=1, required=False)

    # Owner
    first_name = serializers.CharField()
    username = serializers.CharField()
    email = serializers.EmailField()
    phone = serializers.CharField()
    password = serializers.CharField(write_only=True, min_length=8)
    cnic = serializers.CharField()

    # Business
    business_name = serializers.CharField()
    business_type = serializers.CharField(required=False, allow_blank=True)
    business_address = serializers.CharField(required=False, allow_blank=True)
    is_registered = serializers.BooleanField(required=False, default=False)
    registration_number = serializers.CharField(required=False, allow_blank=True)
    # Documents
    business_registration_document = serializers.FileField(required=False, allow_null=True)
    cnic_front = serializers.FileField()
    cnic_back = serializers.FileField()
    passport_size_photo = serializers.ImageField()

    def validate_email(self, value):
        return value.strip().lower()

    def validate_phone(self, value):
        value = value.strip()
        if not re.fullmatch(r"03\d{9}", value):
            raise serializers.ValidationError("Phone number must be in format 03XXXXXXXXX.")
        return value

    def validate_cnic(self, value):
        value = value.strip()
        if not re.fullmatch(r"\d{5}-\d{7}-\d", value):
            raise serializers.ValidationError("CNIC must be in format 12345-1234567-1.")
        return value

    def validate(self, data):
        if data.get("is_registered"):
            if not data.get("business_registration_document"):
                raise serializers.ValidationError(
                    {"business_registration_document": "Business registration document is required."}
                )
            if not data.get("registration_number"):
                raise serializers.ValidationError(
                    {"registration_number": "Registration number is required."}
                )
        return data