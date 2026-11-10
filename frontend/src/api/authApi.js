import axiosClient from "./axiosClient";

export const authApi = {
  login: (data) => axiosClient.post("/accounts/login/", data),
  register: (formData) => axiosClient.post("/accounts/register/", formData),
  verifyEmail: (otp, email) => axiosClient.post("/accounts/verify-email/", { otp, email }),
  resendVerification: (email) => axiosClient.post("/accounts/resend-verification/", { email }),
  me: () => axiosClient.get("/accounts/me/"),
};
