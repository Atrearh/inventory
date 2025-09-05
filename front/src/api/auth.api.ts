// front/src/api/auth.api.ts
import { apiRequest } from '../utils/apiUtils';
import { UserRead, UserCreate, UserUpdate } from '../types/schemas';

interface LoginCredentials {
  email: string;
  password: string;
}

export const login = async (credentials: LoginCredentials): Promise<UserRead> => {
  return apiRequest('post', '/auth/jwt/login', new URLSearchParams({
    username: credentials.email,
    password: credentials.password,
  }), {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
};

export const logout = async (): Promise<void> => {
  return apiRequest('post', '/auth/jwt/logout');
};

export const getUsers = async (): Promise<UserRead[]> => {
  return apiRequest('get', '/users/');
};

export const register = async (userData: UserCreate): Promise<UserRead> => {
  return apiRequest('post', '/auth/jwt/register', userData);
};

export const updateUser = async (id: number, userData: Partial<UserUpdate>): Promise<UserRead> => {
  return apiRequest('patch', `/users/${id}`, userData);
};

export const deleteUser = async (id: number): Promise<void> => {
  return apiRequest('delete', `/users/${id}`);
};