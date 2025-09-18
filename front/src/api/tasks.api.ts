import { apiRequest } from "../utils/apiUtils";
import { ScanTask } from "../types/schemas";

// Виправити getTasks: типізувати response як tuple
export const getTasks = async (
  limit: number = 100,
  offset: number = 0,
): Promise<{ tasks: ScanTask[]; total: number }> => {
  const response = await apiRequest<[ScanTask[], number]>("get", `/tasks/?limit=${limit}&offset=${offset}`);
  return { tasks: response[0], total: response[1] }; // Явна розпакування для TS
};

export const updateTaskState = async (
  taskId: string,
  state: string,
): Promise<ScanTask> => {
  return apiRequest("patch", `/tasks/${taskId}/state?state=${state}`); 
};