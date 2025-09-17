import { apiRequest, cleanAndSerializeParams } from "../utils/apiUtils";
import { DomainCreate, DomainRead, DomainUpdate } from "../types/schemas";

export const getDomains = async (): Promise<DomainRead[]> => {
  return apiRequest<DomainRead[]>("get", "/domains/");
};

export const createDomain = async (data: DomainCreate): Promise<DomainRead> => {
  return apiRequest<DomainRead>("post", "/domains/", data);
};

export const updateDomain = async (
  id: number,
  data: Partial<DomainUpdate>,
): Promise<DomainRead> => {
  return apiRequest<DomainRead>("patch", `/domains/${id}`, data);
};

export const deleteDomain = async (id: number): Promise<void> => {
  return apiRequest<void>("delete", `/domains/${id}`);
};

export const validateDomain = async (
  data: DomainCreate,
): Promise<{ status: string; message: string }> => {
  return apiRequest<{ status: string; message: string }>(
    "post",
    "/domains/validate",
    data,
  );
};

export const scanDomains = async (
  domainId?: number,
): Promise<{ status: string; task_id?: string; task_ids?: string[] }> => {
  const params = domainId ? { domain_id: domainId } : {};
  return apiRequest("post", "/domains/scan", undefined, {
    params,
    paramsSerializer: () => cleanAndSerializeParams(params).toString(),
  });
};
