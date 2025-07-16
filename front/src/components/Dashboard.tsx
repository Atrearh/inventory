// src/components/Dashboard.tsx
import { useQuery } from '@tanstack/react-query';
import { getComputers, getStatistics } from '../api/api';
import { ComputerList, ComputersResponse, DashboardStats } from '../types/schemas';
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

ChartJS.register(ArcElement, Tooltip, Legend);

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

  const { data, error: statsError, isLoading, refetch: refetchStats } = useQuery<DashboardStats, Error>({
    enabled: isAuthenticated, 
    queryKey: ['statistics'],
    queryFn: () => getStatistics({ metrics: ['total_computers', 'os_distribution', 'low_disk_space_with_volumes', 'last_scan_time', 'status_stats'] }),
    refetchOnWindowFocus: false,
    staleTime: 60 * 60 * 1000,
    retry: 3,
    retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 30000),
  });

  const { data: computersData, isLoading: isComputersLoading, error: computersError, refetch: refetchComputers } = useQuery<
    ComputersResponse,
    Error
  >({
    queryKey: ['computers', selectedOs, selectedSubnet, filters.page, filters.limit],
    queryFn: () => {
      console.log('Query params:', { selectedOs, selectedSubnet, page: filters.page, limit: filters.limit });
      const params: any = { page: filters.page, limit: filters.limit };
      if (selectedSubnet) {
        if (selectedSubnet === 'Неизвестно') {
          // Фильтр для компьютеров без IP-адресов
          params.ip_range = 'none'; // Специальный параметр для бэкенда
          console.log('Applying filter for computers without IP addresses');
        } else {
          const match = selectedSubnet.match(/^(\d+\.\d+)\.(\d+)\.0\/23$/);
          if (match) {
            const baseIp = match[1];
            const thirdOctet = parseInt(match[2], 10);
            const ipFilter = `${baseIp}.[${thirdOctet}-${thirdOctet + 1}]`;
            console.log('Applying ip_range filter:', ipFilter);
            params.ip_range = ipFilter;
          } else {
            console.warn('Invalid subnet format:', selectedSubnet);
            params.ip_range = undefined;
          }
        }
      } else if (selectedOs) {
        const isServerOs = selectedOs === 'Other Servers';
        params.os_name = selectedOs === 'Unknown' || isServerOs ? undefined : selectedOs;
        params.server_filter = isServerOs ? 'server' : undefined;
      }
      return getComputers(params);
    },
    enabled: !!(selectedOs || selectedSubnet),
    retry: 3,
    retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 30000),
  });

  useEffect(() => {
    if (statsError) {
      console.error('Statistics error:', statsError);
      if (statsError instanceof AxiosError && statsError.response?.data) {
        console.error('Server error details:', JSON.stringify(statsError.response.data, null, 2));
        notification.error({
          message: 'Ошибка загрузки статистики',
          description: `Не удалось загрузить статистику: ${JSON.stringify(statsError.response.data.detail || statsError.message)}`,
        });
      } else {
        notification.error({
          message: 'Ошибка загрузки статистики',
          description: `Не удалось загрузить статистику: ${statsError.message}`,
        });
      }
    }
    if (computersError) {
      console.error('Computers error:', computersError);
      if (computersError instanceof AxiosError && computersError.response?.data) {
        console.error('Server error details:', JSON.stringify(computersError.response.data, null, 2));
        notification.error({
          message: 'Ошибка загрузки данных компьютеров',
          description: `Не удалось загрузить данные компьютеров: ${JSON.stringify(computersError.response.data.detail || computersError.message)}`,
        });
      } else {
        notification.error({
          message: 'Ошибка загрузки данных компьютеров',
          description: `Не удалось загрузить данные компьютеров: ${computersError.message}`,
        });
      }
    }
    if (computersData?.data) {
      console.log('Filtered computers:', computersData.data.slice(0, 5));
      setFilteredComputers(computersData.data);
      setIsModalVisible(true);
    } else {
      setFilteredComputers([]);
    }
  }, [statsError, computersError, computersData]);

  useEffect(() => {
    if (selectedOs || selectedSubnet) {
      console.log('Refetching computers for:', { selectedOs, selectedSubnet });
      refetchComputers();
    }
  }, [selectedOs, selectedSubnet, refetchComputers]);

  if (isLoading) return <div>Загрузка...</div>;
  if (statsError) return <div style={{ color: 'red' }}>Ошибка: {statsError.message}</div>;
  if (!data) return <div style={{ color: 'red' }}>Данные отсутствуют</div>;

  const handleTabChange = (tab: string) => {
    navigate(`?tab=${tab}`);
  };

  const computerColumns = [
    { title: 'Hostname', dataIndex: 'hostname', key: 'hostname' },
    {
      title: 'IP',
      dataIndex: 'ip_addresses',
      key: 'ip',
      render: (ip_addresses: ComputerList['ip_addresses']) => ip_addresses?.map((ip) => ip.address).join(', ') || '-',
    },
    { title: 'ОС', dataIndex: 'os_version', key: 'os_version' },
    { title: 'Статус', dataIndex: 'check_status', key: 'check_status' },
  ];

  const handleOsClick = (os: string) => {
    setSelectedOs(os);
    setSelectedSubnet(null);
    setFilters({ page: 1, limit: 10 });
  };

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
        title={selectedOs ? selectedOs.replace('%', '') : selectedSubnet ? selectedSubnet : 'Не выбрано'}
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
          <div>Загрузка...</div>
        ) : computersError ? (
          <div style={{ color: 'red' }}>Ошибка: {computersError.message}</div>
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