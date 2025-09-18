import { apiRequest } from "../utils/apiUtils";
import { ScanTask } from "../types/schemas";

export const getTasks = async (
  limit: number = 100,
  offset: number = 0,
): Promise<{ tasks: ScanTask[]; total: number }> => {
  const [tasks, total] = await apiRequest("get", `/tasks/?limit=${limit}&offset=${offset}`);
  return { tasks, total };
};

export const deleteTask = async (taskId: string): Promise<{ ok: boolean }> => {
  return apiRequest("delete", `/tasks/${taskId}`);
};

export const updateTaskState = async (
  taskId: string,
  state: string,
): Promise<ScanTask> => {
  return apiRequest("patch", `/tasks/${taskId}/state?state=${state}`);
};