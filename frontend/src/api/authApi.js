import axiosClient from "./axiosClient";

export const authApi = {
  login: (data) => axiosClient.post("/accounts/login/", data),
  adminLogin: (data) => axiosClient.post("/accounts/admin-login/", data),
  register: (formData) => axiosClient.post("/accounts/register/", formData),
  verifyEmail: (otp, email) => axiosClient.post("/accounts/verify-email/", { otp, email }),
  resendVerification: (email) => axiosClient.post("/accounts/resend-verification/", { email }),
  me: () => axiosClient.get("/accounts/me/"),

  // Super admin
  pendingCompanies: () => axiosClient.get("/accounts/admin/companies/pending/"),
  companyAction: (id, action) =>
    axiosClient.post(`/accounts/admin/companies/${id}/${action}/`), // action: approve | reject
  manualPayments: () => axiosClient.get("/billing/admin/manual-payments/"),
  manualPaymentAction: (id, action, admin_note = "") => axiosClient.post(`/billing/admin/manual-payments/${id}/`, { action, admin_note }),
};