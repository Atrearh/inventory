import { DomainRead, DomainCreate, DomainUpdate } from "../types/schemas";
import { apiInstance } from './api';

const API_URL = "/api/domains";

export const getDomains = async (): Promise<DomainRead[]> => {
  const { data } = await apiInstance.get(API_URL);
  return data;
};

export const createDomain = async (payload: DomainCreate): Promise<DomainRead> => {
  const { data } = await apiInstance.post(API_URL, payload);
  return data;
};

export const updateDomain = async (name: string, payload: DomainUpdate): Promise<DomainRead> => {
  const { data } = await apiInstance.put(`${API_URL}/${name}`, payload);
  return data;
};

export const deleteDomain = async (name: string): Promise<void> => {
  await apiInstance.delete(`${API_URL}/${name}`);
};

