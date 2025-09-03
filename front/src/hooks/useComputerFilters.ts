import { useState, useCallback, useEffect, useMemo} from 'react';
import { useSearchParams } from 'react-router-dom';
import { useDebounce } from './useDebounce';
import { ComputerListItem } from '../types/schemas';
import { ITEMS_PER_PAGE } from '../config';
import type { TablePaginationConfig } from 'antd';
import type { SorterResult } from 'antd/es/table/interface';
import { getDomains } from '../api/domain.api';
import { useQuery } from '@tanstack/react-query';

export interface Filters {
  hostname: string | undefined;
  os_name: string | undefined;
  domain: string | undefined;
  check_status: string | undefined;
  show_disabled: boolean;
  sort_by: string;
  sort_order: 'asc' | 'desc';
  page: number;
  limit: number;
  server_filter?: string;
  ip_range?: string;
}

export const isServerOs = (osName: string) => {
  const serverOsPatterns = [/server/i, /hyper-v/i];
  return serverOsPatterns.some((pattern) => pattern.test(osName.toLowerCase()));
};

const extractDomainFromHostname = (hostname: string): string | null => {
  const parts = hostname.split('.');
  if (parts.length > 1) {
    return parts.slice(1).join('.'); // Повертаємо домен (все після першого '.')
  }
  return null;
};

