// src/components/Dashboard.tsx
import { useQuery } from '@tanstack/react-query';
import { getStatistics } from '../api/api';
import { DashboardStats } from '../types/schemas';
import { Link } from 'react-router-dom';
import { useEffect } from 'react';
import { Table } from 'antd';
import { Pie } from 'react-chartjs-2';
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js';

ChartJS.register(ArcElement, Tooltip, Legend);

const Dashboard: React.FC = () => {
  const { data, error, isLoading } = useQuery<DashboardStats, Error>({
    queryKey: ['statistics'],
    queryFn: () =>
      getStatistics({
        metrics: ['total_computers', 'os_versions', 'low_disk_space', 'last_scan_time', 'status_stats'],
      }),
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });

  useEffect(() => {
    if (data?.disk_stats?.low_disk_space?.length) {
      console.warn(`${data.disk_stats.low_disk_space.length} компьютеров имеют низкое место на диске.`);
    }
  }, [data?.disk_stats?.low_disk_space?.length]);

  if (isLoading) return <div>Загрузка...</div>;
  if (error) return <div>Ошибка: {error.message}</div>;
  if (!data) return <div>Данные недоступны</div>;

  const colors = [
    '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40', '#FFCD56', '#C9CB3F', '#36A2EB', '#4BC0C0',
  ];

  // Фильтрация и форматирование версий Windows
  const windowsVersions = data.os_stats.os_versions?.reduce((acc, os) => {
    const match = os.os_version?.match(/Windows (\d+)/);
    if (match) {
      const version = match[1];
      acc[version] = (acc[version] || 0) + os.count;
    }
    return acc;
  }, {} as Record<string, number>);

  const osChartData = {
    labels: windowsVersions ? Object.keys(windowsVersions) : [],
    datasets: [
      {
        data: windowsVersions ? Object.values(windowsVersions) : [],
        backgroundColor: colors.slice(0, windowsVersions ? Object.keys(windowsVersions).length : 0),
      },
    ],
  };

  const lowDiskSpaceColumns = [
    { title: 'Hostname', dataIndex: 'hostname', key: 'hostname' },
    { title: 'Диск', dataIndex: 'disk_id', key: 'disk_id' },
    { title: 'Свободно (%)', dataIndex: 'free_space_percent', key: 'free_space_percent', render: (value: number) => `${value.toFixed(2)}%` },
    { title: 'Общий объем (GB)', dataIndex: 'total_space', key: 'total_space', render: (value: number) => (value / (1024 * 1024 * 1024)).toFixed(2) },
    { title: 'Свободный объем (GB)', dataIndex: 'free_space', key: 'free_space', render: (value: number | null) => (value ? (value / (1024 * 1024 * 1024)).toFixed(2) : 'N/A') },
  ];

  const lowDiskSpaceData = data.disk_stats.low_disk_space?.map((disk) => ({
    ...disk,
    total_space: disk.total_space, // Предполагается, что total_space приходит в байтах
    free_space: disk.free_space,   // Предполагается, что free_space приходит в байтах
  })) || [];

  return (
    <div>
      <h2>Статистика инвентаризации</h2>
      {data.disk_stats.low_disk_space?.length > 0 && (
        <div style={{ color: 'red', marginBottom: '1rem' }}>
          Внимание: {data.disk_stats.low_disk_space.length} компьютеров с местом на диске менее 10%.
        </div>
      )}
      {data.total_computers !== undefined && (
        <p><strong>Всего компьютеров:</strong> {data.total_computers}</p>
      )}
      {data.scan_stats.last_scan_time && (
        <p><strong>Последний опрос:</strong> {new Date(data.scan_stats.last_scan_time).toLocaleString('ru-RU')}</p>
      )}
      {osChartData.labels.length > 0 && (
        <>
          <h3>Версии Windows</h3>
          <div style={{ maxWidth: '400px', margin: 'auto' }}>
            <Pie data={osChartData} options={{ maintainAspectRatio: true, responsive: true }} />
          </div>
        </>
      )}
      {lowDiskSpaceData.length > 0 ? (
        <>
          <h3>Компьютеры с местом на диске &lt; 10%</h3>
          <Table
            columns={lowDiskSpaceColumns}
            dataSource={lowDiskSpaceData}
            rowKey={(record) => `${record.hostname}-${record.disk_id}`}
            pagination={false}
            size="small"
            locale={{ emptyText: 'Нет данных' }}
          />
        </>
      ) : (
        <p>Нет компьютеров с низким местом на диске.</p>
      )}
      <Link to="/computers" aria-label="Перейти к списку всех компьютеров">
        Перейти к списку компьютеров
      </Link>
    </div>
  );
};

export default Dashboard;