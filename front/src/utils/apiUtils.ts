import { AxiosRequestConfig, AxiosError } from "axios";
import { apiInstance } from "../api/api";
import { handleApiError } from "./apiErrorHandler";

interface ApiRequestOptions extends AxiosRequestConfig {
  paramsSerializer?: (params: Record<string, any>) => string;
}

export async function apiRequest<T>(
  method: "get" | "post" | "put" | "patch" | "delete",
  url: string,
  data?: any,
  options: ApiRequestOptions = {},
  retries = 3, 
): Promise<T> {
  let lastError: AxiosError | null = null;

  for (let attempt = 0; attempt < retries; attempt++) {
    try {
      const response = await apiInstance({ method, url, data, ...options }); 
      return response.data; 
    } catch (error: unknown) { 
      lastError = error instanceof AxiosError ? error : new AxiosError(String(error));
      if (attempt === retries - 1 || !lastError.response || lastError.response.status < 500) {
        throw handleApiError(lastError); 
      }
      await new Promise(resolve => setTimeout(resolve, 1000 * Math.pow(2, attempt)));
    }
  }
  throw handleApiError(lastError || new Error("Retry failed")); 
}

export const cleanAndSerializeParams = (
  params: Record<string, any>,
): string => {
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "" && value !== null) {
      if (Array.isArray(value)) {
        value.forEach((item) => searchParams.append(`${key}[]`, String(item)));
      } else {
        searchParams.append(key, String(value));
      }
    }
  }
  return searchParams.toString();
};
