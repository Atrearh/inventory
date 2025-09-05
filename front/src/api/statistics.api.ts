import { apiRequest, cleanAndSerializeParams } from '../utils/apiUtils';
import { DashboardStats, ScanTask, ScanResponse } from '../types/schemas';

export const getStatistics = async (params: { metrics?: string[] } = {}) => {
  const defaultMetrics = [
    'total_computers',
    'os_distribution',
    'low_disk_space_with_volumes',
    'last_scan_time',
    'status_stats',
  ];
  return apiRequest<DashboardStats>(
    'get',
    '/statistics',
    undefined,
    {
      params: {
        metrics: params.metrics || defaultMetrics,
      },
      paramsSerializer: cleanAndSerializeParams,
    }
  );
};

export const startScan = async () => {
  return apiRequest<ScanResponse>('post', '/scan', {});
};

export const startADScan = async () => {
  return apiRequest<ScanResponse>('post', '/ad/scan', {});
};

export const startHostScan = async (hostname: string) => {
  return apiRequest<ScanResponse>('post', '/scan', { hostname });
};

export const getScanStatus = async (taskId: string) => {
  return apiRequest<ScanTask>('get', `/scan/status/${taskId}`);
};