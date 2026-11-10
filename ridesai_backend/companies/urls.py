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

from .business_config import (
    LocationViewSet, HoursViewSet, ServiceAreaViewSet, KnowledgeViewSet,
    DeliveryEligibilityAPIView,
)

# Register router endpoints before include(router.urls), otherwise the
# included URL list is frozen before these endpoints are registered.
router.register("locations", LocationViewSet, basename="business-locations")
router.register("hours", HoursViewSet, basename="business-hours")
router.register("service-areas", ServiceAreaViewSet, basename="business-service-areas")
router.register("knowledge", KnowledgeViewSet, basename="business-knowledge")

urlpatterns = [
    path("", include(router.urls)),
    path("catalog/import/", CatalogImportAPIView.as_view(), name="catalog-import"),
    path("catalog/export/", CatalogExportAPIView.as_view(), name="catalog-export"),
    path("delivery-eligibility/", DeliveryEligibilityAPIView.as_view(), name="delivery-eligibility"),
]
