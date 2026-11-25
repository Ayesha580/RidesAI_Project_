from rest_framework import serializers
from .models import (
    Company,
    CatalogCategory,
    CatalogItem,
    ItemVariant,
    Inventory,
    StockMovement,
    ItemBatch,
    Deal,
    DealItem,
)


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = [
            "id",
            "name",
            "business_type",
            "address",
            "is_registered",
            "registration_number",
            "cnic",
            "email",
            "phone",
            "status",
            "is_approved",
            "approved_at",
            "subscription_status",
            "trial_ends_at",
            "is_manual_override",
            "manual_override_expires_at",
            "stripe_customer_id",
            "stripe_subscription_id",
            "grace_period_ends_at",
        ]
        read_only_fields = ["id", "approved_at"]


class CatalogCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = CatalogCategory
        fields = ["id", "name", "description", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]


class ItemVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemVariant
        fields = ["id", "name", "sku", "attributes", "price", "is_available"]
        read_only_fields = ["id"]


class InventorySerializer(serializers.ModelSerializer):
    in_stock = serializers.ReadOnlyField()

    class Meta:
        model = Inventory
        fields = ["is_unlimited", "quantity", "low_stock_threshold", "in_stock"]


class ItemBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemBatch
        fields = ["id", "batch_number", "expiry_date", "quantity", "created_at"]
        read_only_fields = ["id", "created_at"]


class CatalogItemSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(
        queryset=CatalogCategory.objects.all(),
        required=False,
        allow_null=True
    )
    category_name = serializers.CharField(source="category.name", read_only=True)
    cost_price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        allow_null=True,
        default=0
    )
    variants = ItemVariantSerializer(many=True, required=False)
    inventory = InventorySerializer(required=False)
    batches = ItemBatchSerializer(many=True, required=False)

    class Meta:
        model = CatalogItem
        fields = [
            "id", "category", "category_name", "name", "item_type",
            "description", "sku", "barcode", "brand", "price",
            "cost_price", "unit", "image", "attributes",
            "modifiers_schema", "kitchen_station", "prep_time_minutes",
            "requires_prescription", "generic_name", "is_available",
            "variants", "inventory", "batches", "created_at", "updated_at"
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def to_internal_value(self, data):
        import json
        if hasattr(data, "copy"):
            data = data.copy()
        else:
            data = dict(data)

        if data.get("category") == "":
            data["category"] = None

        if data.get("cost_price") == "":
            data["cost_price"] = None

        if data.get("price") == "":
            data["price"] = 0

        if data.get("prep_time_minutes") == "":
            data["prep_time_minutes"] = 15

        raw_mods = data.get("modifiers_schema")
        if isinstance(raw_mods, str):
            try:
                data["modifiers_schema"] = json.loads(raw_mods) if raw_mods.strip() else []
            except Exception:
                data["modifiers_schema"] = []

        return super().to_internal_value(data)

    def validate_category(self, category):
        request = self.context.get("request")
        if category and request and hasattr(request, "user") and getattr(request.user, "company_id", None):
            if category.company_id != request.user.company_id:
                raise serializers.ValidationError("Invalid category.")
        return category

    def create(self, validated_data):
        variants_data = validated_data.pop("variants", [])
        inventory_data = validated_data.pop("inventory", {})
        batches_data = validated_data.pop("batches", [])
        company = validated_data.pop("company", self.context["request"].user.company)

        item = CatalogItem.objects.create(company=company, **validated_data)
        Inventory.objects.create(company=company, item=item, **inventory_data)

        for variant in variants_data:
            ItemVariant.objects.create(company=company, item=item, **variant)

        for batch in batches_data:
            ItemBatch.objects.create(company=company, item=item, **batch)

        return item

    def update(self, instance, validated_data):
        variants_data = validated_data.pop("variants", None)
        inventory_data = validated_data.pop("inventory", None)
        batches_data = validated_data.pop("batches", None)

        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()

        if inventory_data is not None:
            Inventory.objects.update_or_create(
                item=instance,
                defaults={"company": instance.company, **inventory_data}
            )

        if variants_data is not None:
            instance.variants.all().delete()
            for variant in variants_data:
                ItemVariant.objects.create(company=instance.company, item=instance, **variant)

        if batches_data is not None:
            instance.batches.all().delete()
            for batch in batches_data:
                ItemBatch.objects.create(company=instance.company, item=instance, **batch)

        return instance


class DealItemSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="item.name", read_only=True)

    class Meta:
        model = DealItem
        fields = ["id", "item", "item_name", "quantity"]
        read_only_fields = ["id"]


class DealSerializer(serializers.ModelSerializer):
    deal_items = DealItemSerializer(many=True, required=False)

    class Meta:
        model = Deal
        fields = [
            "id", "name", "description", "price", "image",
            "is_active", "start_date", "end_date", "deal_items",
            "created_at", "updated_at"
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def create(self, validated_data):
        items_data = validated_data.pop("deal_items", [])
        company = validated_data.pop("company", self.context["request"].user.company)
        
        for row in items_data:
            if not CatalogItem.objects.filter(company=company, id=row["item"].id).exists():
                raise serializers.ValidationError({"deal_items": "An item does not belong to your company."})

        deal = Deal.objects.create(company=company, **validated_data)
        for row in items_data:
            DealItem.objects.create(deal=deal, **row)
        return deal

    def update(self, instance, validated_data):
        items_data = validated_data.pop("deal_items", None)

        if items_data is not None:
            company = instance.company
            for row in items_data:
                if not CatalogItem.objects.filter(company=company, id=row["item"].id).exists():
                    raise serializers.ValidationError({"deal_items": "An item does not belong to your company."})

        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()

        if items_data is not None:
            instance.deal_items.all().delete()
            for row in items_data:
                DealItem.objects.create(deal=instance, **row)

        return instance