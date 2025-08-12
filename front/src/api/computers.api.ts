import { ComputersResponse, Computer, ComponentHistory } from '../types/schemas';
import { apiInstance } from './api';
import { Filters } from '../hooks/useComputerFilters';
import { cleanAndSerializeParams } from '../utils/apiUtils';

// Отримання списку комп’ютерів з бекенду
export const getComputers = async (params: Filters) => {
  const response = await apiInstance.get<ComputersResponse>('/computers', {
    paramsSerializer: () => cleanAndSerializeParams(params).toString(),
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