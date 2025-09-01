// front/src/api/domain.api.ts
import { apiInstance } from './api';
import { DomainCreate, DomainRead, DomainUpdate } from '../types/schemas';

// Отримуємо список всіх доменів
export const getDomains = async (): Promise<DomainRead[]> => {
  const response = await apiInstance.get('/domains/');
  return response.data;
};

// Створюємо новий домен
export const createDomain = async (data: DomainCreate): Promise<DomainRead> => {
  const response = await apiInstance.post('/domains/', data);
  return response.data;
};

// Оновлюємо існуючий домен
export const updateDomain = async (id: number, data: DomainUpdate): Promise<DomainRead> => {
  const response = await apiInstance.put(`/domains/${id}`, data);
  return response.data;
};

// Видаляємо домен
export const deleteDomain = async (id: number): Promise<void> => {
  await apiInstance.delete(`/domains/${id}`);
};

// Перевіряємо з'єднання з доменом
export const validateDomain = async (data: DomainCreate): Promise<{ status: string; message: string }> => {
  const response = await apiInstance.post('/domains/validate', data);
  return response.data;
};

// Запускаємо сканування AD для доменів
export const scanDomains = async (domainId?: number): Promise<{ status: string; task_id?: string; task_ids?: string[] }> => {
  const url = `/domains/scan${domainId ? `?domain_id=${domainId}` : ''}`;
  const response = await apiInstance.post(url);
  return response.data;
};