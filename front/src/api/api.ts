// front/src/api/api.ts
import axios, { AxiosError, AxiosRequestConfig } from 'axios';


// Розширення типу AxiosRequestConfig для додавання _retry
interface CustomAxiosRequestConfig extends AxiosRequestConfig {
  _retry?: boolean;
}

export const apiInstance = axios.create({
  baseURL: '/api',
  withCredentials: true,
});

apiInstance.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as CustomAxiosRequestConfig;
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      try {
        return apiInstance(originalRequest);
      } catch (refreshError) {
        window.location.href = '/login';
        throw new Error('Сесія закінчилася, будь ласка, увійдіть знову');
      }
    }
    throw error;
  }
);

export * from './auth.api';
export * from './computers.api';
export * from './statistics.api';
export * from './scripts.api';