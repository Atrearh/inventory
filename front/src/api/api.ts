import axios from 'axios';
import { API_URL } from '../config';
import { Computer, ComputerList, ComputersResponse, DashboardStats, CheckStatus, ChangeLog } from '../types/schemas';

const axiosInstance = axios.create({
  baseURL: API_URL,
});

// Інтерфейс для відповіді на запит перезапуску сервера
export interface RestartResponse {
  message: string;
}

// Запуск сканування Active Directory
export const startADScan = async () => {
  const response = await axiosInstance.post<{ message: string }>('/ad/scan');
  return response.data;
};

// Отримання статистики дашборда
export const getStatistics = async (params: { metrics?: string[] } = {}) => {
  const response = await axiosInstance.get<DashboardStats>('/statistics', {
    params: {
      metrics: params.metrics || undefined,
    },
    paramsSerializer: (params) => {
      const searchParams = new URLSearchParams();
      if (params.metrics) {
        params.metrics.forEach((metric: string) => {
          searchParams.append('metrics[]', metric);
        });
      }
      return searchParams.toString();
    },
  });
  return response.data;
};

// Отримання списку комп'ютерів з фільтрацією та пагінацією
export const getComputers = async (params: {
  hostname?: string;
  os_name?: string;
  check_status?: string;
  sort_by?: string;
  sort_order?: string;
  page?: number;
  limit?: number;
  server_filter?: string;
}) => {
  const cleanedParams = {
    hostname: params.hostname || undefined,
    os_name: params.os_name || undefined,
    check_status: params.check_status || undefined,
    sort_by: params.sort_by || 'hostname',
    sort_order: params.sort_order === 'asc' || params.sort_order === 'desc' ? params.sort_order : 'asc',
    page: params.page || 1,
    limit: params.limit || 50,
    server_filter: params.server_filter || undefined,
  };

  const response = await axiosInstance.get<ComputersResponse>('/computers', {
    params: cleanedParams,
    paramsSerializer: (params) => {
      const searchParams = new URLSearchParams();
      for (const [key, value] of Object.entries(params)) {
        if (value !== undefined && value !== '') {
          searchParams.append(key, String(value));
        }
      }
      return searchParams.toString();
    },
  });
  return response.data;
};

// Експорт списку комп'ютерів у CSV
export const exportComputersToCSV = async (params: {
  hostname?: string;
  os_name?: string;
  check_status?: string;
  sort_by?: string;
  sort_order?: string;
  server_filter?: string;
}) => {
  const cleanedParams = {
    hostname: params.hostname || undefined,
    os_name: params.os_name || undefined,
    check_status: params.check_status || undefined,
    sort_by: params.sort_by || 'hostname',
    sort_order: params.sort_order === 'asc' || params.sort_order === 'desc' ? params.sort_order : 'asc',
    server_filter: params.server_filter || undefined,
  };

  const response = await axiosInstance.get('/computers/export/csv', {
    params: cleanedParams,
    responseType: 'blob',
    paramsSerializer: (params) => {
      const searchParams = new URLSearchParams();
      for (const [key, value] of Object.entries(params)) {
        if (value !== undefined && value !== '') {
          searchParams.append(key, String(value));
        }
      }
      return searchParams.toString();
    },
  });
  return response.data;
};

// Отримання даних комп'ютера за ID
export const getComputerById = async (computerId: number) => {
  const response = await axiosInstance.get<Computer>(`/computers/${computerId}`);
  return response.data;
};

// Отримання історії змін для комп'ютера
export const getHistory = async (computerId: number) => {
  const response = await axiosInstance.get<ChangeLog[]>(`/history/${computerId}`);
  return response.data;
};

// Запуск сканування
export const startScan = async () => {
  const response = await axiosInstance.post<{ status: string; task_id: string }>('/scan');
  return response.data;
};

// Отримання статусу сканування
export const getScanStatus = async (taskId: string) => {
  const response = await axiosInstance.get(`/scan/status/${taskId}`);
  return response.data;
};

// Перезапуск сервера
export const restartServer = async (): Promise<RestartResponse> => {
  const response = await axiosInstance.post<RestartResponse>('/restart');
  return response.data;
};