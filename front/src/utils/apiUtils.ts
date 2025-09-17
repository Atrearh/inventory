import { AxiosRequestConfig } from "axios";
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
): Promise<T> {
  try {
    const response = await apiInstance({
      method,
      url,
      data,
      withCredentials: true,
      ...options,
    });
    return response.data;
  } catch (error) {
    throw handleApiError(error);
  }
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
