import { AxiosRequestConfig} from 'axios';
import { apiInstance } from '../api/api';
import { handleApiError } from './apiErrorHandler';

interface ApiRequestOptions extends AxiosRequestConfig {
  paramsSerializer?: (params: any) => string;
}

export async function apiRequest<T>(
  method: 'get' | 'post' | 'put' | 'patch' | 'delete',
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

export const cleanAndSerializeParams = (params: Record<string, any>): URLSearchParams => {
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '' && value !== null) {
      searchParams.append(key, String(value));
    }
  }
  return searchParams;
};