import { apiInstance } from './api';

export interface Task {
  id: string;
  name: string;
  status: string;
  created_at: string;
}

export const getTasks = async (): Promise<Task[]> => {
  const response = await apiInstance.get<Task[]>('/tasks', { withCredentials: true });
  return response.data;
};