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
    setIsLoading(true);
    try {
      const users = await getUsers();
      if (users && users.length > 0) {
        setUser(users[0]);
        setIsAuthenticated(true);
        console.log('Auth check successful: User is authenticated.');
      } else {
        setUser(null);
        setIsAuthenticated(false);
      }
    } catch (error: any) {
      console.error('Auth check failed:', error.response?.data || error.message);
      setUser(null);
      setIsAuthenticated(false);
      // Якщо отримали 401, виконуємо логаут
      if (error.response?.status === 401) {
        console.log('Access token expired or invalid, performing logout');
        await handleLogout();
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  const handleLogin = async (email: string, password: string) => {
    try {
      await login({ email, password });
      await checkAuth();
    } catch (error) {
      console.error('Login failed:', error);
      throw error;
    }
  };

  const handleLogout = useCallback(async () => {
    try {
      await logout();
      setUser(null);
      setIsAuthenticated(false);
      console.log('Logout successful');
    } catch (error) {
      console.error('Logout failed:', error);
      throw error;
    }
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