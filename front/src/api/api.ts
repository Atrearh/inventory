import axios, { AxiosError, AxiosRequestConfig } from 'axios';
import { handleApiError } from '../utils/apiErrorHandler';
import { logout } from './auth.api';

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

// Інтерцептор для обробки відповідей
apiInstance.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiErrorResponse>) => {
    // Якщо помилка 401, не намагайтеся повторити запит.
    // Просто завершіть сесію на клієнті.
    if (error.response?.status === 401) {
      // Викликаємо оновлену функцію logout, яка просто
      // очистить cookie і перенаправить на /login
      await logout(); 
      // Викидаємо помилку, щоб ланцюжок promise перервався
      throw new Error('Сесія закінчилася, будь ласка, увійдіть знову');
    }

    // Всі інші помилки обробляються як раніше
    throw handleApiError(error);
  }
);

export * from './auth.api';
export * from './computers.api';
export * from './statistics.api';
export * from './scripts.api';
export * from './domain.api';