import React, { createContext, useState, useEffect, useCallback, useContext } from 'react';
import { login, logout, getUsers } from '../api/auth.api';
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
    try {
      const users = await getUsers();
      const currentUser = users[0] || null;
      setUser(currentUser);
      setIsAuthenticated(!!currentUser);
    } catch (error: any) {
      setUser(null);
      setIsAuthenticated(false);
      if (error.message === 'Сервер недоступний. Перевірте підключення до мережі.') {
        console.warn('Server is unavailable');
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  const handleLogin = async (email: string, password: string) => {
    await login({ email, password });
    await checkAuth();
  };

  const handleLogout = useCallback(async () => {
    await logout();
    setUser(null);
    setIsAuthenticated(false);
  }, []);

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