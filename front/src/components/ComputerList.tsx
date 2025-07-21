// src/components/ComputerList.tsx
import { useQuery } from '@tanstack/react-query';
import { getComputers, getStatistics } from '../api/api';
import { ComputersResponse, DashboardStats, ComputerListItem } from '../types/schemas';
import { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { notification, Skeleton, Input, Select, Table, Button } from 'antd';
import { useExportCSV } from '../hooks/useExportCSV';
import { ITEMS_PER_PAGE } from '../config';
import type { TableProps } from 'antd';
import type { InputRef } from 'antd';
import styles from './ComputerList.module.css';
import { useAuth } from '../context/AuthContext';
import { useComputerFilters, Filters } from '../hooks/useComputerFilters'; // Импортируем Filters

const ComputerListComponent: React.FC = () => {
  const { isAuthenticated } = useAuth();
  const [cachedComputers, setCachedComputers] = useState<ComputerListItem[]>([]);
  const inputRef = useRef<InputRef>(null);

  const isServerOs = (osName: string) => {
    const serverOsPatterns = [/server/i, /hyper-v/i];
    return serverOsPatterns.some((pattern) => pattern.test(osName.toLowerCase()));
  };

  // Перемещаем useComputerFilters выше useComputers
  const { filters, filteredComputers, debouncedSetHostname, handleFilterChange, clearAllFilters, handleTableChange } =
    useComputerFilters(cachedComputers);

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
              onChange={(e) => debouncedSetHostname(e.target.value)}
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