export const useComputerFilters = (cachedComputers: ComputerListItem[]) => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [filters, setFilters] = useState<Filters>({
    hostname: searchParams.get('hostname') || undefined,
    os_name: searchParams.get('os_name') || undefined,
    domain: searchParams.get('domain') || undefined,
    check_status: searchParams.get('check_status') || undefined,
    show_disabled: searchParams.get('show_disabled') === 'true' || false,
    sort_by: searchParams.get('sort_by') || 'hostname',
    sort_order: (searchParams.get('sort_order') as 'asc' | 'desc') || 'asc',
    page: Number(searchParams.get('page')) || 1,
    limit: Number(searchParams.get('limit') || ITEMS_PER_PAGE),
    server_filter: searchParams.get('server_filter') || undefined,
    ip_range: searchParams.get('ip_range') || undefined,
  });

  const debouncedHostname = useDebounce(filters.hostname || '', 300);
  const debouncedOsName = useDebounce(filters.os_name || '', 300);
  const debouncedDomain = useDebounce(filters.domain || '', 300);
  const debouncedCheckStatus = useDebounce(filters.check_status || '', 300);

  const { data: domainsData } = useQuery({
      queryKey: ['domains'],
      queryFn: getDomains,
    });

  const domainMap = useMemo(() => {
    const map = new Map<number, string>();
    domainsData?.forEach((domain) => {
      map.set(domain.id, domain.name);
    });
    return map;
  }, [domainsData]);
  // Оновлення параметрів URL при зміні фільтрів
  useEffect(() => {
    setSearchParams(
      (prevParams) => {
        const newParams = new URLSearchParams(prevParams);
        const filterParams: Record<string, any> = {
          hostname: filters.hostname,
          os_name: filters.os_name,
          domain: filters.domain,
          check_status: filters.check_status,
          show_disabled: filters.show_disabled,
          sort_by: filters.sort_by,
          sort_order: filters.sort_order,
          page: filters.page,
          limit: filters.limit,
          server_filter: filters.server_filter,
          ip_range: filters.ip_range,
        };

        for (const [key, value] of Object.entries(filterParams)) {
          if (value !== undefined && value !== null && String(value) !== '') {
            if (key === 'show_disabled' && value === false) {
              newParams.delete(key);
            } else {
              newParams.set(key, String(value));
            }
          } else {
            newParams.delete(key);
          }
        }

        return newParams;
      },
      { replace: true }
    );
  }, [filters, setSearchParams]);

  // Обробка зміни фільтрів
  const handleFilterChange = useCallback(
    (key: keyof Filters, value: string | boolean | undefined) => {
      setFilters((prev) => ({
        ...prev,
        [key]: value,
        page: key !== 'page' ? 1 : prev.page,
      }));
    },
    []
  );

  // Очищення всіх фільтрів
  const clearAllFilters = useCallback(() => {
    setFilters({
      hostname: undefined,
      os_name: undefined,
      domain: undefined,
      check_status: undefined,
      show_disabled: false,
      sort_by: 'hostname',
      sort_order: 'asc',
      page: 1,
      limit: ITEMS_PER_PAGE,
      server_filter: undefined,
      ip_range: undefined,
    });
  }, []);

  // Обробка зміни таблиці (сортування, пагінація)
  const handleTableChange = useCallback(
    (
      pagination: TablePaginationConfig,
      _filters: Record<string, any>,
      sorter: SorterResult<ComputerListItem> | SorterResult<ComputerListItem>[]
    ) => {
      const sort = Array.isArray(sorter) ? sorter[0] : sorter;
      setFilters((prev) => ({
        ...prev,
        page: pagination.current || 1,
        limit: pagination.pageSize || ITEMS_PER_PAGE,
        sort_by: sort.field ? String(sort.field) : prev.sort_by,
        sort_order: sort.order === 'ascend' ? 'asc' : sort.order === 'descend' ? 'desc' : prev.sort_order,
      }));
    },
    []
  );

  // Фільтрація комп’ютерів на клієнтській стороні
  const filteredComputers = useMemo(() => {
    let filtered = [...cachedComputers];

    if (debouncedHostname) {
      filtered = filtered.filter((comp) =>
        comp.hostname?.toLowerCase().includes(debouncedHostname.toLowerCase())
      );
    }
    if (debouncedOsName) {
      filtered = filtered.filter((comp) =>
        comp.os_name?.toLowerCase().includes(debouncedOsName.toLowerCase())
      );
    }
    if (debouncedDomain) {
      filtered = filtered.filter((comp) =>
        comp.domain_id ? domainMap.get(comp.domain_id)?.toLowerCase() === debouncedDomain.toLowerCase() : false
      );
    }
    if (debouncedCheckStatus) {
      filtered = filtered.filter((comp) => comp.check_status === debouncedCheckStatus);
    }
    if (!filters.show_disabled) {
      filtered = filtered.filter(
        (comp) => comp.check_status !== 'disabled' && comp.check_status !== 'is_deleted'
      );
    }
    if (filters.server_filter === 'server') {
      filtered = filtered.filter((comp) => comp.os_name && isServerOs(comp.os_name));
    } else if (filters.server_filter === 'client') {
      filtered = filtered.filter((comp) => comp.os_name && !isServerOs(comp.os_name));
    }
    if (filters.ip_range) {
      filtered = filtered.filter((comp) =>
        comp.ip_addresses?.some((ip) => {
          const ipParts = ip.address.split('.');
          const rangeParts = filters.ip_range!.split('.');
          if (rangeParts[2]?.startsWith('[')) {
            const [start, end] = rangeParts[2].match(/\[(\d+)-(\d+)\]/)!.slice(1).map(Number);
            const thirdOctet = Number(ipParts[2]);
            return (
              ipParts[0] === rangeParts[0] &&
              ipParts[1] === rangeParts[1] &&
              thirdOctet >= start &&
              thirdOctet <= end
            );
          }
          return ip.address === filters.ip_range;
        })
      );
    }

    filtered.sort((a, b) => {
      const field = filters.sort_by as keyof ComputerListItem;
      let aValue: string | number | boolean | Date = '';
      let bValue: string | number | boolean | Date = '';

      if (field === 'ip_addresses') {
        aValue = a.ip_addresses?.[0]?.address || '';
        bValue = b.ip_addresses?.[0]?.address || '';
      } else if (field === 'is_virtual') {
        aValue = a.is_virtual ?? false;
        bValue = b.is_virtual ?? false;
      } else if (field === 'physical_disks') {
        aValue = a.physical_disks?.[0]?.model || '';
        bValue = b.physical_disks?.[0]?.model || '';
      } else if (field === 'logical_disks') {
        aValue = a.logical_disks?.[0]?.volume_label || '';
        bValue = b.logical_disks?.[0]?.volume_label || '';
      } else if (field === 'processors') {
        aValue = a.processors?.[0]?.name || '';
        bValue = b.processors?.[0]?.name || '';
      } else if (field === 'mac_addresses') {
        aValue = a.mac_addresses?.[0]?.address || '';
        bValue = b.mac_addresses?.[0]?.address || '';
      } else if (field === 'roles') {
        aValue = a.roles?.[0]?.Name || '';
        bValue = b.roles?.[0]?.Name || '';
      } else if (field === 'software') {
        aValue = a.software?.[0]?.DisplayName || '';
        bValue = b.software?.[0]?.DisplayName || '';
      } else if (field === 'video_cards') {
        aValue = a.video_cards?.[0]?.name || '';
        bValue = b.video_cards?.[0]?.name || '';
      } else if (field === 'last_full_scan') {
        aValue = a.last_full_scan ? new Date(a.last_full_scan) : new Date(0);
        bValue = b.last_full_scan ? new Date(b.last_full_scan) : new Date(0);
      } else if (field === 'domain_id') { 
        aValue = a.domain_id ? domainMap.get(a.domain_id) ?? '' : '';
        bValue = b.domain_id ? domainMap.get(b.domain_id) ?? '' : '';
      } else {
        aValue = a[field] ?? '';
        bValue = b[field] ?? '';
      }

      if (typeof aValue === 'boolean' && typeof bValue === 'boolean') {
        return filters.sort_order === 'asc'
          ? aValue === bValue
            ? 0
            : aValue
            ? 1
            : -1
          : aValue === bValue
          ? 0
          : aValue
          ? -1
          : 1;
      }
      if (aValue instanceof Date && bValue instanceof Date) {
        return filters.sort_order === 'asc'
          ? aValue.getTime() - bValue.getTime()
          : bValue.getTime() - aValue.getTime();
      }
      return filters.sort_order === 'asc'
        ? String(aValue).localeCompare(String(bValue))
        : String(bValue).localeCompare(String(aValue));
    });

    const start = (filters.page - 1) * filters.limit;
    const end = start + filters.limit;
    return {
      data: filtered.slice(start, end),
      total: filtered.length,
    };
  }, [cachedComputers, debouncedHostname, debouncedOsName, debouncedDomain, debouncedCheckStatus, filters, domainMap]);

  return {
    filters,
    filteredComputers,
    debouncedSetHostname: handleFilterChange.bind(null, 'hostname'),
    handleFilterChange,
    clearAllFilters,
    handleTableChange,
  };
};