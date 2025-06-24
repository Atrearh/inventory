import { useQuery } from '@tanstack/react-query';
import { getStatistics, getComputers } from '../api/api';
import { DashboardStats, ComputerList } from '../types/schemas';
import { Link } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { Table, Row, Col, Modal } from 'antd';
import { Pie } from 'react-chartjs-2';
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js';

ChartJS.register(ArcElement, Tooltip, Legend);

const Dashboard: React.FC = () => {
  const [selectedOs, setSelectedOs] = useState<string | null>(null);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [filteredComputers, setFilteredComputers] = useState<ComputerList[]>([]);

  const { data, error, isLoading } = useQuery<DashboardStats, Error>({
    queryKey: ['statistics'],
    queryFn: () =>
      getStatistics({
        metrics: ['total_computers', 'os_distribution', 'low_disk_space_with_volumes', 'last_scan_time', 'status_stats'],
      }),
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });

  const { data: computersData, isLoading: isComputersLoading } = useQuery<{ data: ComputerList[]; total: number }, Error>({
    queryKey: ['computers', selectedOs],
    queryFn: () =>
      getComputers({
        os_name: selectedOs || undefined,
        page: 1,
        limit: 100,
      }),
    enabled: !!selectedOs,
  });

  useEffect(() => {
    if (data?.disk_stats?.low_disk_space?.length) {
      console.warn(`${data.disk_stats.low_disk_space.length} компьютеров имеют низкое место на диске.`);
    }
  }, [data?.disk_stats?.low_disk_space?.length]);

  useEffect(() => {
    if (computersData?.data) {
      setFilteredComputers(computersData.data);
      setIsModalVisible(true);
    }
  }, [computersData]);

  if (isLoading) return <div>Загрузка...</div>;
  if (error) return <div>Ошибка: {error.message}</div>;
  if (!data) return <div>Данные недоступны</div>;

  // Данные для диаграммы распределения клиентских ОС
  const clientOsChartData = {
    labels: data.os_stats.client_os.map(os => os.category) || [],
    datasets: [{
      data: data.os_stats.client_os.map(os => os.count) || [],
      backgroundColor: ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF'],
    }],
  };

  // Данные для диаграммы распределения серверных ОС
  const serverOsChartData = {
    labels: data.os_stats.server_os.map(os => os.category) || [],
    datasets: [{
      data: data.os_stats.server_os.map(os => os.count) || [],
      backgroundColor: ['#FF9F40', '#FFCD56', '#C9CB3F', '#36A2EB'],
    }],
  };

  const diskColumns = [
    { title: 'Hostname', dataIndex: 'hostname', key: 'hostname' },
    { title: 'Диск', dataIndex: 'disk_id', key: 'disk_id' },
    { title: 'Общий объем (GB)', dataIndex: 'total_space_gb', key: 'total_space_gb', render: (value: number) => value.toFixed(2) },
    { title: 'Свободный объем (GB)', dataIndex: 'free_space_gb', key: 'free_space_gb', render: (value: number) => value.toFixed(2) },
  ];

  const computerColumns = [
    { title: 'Hostname', dataIndex: 'hostname', key: 'hostname' },
    { title: 'IP', dataIndex: 'ip', key: 'ip' },
    { title: 'Версия ОС', dataIndex: 'os_version', key: 'os_version' },
    { title: 'Статус', dataIndex: 'check_status', key: 'check_status' },
  ];

  const diskData = data.disk_stats.low_disk_space || [];

  const handleChartClick = (os: string, isClientOs: boolean) => {
    setSelectedOs(isClientOs ? os : os);
    setIsModalVisible(true);
  };

  return (
    <div style={{ padding: 16 }}>
      <h2>Статистика инвентаризации</h2>
      {data.disk_stats.low_disk_space?.length > 0 && (
        <div style={{ color: 'red', marginBottom: '1rem' }}>
          Внимание: {data.disk_stats.low_disk_space.length} компьютеров с местом на диске менее 10%.
        </div>
      )}
      <Row gutter={[16, 16]}>
        <Col span={24} md={12}>
          <div style={{ background: '#f0f2f5', padding: 16, borderRadius: 8 }}>
            {data.total_computers !== undefined && (
              <p><strong>Всего компьютеров:</strong> {data.total_computers}</p>
            )}
            {data.scan_stats.last_scan_time && (
              <p><strong>Последний опрос:</strong> {new Date(data.scan_stats.last_scan_time).toLocaleString('ru-RU')}</p>
            )}
          </div>
        </Col>
        <Col span={24} md={12}>
          <h3>Распределение клиентских ОС</h3>
          {clientOsChartData.labels.length > 0 ? (
            <div style={{ height: '300px', cursor: 'pointer' }}>
              <Pie
                data={clientOsChartData}
                options={{ maintainAspectRatio: false, responsive: true }}
                onClick={(_, elements) => {
                  if (elements.length > 0) {
                    const index = elements[0].index;
                    const os = clientOsChartData.labels[index];
                    handleChartClick(os, true);
                  }
                }}
              />
            </div>
          ) : (
            <p>Нет данных о клиентских ОС</p>
          )}
        </Col>
        <Col span={24} md={12}>
          <h3>Распределение серверных ОС</h3>
          {serverOsChartData.labels.length > 0 ? (
            <div style={{ height: '300px', cursor: 'pointer' }}>
              <Pie
                data={serverOsChartData}
                options={{ maintainAspectRatio: false, responsive: true }}
                onClick={(_, elements) => {
                  if (elements.length > 0) {
                    const index = elements[0].index;
                    const os = serverOsChartData.labels[index];
                    handleChartClick(os, false);
                  }
                }}
              />
            </div>
          ) : (
            <p>Нет данных о серверных ОС</p>
          )}
        </Col>
      </Row>
      {diskData.length > 0 ? (
        <div style={{ marginTop: '16px' }}>
          <h3>Компьютеры с местом на диске меньше 10%</h3>
          <Table
            columns={diskColumns}
            dataSource={diskData}
            rowKey={(record) => `${record.hostname}-${record.disk_id}`}
            size="small"
            locale={{ emptyText: 'Нет данных' }}
          />
        </div>
      ) : (
        <p style={{ marginTop: '16px' }}>Нет компьютеров с низким местом на диске.</p>
      )}
      <Modal
        title={`Компьютеры с ОС: ${selectedOs || ''}`}
        open={isModalVisible}
        onCancel={() => {
          setIsModalVisible(false);
          setSelectedOs(null);
        }}
        footer={null}
        width={800}
      >
        {isComputersLoading ? (
          <div>Загрузка...</div>
        ) : filteredComputers.length > 0 ? (
          <Table
            columns={computerColumns}
            dataSource={filteredComputers}
            rowKey="id"
            size="small"
            locale={{ emptyText: 'Нет данных' }}
          />
        ) : (
          <p>Нет компьютеров с выбранной ОС</p>
        )}
      </Modal>
      <Link to="/computers" aria-label="Перейти к списку всех компьютеров" style={{ marginTop: '16px', display: 'block' }}>
        Перейти к списку всех компьютеров
      </Link>
    </div>
  );
};

export default Dashboard;