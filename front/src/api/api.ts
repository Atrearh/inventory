import axios, { AxiosError, AxiosRequestConfig } from 'axios';
import { handleApiError } from '../utils/apiErrorHandler';

// Тип для кастомної конфігурації запиту
interface CustomAxiosRequestConfig extends AxiosRequestConfig {
  _retry?: boolean;
}

// Інтерфейс для структури помилки API
interface ApiErrorResponse {
  detail?: string;
  message?: string;
  errors?: any;
}

// Створення інстансу axios
export const apiInstance = axios.create({
  baseURL: '/api',
  withCredentials: true,
});

apiInstance.interceptors.request.use((config) => {
  if (import.meta.env.DEV) {
    const method = config.method?.toUpperCase() || 'UNKNOWN';
    console.log(`API Request: ${method} ${config.url}`, config.params || {});
  }
  return config;
});


// Інтерцептор для обробки відповідей
apiInstance.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiErrorResponse>) => {
    const originalRequest = error.config as CustomAxiosRequestConfig;

    // Обробка 401 помилки (неавторизований доступ)
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      try {
        // Спроба повторного виконання запиту
        return apiInstance(originalRequest);
      } catch (refreshError) {
        // Перенаправлення на сторінку логіну при невдалій спробі
        window.location.href = '/login';
        throw new Error('Сесія закінчилася, будь ласка, увійдіть знову');
      }
    }

    // Обробка всіх інших помилок через централізований обробник
    throw handleApiError(error);
  }
);

export * from './auth.api';
export * from './computers.api';
export * from './statistics.api';
export * from './scripts.api';
export * from './domain.api';