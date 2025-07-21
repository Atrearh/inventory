// src/hooks/useApiQueries.ts
import { useQuery } from '@tanstack/react-query';
import { getComputers, getStatistics, getUsers } from '../api/api';
import { ComputersResponse, DashboardStats, UserRead } from '../types/schemas';
import { useAuth } from '../context/AuthContext';

// Хук для отримання статистики
export const useStatistics = (metrics: string[]) => {
  const { isAuthenticated } = useAuth();
  return useQuery<DashboardStats, Error>({
    queryKey: ['statistics'],
    queryFn: () => getStatistics({ metrics }),
    enabled: isAuthenticated,
    refetchOnWindowFocus: false,
    staleTime: 60 * 60 * 1000,
    retry: 3,
    retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 30000),
  });
};

// Хук для отримання списку комп'ютерів
export const useComputers = (params: any) => {
  const { isAuthenticated } = useAuth();
  return useQuery<ComputersResponse, Error>({
    queryKey: ['computers', params],
    queryFn: () => getComputers(params),
    enabled: isAuthenticated,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 30 * 60 * 1000,
    gcTime: 60 * 60 * 1000,
    retry: 3,
    retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 30000),
  });
};

// Хук для отримання списку користувачів
export const useUsers = () => {
  const { isAuthenticated } = useAuth();
  return useQuery<UserRead[], Error>({
    queryKey: ['users'],
    queryFn: getUsers,
    enabled: isAuthenticated,
    refetchOnWindowFocus: false,
  });
};