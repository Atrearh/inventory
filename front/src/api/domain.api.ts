import { apiInstance } from './api';
import { DomainCreate, DomainRead, DomainUpdate } from '../types/schemas';

const API_URL = 'http://192.168.0.143:8000/api/domains/';

export const getDomains = async (): Promise<DomainRead[]> => {
  const response = await apiInstance.get(API_URL, {
    headers: { 'Content-Type': 'application/json' },
  });
  return response.data;
};

export const createDomain = async (data: DomainCreate): Promise<DomainRead> => {
  try {
    const response = await apiInstance.post(API_URL, data, {
      headers: { 'Content-Type': 'application/json' },
    });
    return response.data;
  } catch (error: any) {
    console.error('Помилка при створенні домену:', {
      message: error.message,
      response: error.response?.data,
      status: error.response?.status,
    });
    throw error;
  }
};

export const updateDomain = async (id: number, data: DomainUpdate): Promise<DomainRead> => {
  const response = await apiInstance.put(`${API_URL}${id}`, data, {
    headers: { 'Content-Type': 'application/json' },
  });
  return response.data;
};

export const deleteDomain = async (id: number): Promise<void> => {
  await apiInstance.delete(`${API_URL}${id}`, {
    headers: { 'Content-Type': 'application/json' },
  });
};

export const validateDomain = async (data: DomainCreate): Promise<{ status: string; message: string }> => {
  try {
    const response = await apiInstance.post(`${API_URL}validate`, data, {
      headers: { 'Content-Type': 'application/json' },
    });
    return response.data;
  } catch (error: any) {
    console.error('Помилка перевірки домену:', {
      message: error.message,
      response: error.response?.data,
      status: error.response?.status,
    });
    throw error;
  }
};

export const scanDomains = async (domainId?: number): Promise<{ status: string; task_id?: string; task_ids?: string[] }> => {
  try {
    const url = `${API_URL}scan${domainId ? `?domain_id=${domainId}` : ''}`; // Використовуємо query-параметр
    const response = await apiInstance.post(url, {}, {
      headers: { 'Content-Type': 'application/json' },
    });
    return response.data;
  } catch (error: any) {
    console.error('Помилка сканування доменів:', {
      message: error.message,
      response: error.response?.data,
      status: error.response?.status,
    });
    throw error;
  }
};
