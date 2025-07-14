import axios, { AxiosInstance } from 'axios';
import { Computer, ComputersResponse, DashboardStats, ComponentHistory, UserRead, UserCreate, UserUpdate, ScanTask } from '../types/schemas';

export const apiInstance = axios.create({
  baseURL: 'http://192.168.0.143:8000/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

export const authInstance = axios.create({
  baseURL: 'http://192.168.0.143:8000',
  headers: {
    'Content-Type': 'application/x-www-form-urlencoded',
  },
});

// Интерцептор для добавления JWT-токена в заголовки
const addTokenInterceptor = (instance: AxiosInstance) => {
  instance.interceptors.request.use((config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  });
};

// Применяем интерцептор к обоим инстансам
addTokenInterceptor(apiInstance);
addTokenInterceptor(authInstance);

// Интерцептор для обработки ошибки 401
apiInstance.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

authInstance.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Интерфейс для ответа на запрос сканирования хоста
export interface ScanResponse {
  status: string;
  task_id: string;
}

// Запуск сканирования Active Directory
export const startADScan = async () => {
  const response = await apiInstance.post<ScanResponse>('/ad/scan');
  return response.data;
};

// Запуск сканирования конкретного хоста
export const startHostScan = async (hostname: string) => {
  const response = await apiInstance.post<ScanResponse>('/scan', { hostname });
  return response.data;
};

// Получение статистики дашборда
export const getStatistics = async (params: { metrics?: string[] } = {}) => {
  const response = await apiInstance.get<DashboardStats>('/statistics', {
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
  hostname_startswith?: string;
  os_name?: string | null;
  check_status?: string;
  sort_by?: string;
  sort_order?: string;
  page?: number;
  limit?: number;
  server_filter?: string;
}) => {
  const cleanedParams = {
    hostname: params.hostname || undefined,
    hostname_startswith: params.hostname_startswith || undefined,
    os_name: params.os_name ?? undefined,
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
  });
  return response.data;
};

// Получение данных компьютера по ID
export const getComputerById = async (computerId: number) => {
  try {
    const response = await apiInstance.get<Computer>(`/computers/${computerId}`);
    return response.data;
  } catch (error: any) {
    if (error.response?.status === 404) {
      throw new Error('Компьютер не найден');
    } else if (error.response?.status === 500) {
      throw new Error('Ошибка сервера при получении данных компьютера');
    }
    throw error;
  }
};
// Получение истории компонентов
export const getHistory = async (computerId: number): Promise<ComponentHistory[]> => {
  try {
    const response = await apiInstance.get<ComponentHistory[]>(`/computers/${computerId}/history`);
    return response.data;
  } catch (error: any) {
    if (error.response?.status === 404) {
      throw new Error('История компонентов не найдена');
    } else if (error.response?.status === 500) {
      throw new Error('Ошибка сервера при получении истории компонентов');
    }
    throw error;
  }
};

// Запуск сканирования
export const startScan = async () => {
  const response = await apiInstance.post<ScanResponse>('/scan');
  return response.data;
};

// Получение статуса сканирования
export const getScanStatus = async (taskId: string) => {
  const response = await apiInstance.get<ScanTask>(`/scan/status/${taskId}`);
  return response.data;
};

// Аутентификация и управление пользователями
export const login = async (credentials: { email: string; password: string }) => {
  const formData = new URLSearchParams();
  formData.append('username', credentials.email);
  formData.append('password', credentials.password);
  const response = await authInstance.post<{ access_token: string }>('/auth/jwt/login', formData, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  const token = response.data.access_token;
  localStorage.setItem('token', token); // Сохраняем токен
  return response.data;
};

export const register = async (user: UserCreate) => {
  const response = await authInstance.post<UserRead>('/auth/register', user, {
    headers: { 'Content-Type': 'application/json' },
  });
  return response.data;
};

export const getUsers = async () => {
  try {
    const response = await apiInstance.get<UserRead[]>('/users', {
      headers: { 'Content-Type': 'application/json' },
    });
    console.log('Получены пользователи:', response.data);
    return response.data;
  } catch (error: any) {
    console.error('Ошибка получения пользователей:', error.response?.data || error.message);
    if (error.response?.status === 401) {
      console.warn('Неавторизован, перенаправление на логин');
      localStorage.removeItem('token');
      window.location.href = '/login';
    } else if (error.response?.status === 404) {
      console.warn('Маршрут /api/users не найден');
    }
    throw error;
  }
};

export const updateUser = async (id: number, data: Partial<UserUpdate>) => {
  const response = await apiInstance.patch<UserRead>(`/users/${id}`, data, {
    headers: { 'Content-Type': 'application/json' },
  });
  return response.data;
};

export const deleteUser = async (id: number) => {
  await apiInstance.delete(`/users/${id}`, {
    headers: { 'Content-Type': 'application/json' },
  });
};

export const logout = async () => {
  await authInstance.post('/auth/jwt/logout', null, {
    headers: { 'Content-Type': 'application/json' },
  });
};