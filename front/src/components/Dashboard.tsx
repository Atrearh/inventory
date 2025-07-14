
import { useQuery } from '@tanstack/react-query';
import { getComputers, getStatistics } from '../api/api';
import { ComputerList, ComputersResponse, DashboardStats } from '../types/schemas';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { Modal, Table } from 'antd';
import CombinedStats from './CombinedStats';
import LowDiskSpace from './LowDiskSpace';
import DashboardMenu from './DashboardMenu';
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js';

ChartJS.register(ArcElement, Tooltip, Legend);

const Dashboard: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();

  // Determine active tab from URL search parameter
  const params = new URLSearchParams(location.search);
  const activeTab = params.get('tab') || 'summary';

  const [selectedOs, setSelectedOs] = useState<string | null>(null);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [filters, setFilters] = useState({ page: 1, limit: 10 });
  const [filteredComputers, setFilteredComputers] = useState<ComputerList[]>([]);

  const { data, error: statsError, isLoading } = useQuery<DashboardStats, Error>({
    queryKey: ['statistics'],
    queryFn: () => getStatistics({ metrics: ['total_computers', 'os_distribution', 'low_disk_space_with_volumes', 'last_scan_time', 'status_stats'] }),
    refetchOnWindowFocus: false,
    staleTime: 60 * 60 * 1000,
  });

  const { data: computersData, isLoading: isComputersLoading, error: computersError } = useQuery<ComputersResponse, Error>({
    queryKey: ['computers', selectedOs, filters.page, filters.limit],
    queryFn: () => {
      const isServerOs = selectedOs === 'Other Servers';
      return getComputers({ os_name: selectedOs === 'Unknown' || isServerOs ? undefined : selectedOs, server_filter: isServerOs ? 'server' : undefined, page: filters.page, limit: filters.limit });
    },
    enabled: !!selectedOs,
  });

  useEffect(() => {
    if (computersData?.data) {
      setFilteredComputers(computersData.data);
      setIsModalVisible(true);
    }
  }, [computersData]);

  if (isLoading) return <div>Загрузка...</div>;
  if (statsError) return <div style={{ color: 'red' }}>Помилка: {statsError.message}</div>;
  if (!data) return <div style={{ color: 'red' }}>Дані відсутні</div>;

  const handleTabChange = (tab: string) => {
    navigate(`?tab=${tab}`);
  };

  const computerColumns = [
    { title: 'Hostname', dataIndex: 'hostname', key: 'hostname' },
    { title: 'IP', dataIndex: 'ip_addresses', key: 'ip', render: (ip_addresses: ComputerList['ip_addresses']) => ip_addresses?.[0]?.address || '-' },
    { title: 'ОС', dataIndex: 'os_version', key: 'os_version' },
    { title: 'Статус', dataIndex: 'check_status', key: 'check_status' },
  ];

  const handleOsClick = (os: string) => {
    setSelectedOs(os);
    setFilters({ page: 1, limit: 10 });
  };

  return (
    <div style={{ padding: 12 }}>
      <h1 style={{ marginBottom: 0, marginTop: 0  }}>Статистика</h1>
      <DashboardMenu activeTab={activeTab} onTabChange={handleTabChange} />

      {activeTab === 'summary' && (
        <CombinedStats
          totalComputers={data.total_computers}
          lastScanTime={data.scan_stats.last_scan_time}
          clientOsData={data.os_stats.client_os}
          serverOsData={data.os_stats.server_os}
          statusStats={data.scan_stats.status_stats}
          lowDiskSpaceCount={data.disk_stats.low_disk_space.length}
          onOsClick={handleOsClick}
          onStatusClick={(status) => navigate(`/computers?check_status=${encodeURIComponent(status)}`)}
        />
      )}
      {activeTab === 'low_disk_space' && <LowDiskSpace lowDiskSpace={data.disk_stats.low_disk_space} />}

      <Modal
        title={selectedOs ? selectedOs.replace('%', '') : 'Не вибрано'}
        open={isModalVisible}
        onCancel={() => { setIsModalVisible(false); setSelectedOs(null); setFilteredComputers([]); }}
        footer={null}
        width={600}
      >
        {isComputersLoading ? (
          <div>Загрузка...</div>
        ) : computersError ? (
          <div style={{ color: 'red' }}>Помилка: {computersError.message}</div>
        ) : (
          <Table
            columns={computerColumns}
            dataSource={filteredComputers}
            rowKey="id"
            size="small"
            pagination={{ current: filters.page, pageSize: filters.limit, total: computersData?.total || 0, onChange: (p, ps) => setFilters({ ...filters, page: p, limit: ps }) }}
            locale={{ emptyText: '-' }}
          />
        )}
      </Modal>
    </div>
  );
};

export default Dashboard;