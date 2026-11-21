import axiosClient from "./axiosClient";

export const authApi = {
  login: (data) => axiosClient.post("/accounts/login/", data),
  adminLogin: (data) => axiosClient.post("/accounts/admin-login/", data),
  register: (formData) => axiosClient.post("/accounts/register/", formData),
  verifyEmail: (otp, email) => axiosClient.post("/accounts/verify-email/", { otp, email }),
  resendVerification: (email) => axiosClient.post("/accounts/resend-verification/", { email }),
  forgotPassword: (email) => axiosClient.post("/accounts/forgot-password/", { email }),
  resetPassword: (uid, token, new_password) =>
    axiosClient.post("/accounts/reset-password/", { uid, token, new_password }),
  me: () => axiosClient.get("/accounts/me/"),

  // Super admin
  pendingCompanies: () => axiosClient.get("/accounts/admin/companies/pending/"),
  companyAction: (id, action) =>
    axiosClient.post(`/accounts/admin/companies/${id}/${action}/`), // action: approve | reject
  manualPayments: () => axiosClient.get("/billing/admin/manual-payments/"),
  manualPaymentAction: (id, action, admin_note = "") => axiosClient.post(`/billing/admin/manual-payments/${id}/`, { action, admin_note }),
};