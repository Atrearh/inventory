// src/components/Dashboard.tsx
import { useStatistics, useComputers } from '../hooks/useApiQueries';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { Modal, Table, notification } from 'antd';
import CombinedStats from './CombinedStats';
import LowDiskSpace from './LowDiskSpace';
import SubnetStats from './SubnetStats';
import DashboardMenu from './DashboardMenu';
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js';
import { AxiosError } from 'axios';
import { useAuth } from '../context/AuthContext';
import { ComputerList, ComputersResponse, DashboardStats } from '../types/schemas';

ChartJS.register(ArcElement, Tooltip, Legend);

// Компонент для відображення дашборду зі статистикою
const Dashboard: React.FC = () => {
  const { isAuthenticated } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const params = new URLSearchParams(location.search);
  const activeTab = params.get('tab') || 'summary';

  const [selectedOs, setSelectedOs] = useState<string | null>(null);
  const [selectedSubnet, setSelectedSubnet] = useState<string | null>(null);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [filters, setFilters] = useState({ page: 1, limit: 10 });
  const [filteredComputers, setFilteredComputers] = useState<ComputerList[]>([]);

  // Запит для отримання статистики
  const { data, error: statsError, isLoading, refetch: refetchStats } = useStatistics([
    'total_computers',
    'os_distribution',
    'low_disk_space_with_volumes',
    'last_scan_time',
    'status_stats',
  ]);

  // Запит для отримання списку комп’ютерів
const { data: computersData, isLoading: isComputersLoading, error: computersError, refetch: refetchComputers } = useComputers({
    page: filters.page,
    limit: filters.limit,
    hostname: undefined,
    os_name: selectedOs && selectedOs !== 'Unknown' && selectedOs !== 'Other Servers' ? selectedOs : undefined,
    check_status: undefined,
    show_disabled: false,
    sort_by: 'hostname',
    sort_order: 'asc',
    server_filter: selectedOs === 'Other Servers' ? 'server' : undefined,
    ip_range: selectedSubnet
      ? selectedSubnet === 'Невідомо'
        ? 'none'
        : (() => {
            const match = selectedSubnet.match(/^(\d+\.\d+)\.(\d+)\.0\/23$/);
            if (!match) {
              console.error('Некоректний формат підмережі:', selectedSubnet);
              return undefined;
            }
            const baseIp = match[1];
            const thirdOctet = parseInt(match[2], 10);
            const ipRange = `${baseIp}.[${thirdOctet}-${thirdOctet + 1}]`;
            console.log('Сформований ip_range:', ipRange);
            return ipRange;
          })()
      : undefined,
  });

  // Обробка помилок та оновлення фільтрованих комп’ютерів
  useEffect(() => {
    if (statsError) {
      console.error('Помилка статистики:', statsError);
      if (statsError instanceof AxiosError && statsError.response?.data) {
        console.error('Деталі помилки сервера:', JSON.stringify(statsError.response.data, null, 2));
        notification.error({
          message: 'Помилка завантаження статистики',
          description: `Не вдалося завантажити статистику: ${JSON.stringify(statsError.response.data.detail || statsError.message)}`,
        });
      } else {
        notification.error({
          message: 'Помилка завантаження статистики',
          description: `Не вдалося завантажити статистику: ${statsError.message}`,
        });
      }
    }
    if (computersError) {
      console.error('Помилка комп’ютерів:', computersError);
      if (computersError instanceof AxiosError && computersError.response?.data) {
        console.error('Деталі помилки сервера:', JSON.stringify(computersError.response.data, null, 2));
        notification.error({
          message: 'Помилка завантаження даних комп’ютерів',
          description: `Не вдалося завантажити дані комп’ютерів: ${JSON.stringify(computersError.response.data.detail || computersError.message)}`,
        });
      } else {
        notification.error({
          message: 'Помилка завантаження даних комп’ютерів',
          description: `Не вдалося завантажити дані комп’ютерів: ${computersError.message}`,
        });
      }
    }
    if (computersData?.data && (selectedOs || selectedSubnet)) {
      console.log('Фільтровані комп’ютери:', computersData.data.slice(0, 5));
      setFilteredComputers(computersData.data);
      setIsModalVisible(true);
    } else {
      setFilteredComputers([]);
    }
  }, [statsError, computersError, computersData, selectedOs, selectedSubnet]);

  // Оновлення даних комп’ютерів при зміні фільтрів
  useEffect(() => {
    if (selectedOs || selectedSubnet) {
      console.log('Оновлення комп’ютерів для:', { selectedOs, selectedSubnet });
      refetchComputers();
    }
  }, [selectedOs, selectedSubnet, refetchComputers]);

  if (isLoading) return <div>Завантаження...</div>;
  if (statsError) return <div style={{ color: 'red' }}>Помилка: {statsError.message}</div>;
  if (!data) return <div style={{ color: 'red' }}>Дані відсутні</div>;

  // Зміна вкладки
  const handleTabChange = (tab: string) => {
    navigate(`?tab=${tab}`);
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

  // Обробка кліку по ОС
  const handleOsClick = (os: string) => {
    setSelectedOs(os);
    setSelectedSubnet(null);
    setFilters({ page: 1, limit: 10 });
  };

  // Обробка кліку по підмережі
  const handleSubnetClick = (subnet: string) => {
    setSelectedSubnet(subnet);
    setSelectedOs(null);
    setFilters({ page: 1, limit: 10 });
  };

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
          onStatusClick={(status: string) => navigate(`/computers?check_status=${encodeURIComponent(status)}`)}
        />
      )}
      {activeTab === 'low_disk_space' && <LowDiskSpace lowDiskSpace={data.disk_stats?.low_disk_space || []} />}
      {activeTab === 'subnets' && <SubnetStats onSubnetClick={handleSubnetClick} />}

      <Modal
        title={selectedOs ? selectedOs.replace('%', '') : selectedSubnet ? selectedSubnet : 'Не вибрано'}
        open={isModalVisible}
        onCancel={() => {
          setIsModalVisible(false);
          setSelectedOs(null);
          setSelectedSubnet(null);
          setFilteredComputers([]);
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
            dataSource={filteredComputers}
            rowKey="id"
            size="small"
            pagination={{
              current: filters.page,
              pageSize: filters.limit,
              total: computersData?.total || 0,
              onChange: (p, ps) => setFilters({ ...filters, page: p, limit: ps }),
            }}
            locale={{ emptyText: '-' }}
          />
        )}
      </Modal>
    </div>
  );
};

export default Dashboard;