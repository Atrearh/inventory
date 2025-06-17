// src/components/ComputerList.tsx
import { useQuery } from '@tanstack/react-query';
import { getComputers } from '../api/api';
import { Computer } from '../types/schemas';
import { useState, useEffect } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { notification, Skeleton, Input, Select, Table } from 'antd';
import { useDebounce } from '../hooks/useDebounce';
import { ITEMS_PER_PAGE } from '../config';
import styles from './ComputerList.module.css';
import type { TableProps } from 'antd';

interface Filters {
  hostname: string;
  os_version: string;
  check_status: string;
  sort_by: keyof Computer;
  sort_order: 'asc' | 'desc';
  page: number;
  limit: number;
}

interface ComputersResponse {
  data: Computer[];
  total: number;
}

interface Sorter {
  field?: string;
  order?: 'ascend' | 'descend';
}

const ComputerList: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [filters, setFilters] = useState<Filters>({
    hostname: searchParams.get('hostname') || '',
    os_version: searchParams.get('os_version') || '',
    check_status: searchParams.get('check_status') || '',
    sort_by: (searchParams.get('sort_by') as keyof Computer) || 'hostname',
    sort_order: (searchParams.get('sort_order') as 'asc' | 'desc') || 'asc',
    page: Number(searchParams.get('page')) || 1,
    limit: Number(searchParams.get('limit')) || ITEMS_PER_PAGE,
  });

  // Debounce для полей ввода
  const debouncedHostname = useDebounce(filters.hostname, 500);
  const debouncedOsVersion = useDebounce(filters.os_version, 500);

  // Синхронизация фильтров с URL
  useEffect(() => {
    setSearchParams({
      hostname: filters.hostname,
      os_version: filters.os_version,
      check_status: filters.check_status,
      sort_by: filters.sort_by,
      sort_order: filters.sort_order,
      page: String(filters.page),
      limit: String(filters.limit),
    });
  }, [filters, setSearchParams]);

  // Обновление фильтров после debounce
  useEffect(() => {
    setFilters((prev) => ({
      ...prev,
      hostname: debouncedHostname,
      os_version: debouncedOsVersion,
      page: 1, // Сбрасываем страницу при изменении фильтров
    }));
  }, [debouncedHostname, debouncedOsVersion]);

  const { data, error, isLoading } = useQuery<ComputersResponse, Error>({
    queryKey: ['computers', filters],
    queryFn: () => getComputers(filters),
    refetchOnWindowFocus: false, 
    refetchOnReconnect: false,
    staleTime: 0,
  });

  // Обработка сортировки и пагинации через onChange
  const handleTableChange: TableProps<Computer>['onChange'] = (pagination, _, sorter) => {
    const sorterResult = sorter as Sorter;
    setFilters({
      ...filters,
      page: pagination.current || 1,
      limit: pagination.pageSize || ITEMS_PER_PAGE,
      sort_by: sorterResult.field ? (sorterResult.field as keyof Computer) : 'hostname',
      sort_order: sorterResult.order === 'descend' ? 'desc' : 'asc',
    });
  };

  // Обработка изменения фильтров
  const handleFilterChange = (key: keyof Filters, value: string) => {
    setFilters({
      ...filters,
      [key]: value,
      page: 1,
    });
  };

  const columns: TableProps<Computer>['columns'] = [
    {
      title: 'Hostname',
      dataIndex: 'hostname',
      key: 'hostname',
      sorter: true,
      sortOrder: filters.sort_by === 'hostname' ? (filters.sort_order === 'asc' ? 'ascend' : 'descend') : null,
      render: (text: string, record: Computer) => (
        <Link to={`/computer/${record.id}`} className={styles.link}>
          {text}
        </Link>
      ),
    },
    {
      title: 'OS Version',
      dataIndex: 'os_version',
      key: 'os_version',
      sorter: true,
      sortOrder: filters.sort_by === 'os_version' ? (filters.sort_order === 'asc' ? 'ascend' : 'descend') : null,
      render: (text: string) => text ?? '-',
    },
    {
      title: 'Check Status',
      dataIndex: 'check_status',
      key: 'check_status',
      sorter: true,
      sortOrder: filters.sort_by === 'check_status' ? (filters.sort_order === 'asc' ? 'ascend' : 'descend') : null,
      render: (text: string) => text ?? '-',
    },
  ];

  if (isLoading) {
    return <Skeleton active paragraph={{ rows: 10 }} />;
  }
  if (error) {
    return <div className={styles.error}>Ошибка: {error.message}</div>;
  }

  return (
    <div className={styles.container}>
      <h2 className={styles.title}>Список компьютеров</h2>
      <div className={styles.filters}>
        <Input
          placeholder="Фильтр по Hostname"
          value={filters.hostname}
          onChange={(e) => handleFilterChange('hostname', e.target.value)}
          className={styles.filterInput}
        />
        <Input
          placeholder="Фильтр по OS Version"
          value={filters.os_version}
          onChange={(e) => handleFilterChange('os_version', e.target.value)}
          className={styles.filterInput}
        />
        <Select
          value={filters.check_status}
          onChange={(value) => handleFilterChange('check_status', value)}
          className={styles.filterSelect}
          placeholder="Все проверки"
        >
          <Select.Option value="">Все проверки</Select.Option>
          <Select.Option value="success">Success</Select.Option>
          <Select.Option value="failed">Failed</Select.Option>
          <Select.Option value="unreachable">Unreachable</Select.Option>
        </Select>
      </div>
      <Table
        columns={columns}
        dataSource={data?.data || []}
        rowKey="id"
        pagination={{
          current: filters.page,
          pageSize: filters.limit,
          total: data?.total || 0,
          showSizeChanger: false,
          showQuickJumper: false,
        }}
        onChange={handleTableChange}
        locale={{ emptyText: 'Нет данных для отображения' }}
        size="small"
      />
    </div>
  );
};

export default ComputerList;