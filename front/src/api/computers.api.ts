import { ComputersResponse, Computer, ComponentHistory } from '../types/schemas';
import { apiInstance } from './api';
import { Filters } from '../hooks/useComputerFilters';
import { cleanAndSerializeParams } from '../utils/apiUtils';

// Отримання списку комп’ютерів з бекенду
export const getComputers = async (params: Filters) => {
  const response = await apiInstance.get<ComputersResponse>('/computers', {
    params: {
      ...params,
      hostname: undefined, // Фільтрація на клієнтській стороні
      os_name: undefined, // Фільтрація на клієнтській стороні
      check_status: undefined, // Фільтрація на клієнтській стороні
      sort_by: undefined, // Сортування на клієнтській стороні
      sort_order: undefined, // Сортування на клієнтській стороні
    },
    paramsSerializer: () => cleanAndSerializeParams(params).toString(),
    withCredentials: true,
  });
  return response.data;
};

// Отримання даних комп’ютера за ID
export const getComputerById = async (computerId: number) => {
  const response = await apiInstance.get<Computer>(`/computers/${computerId}`, { withCredentials: true });
  return response.data;
};

// Отримання історії компонентів комп’ютера
export const getHistory = async (computerId: number): Promise<ComponentHistory[]> => {
  const response = await apiInstance.get<ComponentHistory[]>(`/computers/${computerId}/history`, {
    withCredentials: true,
  });
  return response.data;
};

// Експорт комп’ютерів у CSV
export const exportComputersToCSV = async (params: Filters) => {
  const response = await apiInstance.get('/computers/export/csv', {
    paramsSerializer: () => cleanAndSerializeParams(params).toString(),
    responseType: 'blob',
    withCredentials: true,
  });
  return response.data;
};