from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("api/accounts/", include("accounts.urls")),
    path("api/billing/", include("billing.urls")),
    path("api/companies/", include("companies.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)