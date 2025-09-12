import { apiRequest } from '../utils/apiUtils';
import { ScanTask } from '../types/schemas'; 

export const getTasks = async (limit: number = 100, offset: number = 0): Promise<[ScanTask[], number]> => {
  return apiRequest('get', `/tasks/?limit=${limit}&offset=${offset}`);
};

export const deleteTask = async (taskId: string): Promise<{ ok: boolean }> => {
  return apiRequest('delete', `/tasks/${taskId}`);
};

export const updateTaskState = async (taskId: string, state: string): Promise<ScanTask> => {
  return apiRequest('patch', `/tasks/${taskId}/state?state=${state}`);
};