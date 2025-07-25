// front/src/api/auth.api.ts
import { apiInstance } from './api';
import { UserRead, UserCreate, UserUpdate } from '../types/schemas';

interface LoginCredentials {
  email: string;
  password: string;
}

// Функція для входу
export const login = async (credentials: LoginCredentials) => {
  try {
    const response = await apiInstance.post('/auth/jwt/login', new URLSearchParams({
      username: credentials.email,
      password: credentials.password,
    }), {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
    return response.data;
  } catch (error: any) {
    console.error('Login error:', error.response?.data || error.message);
    throw error;
  }
};

// Функція для виходу
export const logout = async () => {
  try {
    const response = await apiInstance.post('/auth/jwt/logout', {});
    return response.data;
  } catch (error: any) {
    console.error('Logout error:', error.response?.data || error.message);
    throw error;
  }
};

// Функція для отримання списку користувачів
export const getUsers = async (): Promise<UserRead[]> => {
  try {
    const response = await apiInstance.get<UserRead[]>('/users/');
    return response.data;
  } catch (error: any) {
    console.error('Get users error:', error.response?.data || error.message);
    throw error;
  }
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
  await apiInstance.delete<void>(`/users/${id}`);
};