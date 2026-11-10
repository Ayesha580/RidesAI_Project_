from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

urlpatterns = [
    path("api/accounts/", include("accounts.urls")),
    path("api/billing/", include("billing.urls")),
    path("api/companies/", include("companies.urls")),
    path("api/operations/", include("operations.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)