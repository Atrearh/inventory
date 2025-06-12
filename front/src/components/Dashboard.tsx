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
  });

  useEffect(() => {
    if (data?.low_disk_space?.length) {
      console.warn(`${data.low_disk_space.length} computers have low disk space.`);
    }
  }, [data?.low_disk_space?.length]);

  if (isLoading) return <div>Загрузка...</div>;
  if (error) return <div>Ошибка: {error.message}</div>;
  if (!data) return <div>Данные недоступны</div>;

  const colors = [
    '#FF6384',
    '#36A2EB',
    '#FFCE56',
    '#4BC0C0',
    '#9966FF',
    '#FF9F40',
    '#FFCD56',
    '#C9CB3F',
    '#36A2EB',
    '#4BC0C0',
  ];

  const osChartData = {
    labels: data.os_versions?.map((os) => os.os_version) ?? [],
    datasets: [
      {
        data: data.os_versions?.map((os) => os.count) ?? [],
        backgroundColor: colors.slice(0, data.os_versions?.length ?? 0),
      },
    ],
  };

  const lowDiskSpaceColumns = [
    {
      title: 'Hostname',
      dataIndex: 'hostname',
      key: 'hostname',
    },
    {
      title: 'Диск',
      dataIndex: 'disk_id',
      key: 'disk_id',
    },
    {
      title: 'Свободно (%)',
      dataIndex: 'free_space_percent',
      key: 'free_space_percent',
      render: (value: number) => `${value.toFixed(2)}%`,
    },
  ];

  return (
    <div>
      <h2>Статистика инвентаризации</h2>
      {data.low_disk_space?.length > 0 && (
        <div style={{ color: 'red', marginBottom: '1rem' }}>
          Внимание: {data.low_disk_space.length} компьютеров с местом на диске менее 10%.
        </div>
      )}
      {data.total_computers !== undefined && (
        <p>
          <strong>Всего компьютеров:</strong> {data.total_computers}
        </p>
      )}
      {data.last_scan_time && (
        <p>
          <strong>Последний опрос:</strong>{' '}
          {new Date(data.last_scan_time).toLocaleString('ru-RU')}
        </p>
      )}
      {data.os_versions?.length > 0 && (
        <>
          <h3>Версии ОС</h3>
          <div style={{ maxWidth: '400px', margin: 'auto' }}>
            <Pie data={osChartData} options={{ maintainAspectRatio: true, responsive: true }} />
          </div>
        </>
      )}
      {data.low_disk_space?.length > 0 ? (
        <>
          <h3>Компьютеры с местом на диске &lt; 10%</h3>
          <Table
            columns={lowDiskSpaceColumns}
            dataSource={data.low_disk_space}
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