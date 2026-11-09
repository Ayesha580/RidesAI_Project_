from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views
from .staff_views import (
    ModuleCatalogAPIView, RoleListCreateAPIView, RoleDetailAPIView,
    StaffAPIView, StaffDetailAPIView,
)
from .profile_views import ChangePasswordAPIView, ProfileAPIView

urlpatterns = [

    path("modules/", ModuleCatalogAPIView.as_view()),
    path("roles/", RoleListCreateAPIView.as_view()),
    path("roles/<int:role_id>/", RoleDetailAPIView.as_view()),
    path("staff/", StaffAPIView.as_view()),
    path("staff/<int:user_id>/", StaffDetailAPIView.as_view()),
    path("register/", views.RegisterAPIView.as_view()),
    path("verify-email/", views.VerifyEmailAPIView.as_view()),
    path("resend-verification/", views.ResendVerificationEmailAPIView.as_view()),
    path("login/", views.LoginAPIView.as_view()),
    path("admin-login/", views.AdminLoginAPIView.as_view()),
    path("token/refresh/", TokenRefreshView.as_view()),
    path("me/", views.MeAPIView.as_view()),
    path("users/", views.UserListAPIView.as_view()),
    path("profile/", ProfileAPIView.as_view()),
    path("profile/password/", ChangePasswordAPIView.as_view()),
    path("public/businesses/", views.PublicBusinessesAPIView.as_view()),
    # Super admin
    # path("admin/companies/pending/", views.PendingCompaniesAPIView.as_view()),
    # path("admin/companies/<int:company_id>/approve/", views.ApproveCompanyAPIView.as_view()),
    # path("admin/companies/<int:company_id>/reject/", views.RejectCompanyAPIView.as_view()),
]