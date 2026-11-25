"""
Restaurant Ingredient Inventory, Dish Recipes, Auto-Deduction & Stock Movement Logs.
Strictly multi-tenant (scoped to `request.user.company`) and PostgreSQL 16 compatible.

Endpoints:
- GET / POST   /api/operations/restaurant/inventory/
- PATCH / DEL  /api/operations/restaurant/inventory/<id>/
- POST         /api/operations/restaurant/inventory/<id>/adjust/
- GET          /api/operations/restaurant/inventory/<id>/movements/
- GET / PUT    /api/operations/restaurant/recipes/<catalog_item_id>/
"""

import logging
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Set

from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from companies.models import CatalogItem
from operations.models import (
    IngredientStockMovement,
    MenuItemRecipe,
    Order,
    RestaurantIngredient,
)

logger = logging.getLogger("operations.inventory")


def _to_decimal(val: Any, default: Decimal = Decimal("0")) -> Decimal:
    try:
        return Decimal(str(val))
    except (InvalidOperation, TypeError, ValueError):
        return default


def get_out_of_stock_dish_ids(company) -> Set[int]:
    """
    Returns set of `CatalogItem.id`s in `company` where at least one mapped recipe
    ingredient has `current_stock <= 0` or `current_stock < quantity_required`.
    """
    if not company:
        return set()
    oos_ids: Set[int] = set()
    recipes = MenuItemRecipe.objects.filter(company=company).select_related("ingredient")
    for r in recipes:
        ing = r.ingredient
        if ing.current_stock <= 0 or ing.current_stock < r.quantity_required:
            oos_ids.add(r.catalog_item_id)
    return oos_ids


def deduct_recipe_ingredients_for_order(order: Order) -> None:
    """
    Atomically deducts recipe ingredients for every ordered dish on `order`,
    clamping ingredient stock at 0 and logging `order_deduction` movements.
    """
    if not order or not getattr(order, "company_id", None):
        return
    try:
        with transaction.atomic():
            order_items = list(order.items.select_related("item").all())
            for oi in order_items:
                if not oi.item_id:
                    continue
                recipes = list(
                    MenuItemRecipe.objects.filter(
                        company=order.company,
                        catalog_item_id=oi.item_id,
                    ).select_related("ingredient")
                )
                for recipe in recipes:
                    needed = (recipe.quantity_required * Decimal(str(oi.quantity or 1))).quantize(Decimal("0.001"))
                    if needed <= 0:
                        continue
                    ing = RestaurantIngredient.objects.select_for_update().get(
                        pk=recipe.ingredient_id,
                        company=order.company,
                    )
                    new_stock = max(Decimal("0"), ing.current_stock - needed)
                    actual_delta = new_stock - ing.current_stock  # negative or 0
                    ing.current_stock = new_stock
                    ing.save(update_fields=["current_stock", "updated_at"])

                    IngredientStockMovement.objects.create(
                        company=order.company,
                        ingredient=ing,
                        movement_type=IngredientStockMovement.MOVEMENT_ORDER_DEDUCTION,
                        quantity_delta=-needed if actual_delta == 0 and needed > 0 else actual_delta,
                        stock_after=new_stock,
                        reason=f"Order #{order.order_number} ({oi.item_name} x{oi.quantity})",
                        order=order,
                    )
    except Exception as exc:
        logger.warning("[RestaurantInventory] Recipe deduction failed for order %s: %s", getattr(order, "id", None), exc)


