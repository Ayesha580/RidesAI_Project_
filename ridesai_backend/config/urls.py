from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from django.contrib import admin

urlpatterns = [
    path("api/accounts/", include("accounts.urls")),
    path('admin/', admin.site.urls),
    path("api/billing/", include("billing.urls")),
    path("api/companies/", include("companies.urls")),
    path("api/operations/", include("operations.urls")),
    path("api/dashboard/", include("operations.dashboard_urls")),
    path("api/kitchen/", include("operations.kitchen_urls")),
    path("api/rider/", include("operations.rider_urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)