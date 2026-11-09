import axiosClient from "./axiosClient";

export const billingApi = {
  plans: () => axiosClient.get("/billing/plans/"),
  submitManualPayment: (formData) => axiosClient.post("/billing/manual-payment/", formData),
  businessEmail: () => axiosClient.get("/billing/business-email/"),
  saveBusinessEmail: (data) => axiosClient.put("/billing/business-email/", data),
  consumeMessage: () => axiosClient.post("/billing/messages/consume/"),
  adminManualPayments: () => axiosClient.get("/billing/admin/manual-payments/"),
  adminManualPaymentAction: (id, action, admin_note = "") => axiosClient.post(`/billing/admin/manual-payments/${id}/`, { action, admin_note }),
  overview: () => axiosClient.get("/billing/overview/"),
  customerSession: (portal = false) =>
    axiosClient.post("/billing/customer-session/", { portal }),
  completeRenewal: (checkoutId) =>
    axiosClient.post("/billing/complete-renewal/", { checkout_id: checkoutId }),
  cancel: () => axiosClient.post("/billing/cancel/"),
  resume: () => axiosClient.post("/billing/resume/"),
  getPlanPage: () => axiosClient.get("/billing/select-plan/"),
  selectPlan: (plan_id) => axiosClient.post("/billing/select-plan/", { plan_id }),
  startCheckout: () => axiosClient.post("/billing/customer-session/", {}),
  completePayment: (checkout_id) => axiosClient.post("/billing/complete-renewal/", { checkout_id }),
};