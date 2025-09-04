import { useQuery } from '@tanstack/react-query';
import { getComputers, getStatistics, getUsers } from '../api/api';
import { ComputersResponse, DashboardStats, UserRead } from '../types/schemas';
import { useAuth } from '../context/AuthContext';
import { Filters } from '../hooks/useComputerFilters';

export const useStatistics = (metrics: string[]) => {
  const { isAuthenticated } = useAuth();
  return useQuery<DashboardStats, Error>({
    queryKey: ['statistics', metrics],
    queryFn: () => getStatistics({ metrics }),
    enabled: isAuthenticated,
    refetchOnWindowFocus: false,
    staleTime: 60 * 60 * 1000,
    retry: 3,
    retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 30000),
  });
};

export const useComputers = (params: Partial<Filters>) => {
  const { isAuthenticated } = useAuth();
  return useQuery<ComputersResponse, Error>({
    queryKey: ['computers', params.show_disabled, params.server_filter, params.ip_range, params.domain],
    queryFn: () => getComputers(params as Filters),
    enabled: isAuthenticated,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 30 * 60 * 1000,
    gcTime: 60 * 60 * 1000,
    retry: 3,
    retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 30000),
    
  });
};

export const useUsers = () => {
  const { isAuthenticated } = useAuth();
  return useQuery<UserRead[], Error>({
    queryKey: ['users'],
    queryFn: getUsers,
    enabled: isAuthenticated,
    refetchOnWindowFocus: false,
    staleTime: 30 * 60 * 1000,
    gcTime: 60 * 60 * 1000,
    retry: 3,
    retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 30000),
  });
};