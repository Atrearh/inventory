// src/components/ComputerList.tsx
import { useQuery } from '@tanstack/react-query';
import { getComputers, getStatistics } from '../api/api';
import { ComputersResponse, DashboardStats, ComputerListItem } from '../types/schemas';
import { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { notification, Skeleton, Input, Select, Table, Button, Checkbox } from 'antd';
import { useExportCSV } from '../hooks/useExportCSV';
import { ITEMS_PER_PAGE } from '../config';
import type { TableProps } from 'antd';
import type { InputRef } from 'antd';
import styles from './ComputerList.module.css';
import { useAuth } from '../context/AuthContext';
import { useComputerFilters, Filters } from '../hooks/useComputerFilters';

// Компонент для відображення списку комп’ютерів
const ComputerListComponent: React.FC = () => {
  const { isAuthenticated } = useAuth();
  const [cachedComputers, setCachedComputers] = useState<ComputerListItem[]>([]);
  const inputRef = useRef<InputRef>(null);

  // Функція для перевірки, чи є ОС серверною
  const isServerOs = (osName: string) => {
    const serverOsPatterns = [/server/i, /hyper-v/i];
    return serverOsPatterns.some((pattern) => pattern.test(osName.toLowerCase()));
  };

  const { filters, filteredComputers, debouncedSetHostname, handleFilterChange, clearAllFilters, handleTableChange } =
    useComputerFilters(cachedComputers);

  // Запит для отримання списку комп’ютерів
  const { data: computersData, error: computersError, isLoading: isComputersLoading, refetch } = useQuery<
    ComputersResponse,
    Error
  >({
    queryKey: ['computers', { os_name: filters.os_name, check_status: filters.check_status, show_disabled: filters.show_disabled, sort_by: filters.sort_by, sort_order: filters.sort_order, server_filter: filters.server_filter }],
    queryFn: () => {
      const params: Partial<Filters> = {
        ...filters,
        hostname: undefined, // Вимикаємо серверну фільтрацію по hostname
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

  // Запит для отримання статистики
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

  // Оновлення кешованих комп’ютерів при зміні даних
  useEffect(() => {
    if (computersData?.data) {
      // Видаляємо дублікати за id
      const uniqueComputers = Array.from(
        new Map(computersData.data.map((comp) => [comp.id, comp])).values()
      );
      const transformedComputers = uniqueComputers.slice(0, 1000).map(computer => ({
        ...computer,
        last_updated: computer.last_updated || '',
      }));
      setCachedComputers(transformedComputers);
      if (computersData.total > 1000) {
        notification.warning({
          message: 'Обмеження даних',
          description: 'Відображається лише перші 1000 комп’ютерів. Використовуйте фільтри для точного пошуку.',
        });
      }
    }
  }, [computersData]);

  // Колонки таблиці
  const columns: TableProps<ComputerListItem>['columns'] = [
    {
      title: 'Ім’я хоста',
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
      title: 'IP-адреса',
      dataIndex: 'ip_addresses',
      key: 'ip_addresses',
      sorter: true,
      sortOrder: filters.sort_by === 'ip_addresses' ? (filters.sort_order === 'asc' ? 'ascend' : 'descend') : undefined,
      render: (ip_addresses: ComputerListItem['ip_addresses']) => ip_addresses?.map(ip => ip.address).join(', ') || '-',
    },
    {
      title: 'Версія ОС',
      dataIndex: 'os_name',
      key: 'os_name',
      sorter: true,
      sortOrder: filters.sort_by === 'os_name' ? (filters.sort_order === 'asc' ? 'ascend' : 'descend') : undefined,
      render: (text: string) => text ?? '-',
    },
    {
      title: 'Статус перевірки',
      dataIndex: 'check_status',
      key: 'check_status',
      sorter: true,
      sortOrder: filters.sort_by === 'check_status' ? (filters.sort_order === 'asc' ? 'ascend' : 'descend') : undefined,
      render: (text: string) => {
        const statusMap: Record<string, string> = {
          success: 'Успішно',
          failed: 'Невдало',
          unreachable: 'Недоступно',
          partially_successful: 'Частково успішно',
          disabled: 'Відключено',
          is_deleted: 'Видалено',
        };
        return statusMap[text] || text || '-';
      },
    },
  ];

  return (
    <div className={styles.container}>
      {isComputersLoading || isStatsLoading ? (
        <Skeleton active paragraph={{ rows: 10 }} />
      ) : computersError || statsError ? (
        <div className={styles.error}>Помилка: {(computersError || statsError)?.message}</div>
      ) : (
        <>
          <h2 className={styles.title}>
            Список комп’ютерів ({filteredComputers.total || 0})
            <Button type="primary" onClick={handleExportCSV} style={{ float: 'right', marginLeft: 8 }}>
              Експорт у CSV
            </Button>
          </h2>
          <div className={styles.filters}>
            <Input
              ref={inputRef}
              placeholder="Фільтр за ім’ям хоста (пошук за початком)"
              defaultValue={filters.hostname}
              onChange={(e) => debouncedSetHostname(e.target.value)}
              className={styles.filterInput}
              allowClear
            />
            <Select
              value={filters.os_name || ''}
              onChange={(value) => handleFilterChange('os_name', value)}
              className={styles.filterSelect}
              placeholder="Оберіть ОС"
              loading={isStatsLoading}
              showSearch
              optionFilterProp="children"
            >
              <Select.Option value="">Усі ОС</Select.Option>
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
              placeholder="Усі статуси"
            >
              <Select.Option value="">Усі статуси</Select.Option>
              <Select.Option value="success">Успішно</Select.Option>
              <Select.Option value="failed">Невдало</Select.Option>
              <Select.Option value="unreachable">Недоступно</Select.Option>
              <Select.Option value="partially_successful">Частково успішно</Select.Option>
              {filters.show_disabled && <Select.Option value="disabled">Відключено</Select.Option>}
              {filters.show_disabled && <Select.Option value="is_deleted">Видалено</Select.Option>}
            </Select>
            <Checkbox
              checked={filters.show_disabled}
              onChange={(e) => handleFilterChange('show_disabled', e.target.checked)}
              style={{ marginLeft: 8 }}
            >
              Показувати відключені та видалені
            </Checkbox>
            <Button onClick={clearAllFilters} style={{ marginLeft: 8 }}>
              Очистити всі фільтри
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
            locale={{ emptyText: 'Немає даних для відображення' }}
            size="small"
            showSorterTooltip={false}
          />
        </>
      )}
    </div>
  );
};
export default ComputerListComponent;