import { useQuery } from '@tanstack/react-query';
import { getStatistics } from '../api/api';
import { DashboardStats } from '../types/schemas';
import { Link } from 'react-router-dom';
import { useEffect } from 'react';
import { Table, Row, Col } from 'antd';
import { Pie } from 'react-chartjs-2';
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js';

ChartJS.register(ArcElement, Tooltip, Legend);

const Dashboard: React.FC = () => {
  const { data, error, isLoading } = useQuery<DashboardStats, Error>({
    queryKey: ['statistics'],
    queryFn: () =>
      getStatistics({
        metrics: ['total_computers', 'os_distribution', 'low_disk_space_with_volumes', 'last_scan_time', 'status_stats'],
      }),
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });

  // Логирование предупреждения о низком месте на диске
  useEffect(() => {
    if (data?.disk_stats?.low_disk_space?.length) {
      console.warn(`${data.disk_stats.low_disk_space.length} компьютеров имеют низкое место на диске.`);
    }
  }, [data?.disk_stats?.low_disk_space?.length]);

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

  // Колонки для таблицы дисков
  const diskColumns = [
    { title: 'Hostname', dataIndex: 'hostname', key: 'hostname' },
    { title: 'Диск', dataIndex: 'disk_id', key: 'disk_id' },
    { title: 'Общий объем (GB)', dataIndex: 'total_space_gb', key: 'total_space_gb', render: (value: number) => value.toFixed(2) },
    { title: 'Свободный объем (GB)', dataIndex: 'free_space_gb', key: 'free_space_gb', render: (value: number) => value.toFixed(2) },
  ];

  const diskData = data.disk_stats.low_disk_space || [];

  return (
    <div style={{ padding: 16 }}>
      {/* Заголовок и статистика в одном ряду */}
      <Row gutter={[16, 16]} align="middle">
        <Col>
          <h2 style={{ margin: 0 }}>Статистика инвентаризации</h2>
        </Col>
        <Col>
          <div style={{ background: '#f0f2f5', padding: 8, borderRadius: 8 }}>
            {data.total_computers !== undefined && (
              <span><strong>Всего компьютеров:</strong> {data.total_computers} </span>
            )}
            {data.scan_stats.last_scan_time && (
              <span><strong>Последний опрос:</strong> {new Date(data.scan_stats.last_scan_time).toLocaleString('ru-RU')}</span>
            )}
          </div>
        </Col>
      </Row>

      {/* Предупреждение о низком месте на диске */}
      {data.disk_stats.low_disk_space?.length > 0 && (
        <div style={{ color: 'red', margin: '1rem 0' }}>
          Внимание: {data.disk_stats.low_disk_space.length} компьютеров с местом на диске менее 10%.
        </div>
      )}

      {/* Диаграммы в одном ряду */}
      <Row gutter={[16, 16]}>
        <Col span={12}>
          <h3>Распределение клиентских ОС</h3>
          {clientOsChartData.labels.length > 0 ? (
            <div style={{ height: '300px' }}>
              <Pie data={clientOsChartData} options={{ maintainAspectRatio: false, responsive: true }} />
            </div>
          ) : (
            <p>Нет данных о клиентских ОС</p>
          )}
        </Col>
        <Col span={12}>
          <h3>Распределение серверных ОС</h3>
          {serverOsChartData.labels.length > 0 ? (
            <div style={{ height: '300px' }}>
              <Pie data={serverOsChartData} options={{ maintainAspectRatio: false, responsive: true }} />
            </div>
          ) : (
            <>
<p>Нет данных о серверных ОС</p>
            </>
          )}
        </Col>
      </Row>

      {/* Таблица с отключенной пагинацией */}
      {diskData.length > 0 ? (
        <div style={{ marginTop: '16px' }}>
          <h3>Компьютеры с местом на диске меньше 10%</h3>
          <Table
            columns={diskColumns}
            dataSource={diskData}
            rowKey={(record) => `${record.hostname}-${record.disk_id}`}
            size="default"
            locale={{ emptyText: 'No data' }}
            pagination={false} // Отключаем пагинацию
          />
        </div>
      ) : (
        <p style={{ marginTop: '16px' }}>No computers with low disk space found.</p>
      )}

      <Link to="/computers" aria-label="Перейти к списку всіх комп'ютерів" style={{ marginTop: '16px', display: 'block' }}>
        Перейти к списку всех компьютеров
      </Link>
    </div>
  );
};

export default Dashboard;