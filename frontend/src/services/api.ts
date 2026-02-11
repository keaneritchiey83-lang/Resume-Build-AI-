import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

const api = axios.create({
  baseURL: `${API_URL}/api`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default api;

// Auth API
export const authAPI = {
  register: (data: { email: string; password: string; firstName?: string; lastName?: string }) =>
    api.post('/auth/register', data),
  login: (data: { email: string; password: string }) =>
    api.post('/auth/login', data),
  getProfile: () => api.get('/auth/profile'),
};

// Resume API
export const resumeAPI = {
  create: (data: unknown) => api.post('/resumes', data),
  getAll: () => api.get('/resumes'),
  getOne: (id: string) => api.get(`/resumes/${id}`),
  update: (id: string, data: unknown) => api.put(`/resumes/${id}`, data),
  delete: (id: string) => api.delete(`/resumes/${id}`),
};

// ATS API
export const atsAPI = {
  analyze: (data: { resumeId: string; jobDescription: string }) =>
    api.post('/ats/analyze', data),
  getScore: (resumeId: string) => api.get(`/ats/score/${resumeId}`),
};

// Prediction API
export const predictionAPI = {
  predictCallback: (data: { resumeId: string; jobDescription: string }) =>
    api.post('/predictions/callback', data),
};

// Subscription API
export const subscriptionAPI = {
  createCheckout: (data: { tier: 'PRO' | 'ENTERPRISE' }) =>
    api.post('/subscriptions/checkout', data),
  get: () => api.get('/subscriptions'),
  cancel: () => api.post('/subscriptions/cancel'),
};

// Team API
export const teamAPI = {
  create: (data: { name: string; maxMembers?: number }) =>
    api.post('/teams', data),
  getAll: () => api.get('/teams'),
  getOne: (id: string) => api.get(`/teams/${id}`),
  update: (id: string, data: unknown) => api.put(`/teams/${id}`, data),
  delete: (id: string) => api.delete(`/teams/${id}`),
  addMember: (id: string, data: { email: string; role?: string }) =>
    api.post(`/teams/${id}/members`, data),
  removeMember: (id: string, userId: string) =>
    api.delete(`/teams/${id}/members/${userId}`),
  getMembers: (id: string) => api.get(`/teams/${id}/members`),
};

// Admin API
export const adminAPI = {
  getStats: () => api.get('/admin/stats'),
  getUsers: (params?: { page?: number; limit?: number }) =>
    api.get('/admin/users', { params }),
  getUser: (id: string) => api.get(`/admin/users/${id}`),
  updateUser: (id: string, data: unknown) => api.put(`/admin/users/${id}`, data),
  deleteUser: (id: string) => api.delete(`/admin/users/${id}`),
  getSubscriptions: () => api.get('/admin/subscriptions'),
};
