// front/src/utils/apiUtils.ts
import { AxiosRequestConfig, AxiosError } from "axios";
import { handleApiError } from "./apiErrorHandler";
import { cleanAndSerializeParams } from "./paramsUtils";
import { apiInstance } from "../api/instance";

interface ApiRequestOptions extends AxiosRequestConfig {
  paramsSerializer?: (params: Record<string, any>) => string;
}

export async function apiRequest<T>(
  method: "get" | "post" | "put" | "patch" | "delete",
  url: string,
  data?: any,
  options: ApiRequestOptions = {},
  retries = 3
): Promise<T> {
  const { params, ...restOptions } = options;
  const queryString = params ? cleanAndSerializeParams(params) : "";
  const fullUrl = queryString ? `${url}?${queryString}` : url;

  let lastError: AxiosError | null = null;

  for (let attempt = 0; attempt < retries; attempt++) {
    try {
      const response = await apiInstance({ method, url: fullUrl, data, ...restOptions });
      return response.data;
    } catch (error: unknown) {
      lastError = error instanceof AxiosError ? error : new AxiosError(String(error));
      console.error(
        `apiRequest: Error on attempt ${attempt + 1} for ${method.toUpperCase()} ${fullUrl}`,
        lastError.response?.status,
        lastError.response?.data
      );
      if (attempt === retries - 1 || !lastError.response || lastError.response.status < 500) {
        throw handleApiError(lastError);
      }
      await new Promise((resolve) => setTimeout(resolve, 1000 * Math.pow(2, attempt)));
    }
  }
  throw handleApiError(lastError || new Error("Retry failed"));
}