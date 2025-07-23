// front/src/api/statistics.api.ts
import { apiInstance } from './api';
import { DashboardStats, ScanTask, ScanResponse } from '../types/schemas';

export const getStatistics = async (params: { metrics?: string[] } = {}) => {
  const response = await apiInstance.get<DashboardStats>('/statistics', {
    params: {
      metrics: params.metrics || [
        'total_computers',
        'os_distribution',
        'low_disk_space_with_volumes',
        'last_scan_time',
        'status_stats',
      ],
    },
    paramsSerializer: (params) => {
      const searchParams = new URLSearchParams();
      if (params.metrics) {
        params.metrics.forEach((metric: string) => {
          searchParams.append('metrics[]', metric);
        });
      }
      return searchParams.toString();
    },
    withCredentials: true,
  });
  return response.data;
};

export const startScan = async () => {
  const response = await apiInstance.post<ScanResponse>('/scan', {}, { withCredentials: true });
  return response.data;
};

export const startADScan = async () => {
  const response = await apiInstance.post<ScanResponse>('/ad/scan', {}, { withCredentials: true });
  return response.data;
};

export const startHostScan = async (hostname: string) => {
  const response = await apiInstance.post<ScanResponse>('/scan', { hostname }, { withCredentials: true });
  return response.data;
};

export const getScanStatus = async (taskId: string) => {
  const response = await apiInstance.get<ScanTask>(`/scan/status/${taskId}`, { withCredentials: true });
  return response.data;
};