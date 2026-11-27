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
  whatsappReconnect: () => api.post("/operations/whatsapp/reconnect/"),
  whatsappDisconnect: () => api.post("/operations/whatsapp/disconnect/"),
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
  getDashboard: () => api.get("/operations/hospital/dashboard/"),
  listDepartments: (params = {}) => api.get("/operations/hospital/departments/", { params }),
  getDepartments: (params = {}) => api.get("/operations/hospital/departments/", { params }),
  createDepartment: (data) => api.post("/operations/hospital/departments/", data),
  updateDepartment: (id, data) => api.patch(`/operations/hospital/departments/${id}/`, data),
  deleteDepartment: (id) => api.delete(`/operations/hospital/departments/${id}/`),
  listWards: () => api.get("/operations/hospital/wards/"),
  createWard: (data) => api.post("/operations/hospital/wards/", data),
  updateWard: (id, data) => api.patch(`/operations/hospital/wards/${id}/`, data),
  deleteWard: (id) => api.delete(`/operations/hospital/wards/${id}/`),
  addBed: (wardId, data) => api.post(`/operations/hospital/wards/${wardId}/beds/`, data),
  updateBedStatus: (bedId, status) => api.patch(`/operations/hospital/beds/${bedId}/`, { status }),
  deleteBed: (bedId) => api.delete(`/operations/hospital/beds/${bedId}/`),
  admitBed: (bedId, data) => api.post(`/operations/hospital/beds/${bedId}/admit/`, data),
  dischargeBed: (bedId, data = {}) => api.post(`/operations/hospital/beds/${bedId}/discharge/`, data),
  listDoctors: (params = {}) => api.get("/operations/hospital/doctors/", { params }),
  createDoctor: (data) => api.post("/operations/hospital/doctors/", data),
  updateDoctor: (id, data) => api.patch(`/operations/hospital/doctors/${id}/`, data),
  deleteDoctor: (id) => api.delete(`/operations/hospital/doctors/${id}/`),
  updateDoctorStatus: (id, availability_status) =>
    api.post(`/operations/hospital/doctors/${id}/status/`, { availability_status }),
  listAppointments: (params = {}) => api.get("/operations/hospital/appointments/", { params }),
  createAppointment: (data) => api.post("/operations/hospital/appointments/", data),
  updateAppointment: (id, data) => api.patch(`/operations/hospital/appointments/${id}/`, data),
  deleteAppointment: (id) => api.delete(`/operations/hospital/appointments/${id}/`),
  updateAppointmentStatus: (id, data) =>
    api.post(
      `/operations/hospital/appointments/${id}/status/`,
      typeof data === "string" ? { status: data } : data
    ),
  getOpdQueue: (params = {}) => api.get("/operations/hospital/opd-queue/", { params }),
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

export const faqLearningApi = {
  listSuggestions: (params = {}) => api.get("/operations/faqs/suggestions/", { params }),
  approveSuggestion: (id, data) => api.post(`/operations/faqs/suggestions/${id}/approve/`, data),
  dismissSuggestion: (id) => api.post(`/operations/faqs/suggestions/${id}/dismiss/`),
  listFaqs: () => api.get("/operations/faqs/"),
  createFaq: (data) => api.post("/operations/faqs/", data),
  updateFaq: (id, data) => api.patch(`/operations/faqs/${id}/`, data),
  deleteFaq: (id) => api.delete(`/operations/faqs/${id}/`),
};

export const tablesApi = {
  list: (params = {}) => api.get("/operations/tables/", { params }),
  create: (data) => api.post("/operations/tables/", data),
  update: (id, data) => api.patch(`/operations/tables/${id}/`, data),
  remove: (id) => api.delete(`/operations/tables/${id}/`),
};

export const privacyApi = {
  getRetention: () => api.get("/operations/privacy/retention/"),
  updateRetention: (data) => api.patch("/operations/privacy/retention/", data),
  runPurge: (data = {}) => api.post("/operations/privacy/retention/run-purge/", data),
  listConsents: () => api.get("/operations/privacy/consents/"),
  recordConsent: (data) => api.post("/operations/privacy/consents/", data),
  eraseCustomer: (customer_phone_or_email) =>
    api.post("/operations/privacy/erase-customer/", { customer_phone_or_email }),
};

export const superAdminApi = {
  getOverview: () => api.get("/superadmin/overview/"),
  listCompanies: (params = {}) => api.get("/superadmin/companies/", { params }),
  updateCompanyStatus: (id, is_active, reason = "") =>
    api.patch(`/superadmin/companies/${id}/status/`, { is_active, reason }),
  listAuditLogs: () => api.get("/superadmin/audit-logs/"),
};

