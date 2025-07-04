// src/components/Dashboard.tsx
import { useQuery } from '@tanstack/react-query';
import { getComputers, getStatistics } from '../api/api';
import { ComputerList, ComputersResponse, DashboardStats } from '../types/schemas';
import { Link } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { Modal } from 'antd';
import StatsSummary from './StatsSummary';
import OsDistribution from './OsDistribution';
import LowDiskSpace from './LowDiskSpace';
import StatusStats from './StatusStats';
import DashboardMenu from './DashboardMenu';
import { Table } from 'antd';
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js';

ChartJS.register(ArcElement, Tooltip, Legend);

const Dashboard: React.FC = () => {
  const [selectedOs, setSelectedOs] = useState<string | null>(null);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [activeTab, setActiveTab] = useState('summary');
  const [filters, setFilters] = useState<{ os_name?: string; page: number; limit: number; server_filter?: string }>({
    page: 1,
    limit: 10,
  });
  const [filteredComputers, setFilteredComputers] = useState<ComputerList[]>([]);

  const { data, error: statsError, isLoading } = useQuery<DashboardStats, Error>({
    queryKey: ['statistics'],
    queryFn: () =>
      getStatistics({
        metrics: ['total_computers', 'os_distribution', 'low_disk_space_with_volumes', 'last_scan_time', 'status_stats'],
      }),
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 60 * 60 * 1000,
  });

  const {
    data: computersData,
    isLoading: isComputersLoading,
    error: computersError,
  } = useQuery<ComputersResponse, Error>({
    queryKey: ['computers', selectedOs, filters.page, filters.limit],
    queryFn: () => {
      console.log('Отправка запроса getComputers с os_name:', selectedOs);
      const isServerOs = selectedOs === 'Other Servers';
      return getComputers({
        os_name: selectedOs === 'Unknown' || isServerOs ? undefined : selectedOs || undefined,
        server_filter: isServerOs ? 'server' : undefined,
        page: filters.page,
        limit: filters.limit,
      });
    },
    enabled: !!selectedOs,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });

  useEffect(() => {
    if (computersData?.data) {
      console.log('Получены данные компьютеров:', computersData.data);
      setFilteredComputers(computersData.data);
      setIsModalVisible(true);
    }
  }, [computersData]);

  useEffect(() => {
    if (data?.disk_stats?.low_disk_space?.length) {
      console.warn(`${data.disk_stats.low_disk_space.length} компьютеров имеют низкий объем диска.`);
    }
  }, [data?.disk_stats?.low_disk_space?.length]);

  if (isLoading) return <div>Загрузка...</div>;
  if (statsError) return <div>Ошибка: {statsError.message}</div>;
  if (!data) return <div>Данные недоступны</div>;

  const computerColumns = [
    { title: 'Hostname', dataIndex: 'hostname', key: 'hostname' },
    {
      title: 'IP',
      dataIndex: 'ip_addresses',
      key: 'ip',
      render: (ip_addresses: ComputerList['ip_addresses']) =>
        ip_addresses && ip_addresses.length > 0 ? ip_addresses[0].address : '-',
    },
    { title: 'Версия ОС', dataIndex: 'os_version', key: 'os_version' },
    { title: 'Статус', dataIndex: 'check_status', key: 'check_status' },
  ];

  const osMapping: Record<string, string | undefined> = {
    'Unknown': undefined,
    'Other Servers': undefined,
    'Windows 10': 'Windows 10%',
    'Windows 11': 'Windows 11%',
    'Windows 7': 'Windows 7%',
    'Ubuntu': 'Ubuntu%',
    'CentOS': 'CentOS%',
    'Debian': 'Debian%',
    'Windows Server 2022': 'Windows Server 2022%',
    'Windows Server 2019': 'Windows Server 2019%',
    'Windows Server 2016': 'Windows Server 2016%',
    'Windows Server 2008': 'Windows Server 2008%',
    'Hyper-V': 'Hyper-V%',
    'Other Clients': '',
  };

  const handleOsClick = (os: string, isClientOs: boolean) => {
    const mappedOs = osMapping[os] || os;
    console.log(`Выбрано ОС: ${os}, mappedOs: ${mappedOs}, isClientOs: ${isClientOs}`);
    setSelectedOs(os);
    setFilters({ page: 1, limit: 10 });
  };

  return (
    <div style={{ padding: 16 }}>
      <h2 style={{ marginBottom: 16 }}>Статистика інвентаризації</h2>
      <DashboardMenu onTabChange={setActiveTab} />
      {activeTab === 'summary' && (
        <StatsSummary
          totalComputers={data.total_computers}
          lastScanTime={data.scan_stats.last_scan_time}
        />
      )}
      {activeTab === 'os_distribution' && (
        <OsDistribution
          clientOsData={data.os_stats.client_os}
          serverOsData={data.os_stats.server_os}
          onOsClick={handleOsClick}
        />
      )}
      {activeTab === 'low_disk_space' && (
        <LowDiskSpace lowDiskSpace={data.disk_stats.low_disk_space} />
      )}
      {activeTab === 'status_stats' && (
        <StatusStats statusStats={data.scan_stats.status_stats} />
      )}
      {data.disk_stats.low_disk_space.length > 0 && (
        <div style={{ color: 'red', marginTop: '1rem' }}>
          Увага: {data.disk_stats.low_disk_space.length} комп'ютерів мають низький обсяг диска.
        </div>
      )}
      <Modal
        title={`Комп'ютери з ОС: ${selectedOs ? selectedOs.replace('%', '') : 'Не вибрано'}`}
        open={isModalVisible}
        onCancel={() => {
          setIsModalVisible(false);
          setSelectedOs(null);
          setFilteredComputers([]);
        }}
        footer={null}
        width={800}
      >
        {isComputersLoading ? (
          <div>Загрузка...</div>
        ) : computersError ? (
          <p>Помилка завантаження даних: {computersError.message}</p>
        ) : filteredComputers.length > 0 ? (
          <Table
            columns={computerColumns}
            dataSource={filteredComputers}
            rowKey="id"
            size="small"
            pagination={{
              current: filters.page,
              pageSize: filters.limit,
              total: computersData?.total || 0,
              onChange: (page, pageSize) => setFilters({ ...filters, page, limit: pageSize }),
            }}
            locale={{ emptyText: 'Немає даних' }}
          />
        ) : (
          <p>Немає даних</p>
        )}
      </Modal>
      <Link to="/computers" aria-label="Перейти до списку всіх комп'ютерів" style={{ marginTop: '16px', display: 'block' }}>
        Перейти до списку комп'ютерів
      </Link>
    </div>
  );
};

export default Dashboard;