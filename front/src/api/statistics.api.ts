import { apiRequest} from "../utils/apiUtils";
import { DashboardStats, ScanTask, ScanResponse } from "../types/schemas";

const DEFAULT_METRICS = [
  "total_computers",
  "os_distribution",
  "low_disk_space_with_volumes",
  "last_scan_time",
  "status_stats",
  "software_distribution",
] as const;

export const getStatistics = async (params: { metrics?: string[] } = {}) => {
  return apiRequest<DashboardStats>("get", "/statistics", undefined, {
    params: {
      metrics: params.metrics || DEFAULT_METRICS,
    },
  });
};

export const startScan = async () => {
  return apiRequest<ScanResponse>("post", "/scan", {});
};

export const startADScan = async () => {
  return apiRequest<ScanResponse>("post", "/ad/scan", {});
};

export const startHostScan = async (hostname: string) => {
  return apiRequest<ScanResponse>("post", "/scan", { hostname });
};

export const getScanStatus = async (taskId: string, retries = 3) => {
  for (let i = 0; i < retries; i++) {
    try {
      return await apiRequest<ScanTask>("get", `/scan/status/${taskId}`);
    } catch (error) {
      if (i === retries - 1) throw error; // Останній retry
      await new Promise(resolve => setTimeout(resolve, 1000 * (i + 1))); // Exponential backoff
    }
  }
};