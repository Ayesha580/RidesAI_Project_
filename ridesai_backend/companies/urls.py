from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CatalogCategoryViewSet,
    CatalogItemViewSet,
    DealViewSet,
    CatalogImportAPIView,
    CatalogExportAPIView,
)

router = DefaultRouter()
router.register("catalog/categories", CatalogCategoryViewSet, basename="catalog-categories")
router.register("catalog/items", CatalogItemViewSet, basename="catalog-items")
router.register("catalog/deals", DealViewSet, basename="catalog-deals")

urlpatterns = [
    path("", include(router.urls)),
    path("catalog/import/", CatalogImportAPIView.as_view(), name="catalog-import"),
    path("catalog/export/", CatalogExportAPIView.as_view(), name="catalog-export"),
]