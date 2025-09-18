import { useQuery } from "@tanstack/react-query";
import { getComputers, getStatistics, getUsers } from "../api/api";
import { ComputersResponse, DashboardStats, UserRead } from "../types/schemas";
import { useAppContext } from "../context/AppContext";
import { Filters } from "../hooks/useComputerFilters";

export const useStatistics = (metrics: string[]) => {
  const { isAuthenticated } = useAppContext();
  return useQuery<DashboardStats, Error>({
    queryKey: ["statistics", metrics],
    queryFn: () => getStatistics({ metrics }),
    enabled: isAuthenticated,
    refetchOnWindowFocus: false,
    staleTime: 60 * 60 * 1000,
    retry: 3,
    retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 30000),
  });
};

export const useComputers = (params: Partial<Filters>) => {
  const { isAuthenticated } = useAppContext();
  const serializedParams = JSON.stringify({
    ...params,
    hostname: params.hostname || undefined, 
    os_name: params.os_name || undefined,
    check_status: params.check_status || undefined,
    sort_by: params.sort_by || undefined,
    sort_order: params.sort_order || undefined,
  });
  return useQuery<ComputersResponse, Error>({
    queryKey: ["computers", serializedParams], 
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
  const { isAuthenticated } = useAppContext();
  return useQuery<UserRead[], Error>({
    queryKey: ["users"],
    queryFn: getUsers,
    enabled: isAuthenticated,
    refetchOnWindowFocus: false,
    staleTime: 30 * 60 * 1000,
    gcTime: 60 * 60 * 1000,
    retry: 3,
    retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 30000),
  });
};
