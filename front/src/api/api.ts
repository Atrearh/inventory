// src/api/api.ts
import axios from 'axios';
import { Computer, ChangeLog, DashboardStats } from '../types/schemas';
import { API_URL } from '../config';

const axiosInstance = axios.create({
  baseURL: API_URL,
});

export const getStatistics = async (params: { metrics?: string[] } = {}) => {
  const response = await axiosInstance.get<DashboardStats>('/statistics', {
    params: {
      metrics: params.metrics || undefined,
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
  });
  return response.data;
};

export const getComputers = async (params: {
  hostname?: string;
  os_version?: string;
  status?: string;
  check_status?: string;
  sort_by?: string;
  sort_order?: string;
  page?: number;
  limit?: number;
  id?: string;
}) => {
  const response = await axiosInstance.get<{ data: Computer[]; total: number }>('/computers', {
    params: {
      ...params,
      page: params.page || 1,
      limit: params.limit || 50,
      sort_order: params.sort_order === 'asc' ? 'asc' : params.sort_order === 'desc' ? 'desc' : undefined,
    },
  });
  return response.data;
};

export const getHistory = async (computerId: number) => {
  const response = await axiosInstance.get<ChangeLog[]>(`/history/${computerId}`);
  return response.data;
};

export const startScan = async () => {
  const response = await axiosInstance.post<{ status: string; task_id: string }>('/scan');
  return response.data;
};

export const getScanStatus = async (taskId: string) => {
  const response = await axiosInstance.get(`/scan/status/${taskId}`);
  return response.data;
};