export const attendanceApi = {
  getByDate: (date) => api.get("/operations/attendance/", { params: date ? { date } : {} }),
  mark: (data) => api.post("/operations/attendance/", data),
};

export const suppliersApi = {
  list: (params = {}) => api.get("/operations/suppliers/", { params }),
  create: (data) => api.post("/operations/suppliers/", data),
  update: (id, data) => api.patch(`/operations/suppliers/${id}/`, data),
  remove: (id) => api.delete(`/operations/suppliers/${id}/`),
};

export const restaurantDashboardApi = {
  getSummary: (period = "today") =>
    api.get("/operations/restaurant/dashboard-summary/", { params: { period } }),
};

export const restaurantKdsApi = {
  getTickets: (station = "all") =>
    api.get("/operations/restaurant/kds/", { params: { station } }),
  bumpOrder: (orderId) =>
    api.post(`/operations/restaurant/kds/${orderId}/bump/`),
};

export const customersApi = {
  lookup: (q) => api.get("/operations/customers/lookup/", { params: { q } }),
};

export const restaurantFloorApi = {
  getFloorPlan: () => api.get("/operations/restaurant/floor-plan/"),
  updateTableStatus: (tableId, status) =>
    api.post(`/operations/restaurant/tables/${tableId}/status/`, { status }),
  listReservations: (params = {}) =>
    api.get("/operations/restaurant/reservations/", { params }),
  createReservation: (data) =>
    api.post("/operations/restaurant/reservations/", data),
  updateReservation: (id, data) =>
    api.patch(`/operations/restaurant/reservations/${id}/`, data),
  deleteReservation: (id) =>
    api.delete(`/operations/restaurant/reservations/${id}/`),
  seatReservation: (id, table_id) =>
    api.post(`/operations/restaurant/reservations/${id}/seat/`, table_id ? { table_id } : {}),
  completeReservation: (id, table_status = "available") =>
    api.post(`/operations/restaurant/reservations/${id}/complete/`, { table_status }),
};

export const restaurantInventoryApi = {
  list: (params = {}) => api.get("/operations/restaurant/inventory/", { params }),
  create: (data) => api.post("/operations/restaurant/inventory/", data),
  update: (id, data) => api.patch(`/operations/restaurant/inventory/${id}/`, data),
  remove: (id) => api.delete(`/operations/restaurant/inventory/${id}/`),
  adjust: (id, data) => api.post(`/operations/restaurant/inventory/${id}/adjust/`, data),
  movements: (id) => api.get(`/operations/restaurant/inventory/${id}/movements/`),
  getRecipe: (catalogItemId) => api.get(`/operations/restaurant/recipes/${catalogItemId}/`),
  saveRecipe: (catalogItemId, ingredients) =>
    api.put(`/operations/restaurant/recipes/${catalogItemId}/`, { ingredients }),
};

export const restaurantDeliveryApi = {
  getBoard: (params = {}) => api.get("/operations/restaurant/deliveries/", { params }),
  updateSettings: (data) => api.patch("/operations/restaurant/deliveries/settings/", data),
  assignRider: (orderId, data) =>
    api.post(`/operations/restaurant/deliveries/${orderId}/assign/`, data),
  updateStatus: (orderId, status, note = "") =>
    api.post(`/operations/restaurant/deliveries/${orderId}/status/`, { status, note }),
  settleCod: (data) => api.post("/operations/restaurant/deliveries/settle-cod/", data),
};

export const restaurantCustomersApi = {
  list: (params = {}) => api.get("/operations/restaurant/customers/", { params }),
  getDetail: (phone) =>
    api.get(`/operations/restaurant/customers/${encodeURIComponent(phone)}/`),
  updateProfile: (phone, data) =>
    api.patch(`/operations/restaurant/customers/${encodeURIComponent(phone)}/`, data),
};

export const restaurantReportsApi = {
  getSummary: (params = {}) => api.get("/operations/restaurant/reports/", { params }),
  downloadCsv: (params = {}) =>
    api.get("/operations/restaurant/reports/export/", { params, responseType: "blob" }),
  listExpenses: (params = {}) => api.get("/operations/restaurant/expenses/", { params }),
  createExpense: (data) => api.post("/operations/restaurant/expenses/", data),
  deleteExpense: (id) => api.delete(`/operations/restaurant/expenses/${id}/`),
};

export const restaurantSuppliersApi = {
  list: () => api.get("/operations/restaurant/suppliers/"),
  create: (data) => api.post("/operations/restaurant/suppliers/", data),
  update: (id, data) => api.patch(`/operations/restaurant/suppliers/${id}/`, data),
  remove: (id) => api.delete(`/operations/restaurant/suppliers/${id}/`),
};