def restore_recipe_ingredients_for_order(order: Order) -> None:
    """
    Idempotently restores deducted recipe ingredients when an order is cancelled
    and logs `order_cancellation_restore` movements.
    """
    if not order or not getattr(order, "company_id", None):
        return
    try:
        with transaction.atomic():
            already_restored = IngredientStockMovement.objects.filter(
                company=order.company,
                order=order,
                movement_type=IngredientStockMovement.MOVEMENT_ORDER_CANCEL_RESTORE,
            ).exists()
            if already_restored:
                return

            deductions = list(
                IngredientStockMovement.objects.filter(
                    company=order.company,
                    order=order,
                    movement_type=IngredientStockMovement.MOVEMENT_ORDER_DEDUCTION,
                )
            )
            for mov in deductions:
                restore_qty = abs(mov.quantity_delta)
                if restore_qty <= 0:
                    continue
                ing = RestaurantIngredient.objects.select_for_update().filter(
                    pk=mov.ingredient_id,
                    company=order.company,
                ).first()
                if not ing:
                    continue
                ing.current_stock = ing.current_stock + restore_qty
                ing.save(update_fields=["current_stock", "updated_at"])
                IngredientStockMovement.objects.create(
                    company=order.company,
                    ingredient=ing,
                    movement_type=IngredientStockMovement.MOVEMENT_ORDER_CANCEL_RESTORE,
                    quantity_delta=restore_qty,
                    stock_after=ing.current_stock,
                    reason=f"Restored from cancelled Order #{order.order_number}",
                    order=order,
                )
    except Exception as exc:
        logger.warning("[RestaurantInventory] Recipe restore failed for order %s: %s", getattr(order, "id", None), exc)


def _serialize_ingredient(ing: RestaurantIngredient, linked_dishes_count: int = 0) -> Dict[str, Any]:
    return {
        "id": ing.id,
        "name": ing.name,
        "sku": ing.sku,
        "unit": ing.unit,
        "current_stock": float(ing.current_stock),
        "low_stock_threshold": float(ing.low_stock_threshold),
        "cost_per_unit": float(ing.cost_per_unit),
        "supplier_name": ing.supplier_name,
        "status": ing.stock_status,
        "linked_dishes_count": linked_dishes_count,
        "updated_at": ing.updated_at.isoformat() if ing.updated_at else None,
    }


