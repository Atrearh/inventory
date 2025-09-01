import { apiInstance } from './api';
import { UserRead, UserCreate, UserUpdate } from '../types/schemas';

interface LoginCredentials {
  email: string;
  password: string;
}

// Функція для входу
export const login = async (credentials: LoginCredentials): Promise<UserRead> => {
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
};

// Функція для виходу
export const logout = async (): Promise<void> => {
  await apiInstance.post('/auth/jwt/logout');
};

// Функція для отримання списку користувачів
export const getUsers = async (): Promise<UserRead[]> => {
  const response = await apiInstance.get<UserRead[]>('/users/');
  return response.data;
};

// Реєстрація нового користувача
export const register = async (userData: UserCreate): Promise<UserRead> => {
  const response = await apiInstance.post<UserRead>('/auth/jwt/register', userData);
  return response.data;
};

// Оновлення даних користувача
export const updateUser = async (id: number, userData: Partial<UserUpdate>): Promise<UserRead> => {
  const response = await apiInstance.patch<UserRead>(`/users/${id}`, userData);
  return response.data;
};

// Видалення користувача
export const deleteUser = async (id: number): Promise<void> => {
  await apiInstance.delete(`/users/${id}`);
};