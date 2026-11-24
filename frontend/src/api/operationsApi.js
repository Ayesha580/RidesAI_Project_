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
  toggleAgentPause: (is_ai_paused) => api.post("/operations/agent/toggle-pause/", is_ai_paused !== undefined ? { is_ai_paused } : {}),
  chat: (data) => api.post("/operations/agent/chat/", data),
  conversations: () => api.get("/operations/agent/conversations/"),
  updateConversation: (data) => api.patch("/operations/agent/conversations/", data),
  whatsappConnectStatus: () => api.get("/operations/whatsapp/connect/"),
  whatsappConnectGenerate: () => api.post("/operations/whatsapp/connect/"),
  autoAssignRider: (orderId) => api.post(`/operations/orders/${orderId}/auto-assign-rider/`),
  ownerAssistant: (data) => api.post("/operations/owner/assistant/", data),
};

export const dashboardApi = {
  getConversations: (params = {}) => api.get("/dashboard/conversations/", { params }),
  getConversationDetail: (conversationKey) => api.get(`/dashboard/conversations/${conversationKey}/`),
  sendConversationReply: (conversationKey, data) => api.post(`/dashboard/conversations/${conversationKey}/reply/`, data),
  getOrders: (params = {}) => api.get("/dashboard/orders/", { params }),
  updateOrderStatus: (orderId, data) => api.patch(`/dashboard/orders/${orderId}/status/`, data),
  autoAssignRider: (orderId) => api.post(`/dashboard/orders/${orderId}/auto-assign-rider/`),
  getOrderReceipt: (orderId, type = "invoice") => api.get(`/dashboard/orders/${orderId}/receipt/`, { params: { type } }),
  printOrderReceipt: (orderId, data) => api.post(`/dashboard/orders/${orderId}/print/`, data),
  getCalls: (params = {}) => api.get("/dashboard/calls/", { params }),
  getCallEvents: (callId) => api.get(`/dashboard/calls/${callId}/events/`),
};

export const kitchenApi = {
  getOrders: () => api.get("/kitchen/orders/"),
  updateOrderStatus: (orderId, status) => api.patch(`/kitchen/orders/${orderId}/status/`, { status }),
};

export const riderApi = {
  getOrders: () => api.get("/rider/orders/"),
  updateOrderStatus: (orderId, status) => api.patch(`/rider/orders/${orderId}/status/`, { status }),
};

export const pharmacyApi = {
  getBatches: (params = {}) => api.get("/pharmacy/batches/", { params }),
  createBatch: (data) => api.post("/pharmacy/batches/", data),
  updateBatch: (batchId, data) => api.patch(`/pharmacy/batches/${batchId}/`, data),
  deleteBatch: (batchId) => api.delete(`/pharmacy/batches/${batchId}/`),
  getPrescriptions: (params = {}) => api.get("/pharmacy/prescriptions/", { params }),
  createPrescription: (data) => api.post("/pharmacy/prescriptions/", data),
  updatePrescriptionStatus: (prescriptionId, data) =>
    api.patch(`/pharmacy/prescriptions/${prescriptionId}/status/`, data),
};

export const clinicApi = {
  getDoctors: (params = {}) => api.get("/clinic/doctors/", { params }),
  createDoctor: (data) => api.post("/clinic/doctors/", data),
  updateDoctor: (id, data) => api.patch(`/clinic/doctors/${id}/`, data),
  deleteDoctor: (id) => api.delete(`/clinic/doctors/${id}/`),
  getPatients: (params = {}) => api.get("/clinic/patients/", { params }),
  createPatient: (data) => api.post("/clinic/patients/", data),
  updatePatient: (id, data) => api.patch(`/clinic/patients/${id}/`, data),
  deletePatient: (id) => api.delete(`/clinic/patients/${id}/`),
  getAppointments: (params = {}) => api.get("/clinic/appointments/", { params }),
  createAppointment: (data) => api.post("/clinic/appointments/", data),
  updateAppointmentStatus: (id, data) => api.patch(`/clinic/appointments/${id}/status/`, data),
};

export const retailApi = {
  getFulfillmentOrders: (params = {}) => api.get("/retail/fulfillment/", { params }),
  updateFulfillmentStatus: (orderId, data) => api.patch(`/retail/fulfillment/${orderId}/status/`, data),
  getReturns: (params = {}) => api.get("/retail/returns/", { params }),
  createReturn: (data) => api.post("/retail/returns/", data),
  updateReturnStatus: (id, data) => api.patch(`/retail/returns/${id}/status/`, data),
  getInventoryAlerts: () => api.get("/retail/inventory-alerts/"),
};

export const hospitalApi = {
  getSummary: () => api.get("/operations/hospital/summary/"),
  getDepartments: (params = {}) => api.get("/operations/hospital/departments/", { params }),
  createDepartment: (data) => api.post("/operations/hospital/departments/", data),
  updateDepartment: (id, data) => api.patch(`/operations/hospital/departments/${id}/`, data),
  deleteDepartment: (id) => api.delete(`/operations/hospital/departments/${id}/`),
  getLabBookings: (params = {}) => api.get("/operations/hospital/lab-bookings/", { params }),
  createLabBooking: (data) => api.post("/operations/hospital/lab-bookings/", data),
  updateLabBookingStatus: (id, data) => api.patch(`/operations/hospital/lab-bookings/${id}/status/`, data),
};

export const analyticsApi = {
  getOverview: (params = {}) => api.get("/operations/analytics/overview/", { params }),
  exportCsv: (params = {}) => api.get("/operations/analytics/export/csv/", { params, responseType: "blob" }),
};

export const notificationTemplatesApi = {
  list: () => api.get("/operations/notifications/templates/"),
  update: (eventType, data) => api.patch(`/operations/notifications/templates/${eventType}/`, data),
  reset: (eventType) => api.post(`/operations/notifications/templates/${eventType}/reset/`),
};