def _serialize_movement(m: IngredientStockMovement) -> Dict[str, Any]:
    return {
        "id": m.id,
        "ingredient_id": m.ingredient_id,
        "ingredient_name": m.ingredient.name if m.ingredient else "",
        "unit": m.ingredient.unit if m.ingredient else "",
        "movement_type": m.movement_type,
        "movement_label": m.get_movement_type_display(),
        "quantity_delta": float(m.quantity_delta),
        "stock_after": float(m.stock_after),
        "reason": m.reason,
        "order_id": m.order_id,
        "order_number": m.order.order_number if m.order else None,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


class RestaurantIngredientListCreateAPIView(APIView):
    """GET / POST /api/operations/restaurant/inventory/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        qs = (
            RestaurantIngredient.objects.filter(company=company)
            .annotate(linked_dishes=Count("used_in_recipes", distinct=True))
            .order_by("name")
        )
        all_items = [_serialize_ingredient(i, linked_dishes_count=i.linked_dishes) for i in qs]

        summary = {
            "total": len(all_items),
            "in_stock": sum(1 for i in all_items if i["status"] == "in_stock"),
            "low_stock": sum(1 for i in all_items if i["status"] == "low_stock"),
            "out_of_stock": sum(1 for i in all_items if i["status"] == "out_of_stock"),
        }

        status_filter = (request.query_params.get("status") or "all").strip().lower()
        search = (request.query_params.get("q") or "").strip().lower()

        filtered = all_items
        if status_filter in ("in_stock", "low_stock", "out_of_stock"):
            filtered = [i for i in filtered if i["status"] == status_filter]
        if search:
            filtered = [
                i for i in filtered
                if search in i["name"].lower()
                or search in (i["sku"] or "").lower()
                or search in (i["supplier_name"] or "").lower()
            ]

        return Response({"summary": summary, "ingredients": filtered}, status=200)

    def post(self, request):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        name = str(request.data.get("name") or "").strip()[:160]
        if not name:
            return Response({"name": "Ingredient name is required."}, status=400)

        if RestaurantIngredient.objects.filter(company=company, name__iexact=name).exists():
            return Response({"name": f"Ingredient '{name}' already exists."}, status=400)

        unit = str(request.data.get("unit") or "pcs").strip().lower()
        if unit not in {c[0] for c in RestaurantIngredient.UNIT_CHOICES}:
            unit = "pcs"

        initial_stock = max(Decimal("0"), _to_decimal(request.data.get("current_stock"), Decimal("0")))
        threshold = max(Decimal("0"), _to_decimal(request.data.get("low_stock_threshold"), Decimal("5")))
        cost = max(Decimal("0"), _to_decimal(request.data.get("cost_per_unit"), Decimal("0")))

        ing = RestaurantIngredient.objects.create(
            company=company,
            name=name,
            sku=str(request.data.get("sku") or "").strip()[:80],
            unit=unit,
            current_stock=initial_stock,
            low_stock_threshold=threshold,
            cost_per_unit=cost,
            supplier_name=str(request.data.get("supplier_name") or "").strip()[:160],
        )

        if initial_stock > 0:
            IngredientStockMovement.objects.create(
                company=company,
                ingredient=ing,
                movement_type=IngredientStockMovement.MOVEMENT_RESTOCK,
                quantity_delta=initial_stock,
                stock_after=initial_stock,
                reason="Initial stock on creation",
            )

        return Response(_serialize_ingredient(ing, linked_dishes_count=0), status=201)


class RestaurantIngredientDetailAPIView(APIView):
    """PATCH / DELETE /api/operations/restaurant/inventory/<pk>/"""
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk: int):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        ing = get_object_or_404(RestaurantIngredient, pk=pk, company=company)

        if "name" in request.data and str(request.data["name"]).strip():
            ing.name = str(request.data["name"]).strip()[:160]
        if "sku" in request.data:
            ing.sku = str(request.data["sku"] or "").strip()[:80]
        if "unit" in request.data:
            u = str(request.data["unit"]).strip().lower()
            if u in {c[0] for c in RestaurantIngredient.UNIT_CHOICES}:
                ing.unit = u
        if "low_stock_threshold" in request.data:
            ing.low_stock_threshold = max(Decimal("0"), _to_decimal(request.data["low_stock_threshold"], ing.low_stock_threshold))
        if "cost_per_unit" in request.data:
            ing.cost_per_unit = max(Decimal("0"), _to_decimal(request.data["cost_per_unit"], ing.cost_per_unit))
        if "supplier_name" in request.data:
            ing.supplier_name = str(request.data["supplier_name"] or "").strip()[:160]
        if "current_stock" in request.data:
            new_val = max(Decimal("0"), _to_decimal(request.data["current_stock"], ing.current_stock))
            delta = new_val - ing.current_stock
            if delta != 0:
                ing.current_stock = new_val
                IngredientStockMovement.objects.create(
                    company=company,
                    ingredient=ing,
                    movement_type=IngredientStockMovement.MOVEMENT_MANUAL_ADJUSTMENT,
                    quantity_delta=delta,
                    stock_after=new_val,
                    reason="Updated via ingredient edit",
                )

        ing.save()
        linked = ing.used_in_recipes.count()
        return Response(_serialize_ingredient(ing, linked_dishes_count=linked), status=200)

    def delete(self, request, pk: int):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)
        ing = get_object_or_404(RestaurantIngredient, pk=pk, company=company)
        ing.delete()
        return Response(status=204)


class RestaurantIngredientAdjustAPIView(APIView):
    """POST /api/operations/restaurant/inventory/<pk>/adjust/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        movement_type = str(request.data.get("movement_type") or IngredientStockMovement.MOVEMENT_RESTOCK).strip().lower()
        allowed_types = {
            IngredientStockMovement.MOVEMENT_RESTOCK,
            IngredientStockMovement.MOVEMENT_WASTE,
            IngredientStockMovement.MOVEMENT_MANUAL_ADJUSTMENT,
        }
        if movement_type not in allowed_types:
            return Response({"movement_type": "Must be restock, waste, or manual_adjustment."}, status=400)

        qty = _to_decimal(request.data.get("quantity"), Decimal("0"))
        if qty == 0:
            return Response({"quantity": "Quantity must be non-zero."}, status=400)

        reason = str(request.data.get("reason") or "").strip()[:255]

        with transaction.atomic():
            ing = get_object_or_404(
                RestaurantIngredient.objects.select_for_update(),
                pk=pk,
                company=company,
            )
            if movement_type == IngredientStockMovement.MOVEMENT_RESTOCK:
                delta = abs(qty)
            elif movement_type == IngredientStockMovement.MOVEMENT_WASTE:
                delta = -abs(qty)
            else:
                delta = qty

            new_stock = max(Decimal("0"), ing.current_stock + delta)
            ing.current_stock = new_stock
            ing.save(update_fields=["current_stock", "updated_at"])

            mov = IngredientStockMovement.objects.create(
                company=company,
                ingredient=ing,
                movement_type=movement_type,
                quantity_delta=delta,
                stock_after=new_stock,
                reason=reason or movement_type.replace("_", " ").title(),
            )

        linked = ing.used_in_recipes.count()
        return Response({
            "ingredient": _serialize_ingredient(ing, linked_dishes_count=linked),
            "movement": _serialize_movement(mov),
        }, status=200)


class RestaurantIngredientMovementsAPIView(APIView):
    """GET /api/operations/restaurant/inventory/<pk>/movements/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk: int):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        ing = get_object_or_404(RestaurantIngredient, pk=pk, company=company)
        movements = (
            IngredientStockMovement.objects.filter(company=company, ingredient=ing)
            .select_related("ingredient", "order")
            .order_by("-created_at", "-id")[:50]
        )
        return Response([_serialize_movement(m) for m in movements], status=200)


class MenuItemRecipeAPIView(APIView):
    """GET / PUT /api/operations/restaurant/recipes/<catalog_item_id>/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, catalog_item_id: int):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        dish = get_object_or_404(CatalogItem, pk=catalog_item_id, company=company)
        rows = (
            MenuItemRecipe.objects.filter(company=company, catalog_item=dish)
            .select_related("ingredient")
            .order_by("ingredient__name")
        )
        return Response({
            "catalog_item_id": dish.id,
            "catalog_item_name": dish.name,
            "ingredients": [
                {
                    "id": r.id,
                    "ingredient_id": r.ingredient_id,
                    "ingredient_name": r.ingredient.name,
                    "unit": r.ingredient.unit,
                    "current_stock": float(r.ingredient.current_stock),
                    "quantity_required": float(r.quantity_required),
                }
                for r in rows
            ],
        }, status=200)

    def put(self, request, catalog_item_id: int):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        dish = get_object_or_404(CatalogItem, pk=catalog_item_id, company=company)
        items_payload = request.data.get("ingredients")
        if not isinstance(items_payload, list):
            return Response({"ingredients": "Expected a list of {ingredient_id, quantity_required}."}, status=400)

        cleaned_rows = []
        seen_ids = set()
        for row in items_payload:
            if not isinstance(row, dict):
                continue
            ing_id = row.get("ingredient_id")
            qty = _to_decimal(row.get("quantity_required"), Decimal("0"))
            if not ing_id or qty <= 0 or ing_id in seen_ids:
                continue
            ing = get_object_or_404(RestaurantIngredient, pk=ing_id, company=company)
            seen_ids.add(ing_id)
            cleaned_rows.append((ing, qty))

        with transaction.atomic():
            MenuItemRecipe.objects.filter(company=company, catalog_item=dish).delete()
            for ing, qty in cleaned_rows:
                MenuItemRecipe.objects.create(
                    company=company,
                    catalog_item=dish,
                    ingredient=ing,
                    quantity_required=qty,
                )

        return self.get(request, catalog_item_id)
