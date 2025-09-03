import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { useState, useEffect, useMemo, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { notification, Skeleton, Table, Button } from 'antd';
import { debounce } from 'lodash';
import { useExportCSV } from '../hooks/useExportCSV';
import { useComputers, useStatistics } from '../hooks/useApiQueries';
import { Resizable } from 'react-resizable';
import type { TableProps } from 'antd';
import styles from './ComputerList.module.css';
import { useComputerFilters} from '../hooks/useComputerFilters';
import ComputerFiltersPanel from './ComputerFiltersPanel';
import { handleApiError } from '../utils/apiErrorHandler';
import { AxiosError } from 'axios';
import { useTimezone } from '../context/TimezoneContext';
import { formatDateInUserTimezone } from '../utils/formatDate';
import 'react-resizable/css/styles.css';
import { getDomains } from '../api/domain.api';
import { ComputerListItem } from '../types/schemas';

// Компонент для зміни розміру колонок
const ResizableTitle = (props: any) => {
  const { onResize, width, ...restProps } = props;

  if (!width) {
    return <th {...restProps} />;
  }

  return (
    <Resizable
      width={width}
      height={0}
      handle={
        <span
          className="react-resizable-handle"
          onClick={(e) => {
            e.stopPropagation();
          }}
        />
      }
      onResize={onResize}
      draggableOpts={{ enableUserSelectHack: false }}
    >
      <th {...restProps} />
    </Resizable>
  );
};

const ComputerListComponent: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { timezone } = useTimezone();
  const [cachedComputers, setCachedComputers] = useState<ComputerListItem[]>([]);
  const [columnWidths, setColumnWidths] = useState({
    hostname: 200,
    domain_id: 100,
    ip_addresses: 150,
    os_name: 150,
    check_status: 100,
    last_full_scan: 100,
  });

  const { data: domainsData, isLoading: isDomainsLoading } = useQuery({
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

  const { filters, filteredComputers, debouncedSetHostname, handleFilterChange, clearAllFilters, handleTableChange } =
    useComputerFilters(cachedComputers);
  const { data: computersData, error: computersError, isLoading: isComputersLoading } = useComputers({
    ...filters,
    hostname: undefined, 
    os_name: undefined, 
    check_status: undefined, 
    sort_by: undefined, 
    sort_order: undefined, 
    limit: 1000,
  });

  const { data: statsData, error: statsError, isLoading: isStatsLoading } = useStatistics(['os_distribution']);

  const { handleExportCSV } = useExportCSV(filters);

  useEffect(() => {
    if (computersData?.data) {
      const uniqueComputers = Array.from(
        new Map(computersData.data.map((comp) => [comp.id, comp])).values()
      );
      const transformedComputers = uniqueComputers.slice(0, 1000).map((computer) => ({
        ...computer,
        last_updated: computer.last_updated || '',
        last_check: computer.last_full_scan
|| '',
      }));
      setCachedComputers(transformedComputers);
      if (computersData.total > 1000) {
        notification.warning({
          message: t('data_limit', 'Обмеження даних'),
          description: t('data_limit_description', 'Відображається лише перші 1000 комп’ютерів. Використовуйте фільтри для точного пошуку.'),
        });
      }
    }
  }, [computersData, t]);

  const getCheckStatusColor = (status: string | null | undefined) => {
    switch (status) {
      case 'success':
        return '#52c41a'; // Зелений
      case 'failed':
      case 'unreachable':
        return '#ff4d4f'; // Червоний
      case 'partially_successful':
        return '#faad14'; // Жовтий
      case 'disabled':
      case 'is_deleted':
        return '#8c8c8c'; // Сірий
      default:
        return '#000'; // Чорний
    }
  };

  const columns = useMemo<TableProps<ComputerListItem>['columns']>(
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
        render: (text: string | null) => (text ? formatDateInUserTimezone(text, timezone) : '-'),
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
  ) as NonNullable<TableProps<ComputerListItem>['columns']>;

  const handleResize = useCallback(
      (key: keyof typeof columnWidths) =>
        debounce((_: any, { size }: { size: { width: number } }) => {
          setColumnWidths((prev) => ({
            ...prev,
            [key]: size.width,
          }));
        }, 100),
      []
    );

  const resizableColumns = columns.map((col) => ({
    ...col,
    onHeaderCell: (column: any) => ({
      width: column.width,
      onResize: handleResize(column.key as keyof typeof columnWidths),
    }),
  }));

  if (computersError || statsError) {
    const error = handleApiError((computersError || statsError) as AxiosError, t('error', 'Помилка'));
    if ((computersError as AxiosError)?.response?.status === 401 || (statsError as AxiosError)?.response?.status === 401) {
      notification.error({ message: t('session_expired', 'Ваша сесія закінчилася. Будь ласка, увійдіть знову.') });
      navigate('/login');
    } else {
      notification.error({ message: error.message });
    }
  }

  return (
    <div className={styles.container}>
      {isComputersLoading || isStatsLoading ? (
        <Skeleton active paragraph={{ rows: 10 }} />
      ) : computersError || statsError ? (
        <div className={styles.error}>
          {t('error', 'Помилка')}: {(computersError || statsError)?.message}
        </div>
      ) : (
        <>
          <h2 className={styles.title}>
            {t('computers_list', 'Список комп’ютерів')} ({filteredComputers.total || 0})
            <Button type="primary" onClick={handleExportCSV} style={{ float: 'right', marginLeft: 8 }}>
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
          <Table
            components={{
              header: {
                cell: ResizableTitle,
              },
            }}
            columns={resizableColumns}
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
            locale={{ emptyText: t('no_data', 'Немає даних для відображення') }}
            size="small"
            showSorterTooltip={false}
          />
        </>
      )}
    </div>
  );
};

export default ComputerListComponent;