import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:3000/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Generate a resume
 */
export const generateResume = async (data) => {
  const response = await api.post('/resume/generate', data);
  return response.data;
};

/**
 * Optimize resume for ATS
 */
export const optimizeResume = async (data) => {
  const response = await api.post('/resume/optimize', data);
  return response.data;
};

/**
 * Prepare for interview
 */
export const prepareInterview = async (data) => {
  const response = await api.post('/interview/prepare', data);
  return response.data;
};

/**
 * Analyze skill gap
 */
export const analyzeSkillGap = async (data) => {
  const response = await api.post('/career/skills-gap', data);
  return response.data;
};

/**
 * Health check
 */
export const healthCheck = async () => {
  const response = await api.get('/health');
  return response.data;
};

export default api;
