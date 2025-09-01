import { useStatistics, useComputers } from '../hooks/useApiQueries';
import { useLocation, useNavigate} from 'react-router-dom';
import { useMemo, useEffect } from 'react';
import { Modal, Table, notification, Empty, Button } from 'antd';
import CombinedStats from './CombinedStats';
import LowDiskSpace from './LowDiskSpace';
import SubnetStats from './SubnetStats';
import DashboardMenu from './DashboardMenu';
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js';
import { AxiosError } from 'axios';
import { ComputerList, ComputerListItem } from '../types/schemas';
import { useComputerFilters, isServerOs } from '../hooks/useComputerFilters';
import { ITEMS_PER_PAGE } from '../config';
import { startHostScan } from '../api/api'; 
import { useScanEvents } from '../hooks/useScanEvents'; // Імпортуємо хук для SSE

ChartJS.register(ArcElement, Tooltip, Legend);

// Компонент для відображення дашборду зі статистикою
const Dashboard: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const params = new URLSearchParams(location.search);
  const activeTab = params.get('tab') || 'summary';
  const events = useScanEvents(); <pre>{JSON.stringify(events, null, 2)}</pre>

  // Використання хука useComputerFilters для уніфікованих фільтрів
  const { filters, handleFilterChange, handleTableChange } = useComputerFilters([]);

// Оновлення фільтрів при кліку на ОС
  const handleOsClick = (os: string) => {
    handleFilterChange('os_name', os === 'Unknown' || os === 'Other Servers' ? undefined : os);
    handleFilterChange('server_filter', os === 'Other Servers' ? 'server' : undefined);
    handleFilterChange('ip_range', undefined);
    handleFilterChange('page', 1);
    handleFilterChange('limit', ITEMS_PER_PAGE);
  };

