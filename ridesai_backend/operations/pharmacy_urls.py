from django.urls import path
from operations.pharmacy_views import (
    PharmacyBatchesAPIView,
    PharmacyBatchDetailAPIView,
    PharmacyPrescriptionsAPIView,
    PharmacyPrescriptionStatusAPIView,
)

urlpatterns = [
    path("batches/", PharmacyBatchesAPIView.as_view(), name="pharmacy-batches"),
    path("batches/<int:batch_id>/", PharmacyBatchDetailAPIView.as_view(), name="pharmacy-batch-detail"),
    path("prescriptions/", PharmacyPrescriptionsAPIView.as_view(), name="pharmacy-prescriptions"),
    path("prescriptions/<int:prescription_id>/status/", PharmacyPrescriptionStatusAPIView.as_view(), name="pharmacy-prescription-status"),
]
