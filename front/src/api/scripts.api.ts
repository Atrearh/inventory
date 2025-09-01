import { apiInstance } from './api';

export const updatePolicies = async (hostname: string) => {
  if (!hostname) {
    throw new Error('Hostname не вказано');
  }
  const response = await apiInstance.post('/scripts/execute/updatePolicies.ps1', { hostname }, { withCredentials: true });
  return response.data;
};

export const restartPrintSpooler = async (hostname: string) => {
  if (!hostname) {
    throw new Error('Hostname не вказано');
  }
  const response = await apiInstance.post('/scripts/execute/restartPrintSpooler.ps1', { hostname }, {
    withCredentials: true,
  });
  return response.data;
};

export const getScriptsList = async (): Promise<string[]> => {
  const response = await apiInstance.get(`/scripts/list`, { withCredentials: true });
  return response.data;
};

export const executeScript = async (hostname: string, scriptName: string): Promise<{ output: string; error: string }> => {
  if (!hostname) {
    throw new Error('Hostname не вказано');
  }
  const response = await apiInstance.post(`/scripts/execute/${scriptName}`, { hostname }, { withCredentials: true });
  return response.data;
};