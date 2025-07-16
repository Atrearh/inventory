import React, { createContext, useContext, useState, useEffect } from 'react';
import { login, logout, refreshToken } from '../api/api';
import { jwtDecode } from 'jwt-decode';

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

interface JwtPayload {
  exp: number;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    const checkToken = async () => {
      const accessToken = localStorage.getItem('access_token');
      const refreshTokenValue = localStorage.getItem('refresh_token');
      if (accessToken && refreshTokenValue) {
        try {
          const decoded: JwtPayload = jwtDecode(accessToken);
          const currentTime = Date.now() / 1000;
          if (decoded.exp > currentTime) {
            setIsAuthenticated(true);
          } else {
            try {
              await refreshToken();
              setIsAuthenticated(true);
            } catch (error) {
              console.error('Failed to refresh token:', error);
              localStorage.removeItem('access_token');
              localStorage.removeItem('refresh_token');
              setIsAuthenticated(false);
            }
          }
        } catch (error) {
          console.error('Invalid access token:', error);
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          setIsAuthenticated(false);
        }
      }
      setIsLoading(false);
    };

    checkToken();

    const interval = setInterval(async () => {
      const accessToken = localStorage.getItem('access_token');
      if (accessToken) {
        try {
          const decoded: JwtPayload = jwtDecode(accessToken);
          const currentTime = Date.now() / 1000;
          if (decoded.exp < currentTime + 300) {
            await refreshToken();
          }
        } catch (error) {
          console.error('Error checking token:', error);
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          setIsAuthenticated(false);
        }
      }
    }, 5 * 60 * 1000);

    return () => clearInterval(interval);
  }, []);

  const handleLogin = async (email: string, password: string) => {
    try {
      await login({ email, password });
      setIsAuthenticated(true);
    } catch (error) {
      console.error('Login failed:', error);
      throw error;
    }
  };

  const handleLogout = async () => {
    try {
      await logout();
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      setIsAuthenticated(false);
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated, isLoading, login: handleLogin, logout: handleLogout }}>
      {isLoading ? <div>Загрузка...</div> : children}
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