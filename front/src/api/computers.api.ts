// front/src/api/computers.api.ts
import { apiRequest, cleanAndSerializeParams } from "../utils/apiUtils";
import {
  ComputersResponse,
  ComputerDetail,
  ComponentHistory,
} from "../types/schemas";
import { Filters } from "../hooks/useComputerFilters";

export const getComputers = async (params: Filters) => {
  const serializedParams = cleanAndSerializeParams({
    ...params,
    hostname: undefined, 
    os_name: undefined,
    check_status: undefined,
    sort_by: undefined,
    sort_order: undefined,
  });
  return apiRequest<ComputersResponse>("get", `/computers?${serializedParams}`);
};

export const getComputerById = async (computerId: number) => {
  return apiRequest<ComputerDetail>("get", `/computers/${computerId}`);
};

export const getHistory = async (
  computerId: number,
): Promise<ComponentHistory[]> => {
  return apiRequest("get", `/computers/${computerId}/history`);
};

export const exportComputersToCSV = async (params: Filters) => {
  const blob = await apiRequest<Blob>("get", "/computers/export/csv", undefined, {
    params: params, // Використовувати дефолт serializer з api.ts
    responseType: "blob",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'computers.csv';
  a.click();
  URL.revokeObjectURL(url); // Cleanup
};