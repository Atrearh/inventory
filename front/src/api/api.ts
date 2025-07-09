import axios from 'axios';
import { API_URL } from '../config';
import { Computer, ComputersResponse, DashboardStats, ComponentHistory } from '../types/schemas';

const axiosInstance = axios.create({
  baseURL: API_URL,
});

// Интерфейс для ответа на запрос перезапуска сервера
export interface RestartResponse {
  message: string;
}

// Интерфейс для ответа на запрос сканирования хоста
export interface ScanResponse {
  status: string;
  task_id: string;
}

// Запуск сканирования Active Directory
export const startADScan = async () => {
  const response = await axiosInstance.post<{ status: string; task_id: string }>('/ad/scan');
  return response.data;
};

// Запуск сканирования конкретного хоста
export const startHostScan = async (hostname: string) => {
  const response = await axiosInstance.post<ScanResponse>('/scan', { hostname });
  return response.data;
};

// Получение статистики дашборда
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

// Получение списка компьютеров с фильтрацией и пагинацией
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

// Экспорт списка компьютеров в CSV
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

// Получение данных компьютера по ID
export const getComputerById = async (computerId: number) => {
  const response = await axiosInstance.get<Computer>(`/computers/${computerId}`);
  return response.data;
};

export const getHistory = async (computerId: number): Promise<ComponentHistory[]> => {
  const response = await axiosInstance.get<ComponentHistory[]>(`/api/computers/${computerId}/history`);
  return response.data;
};

// Запуск сканирования
export const startScan = async () => {
  const response = await axiosInstance.post<{ status: string; task_id: string }>('/scan');
  return response.data;
};

// Получение статуса сканирования
export const getScanStatus = async (taskId: string) => {
  const response = await axiosInstance.get(`/scan/status/${taskId}`);
  return response.data;
};

// Перезапуск сервера
export const restartServer = async (): Promise<RestartResponse> => {
  const response = await axiosInstance.post<RestartResponse>('/restart');
  return response.data;
};