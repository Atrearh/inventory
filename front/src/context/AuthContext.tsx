import React, { createContext, useState, useEffect, useCallback, useContext } from 'react';
import { login, logout, refreshToken, getUsers } from '../api/auth.api';
import { UserRead } from '../types/schemas';

interface AuthContextType {
  user: UserRead | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextType>({
  user: null,
  isAuthenticated: false,
  isLoading: true,
  login: async () => {},
  logout: async () => {},
});

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserRead | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  const checkAuth = useCallback(async () => {
  setIsLoading(true);
  try {
    // Просто робимо запит на захищений ендпоінт.
    // Браузер автоматично надішле cookie 'access_token'.
    // Якщо сесія валідна, ми отримаємо дані. В іншому випадку - помилку 401.
    const users = await getUsers();
    
    // В ідеалі, тут має бути запит до /api/users/me, що повертає одного користувача.
    // Але для поточної структури перевіряємо, чи повернувся масив.
    if (users && users.length > 0) {
      setUser(users[0]);
      setIsAuthenticated(true);
      console.log('Auth check successful: User is authenticated.');
    } else {
      setUser(null);
      setIsAuthenticated(false);
    }
  } catch (error) {
    console.error('Auth check failed: User is not authenticated.', error);
    setUser(null);
    setIsAuthenticated(false);
  } finally {
    setIsLoading(false);
  }
}, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  const handleLogin = async (email: string, password: string) => {
    try {
      const response = await login({ email, password });
      console.log('Login response:', response);
      localStorage.setItem('refresh_token', response.refresh_token); // Переконайтеся, що сервер повертає refresh_token
      await checkAuth();
    } catch (error) {
      console.error('Login failed:', error);
      throw error;
    }
  };

  const handleLogout = async () => {
    try {
      await logout();
      setUser(null);
      setIsAuthenticated(false);
    } catch (error) {
      console.error('Logout failed:', error);
      throw error;
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated,
        isLoading,
        login: handleLogin,
        logout: handleLogout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};