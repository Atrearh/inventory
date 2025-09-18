// front/src/api/auth.api.ts
import { apiRequest } from "../utils/apiUtils";
import { UserRead, UserCreate, UserUpdate } from "../types/schemas";

export interface LoginCredentials { 
  email: string;
  password: string;
}

export interface SessionData {
  id: number;
  issued_at: string;
  expires_at: string;
  is_current: boolean;
}

export const getMe = async (): Promise<UserRead> => {
  return apiRequest("get", "/users/me");
};

export const login = async (
  credentials: LoginCredentials,
): Promise<UserRead> => {
  return apiRequest(
    "post",
    "/auth/jwt/login",
    new URLSearchParams({
      username: credentials.email,
      password: credentials.password,
    }),
    {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    },
  );
};

// Використовувати apiRequest для logout (додати ендпоінт на бекенді /auth/jwt/logout якщо немає)
export const logout = async (): Promise<void> => {
  try {
    await apiRequest("post", "/auth/jwt/logout"); // Серверний logout
  } catch (error) {
    // Ігнорувати помилки (токен може бути invalid)
  } finally {
    document.cookie = "auth_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
    window.location.href = "/login";
  }
};

export const getUsers = async (): Promise<UserRead[]> => {
  return apiRequest("get", "/users/");
};

export const register = async (userData: UserCreate): Promise<UserRead> => {
  return apiRequest("post", "/auth/jwt/register", userData);
};

export const updateUser = async (
  id: number,
  userData: Partial<UserUpdate>,
): Promise<UserRead> => {
  return apiRequest("patch", `/users/${id}`, userData);
};

export const deleteUser = async (id: number): Promise<void> => {
  return apiRequest("delete", `/users/${id}`);
};

export const getSessions = async (): Promise<SessionData[]> => {
  return apiRequest("get", "/sessions");
};

export const revokeSession = async (tokenId: number): Promise<void> => {
  return apiRequest("delete", `/sessions/${tokenId}`);
};

export const revokeAllOtherSessions = async (): Promise<void> => {
  return apiRequest("post", "/sessions/revoke-all-others");
};
