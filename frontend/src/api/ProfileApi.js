import axiosClient from "./axiosClient";

export const profileApi = {
  get: () => axiosClient.get("/accounts/profile/"),
  update: (data) => axiosClient.patch("/accounts/profile/", data),
  changePassword: (data) => axiosClient.post("/accounts/profile/password/", data),
};