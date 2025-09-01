import { useState, useCallback, useEffect, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { debounce } from 'lodash';
import { ComputerListItem } from '../types/schemas';
import { ITEMS_PER_PAGE } from '../config';
import type { TableProps, TablePaginationConfig } from 'antd';
import type { SortOrder } from 'antd/es/table/interface';

// Інтерфейс для фільтрів таблиці комп’ютерів
export interface Filters {
  hostname: string | undefined;
  os_name: string | undefined;
  check_status: string | undefined;
  show_disabled: boolean;
  sort_by: string;
  sort_order: 'asc' | 'desc';
  page: number; // Змінено на number
  limit: number; // Змінено на number
  server_filter?: string;
  ip_range?: string;
}

interface Sorter {
  field?: string;
  order?: SortOrder;
}

// Функція для перевірки, чи є ОС серверною
export const isServerOs = (osName: string) => {
  const serverOsPatterns = [/server/i, /hyper-v/i];
  return serverOsPatterns.some((pattern) => pattern.test(osName.toLowerCase()));
};

export const useComputerFilters = (cachedComputers: ComputerListItem[]) => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [filters, setFilters] = useState<Filters>({
    hostname: searchParams.get('hostname') || undefined,
    os_name: searchParams.get('os_name') || undefined,
    check_status: searchParams.get('check_status') || undefined,
    show_disabled: searchParams.get('show_disabled') === 'true' || false,
    sort_by: searchParams.get('sort_by') || 'hostname',
    sort_order: (searchParams.get('sort_order') as 'asc' | 'desc') || 'asc',
    page: Number(searchParams.get('page')) || 1,
    limit: Number(searchParams.get('limit') || ITEMS_PER_PAGE),
    server_filter: searchParams.get('server_filter') || undefined,
    ip_range: searchParams.get('ip_range') || undefined,
  });

  // Оновлення параметрів URL при зміні фільтрів
  useEffect(() => {
    setSearchParams(prevParams => {
      // 1. Створюємо копію існуючих параметрів, щоб зберегти 'tab' та інші.
      const newParams = new URLSearchParams(prevParams);

      // 2. Створюємо об'єкт з поточними фільтрами для зручності.
      const filterParams: Record<string, any> = {
        hostname: filters.hostname,
        os_name: filters.os_name,
        check_status: filters.check_status,
        show_disabled: filters.show_disabled,
        sort_by: filters.sort_by,
        sort_order: filters.sort_order,
        page: filters.page,
        limit: filters.limit,
        server_filter: filters.server_filter,
        ip_range: filters.ip_range,
      };

      // 3. Проходимося по фільтрах і оновлюємо/видаляємо їх у newParams.
      for (const [key, value] of Object.entries(filterParams)) {
        // Якщо значення існує і не є порожнім, встановлюємо його.
        if (value !== undefined && value !== null && String(value) !== '') {
          // Окремо обробляємо булеве значення, щоб не додавати 'show_disabled=false' до URL
          if (key === 'show_disabled' && value === false) {
            newParams.delete(key);
          } else {
            newParams.set(key, String(value));
          }
        } else {
          // Якщо значення порожнє, видаляємо параметр з URL.
          newParams.delete(key);
        }
      }

      // 4. Повертаємо оновлений набір параметрів.
      return newParams;
    }, { replace: true });
  }, [filters, setSearchParams]);

  // Дебансована функція для оновлення hostname
  const debouncedSetHostname = useCallback(
    debounce((value: string) => {
      setFilters({
        hostname: value || undefined,
        os_name: undefined,
        check_status: undefined,
        show_disabled: false,
        sort_by: 'hostname',
        sort_order: 'asc',
        page: 1,
        limit: ITEMS_PER_PAGE,
        server_filter: undefined,
        ip_range: undefined,
      });
    }, 300),
    []
  );

  // Обробка змін фільтрів
  const handleFilterChange = useCallback((key: keyof Filters, value: string | boolean | number | undefined) => {
    const finalValue = value === '' || value === undefined ? undefined : value;
    setFilters((prev) => {
      const newFilters = {
        ...prev,
        [key]: finalValue,
        page: key !== 'page' && key !== 'limit' ? 1 : prev.page,
        server_filter: key === 'os_name' && finalValue && typeof finalValue === 'string' && isServerOs(finalValue) ? 'server' : undefined,
      };
      if (key === 'check_status' && finalValue && finalValue !== 'disabled' && finalValue !== 'is_deleted') {
        newFilters.show_disabled = false;
      }
      if (key === 'show_disabled' && !finalValue && (prev.check_status === 'disabled' || prev.check_status === 'is_deleted')) {
        newFilters.check_status = undefined;
      }
      return newFilters;
    });
  }, []);

  // Очищення всіх фільтрів
  const clearAllFilters = useCallback(() => {
    setFilters({
      hostname: undefined,
      os_name: undefined,
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

  // Обробка змін таблиці (пагінація та сортування)
  const handleTableChange: NonNullable<TableProps<ComputerListItem>['onChange']> = useCallback(
    (pagination: TablePaginationConfig, _filters: Record<string, any>, sorter: any, _extra: any) => {
      const sorterResult = Array.isArray(sorter) ? sorter[0] : sorter;
      setFilters((prev) => ({
        ...prev,
        page: pagination.current || 1,
        limit: pagination.pageSize || ITEMS_PER_PAGE,
        sort_by: (sorterResult.field as string) || 'hostname',
        sort_order: sorterResult.order === 'descend' ? 'desc' : 'asc',
      }));
    },
    []
  );

  // Фільтрація та сортування комп’ютерів
  const filteredComputers = useMemo(() => {
    const uniqueComputers = Array.from(
      new Map(cachedComputers.map((comp) => [comp.id, comp])).values()
    );

    let filtered = [...uniqueComputers];

    if (filters.hostname) {
      filtered = filtered.filter((comp) => comp.hostname.toLowerCase().startsWith(filters.hostname!.toLowerCase()));
    }
    if (filters.os_name) {
      filtered = filtered.filter((comp) => comp.os_name?.toLowerCase().includes(filters.os_name!.toLowerCase()));
    }
    if (filters.check_status) {
      filtered = filtered.filter((comp) => comp.check_status === filters.check_status);
    }
    if (!filters.show_disabled) {
      filtered = filtered.filter((comp) => comp.check_status !== 'disabled' && comp.check_status !== 'is_deleted');
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
          if (rangeParts[2].startsWith('[')) {
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
      let aValue: string | number | boolean = '';
      let bValue: string | number | boolean = '';

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
      } else {
        aValue = a[field] ?? '';
        bValue = b[field] ?? '';
      }

      if (typeof aValue === 'boolean' && typeof bValue === 'boolean') {
        return filters.sort_order === 'asc'
          ? aValue === bValue ? 0 : aValue ? 1 : -1
          : aValue === bValue ? 0 : aValue ? -1 : 1;
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
  }, [cachedComputers, filters]);

  return {
    filters,
    filteredComputers,
    debouncedSetHostname,
    handleFilterChange,
    clearAllFilters,
    handleTableChange,
  };
};