import axiosClient from "./axiosClient";

export const billingApi = {
  plans: () => axiosClient.get("/billing/plans/"),
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