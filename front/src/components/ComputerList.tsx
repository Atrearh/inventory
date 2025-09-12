import { useState, useEffect, useMemo, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { useNavigate, Link } from 'react-router-dom';
import { notification, Skeleton, Button } from 'antd';
import { useExportCSV } from '../hooks/useExportCSV';
import { useComputers, useStatistics } from '../hooks/useApiQueries';
import usePersistentState from '../hooks/usePersistentState';
import { useComputerFilters } from '../hooks/useComputerFilters';
import ComputerFiltersPanel from './ComputerFiltersPanel';
import { AxiosError } from 'axios';
import { useTimezone } from '../context/TimezoneContext';
import { formatDateInUserTimezone } from '../utils/formatDate';
import { getDomains } from '../api/domain.api';
import { ComputerListItem } from '../types/schemas';
import { usePageTitle } from '../context/PageTitleContext';
import ReusableTable from '../components/ReusableTable';
import styles from './ComputerList.module.css';

const defaultColumnWidths = {
  hostname: 200,
  ip_addresses: 150,
  os_name: 150,
  check_status: 100,
  last_full_scan: 100,
};

const ComputerList: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { timezone } = useTimezone();
  const { setPageTitle } = usePageTitle();
  const [cachedComputers, setCachedComputers] = useState<ComputerListItem[]>([]);
  const [columnWidths, setColumnWidths] = usePersistentState('computerListColumnWidths', defaultColumnWidths);

  const { data: domainsData, isLoading: isDomainsLoading } = useQuery({
    queryKey: ['domains'],
    queryFn: getDomains,
  });

  const domainMap = useMemo(() => {
    const map = new Map<number, string>();
    domainsData?.forEach((domain) => map.set(domain.id, domain.name));
    return map;
  }, [domainsData]);

  const { filters, filteredComputers, debouncedSetHostname, handleFilterChange, clearAllFilters, handleTableChange } =
    useComputerFilters(cachedComputers);

  const fetchData = useCallback(
    async (params: any) => {
      const { data, total } = await useComputers({
        ...params,
        hostname: undefined,
        os_name: undefined,
        check_status: undefined,
        sort_by: params.sort_by,
        sort_order: params.sort_order,
        limit: 1000,
      }).queryFn();
      return { data, total };
    },
    []
  );

  const { data: computersData, error: computersError, isLoading: isComputersLoading } = useQuery({
    queryKey: ['computers', filters],
    queryFn: () => fetchData(filters),
  });

  const { data: statsData, error: statsError, isLoading: isStatsLoading } = useStatistics(['os_distribution']);
  const { handleExportCSV } = useExportCSV(filters);

  useEffect(() => {
    if (computersData?.data) {
      const uniqueComputers = Array.from(new Map(computersData.data.map((comp) => [comp.id, comp])).values());
      const transformedComputers = uniqueComputers.slice(0, 1000).map((computer) => ({
        ...computer,
        last_updated: computer.last_updated || '',
        last_check: computer.last_full_scan || '',
      }));
      setCachedComputers(transformedComputers);
      setPageTitle(`${t('computers_list', 'Список комп’ютерів')} (${filteredComputers.total || 0})`);
      if (computersData.total > 1000) {
        notification.warning({
          message: t('data_limit', 'Обмеження даних'),
          description: t('data_limit_description', 'Відображається лише перші 1000 комп’ютерів. Використовуйте фільтри для точного пошуку.'),
        });
      }
    }
  }, [computersData, t, filteredComputers.total, setPageTitle]);

  const getCheckStatusColor = (status: string | null | undefined) => {
    switch (status) {
      case 'success': return '#52c41a';
      case 'failed':
      case 'unreachable': return '#ff4d4f';
      case 'partially_successful': return '#faad14';
      case 'disabled':
      case 'is_deleted': return '#8c8c8c';
      default: return '#000';
    }
  };

  const getLastScanColor = (scanDate: string | null) => {
    if (!scanDate) return '#000';
    const date = new Date(scanDate);
    const now = new Date();
    const diffDays = (now.getTime() - date.getTime()) / (1000 * 3600 * 24);
    if (diffDays <= 7) return '#52c41a';
    if (diffDays <= 14) return '#faad14';
    return '#ff4d4f';
  };

  const columns = useMemo(
    () => [
      {
        title: t('hostname', 'Ім’я хоста'),
        dataIndex: 'hostname',
        key: 'hostname',
        sorter: true,
        width: columnWidths.hostname,
        sortOrder: filters.sort_by === 'hostname' ? (filters.sort_order === 'asc' ? 'ascend' : 'descend') : undefined,
        render: (_: string, record: ComputerListItem) => (
          <Link to={`/computer/${record.id}`} className={styles.link}>{record.hostname}</Link>
        ),
      },
      {
        title: t('ip_addresses', 'IP-адреси'),
        dataIndex: 'ip_addresses',
        key: 'ip_addresses',
        sorter: true,
        width: columnWidths.ip_addresses,
        sortOrder: filters.sort_by === 'ip_addresses' ? (filters.sort_order === 'asc' ? 'ascend' : 'descend') : undefined,
        render: (_: any, record: ComputerListItem) =>
          record.ip_addresses?.map((ip) => ip.address).join(', ') || '-',
      },
      {
        title: t('os_name', 'Операційна система'),
        dataIndex: 'os_name',
        key: 'os_name',
        sorter: true,
        width: columnWidths.os_name,
        sortOrder: filters.sort_by === 'os_name' ? (filters.sort_order === 'asc' ? 'ascend' : 'descend') : undefined,
        render: (text: string) => text ?? '-',
      },
      {
        title: t('last_check', 'Остання перевірка'),
        dataIndex: 'last_full_scan',
        key: 'last_full_scan',
        sorter: true,
        width: columnWidths.last_full_scan,
        sortOrder: filters.sort_by === 'last_full_scan' ? (filters.sort_order === 'asc' ? 'ascend' : 'descend') : undefined,
        render: (text: string | null) => (
          <span style={{ color: getLastScanColor(text) }}>
            {text ? formatDateInUserTimezone(text, timezone) : '-'}
          </span>
        ),
      },
      {
        title: t('check_status', 'Статус перевірки'),
        dataIndex: 'check_status',
        key: 'check_status',
        sorter: true,
        width: columnWidths.check_status,
        sortOrder: filters.sort_by === 'check_status' ? (filters.sort_order === 'asc' ? 'ascend' : 'descend') : undefined,
        render: (text: string | null) => {
          const statusMap: Record<string, string> = {
            success: t('status_success', 'Успішно'),
            failed: t('status_failed', 'Невдало'),
            unreachable: t('status_unreachable', 'Недоступно'),
            partially_successful: t('status_partially_successful', 'Частково успішно'),
            disabled: t('status_disabled', 'Відключено'),
            is_deleted: t('status_is_deleted', 'Видалено'),
          };
          return <span style={{ color: getCheckStatusColor(text) }}>{statusMap[text || ''] || text || '-'}</span>;
        },
      },
    ],
    [t, filters.sort_by, filters.sort_order, columnWidths, timezone]
  );

  const handleResize = useCallback(
    (key: keyof typeof columnWidths) => (_: any, { size }: { size: { width: number } }) => {
      setColumnWidths((prev: typeof columnWidths) => ({
        ...prev,
        [key]: size.width,
      }));
    },
    [setColumnWidths]
  );

  const resizableColumns = columns.map((col) => ({
    ...col,
    onHeaderCell: (column: any) => ({
      width: column.width,
      onResize: handleResize(column.key as keyof typeof columnWidths),
    }),
  }));

  if (computersError || statsError) {
    if ((computersError as AxiosError)?.response?.status === 401 || (statsError as AxiosError)?.response?.status === 401) {
      navigate('/login');
    }
  }

  return (
    <div className={styles.container}>
      {isComputersLoading || isStatsLoading || isDomainsLoading ? (
        <Skeleton active paragraph={{ rows: 10 }} />
      ) : (
        <>
          <h2 className={styles.title}>
            {t('computers_list', 'Список комп’ютерів')} ({filteredComputers.total || 0})
            <Button type="primary" onClick={handleExportCSV} className={styles.csvButton}>
              {t('export_csv', 'Експорт у CSV')}
            </Button>
          </h2>
          <ComputerFiltersPanel
            filters={filters}
            statsData={statsData}
            isStatsLoading={isStatsLoading}
            debouncedSetHostname={debouncedSetHostname}
            handleFilterChange={handleFilterChange}
            clearAllFilters={clearAllFilters}
          />
          <ReusableTable<ComputerListItem>
            queryKey={['computers', filters]}
            fetchData={fetchData}
            columns={resizableColumns}
            filters={filters}
            onTableChange={handleTableChange}
          />
        </>
      )}
    </div>
  );
};

export default ComputerList;