import React, { createContext, useContext, useState, useEffect } from 'react';
import { login, logout } from '../api/api';
import { jwtDecode } from 'jwt-decode'; // Используем именованный импорт

interface AuthContextType {
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

interface JwtPayload {
  exp: number;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      try {
        const decoded: JwtPayload = jwtDecode(token); // Используем jwtDecode как функцию
        const currentTime = Date.now() / 1000;
        if (decoded.exp > currentTime) {
          setIsAuthenticated(true);
        } else {
          console.warn('Token expired, clearing localStorage');
          localStorage.removeItem('token');
          setIsAuthenticated(false);
        }
      } catch (error) {
        console.error('Invalid token:', error);
        localStorage.removeItem('token');
        setIsAuthenticated(false);
      }
    }
  }, []);

  const handleLogin = async (email: string, password: string) => {
    try {
      const response = await login({ email, password });
      localStorage.setItem('token', response.access_token);
      setIsAuthenticated(true);
    } catch (error) {
      console.error('Login failed:', error);
      throw error;
    }
  };

  const handleLogout = async () => {
    try {
      await logout();
      localStorage.removeItem('token');
      setIsAuthenticated(false);
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated, login: handleLogin, logout: handleLogout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};