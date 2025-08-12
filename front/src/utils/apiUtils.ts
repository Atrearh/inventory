import { Filters } from '../hooks/useComputerFilters';

export const cleanAndSerializeParams = (params: Filters): URLSearchParams => {
  const cleanedParams = {
    hostname: params.hostname || undefined,
    os_name: params.os_name || undefined,
    check_status: params.check_status || undefined,
    sort_by: params.sort_by || 'hostname',
    sort_order: params.sort_order === 'asc' || params.sort_order === 'desc' ? params.sort_order : 'asc',
    page: params.page || 1,
    limit: params.limit || 10,
    server_filter: params.server_filter || undefined,
    ip_range: params.ip_range || undefined, // Додано для сумісності з іншими функціями
  };

  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(cleanedParams)) {
    if (value !== undefined && value !== '') {
      searchParams.append(key, String(value));
    }
  }
  return searchParams;
};