import api from "./axiosClient";

export const operationsApi = {
  orderCatalog: () => api.get("/operations/orders/catalog/"),
  orders: (params = {}) => api.get("/operations/orders/", { params }),
  createOrder: (data) => api.post("/operations/orders/", data),
  updateOrderStatus: (id, status, note = "") => api.patch(`/operations/orders/${id}/status/`, { status, note }),
  assignOrder: (id, data) => api.post(`/operations/orders/${id}/assign/`, data),
  myDeliveries: () => api.get("/operations/deliveries/my/"),
  deliveries: () => api.get("/operations/deliveries/"),
  assignDelivery: (order_id, rider_id) => api.post("/operations/deliveries/assign/", { order_id, rider_id }),
  riders: () => api.get("/operations/deliveries/riders/"),
  agentSettings: () => api.get("/operations/agent/settings/"),
  updateAgentSettings: (data) => api.patch("/operations/agent/settings/", data),
  chat: (data) => api.post("/operations/agent/chat/", data),
  conversations: () => api.get("/operations/agent/conversations/"),
  updateConversation: (data) => api.patch("/operations/agent/conversations/", data),
};
