// src/api/staffApi.js
import api from "./axiosClient";

export const staffApi = {
  list: () => api.get("/accounts/staff/"),
  create: (data) => api.post("/accounts/staff/", data),
  update: (id, data) => api.patch(`/accounts/staff/${id}/`, data),
  remove: (id) => api.delete(`/accounts/staff/${id}/`),
};

export const roleApi = {
  modules: () => api.get("/accounts/modules/"),
  list: () => api.get("/accounts/roles/"),
  create: (data) => api.post("/accounts/roles/", data),
  update: (id, data) => api.patch(`/accounts/roles/${id}/`, data),
  remove: (id) => api.delete(`/accounts/roles/${id}/`),
};

export const billingApi = {
  overview: () => api.get("/billing/overview/"),
};