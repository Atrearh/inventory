// front/src/utils/apiErrorHandler.ts
import { AxiosError } from "axios";
import { t as i18n } from "i18next";

interface ApiErrorResponse {
  detail?: string;
  error?: string;
  message?: string;
  errors?: any;
}

export function handleApiError(
  error: AxiosError<ApiErrorResponse> | any,
  t: (key: string, options?: any) => string = i18n,
  defaultMessage?: string,
): Error {
  if (error instanceof AxiosError) {
    const status = error.response?.status;
    const detail = error.response?.data?.detail || error.response?.data?.message || error.message;

    if (error.code === "ECONNREFUSED" || status === 503) {
      return new Error(t("server_unavailable", "Сервер недоступний. Перевірте підключення до мережі."));
    }
    if (status === 404) {
      return new Error(t("resource_not_found", "Ресурс не знайдено"));
    }
    if (status === 401) {
      return new Error(t("session_expired", "Ваша сесія закінчилася. Будь ласка, увійдіть знову."));
    }
    if (status === 500) {
      return new Error(t("internal_server_error", "Внутрішня помилка сервера"));
    }
    if (status === 200 && !error.response?.data) {
      return new Error(t("empty_response", "Отримано порожню відповідь від сервера"));
    }
    return new Error(defaultMessage || t("unknown_error", { detail }));
  }

  if (error.message.includes("Failed to fetch user data after login")) {
    return new Error(t("login_failed", "Не вдалося отримати дані користувача після входу. Спробуйте ще раз."));
  }
  if (error.message.includes("Invalid credentials")) {
    return new Error(t("invalid_credentials", "Помилка під час входу. Перевірте email та пароль."));
  }

  return new Error(defaultMessage || t("unknown_error", { error: String(error) }));
}
