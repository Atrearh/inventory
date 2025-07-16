// src/components/ComputerList.tsx
import { useQuery } from '@tanstack/react-query';
import { getComputers, getStatistics } from '../api/api';
import { ComputersResponse, DashboardStats, ComputerListItem } from '../types/schemas';
import { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { notification, Skeleton, Input, Select, Table, Button } from 'antd';
import { debounce } from 'lodash';
import { useExportCSV } from '../hooks/useExportCSV';
import { ITEMS_PER_PAGE } from '../config';
import type { TableProps } from 'antd';
import type { InputRef } from 'antd';
import styles from './ComputerList.module.css';
import { useAuth } from '../context/AuthContext';

interface Filters {
  hostname: string | undefined;
  os_name: string | undefined;
  check_status: string | undefined;
  sort_by: string;
  sort_order: 'asc' | 'desc';
  page: number;
  limit: number;
  server_filter?: string;
}

interface Sorter {
  field?: string;
  order?: 'ascend' | 'descend';
}

const ComputerListComponent: React.FC = () => {
  const { isAuthenticated } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [filters, setFilters] = useState<Filters>({
    hostname: searchParams.get('hostname') || undefined,
    os_name: searchParams.get('os_name') || undefined,
    check_status: searchParams.get('check_status') || undefined,
    sort_by: searchParams.get('sort_by') || 'hostname',
    sort_order: (searchParams.get('sort_order') as 'asc' | 'desc') || 'asc',
    page: Number(searchParams.get('page')) || 1,
    limit: Number(searchParams.get('limit') || ITEMS_PER_PAGE),
  });
  const [cachedComputers, setCachedComputers] = useState<ComputerListItem[]>([]);
  const inputRef = useRef<InputRef>(null);

  const isServerOs = (osName: string) => {
    const serverOsPatterns = [/server/i, /hyper-v/i];
    return serverOsPatterns.some((pattern) => pattern.test(osName.toLowerCase()));
  };

  const { data: computersData, error: computersError, isLoading: isComputersLoading, refetch } = useQuery<
    ComputersResponse,
    Error
  >({
    queryKey: ['computers', { os_name: filters.os_name, check_status: filters.check_status, sort_by: filters.sort_by, sort_order: filters.sort_order, server_filter: filters.server_filter }],
    queryFn: () => {
      const params: Partial<Filters> = {
        ...filters,
        hostname: undefined, // Отключаем серверную фильтрацию по hostname
        limit: 1000,
      };
      if (params.os_name && params.os_name.toLowerCase() === 'unknown') {
        params.os_name = 'unknown';
      } else if (params.os_name && isServerOs(params.os_name)) {
        params.server_filter = 'server';
      } else {
        params.server_filter = undefined;
      }
      return getComputers(params as Filters);
    },
    enabled: isAuthenticated,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 30 * 60 * 1000,
    gcTime: 60 * 60 * 1000,
  });

  const { data: statsData, error: statsError, isLoading: isStatsLoading } = useQuery<DashboardStats, Error>({
    queryKey: ['statistics'],
    queryFn: () =>
      getStatistics({
        metrics: ['os_distribution'],
      }),
    enabled: isAuthenticated,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 60 * 60 * 1000,
  });

  const { handleExportCSV } = useExportCSV(filters);

  const debouncedSetHostname = useCallback(
  debounce((value: string) => {
    setFilters({
      hostname: value || undefined,
      os_name: undefined, // Сбрасываем фильтр по OS
      check_status: undefined, // Сбрасываем фильтр по статусу проверки
      sort_by: 'hostname', // Сбрасываем сортировку на hostname
      sort_order: 'asc', // Сбрасываем порядок сортировки на asc
      page: 1, // Сбрасываем страницу на первую
      limit: ITEMS_PER_PAGE, // Сбрасываем лимит на дефолтный
      server_filter: undefined, // Сбрасываем фильтр по серверным ОС
    });
  }, 300),
  []
);

  useEffect(() => {
    if (computersData?.data) {
      setCachedComputers(computersData.data.slice(0, 1000));
      if (computersData.total > 1000) {
        notification.warning({
          message: 'Ограничение данных',
          description: 'Отображается только первые 1000 компьютеров. Используйте фильтры для точного поиска.',
        });
      }
    }
  }, [computersData]);

  useEffect(() => {
    const params: Record<string, string> = {};
    if (filters.hostname) params.hostname = filters.hostname;
    if (filters.check_status) params.check_status = filters.check_status;
    if (filters.os_name) params.os_name = filters.os_name;
    if (filters.server_filter) params.server_filter = filters.server_filter;
    params.sort_by = filters.sort_by;
    params.sort_order = filters.sort_order;
    params.page = String(filters.page);
    params.limit = String(filters.limit);
    setSearchParams(params, { replace: true });
  }, [filters, setSearchParams]);

  const filteredComputers = useMemo(() => {
  let filtered = [...cachedComputers];

  if (filters.hostname) {
    filtered = filtered.filter((comp) => comp.hostname.toLowerCase().startsWith(filters.hostname!.toLowerCase()));
  }
  if (filters.os_name) {
    filtered = filtered.filter((comp) => comp.os_name?.toLowerCase().includes(filters.os_name!.toLowerCase()));
  }
  if (filters.check_status) {
    filtered = filtered.filter((comp) => comp.check_status === filters.check_status);
  }
  if (filters.server_filter === 'server') {
    filtered = filtered.filter((comp) => comp.os_name && isServerOs(comp.os_name));
  } else if (filters.server_filter === 'client') {
    filtered = filtered.filter((comp) => comp.os_name && !isServerOs(comp.os_name));
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

  const handleTableChange: TableProps<ComputerListItem>['onChange'] = (pagination, _, sorter) => {
    const sorterResult = sorter as Sorter;
    setFilters({
      ...filters,
      page: pagination.current || 1,
      limit: pagination.pageSize || ITEMS_PER_PAGE,
      sort_by: (sorterResult.field as string) || 'hostname',
      sort_order: sorterResult.order === 'descend' ? 'desc' : 'asc',
    });
  };

  const handleFilterChange = (key: keyof Filters, value: string | undefined) => {
    const finalValue = value === '' ? undefined : value;
    setFilters({
      ...filters,
      [key]: finalValue,
      page: 1,
      server_filter: key === 'os_name' && finalValue && isServerOs(finalValue) ? 'server' : undefined,
    });
  };

  const clearAllFilters = () => {
    setFilters({
      hostname: undefined,
      os_name: undefined,
      check_status: undefined,
      sort_by: 'hostname',
      sort_order: 'asc',
      page: 1,
      limit: ITEMS_PER_PAGE,
      server_filter: undefined,
    });
    refetch();
  };

  const columns: TableProps<ComputerListItem>['columns'] = [
    {
      title: 'Hostname',
      dataIndex: 'hostname',
      key: 'hostname',
      sorter: true,
      sortOrder: filters.sort_by === 'hostname' ? (filters.sort_order === 'asc' ? 'ascend' : 'descend') : undefined,
      render: (text: string, record: ComputerListItem) => (
        <Link to={`/computer/${record.id}`} className={styles.link}>
          {text}
        </Link>
      ),
    },
    {
      title: 'IP Address',
      dataIndex: 'ip_addresses',
      key: 'ip_addresses',
      sorter: true,
      sortOrder: filters.sort_by === 'ip_addresses' ? (filters.sort_order === 'asc' ? 'ascend' : 'descend') : undefined,
      render: (ip_addresses: ComputerListItem['ip_addresses']) => ip_addresses?.map(ip => ip.address).join(', ') || '-',
    },
    {
      title: 'OS Version',
      dataIndex: 'os_name',
      key: 'os_name',
      sorter: true,
      sortOrder: filters.sort_by === 'os_name' ? (filters.sort_order === 'asc' ? 'ascend' : 'descend') : undefined,
      render: (text: string) => text ?? '-',
    },
    {
      title: 'Check Status',
      dataIndex: 'check_status',
      key: 'check_status',
      sorter: true,
      sortOrder: filters.sort_by === 'check_status' ? (filters.sort_order === 'asc' ? 'ascend' : 'descend') : undefined,
      render: (text: string) => text ?? '-',
    },
  ];

  return (
    <div className={styles.container}>
      {isComputersLoading || isStatsLoading ? (
        <Skeleton active paragraph={{ rows: 10 }} />
      ) : computersError || statsError ? (
        <div className={styles.error}>Ошибка: {(computersError || statsError)?.message}</div>
      ) : (
        <>
          <h2 className={styles.title}>
            Список компьютеров ({filteredComputers.total || 0})
            <Button type="primary" onClick={handleExportCSV} style={{ float: 'right', marginLeft: 8 }}>
              Экспорт в CSV
            </Button>
          </h2>
          <div className={styles.filters}>
            <Input
              ref={inputRef}
              placeholder="Фильтр по Hostname (поиск по началу)"
              defaultValue={filters.hostname}
              onChange={(e) => {
                debouncedSetHostname(e.target.value);
              }}
              className={styles.filterInput}
              allowClear
            />
            <Select
              value={filters.os_name || ''}
              onChange={(value) => handleFilterChange('os_name', value)}
              className={styles.filterSelect}
              placeholder="Выберите ОС"
              loading={isStatsLoading}
              showSearch
              optionFilterProp="children"
            >
              <Select.Option value="">Все ОС</Select.Option>
              {[...new Set([...(statsData?.os_stats.client_os.map((item) => item.category) || []), ...(statsData?.os_stats.server_os.map((item) => item.category) || [])])].map(
                (os: string) => (
                  <Select.Option key={os} value={os}>
                    {os}
                  </Select.Option>
                )
              )}
            </Select>
            <Select
              value={filters.check_status || ''}
              onChange={(value) => handleFilterChange('check_status', value)}
              className={styles.filterSelect}
              placeholder="Все проверки"
            >
              <Select.Option value="">Все проверки</Select.Option>
              <Select.Option value="success">Success</Select.Option>
              <Select.Option value="failed">Failed</Select.Option>
              <Select.Option value="unreachable">Unreachable</Select.Option>
            </Select>
            <Button onClick={clearAllFilters} style={{ marginLeft: 8 }}>
              Очистить все фильтры
            </Button>
          </div>
          <Table
            columns={columns}
            dataSource={filteredComputers.data}
            rowKey="id"
            pagination={{
              current: filters.page,
              pageSize: filters.limit,
              total: filteredComputers.total || 0,
              showSizeChanger: false,
              showQuickJumper: false,
            }}
            onChange={handleTableChange}
            locale={{ emptyText: 'Нет данных для отображения' }}
            size="small"
            showSorterTooltip={false}
          />
        </>
      )}
    </div>
  );
};

export default ComputerListComponent;