// front/src/utils/apiErrorHandler.ts

import { AxiosError } from 'axios';
import { TFunction } from 'i18next';

interface ApiErrorResponse {
  detail?: string;  // Повідомлення від нашого FastAPI бекенда
  error?: string;   // Альтернативне поле, яке ми визначили в ErrorResponse
  message?: string; // Загальне поле для інших помилок
  errors?: any;
}

export function handleApiError(error: AxiosError<ApiErrorResponse> | any, t: TFunction, defaultMessage?: string): Error {
  // 1. Помилки мережі або недоступності сервера
  if (error.code === 'ECONNREFUSED' || !error.response || error.response?.status === 503) {
    return new Error(t('server_unavailable', 'Сервер недоступний. Перевірте підключення до мережі.'));
  }

  // 2. Пріоритетне повідомлення з бекенда (з нашого global_exception_handler)
  const backendError = error.response?.data?.error;
  const backendDetail = error.response?.data?.detail;

  // Використовуємо поле 'error' з нашої схеми ErrorResponse, бо воно більш user-friendly
  if (backendError && typeof backendError === 'string') {
    return new Error(backendError);
  }

  // 3. Обробка стандартних HTTP-статусів
  if (error.response?.status === 404) {
    return new Error(t('resource_not_found', 'Ресурс не знайдено'));
  }
  if (error.response?.status === 401) {
    return new Error(t('session_expired', 'Ваша сесія закінчилася. Будь ласка, увійдіть знову.'));
  }
  if (error.response?.status === 500) {
    // Якщо є деталі в режимі DEBUG, показуємо їх
    if (backendDetail && typeof backendDetail === 'string') {
        return new Error(`${t('internal_server_error', 'Внутрішня помилка сервера')}: ${backendDetail}`);
    }
    return new Error(t('internal_server_error', 'Внутрішня помилка сервера'));
  }

  // 4. Запасний варіант
  const message =
    backendDetail ||
    defaultMessage ||
    error.message ||
    t('unknown_error', 'Невідома помилка');

  return new Error(message);
}