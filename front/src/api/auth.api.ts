import { apiInstance } from './api';
import { UserRead, UserCreate, UserUpdate } from '../types/schemas';

interface LoginCredentials {
  email: string;
  password: string;
}

interface ApiError {
  response?: {
    status: number;
    data: any;
  };
  message: string;
  code?: string;
}

// Функція для входу
export const login = async (credentials: LoginCredentials): Promise<UserRead> => {
  try {
    const response = await apiInstance.post<UserRead>(
      '/auth/jwt/login',
      new URLSearchParams({
        username: credentials.email,
        password: credentials.password,
      }),
      {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      }
    );
    return response.data;
  } catch (error: any) {
    throw handleApiError(error, 'Login failed');
  }
};

// Функція для виходу
export const logout = async (): Promise<void> => {
  try {
    await apiInstance.post('/auth/jwt/logout');
  } catch (error: any) {
    throw handleApiError(error, 'Logout failed');
  }
};

// Функція для отримання списку користувачів
export const getUsers = async (): Promise<UserRead[]> => {
  try {
    const response = await apiInstance.get<UserRead[]>('/users/');
    return response.data;
  } catch (error: any) {
    throw handleApiError(error, 'Failed to fetch users');
  }
};

// Реєстрація нового користувача
export const register = async (userData: UserCreate): Promise<UserRead> => {
  try {
    const response = await apiInstance.post<UserRead>('/auth/jwt/register', userData);
    return response.data;
  } catch (error: any) {
    throw handleApiError(error, 'Registration failed');
  }
};

// Оновлення даних користувача
export const updateUser = async (id: number, userData: Partial<UserUpdate>): Promise<UserRead> => {
  try {
    const response = await apiInstance.patch<UserRead>(`/users/${id}`, userData);
    return response.data;
  } catch (error: any) {
    throw handleApiError(error, 'User update failed');
  }
};

// Видалення користувача
export const deleteUser = async (id: number): Promise<void> => {
  try {
    await apiInstance.delete(`/users/${id}`);
  } catch (error: any) {
    throw handleApiError(error, 'User deletion failed');
  }
};

// Обробка помилок API
const handleApiError = (error: any, defaultMessage: string): Error => {
  if (error.code === 'ECONNREFUSED' || !error.response || error.response?.status === 503) {
    return new Error('Сервер недоступний. Перевірте підключення до мережі.');
  }
  const message = error.response?.data?.detail || defaultMessage;
  return new Error(message);
};