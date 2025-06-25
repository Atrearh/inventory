// src/components/ComputerList.tsx
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getComputers, getStatistics} from '../api/api';
import { ComputersResponse, DashboardStats, ComputerList } from '../types/schemas';
import { useState, useEffect } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { notification, Skeleton, Input, Select, Table, Button } from 'antd';
import { useDebounce } from '../hooks/useDebounce';
import { ITEMS_PER_PAGE } from '../config';
import styles from './ComputerList.module.css';
import type { TableProps } from 'antd';
import axios from 'axios';
import { API_URL } from '../config';

interface Filters {
  hostname: string;
  os_name: string | undefined;
  check_status: string;
  sort_by: string; // Изменено на string вместо keyof ComputerList
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
  const [searchParams, setSearchParams] = useSearchParams();
  const [filters, setFilters] = useState<Filters>({
    hostname: searchParams.get('hostname') || '',
    os_name: searchParams.get('os_name') || '',
    check_status: searchParams.get('check_status') || '',
    sort_by: searchParams.get('sort_by') || 'hostname',
    sort_order: (searchParams.get('sort_order') as 'asc' | 'desc') || 'asc',
    page: Number(searchParams.get('page')) || 1,
    limit: Number(searchParams.get('limit')) || ITEMS_PER_PAGE,
  });

  const debouncedHostname = useDebounce(filters.hostname, 800);
  const debouncedOsName = useDebounce(filters.os_name, 800);

   const { data: computersData, error: computersError, isLoading: isComputersLoading, refetch } = useQuery<ComputersResponse, Error>({
    queryKey: ['computers', { ...filters, hostname: debouncedHostname, os_name: debouncedOsName }],
    queryFn: () => {
      const params = { ...filters, hostname: debouncedHostname, os_name: debouncedOsName };
      if (params.os_name && params.os_name.toLowerCase() === 'unknown') {
        params.os_name = 'unknown';
      } else if (params.os_name === 'Other Servers') {
        params.os_name = undefined;
        params.server_filter = 'server';
      }
      return getComputers(params);
    },
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 30 * 60 * 1000,
    gcTime: 60 * 60 * 1000,
  });

  const { data: statsData, error: statsError, isLoading: isStatsLoading } = useQuery<DashboardStats, Error>({
    queryKey: ['statistics'],
    queryFn: () => getStatistics({
      metrics: ['os_names'], // Запрашиваем только os_names для оптимизации
    }),
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 60 * 60 * 1000, // Кэшируем на 1 час
  });

  useEffect(() => {
    const params: Record<string, string> = {
      hostname: filters.hostname,
      check_status: filters.check_status,
      sort_by: filters.sort_by,
      sort_order: filters.sort_order,
      page: String(filters.page),
      limit: String(filters.limit),
    };
    if (filters.os_name) {
      params.os_name = filters.os_name;
  }
  setSearchParams(params);
}, [filters, setSearchParams]);

  useEffect(() => {
    if (
      debouncedHostname.length > 2 ||
      (debouncedOsName && debouncedOsName.length > 2) ||
      debouncedHostname === '' ||
      (debouncedOsName === '' || debouncedOsName === undefined)
    ) {
      setFilters((prev) => ({
        ...prev,
        hostname: debouncedHostname,
        os_name: debouncedOsName,
        page: 1,
      }));
    }
  }, [debouncedHostname, debouncedOsName]);

  const handleExportCSV = async () => {
    try {
      const params = {
        hostname: filters.hostname || undefined,
        os_name: filters.os_name || undefined,
        check_status: filters.check_status || undefined,
        sort_by: filters.sort_by,
        sort_order: filters.sort_order,
        server_filter: filters.os_name === 'Other Servers' ? 'server' : undefined,
      };
      const response = await axios.get(`${API_URL}/computers/export/csv`, {
        params,
        responseType: 'blob',
      });

      const currentDate = new Date().toISOString().split('T')[0];
      const filename = `computers_${currentDate}.csv`;

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      notification.success({
        message: 'Успех',
        description: 'Файл CSV успешно скачан',
      });
    } catch (error) {
      notification.error({
        message: 'Ошибка',
        description: 'Не удалось экспортировать данные в CSV',
      });
    }
  };

  const handleTableChange: TableProps<ComputerList>['onChange'] = (pagination, _, sorter) => {
    const sorterResult = sorter as Sorter;
    setFilters({
      ...filters,
      page: pagination.current || 1,
      limit: pagination.pageSize || ITEMS_PER_PAGE,
      sort_by: sorterResult.field || 'hostname',
      sort_order: sorterResult.order === 'descend' ? 'desc' : 'asc',
    });
  };

  const handleFilterChange = (key: keyof Filters, value: string) => {
    setFilters({
      ...filters,
      [key]: value,
      page: 1,
    });
  };

  const clearFilter = (key: keyof Filters) => {
    setFilters((prev) => ({
      ...prev,
      [key]: '',
      page: 1,
    }));
  };

  const clearAllFilters = () => {
    setFilters({
      hostname: '',
      os_name: '',
      check_status: '',
      sort_by: 'hostname',
      sort_order: 'asc',
      page: 1,
      limit: ITEMS_PER_PAGE,
    });
    refetch();
  };

  const columns: TableProps<ComputerList>['columns'] = [
    {
      title: 'Hostname',
      dataIndex: 'hostname',
      key: 'hostname',
      sorter: true,
      sortOrder: filters.sort_by === 'hostname' ? (filters.sort_order === 'asc' ? 'ascend' : 'descend') : undefined,
      render: (text: string, record: ComputerList) => (
        <Link to={`/computer/${record.id}`} className={styles.link}>
          {text}
        </Link>
      ),
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

  if (isComputersLoading || isStatsLoading) {
    return <Skeleton active paragraph={{ rows: 10 }} />;
  }
  if (computersError || statsError) {
    return <div className={styles.error}>Ошибка: {(computersError || statsError)?.message}</div>;
  }

  return (
    <div className={styles.container}>
      <h2 className={styles.title}>
        Список компьютеров ({computersData?.total || 0})
        <Button
          type="primary"
          onClick={handleExportCSV}
          style={{ float: 'right', marginLeft: 8 }}
        >
          Экспорт в CSV
        </Button>
      </h2>
      <div className={styles.filters}>
        <Input
          placeholder="Фильтр по Hostname"
          value={filters.hostname}
          onChange={(e) => handleFilterChange('hostname', e.target.value)}
          className={styles.filterInput}
          allowClear
        />
        <Select
          value={filters.os_name}
          onChange={(value) => handleFilterChange('os_name', value)}
          className={styles.filterSelect}
          placeholder="Выберите ОС"
          loading={isStatsLoading}
        >
          <Select.Option value="">Все ОС</Select.Option>
          <Select.Option value="Unknown">Unknown</Select.Option>
          <Select.Option value="Other Servers">Other Servers</Select.Option>
          {statsData && statsData.os_names && statsData.os_names.map((os: string) => (
            <Select.Option key={os} value={os}>
              {os}
            </Select.Option>
          ))}
        </Select>
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
        <Button onClick={clearAllFilters} style={{ marginLeft: 8 }}>
          Очистить все фильтры
        </Button>
      </div>
      <Table
        columns={columns}
        dataSource={computersData?.data || []}
        rowKey="id"
        pagination={{
          current: filters.page,
          pageSize: filters.limit,
          total: computersData?.total || 0,
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

export default ComputerListComponent;