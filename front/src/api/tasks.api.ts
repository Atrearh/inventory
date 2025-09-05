import { apiRequest } from '../utils/apiUtils';

export interface Task {
  id: string;
  name: string;
  status: string;
  created_at: string;
}

export const getTasks = async (): Promise<Task[]> => {
  return apiRequest<Task[]>('get', '/tasks');
};