// front/src/utils/apiErrorHandler.ts

import { AxiosError } from "axios";
import i18n from "../components/i18n";

interface ApiErrorResponse {
  detail?: string; // Повідомлення від нашого FastAPI бекенда
  error?: string; // Альтернативне поле, яке ми визначили в ErrorResponse
  message?: string; // Загальне поле для інших помилок
  errors?: any;
}

export function handleApiError(
  error: AxiosError<ApiErrorResponse> | any,
  defaultMessage?: string,
): Error {
  const t = i18n.t; // Отримуємо функцію t з i18n

  if (
    error.code === "ECONNREFUSED" ||
    !error.response ||
    error.response?.status === 503
  ) {
    return new Error(
      t(
        "server_unavailable",
        "Сервер недоступний. Перевірте підключення до мережі.",
      ),
    );
  }
  if (error.response?.status === 404) {
    return new Error(t("resource_not_found", "Ресурс не знайдено"));
  }
  if (error.response?.status === 401) {
    return new Error(
      t(
        "session_expired",
        "Ваша сесія закінчилася. Будь ласка, увійдіть знову.",
      ),
    );
  }
  if (error.response?.status === 500) {
    return new Error(t("internal_server_error", "Внутрішня помилка сервера"));
  }
  const message =
    error.response?.data?.detail ||
    error.response?.data?.message ||
    defaultMessage ||
    t("unknown_error", "Невідома помилка");
  return new Error(message);
}
