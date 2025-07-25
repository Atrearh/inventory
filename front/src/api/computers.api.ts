import { ComputersResponse, Computer, ComponentHistory } from '../types/schemas';
import { apiInstance } from './api';
import { Filters } from '../hooks/useComputerFilters';

// Отримання списку комп’ютерів з бекенду
export const getComputers = async (params: Filters) => {
  const cleanedParams = {
    hostname: params.hostname || undefined,
    os_name: params.os_name || undefined,
    check_status: params.check_status || undefined,
    sort_by: params.sort_by || 'hostname',
    sort_order: params.sort_order === 'asc' || params.sort_order === 'desc' ? params.sort_order : 'asc',
    page: params.page || 1,
    limit: params.limit || 10,
    server_filter: params.server_filter || undefined,
  };

  const response = await apiInstance.get<ComputersResponse>('/computers', {
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
    withCredentials: true,
  });
  return response.data;
};

// Експорт комп’ютерів у CSV
export const exportComputersToCSV = async (params: Filters) => {
  const cleanedParams = {
    hostname: params.hostname || undefined,
    os_name: params.os_name || undefined,
    check_status: params.check_status || undefined,
    sort_by: params.sort_by || 'hostname',
    sort_order: params.sort_order === 'asc' || params.sort_order === 'desc' ? params.sort_order : 'asc',
    server_filter: params.server_filter || undefined,
  };

  const response = await apiInstance.get('/computers/export/csv', {
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
    withCredentials: true,
  });
  return response.data;
};

// Отримання даних комп’ютера за ID
export const getComputerById = async (computerId: number) => {
  try {
    const response = await apiInstance.get<Computer>(`/computers/${computerId}`, { withCredentials: true });
    return response.data;
  } catch (error: any) {
    if (error.response?.status === 404) {
      throw new Error('Комп’ютер не знайдено');
    } else if (error.response?.status === 500) {
      throw new Error('Помилка сервера при отриманні даних комп’ютера');
    }
    throw error;
  }
};

// Отримання історії компонентів комп’ютера
export const getHistory = async (computerId: number): Promise<ComponentHistory[]> => {
  try {
    const response = await apiInstance.get<ComponentHistory[]>(`/computers/${computerId}/history`, {
      withCredentials: true,
    });
    return response.data;
  } catch (error: any) {
    if (error.response?.status === 404) {
      throw new Error('Історія компонентів не знайдена');
    } else if (error.response?.status === 500) {
      throw new Error('Помилка сервера при отриманні історії компонентів');
    }
    throw error;
  }
};