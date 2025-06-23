// src/api/api.ts
import axios from 'axios';
import { Computer, ChangeLog, DashboardStats } from '../types/schemas';
import { API_URL } from '../config';
//import { apiClient } from './client';

const axiosInstance = axios.create({
  baseURL: API_URL,
});

export const startADScan = async () => {
  const response = await apiClient.post('/ad/scan');
  return response.data;
};

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
  check_status?: string;
  sort_by?: string;
  sort_order?: string;
  page?: number;
  limit?: number;
  id?: string;
}) => {
  const cleanedParams = {
    hostname: params.hostname || undefined,
    os_version: params.os_version || undefined,
    check_status: params.check_status || undefined,
    sort_by: params.sort_by || 'hostname',
    sort_order: params.sort_order === 'asc' || params.sort_order === 'desc' ? params.sort_order : 'asc',
    page: params.page || 1,
    limit: params.limit || 50,
    id: params.id ? Number(params.id) : undefined,
  };

  const response = await axiosInstance.get<{ data: Computer[]; total: number }>('/computers', {
    params: cleanedParams,
    paramsSerializer: (params) => {
      const searchParams = new URLSearchParams();
      for (const [key, value] of Object.entries(params)) {
        if (value !== undefined && value !== '') {
          searchParams.append(key, String(value));
        }
      }
      return searchParams.toString();
    },
  });
  return response.data;
};

export const getComputerById = async (computerId: number) => {
  const response = await axiosInstance.get<Computer>(`/computers/${computerId}`);
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