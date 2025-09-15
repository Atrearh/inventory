import React, { createContext, useState, useEffect, useCallback, useContext } from 'react';
import { UserRead } from '../types/schemas';
import { useNavigate } from 'react-router-dom';
import { getMe, login, logout } from '../api/auth.api';


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
      // Використовуємо спеціальний ендпоінт /users/me для перевірки сесії
      const currentUser = await getMe(); 
      setUser(currentUser);
      setIsAuthenticated(!!currentUser);
    } catch (error: any) {
      setUser(null);
      setIsAuthenticated(false);
      // Не виводимо помилку в консоль, якщо це просто 401, це очікувана поведінка
      if (error.message.includes('401')) {
        console.log('User is not authenticated.');
      } else {
        console.error('An error occurred during auth check:', error);
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  // Змінюємо назву, щоб уникнути конфлікту імен
  const handleLogin = async (email: string, password: string) => {
    await apiLogin({ email, password });
    // Після успішного входу, знову перевіряємо статус
    await checkAuth();
  };

  const handleLogout = useCallback(async () => {
    await apiLogout();
    setUser(null);
    setIsAuthenticated(false);
  }, []);
  
  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated,
        isLoading,
        login: handleLogin, // Передаємо handleLogin
        logout: handleLogout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};