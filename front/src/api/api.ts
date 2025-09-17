import axios, { AxiosError } from "axios";
import { handleApiError } from "../utils/apiErrorHandler";

// Інтерфейс для структури помилки API
interface ApiErrorResponse {
  detail?: string;
  message?: string;
  errors?: any;
}

// Створення інстансу axios
export const apiInstance = axios.create({
  baseURL: "/api",
  withCredentials: true,
});

apiInstance.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiErrorResponse>) => {
    if (error.response?.status === 401) {
      if (window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
      return;
    }
    throw handleApiError(error);
  },
);

export * from "./auth.api";
export * from "./computers.api";
export * from "./statistics.api";
export * from "./scripts.api";
export * from "./domain.api";
