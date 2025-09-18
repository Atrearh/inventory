import { AxiosError } from "axios";
import { apiInstance } from "./instance"; 

// Інтерфейс для структури помилки API
interface ApiErrorResponse {
  detail?: string;
  message?: string;
  errors?: any;
}

apiInstance.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiErrorResponse>) => {
    return Promise.reject(error);
  }
);

export * from "./auth.api";
export * from "./computers.api";
export * from "./statistics.api";
export * from "./scripts.api";
export * from "./domain.api";
