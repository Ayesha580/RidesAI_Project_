import csv
from decimal import Decimal, InvalidOperation
from django.db import transaction
from django.http import HttpResponse
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from accounts.permissions import IsCompanyPaymentActive, IsOwner
from .models import CatalogCategory, CatalogItem, Inventory, StockMovement, Deal, ItemBatch
from .serializers import CatalogCategorySerializer, CatalogItemSerializer, DealSerializer
from .permissions import CatalogModulePermission


class CatalogBaseViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsCompanyPaymentActive, IsOwner, CatalogModulePermission]

    def get_queryset(self):
        return self.queryset.filter(company=self.request.user.company)

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)


class CatalogCategoryViewSet(CatalogBaseViewSet):
    queryset = CatalogCategory.objects.all()
    serializer_class = CatalogCategorySerializer


class CatalogItemViewSet(CatalogBaseViewSet):
    queryset = CatalogItem.objects.select_related("category").prefetch_related("variants", "batches", "inventory")
    serializer_class = CatalogItemSerializer

    @action(detail=True, methods=["patch"])
    def stock(self, request, pk=None):
        item = self.get_object()
        inventory, _ = Inventory.objects.get_or_create(
            company=request.user.company,
            item=item
        )

        is_unlimited = request.data.get("is_unlimited", inventory.is_unlimited)
        quantity = request.data.get("quantity", inventory.quantity)
        note = request.data.get("note", "")

        try:
            quantity = Decimal(str(quantity))
            if quantity < 0:
                raise ValueError
        except (InvalidOperation, ValueError):
            return Response({"error": "Quantity must be zero or greater."}, status=400)

        old_quantity = inventory.quantity
        inventory.is_unlimited = is_unlimited
        inventory.quantity = quantity
        inventory.save()

        if not is_unlimited and quantity != old_quantity:
            movement_type = "add" if quantity > old_quantity else "remove"
            StockMovement.objects.create(
                company=request.user.company,
                item=item,
                movement_type=movement_type,
                quantity=abs(quantity - old_quantity),
                note=note
            )

        return Response({
            "message": "Stock updated successfully.",
            "is_unlimited": inventory.is_unlimited,
            "quantity": inventory.quantity,
            "in_stock": inventory.in_stock
        })

    @action(detail=True, methods=["post"])
    def add_stock(self, request, pk=None):
        item = self.get_object()
        try:
            quantity = Decimal(str(request.data.get("quantity", 0)))
            if quantity <= 0:
                raise ValueError
        except (InvalidOperation, ValueError):
            return Response({"error": "Enter a valid quantity greater than zero."}, status=400)

        inventory, _ = Inventory.objects.get_or_create(
            company=request.user.company,
            item=item
        )
        inventory.is_unlimited = False
        inventory.quantity += quantity
        inventory.save()

        StockMovement.objects.create(
            company=request.user.company,
            item=item,
            movement_type="add",
            quantity=quantity,
            note=request.data.get("note", "")
        )

        return Response({"message": "Stock added.", "quantity": inventory.quantity})

    @action(detail=True, methods=["post"])
    def remove_stock(self, request, pk=None):
        item = self.get_object()
        inventory = Inventory.objects.filter(company=request.user.company, item=item).first()

        if not inventory:
            return Response({"error": "Inventory record not found."}, status=404)

        if inventory.is_unlimited:
            return Response({"error": "This item has unlimited stock."}, status=400)

        try:
            quantity = Decimal(str(request.data.get("quantity", 0)))
            if quantity <= 0 or quantity > inventory.quantity:
                raise ValueError
        except (InvalidOperation, ValueError):
            return Response({"error": "Enter a valid quantity within available stock."}, status=400)

        inventory.quantity -= quantity
        inventory.save()

        StockMovement.objects.create(
            company=request.user.company,
            item=item,
            movement_type="remove",
            quantity=quantity,
            note=request.data.get("note", "")
        )

        return Response({"message": "Stock removed.", "quantity": inventory.quantity})


class DealViewSet(CatalogBaseViewSet):
    queryset = Deal.objects.prefetch_related("deal_items__item")
    serializer_class = DealSerializer


class CatalogImportAPIView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyPaymentActive, IsOwner, CatalogModulePermission]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        file = request.FILES.get("file")
        if not file:
            return Response({"error": "CSV file is required."}, status=400)

        if not file.name.lower().endswith(".csv"):
            return Response({"error": "Only CSV files are supported."}, status=400)

        try:
            decoded = file.read().decode("utf-8-sig")
            reader = csv.DictReader(decoded.splitlines())
            required = {"name", "price"}

            if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
                return Response({"error": "CSV must contain name and price columns."}, status=400)

            company = request.user.company
            created = 0

            with transaction.atomic():
                for row in reader:
                    name = (row.get("name") or "").strip()
                    if not name:
                        continue

                    category = None
                    category_name = (row.get("category") or "").strip()
                    if category_name:
                        category, _ = CatalogCategory.objects.get_or_create(
                            company=company,
                            name=category_name
                        )

                    price = Decimal(row.get("price") or "0")
                    if price < 0:
                        raise ValueError("Price cannot be negative.")

                    item = CatalogItem.objects.create(
                        company=company,
                        category=category,
                        name=name,
                        description=row.get("description", ""),
                        sku=row.get("sku", "").strip(),
                        barcode=row.get("barcode", "").strip(),
                        brand=row.get("brand", "").strip(),
                        price=price,
                        unit=row.get("unit", "").strip(),
                        is_available=(row.get("is_available", "true").lower() in ["true", "1", "yes"])
                    )

                    unlimited = row.get("is_unlimited", "true").lower() in ["true", "1", "yes"]
                    quantity = Decimal(row.get("quantity") or "0")

                    Inventory.objects.create(
                        company=company,
                        item=item,
                        is_unlimited=unlimited,
                        quantity=quantity
                    )
                    created += 1

            return Response({"message": f"{created} items imported successfully.", "created": created})

        except (UnicodeDecodeError, InvalidOperation, ValueError) as error:
            return Response({"error": str(error)}, status=400)


class CatalogExportAPIView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyPaymentActive, IsOwner, CatalogModulePermission]

    def get(self, request):
        company = request.user.company
        items = CatalogItem.objects.filter(company=company).select_related("category").select_related("inventory")

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="catalog_items.csv"'

        writer = csv.writer(response)
        writer.writerow([
            "name", "description", "category", "sku", "barcode",
            "brand", "price", "unit", "is_available",
            "is_unlimited", "quantity"
        ])

        for item in items:
            inventory = getattr(item, "inventory", None)
            writer.writerow([
                item.name,
                item.description,
                item.category.name if item.category else "",
                item.sku,
                item.barcode,
                item.brand,
                item.price,
                item.unit,
                item.is_available,
                inventory.is_unlimited if inventory else True,
                inventory.quantity if inventory else 0
            ])

        return response