// Оновлення фільтрів при кліку на підмережу
  const handleSubnetClick = (subnet: string) => {
    const ipRange = subnet === 'Невідомо' ? 'none' : subnet; // Використовуємо subnet як є
    console.log('Applying ip_range filter:', ipRange); // Дебаг
    handleFilterChange('ip_range', ipRange);
    handleFilterChange('os_name', undefined);
    handleFilterChange('server_filter', undefined);
    handleFilterChange('page', 1);
    handleFilterChange('limit', ITEMS_PER_PAGE);
  };

  // Запит для отримання статистики
  const { data, error: statsError, isLoading } = useStatistics([
    'total_computers',
    'os_distribution',
    'low_disk_space_with_volumes',
    'last_scan_time',
    'status_stats',
  ]);

  // Запит для отримання списку комп’ютерів
  const { data: computersData, isLoading: isComputersLoading, error: computersError } = useComputers({
    ...filters,
    hostname: undefined, // Вимикаємо серверну фільтрацію по hostname
    show_disabled: false,
    sort_by: 'hostname',
    sort_order: 'asc',
    server_filter: filters.os_name && isServerOs(filters.os_name) ? 'server' : filters.server_filter,
  });

  // Трансформація computersData.data до типу ComputerListItem[]
  const transformedComputers: ComputerListItem[] = useMemo(() => {
    return (computersData?.data || []).map((item) => ({
      ...item,
      last_updated: item.last_updated ?? '', // Приводимо last_updated до string
    }));
  }, [computersData]);

  // Обробка помилок
  useEffect(() => {
    if (statsError) {
      console.error('Помилка статистики:', statsError);
      const errorMessage = statsError instanceof AxiosError && statsError.response?.data
        ? JSON.stringify(statsError.response.data.detail || statsError.message)
        : statsError.message;
      notification.error({
        message: 'Помилка завантаження статистики',
        description: `Не вдалося завантажити статистику: ${errorMessage}`,
      });
    }
    if (computersError) {
      console.error('Помилка комп’ютерів:', computersError);
      const errorMessage = computersError instanceof AxiosError && computersError.response?.data
        ? JSON.stringify(computersError.response.data.detail || computersError.message)
        : computersError.message;
      notification.error({
        message: 'Помилка завантаження даних комп’ютерів',
        description: `Не вдалося завантажити дані комп’ютерів: ${errorMessage}`,
      });
    }
  }, [statsError, computersError]);

  // Оновлення відфільтрованих комп’ютерів
  useEffect(() => {
    if (computersData?.data && (filters.os_name || filters.ip_range)) {
      console.log('Фільтровані комп’ютери:', computersData.data.slice(0, 5));
    }
  }, [computersData, filters.os_name, filters.ip_range]);

  // Функція для запуску першого сканування
  const handleStartScan = async () => {
    try {
      const response = await startHostScan(''); // Порожній hostname для сканування всіх хостів
      notification.success({
        message: 'Сканування розпочато',
        description: `Task ID: ${response.task_id}`,
      });
    } catch (error) {
      notification.error({
        message: 'Помилка сканування',
        description: (error as Error).message,
      });
    }
  };

  // Компонент для порожнього стану
  const renderEmptyState = () => (
    <Empty
      description="Дані відсутні. Запустіть перше сканування, щоб отримати статистику."
      image={Empty.PRESENTED_IMAGE_SIMPLE}
    >
      <Button type="primary" onClick={handleStartScan}>
        Запустити сканування
      </Button>
    </Empty>
  );

  if (isLoading) return <div>Завантаження...</div>;
  if (statsError) return <div style={{ color: 'red' }}>Помилка: {statsError.message}</div>;
  if (!data || data.total_computers === 0) return renderEmptyState(); // Показуємо порожній стан

  // Зміна вкладки
  const handleTabChange = (tab: string) => {
    navigate(`?tab=${tab}`, { replace: true }); // Додаємо replace для уникнення дублювання історії
  };

  // Колонки для таблиці комп’ютерів у модальному вікні
  const computerColumns = [
    { title: 'Ім’я хоста', dataIndex: 'hostname', key: 'hostname' },
    {
      title: 'IP-адреса',
      dataIndex: 'ip_addresses',
      key: 'ip',
      render: (ip_addresses: ComputerList['ip_addresses']) => ip_addresses?.map((ip) => ip.address).join(', ') || '-',
    },
    { title: 'ОС', dataIndex: 'os_version', key: 'os_version' },
    {
      title: 'Статус',
      dataIndex: 'check_status',
      key: 'check_status',
      render: (status: string) => {
        const statusTranslations: Record<string, string> = {
          success: 'Успішно',
          partially_successful: 'Частково успішно',
          failed: 'Невдало',
          unreachable: 'Недоступно',
          disabled: 'Відключено',
          is_deleted: 'Видалено',
        };
        return statusTranslations[status] || status || '-';
      },
    },
  ];

  return (
    <div style={{ padding: 12 }}>
      <h1 style={{ marginBottom: 0, marginTop: 0 }}>Статистика</h1>
      <DashboardMenu activeTab={activeTab} onTabChange={handleTabChange} />

      {activeTab === 'summary' && (
        <CombinedStats
          totalComputers={data.total_computers}
          lastScanTime={data.scan_stats?.last_scan_time}
          clientOsData={data.os_stats?.client_os || []}
          serverOsData={data.os_stats?.server_os || []}
          statusStats={data.scan_stats?.status_stats || []}
          lowDiskSpaceCount={data.disk_stats?.low_disk_space?.length || 0}
          onOsClick={handleOsClick}
          onStatusClick={(status: string) =>
            navigate(`/computers?check_status=${encodeURIComponent(status)}`)
          }
        />
      )}
      {activeTab === 'low_disk_space' && (
        <LowDiskSpace
          lowDiskSpace={data.disk_stats?.low_disk_space || []}
          emptyComponent={renderEmptyState()} // Передаємо порожній стан
        />
      )}
      {activeTab === 'subnets' && (
        <SubnetStats
          onSubnetClick={handleSubnetClick}
          emptyComponent={renderEmptyState()} // Передаємо порожній стан
        />
      )}

      <Modal
        title={filters.os_name || filters.ip_range || 'Не вибрано'}
        open={!!(filters.os_name || filters.ip_range)}
        onCancel={() => {
          handleFilterChange('os_name', undefined);
          handleFilterChange('ip_range', undefined);
          handleFilterChange('server_filter', undefined);
        }}
        footer={null}
        width={600}
      >
        {isComputersLoading ? (
          <div>Завантаження...</div>
        ) : computersError ? (
          <div style={{ color: 'red' }}>Помилка: {computersError.message}</div>
        ) : (
          <Table
            columns={computerColumns}
            dataSource={transformedComputers}
            rowKey="id"
            size="small"
            pagination={{
              current: filters.page,
              pageSize: filters.limit,
              total: computersData?.total || 0,
              onChange: (page, pageSize) =>
                handleTableChange(
                  { current: page, pageSize },
                  {},
                  {},
                  { currentDataSource: transformedComputers, action: 'paginate' }
                ),
            }}
            locale={{ emptyText: renderEmptyState() }} // Використовуємо кастомний порожній стан
          />
        )}
      </Modal>
    </div>
  );
};

export default Dashboard;