// front/src/api/computers.api.ts
import { apiRequest, cleanAndSerializeParams } from '../utils/apiUtils';
import { ComputersResponse, Computer, ComponentHistory } from '../types/schemas';
import { Filters } from '../hooks/useComputerFilters';

export const getComputers = async (params: Filters) => {
  return apiRequest<ComputersResponse>('get', '/computers', undefined, {
    params: {
      ...params,
      hostname: undefined,
      os_name: undefined,
      check_status: undefined,
      sort_by: undefined,
      sort_order: undefined,
    },
    paramsSerializer: () => cleanAndSerializeParams(params).toString(),
  });
};

export const getComputerById = async (computerId: number) => {
  return apiRequest<Computer>('get', `/computers/${computerId}`);
};

export const getHistory = async (computerId: number): Promise<ComponentHistory[]> => {
  return apiRequest('get', `/computers/${computerId}/history`);
};

export const exportComputersToCSV = async (params: Filters) => {
  return apiRequest('get', '/computers/export/csv', undefined, {
    paramsSerializer: () => cleanAndSerializeParams(params).toString(),
    responseType: 'blob',
  });
};