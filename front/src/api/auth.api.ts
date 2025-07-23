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

// Функція для оновлення токена (використовується інтерсепторами)
export const refreshToken = async () => {
  try {
    const response = await apiInstance.post('/auth/jwt/refresh', {});
    return response.data;
  } catch (error: any) {
    console.error('Refresh token error:', error.response?.data || error.message);
    throw error;
  }
};

// Функція для отримання списку користувачів
export const getUsers = async (): Promise<UserRead[]> => {
  try {
    // Шлях /users/ відповідає префіксу /api/users з main.py
    const response = await apiInstance.get<UserRead[]>('/users/');
    return response.data;
  } catch (error: any) {
    console.error('Get users error:', error.response?.data || error.message);
    throw error;
  }
};

// ✅ НОВА ФУНКЦІЯ: Реєстрація нового користувача
export const register = async (userData: UserCreate): Promise<UserRead> => {
  // Шлях /auth/jwt/register відповідає /api/auth/jwt/register
  const response = await apiInstance.post<UserRead>('/auth/jwt/register', userData);
  return response.data;
};

// ✅ НОВА ФУНКЦІЯ: Оновлення даних користувача
export const updateUser = async (id: number, userData: Partial<UserUpdate>): Promise<UserRead> => {
  // Шлях /users/:id відповідає /api/users/:id
  const response = await apiInstance.patch<UserRead>(`/users/${id}`, userData);
  return response.data;
};

// ✅ НОВА ФУНКЦІЯ: Видалення користувача
export const deleteUser = async (id: number): Promise<void> => {
  // Шлях /users/:id відповідає /api/users/:id
  await apiInstance.delete<void>(`/users/${id}`);
};