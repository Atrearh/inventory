import { apiRequest } from '../utils/apiUtils';

export const updatePolicies = async (hostname: string) => {
  if (!hostname) {
    throw new Error('Hostname не вказано');
  }
  return apiRequest<{ output: string; error: string }>('post', '/scripts/execute/updatePolicies.ps1', { hostname });
};

export const restartPrintSpooler = async (hostname: string) => {
  if (!hostname) {
    throw new Error('Hostname не вказано');
  }
  return apiRequest<{ output: string; error: string }>('post', '/scripts/execute/restartPrintSpooler.ps1', { hostname });
};

export const getScriptsList = async (): Promise<string[]> => {
  return apiRequest<string[]>('get', '/scripts/list');
};

export const executeScript = async (hostname: string, scriptName: string): Promise<{ output: string; error: string }> => {
  if (!hostname) {
    throw new Error('Hostname не вказано');
  }
  return apiRequest<{ output: string; error: string }>('post', `/scripts/execute/${scriptName}`, { hostname });
};