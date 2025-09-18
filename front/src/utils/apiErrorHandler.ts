// front/src/utils/apiErrorHandler.ts
import { AxiosError } from "axios";

interface ApiErrorResponse {
  detail?: string; 
  error?: string; 
  message?: string; 
  errors?: any;
}

export function handleApiError(
  error: AxiosError<ApiErrorResponse> | any,
  t?: (key: string, fallback: string) => string, 
  defaultMessage?: string,
): Error {
  const translate = t || ((_: string, fallback: string) => fallback); 

  if (error.code === "ECONNREFUSED" || !error.response || error.response?.status === 503) {
    return new Error(translate("server_unavailable", "Сервер недоступний. Перевірте підключення до мережі.")); 
  }
  if (error.response?.status === 404) {
    return new Error(translate("resource_not_found", "Ресурс не знайдено"));
  }
  if (error.response?.status === 401) {
    return new Error(translate("session_expired", "Ваша сесія закінчилася. Будь ласка, увійдіть знову."));
  }
  if (error.response?.status === 500) {
    return new Error(translate("internal_server_error", "Внутрішня помилка сервера"));
  }
  const message = 
    error.response?.data?.detail || 
    error.response?.data?.message || 
    defaultMessage || 
    translate("unknown_error", "Невідома помилка"); 
  return new Error(message);
}
