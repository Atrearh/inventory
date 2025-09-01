// src/utils/apiErrorHandler.ts
import { AxiosError } from 'axios';

interface ApiErrorResponse {
  detail?: string;
  message?: string;
  errors?: any;
}

export function handleApiError(error: AxiosError<ApiErrorResponse> | any, defaultMessage?: string): Error {
  if (error.code === 'ECONNREFUSED' || !error.response || error.response?.status === 503) {
    return new Error('Сервер недоступний. Перевірте підключення до мережі.');
  }
  if (error.response?.status === 404) {
    return new Error('Ресурс не знайдено');
  }
  if (error.response?.status === 500) {
    return new Error('Внутрішня помилка сервера');
  }
  const message =
    error.response?.data?.detail ||
    error.response?.data?.message ||
    defaultMessage ||
    'Невідома помилка';
  return new Error(message);
}
