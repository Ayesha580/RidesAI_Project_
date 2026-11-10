from rest_framework import serializers
from .models import CatalogCategory, CatalogItem, ItemVariant, Inventory, StockMovement, ItemBatch, Deal, DealItem


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
    category_name = serializers.CharField(source="category.name", read_only=True)
    variants = ItemVariantSerializer(many=True, required=False)
    inventory = InventorySerializer(required=False)
    batches = ItemBatchSerializer(many=True, required=False)

    class Meta:
        model = CatalogItem
        fields = [
            "id", "category", "category_name", "name", "item_type",
            "description", "sku", "barcode", "brand", "price",
            "cost_price", "unit", "image", "attributes", "is_available",
            "variants", "inventory", "batches", "created_at", "updated_at"
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_category(self, category):
        request = self.context.get("request")
        if category and category.company_id != request.user.company_id:
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