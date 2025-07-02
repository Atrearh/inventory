// src/components/Dashboard.tsx
import { useQuery } from '@tanstack/react-query';
import { getComputers, getStatistics } from '../api/api';
import { ComputerList, ComputersResponse, DashboardStats } from '../types/schemas';
import { Link } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { Table, Row, Col, Modal } from 'antd';
import { Pie } from 'react-chartjs-2';
import { Chart as ChartJS, ArcElement, Tooltip, Legend, Chart, ActiveElement } from 'chart.js';

ChartJS.register(ArcElement, Tooltip, Legend);

const Dashboard: React.FC = () => {
  const [selectedOs, setSelectedOs] = useState<string | null>(null);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [filters, setFilters] = useState<{ os_name?: string; page: number; limit: number; server_filter?: string }>({
    page: 1,
    limit: 10,
  });
  const [filteredComputers, setFilteredComputers] = useState<ComputerList[]>([]);

  // Запрос статистики для дашборда
  const { data, error: statsError, isLoading } = useQuery<DashboardStats, Error>({
    queryKey: ['statistics'],
    queryFn: () =>
      getStatistics({
        metrics: ['total_computers', 'os_distribution', 'low_disk_space_with_volumes', 'last_scan_time', 'status_stats'],
      }),
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 60 * 60 * 1000, // Кэш на 1 час
  });

  // Запрос отфильтрованного списка компьютеров
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

  // Обновление списка компьютеров и открытие модального окна
  useEffect(() => {
    if (computersData?.data) {
      console.log('Получены данные компьютеров:', computersData.data);
      setFilteredComputers(computersData.data);
      setIsModalVisible(true);
    }
  }, [computersData]);

  // Логирование предупреждения о низком объеме диска
  useEffect(() => {
    if (data?.disk_stats?.low_disk_space?.length) {
      console.warn(`${data.disk_stats.low_disk_space.length} компьютеров имеют низкий объем диска.`);
    }
  }, [data?.disk_stats?.low_disk_space?.length]);

  if (isLoading) return <div>Загрузка...</div>;
  if (statsError) return <div>Ошибка: {statsError.message}</div>;
  if (!data) return <div>Данные недоступны</div>;

  // Данные для диаграммы клиентских ОС
  const clientOsChartData = {
    labels: data.os_stats.client_os.map(os => os.category) || [],
    datasets: [
      {
        data: data.os_stats.client_os.map(os => os.count) || [],
        backgroundColor: ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF'],
      },
    ],
  };

  // Данные для диаграммы серверных ОС
  const serverOsChartData = {
    labels: data.os_stats.server_os.map(os => os.category) || [],
    datasets: [
      {
        data: data.os_stats.server_os.map(os => os.count) || [],
        backgroundColor: ['#FF9F40', '#FFCD56', '#C9CB3F', '#36A2EB'],
      },
    ],
  };

  // Колонки для таблицы дисков
  const diskColumns = [
    { title: 'Hostname', dataIndex: 'hostname', key: 'hostname' },
    { title: 'Диск', dataIndex: 'disk_id', key: 'disk_id' },
    { title: 'Общий объем (ГБ)', dataIndex: 'total_space_gb', key: 'total_space_gb', render: (value: number) => value.toFixed(2) },
    { title: 'Свободный объем (ГБ)', dataIndex: 'free_space_gb', key: 'free_space_gb', render: (value: number) => value.toFixed(2) },
  ];

  // Колонки для таблицы компьютеров в модальном окне
  const computerColumns = [
    { title: 'Hostname', dataIndex: 'hostname', key: 'hostname' },
    { title: 'IP', dataIndex: 'ip', key: 'ip' },
    { title: 'Версия ОС', dataIndex: 'os_version', key: 'os_version' },
    { title: 'Статус', dataIndex: 'check_status', key: 'check_status' },
  ];

  const diskData = data.disk_stats.low_disk_space || [];

  // Маппинг для обработки категорий ОС
  const osMapping: Record<string, string | undefined> = {
    'Unknown': undefined, // Для Unknown фильтруем по os_name IS NULL
    'Other Servers': undefined, // Для Other Servers используем server_filter
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

  // Обработчик клика по диаграмме
  const handlePieClick = (
    elements: ActiveElement[],
    chart: Chart, // Используем общий тип Chart
    isClientOs: boolean
  ) => {
    if (!elements.length) {
      console.log('Клик вне активных элементов диаграммы');
      return;
    }
    // Приводим chart к нужному типу
    const pieChart = chart as Chart<'pie', number[], string>;
    const index = elements[0].index;
    const os = pieChart.data.labels?.[index];
    if (typeof os === 'string') {
      const mappedOs = osMapping[os] || os;
      console.log(`Выбрано ОС: ${os}, mappedOs: ${mappedOs}, isClientOs: ${isClientOs}`);
      setSelectedOs(os); // Используем оригинальное имя ОС для фильтрации
      setFilters({ page: 1, limit: 10 }); // Сбрасываем пагинацию
    } else {
      console.error('Метка ОС не является строкой:', os);
    }
  };

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
              <span>
                <strong>Всего компьютеров:</strong> {data.total_computers}{' '}
              </span>
            )}
            {data.scan_stats.last_scan_time && (
              <span>
                <strong>Последнее сканирование:</strong>{' '}
                {new Date(data.scan_stats.last_scan_time).toLocaleString('uk-UA')}
              </span>
            )}
          </div>
        </Col>
      </Row>

      {/* Предупреждение о низком объеме диска */}
      {data.disk_stats.low_disk_space.length > 0 && (
        <div style={{ color: 'red', marginTop: '1rem' }}>
          Внимание: {data.disk_stats.low_disk_space.length} компьютеров имеют низкий объем диска.
        </div>
      )}

      {/* Диаграммы в одном ряду */}
      <Row gutter={[16, 16]}>
        <Col span={12}>
          <h3>Распределение клиентских ОС</h3>
          {clientOsChartData.labels.length > 0 ? (
            <div style={{ height: '300px', cursor: 'pointer' }}>
              <Pie
                data={clientOsChartData}
                options={{
                  maintainAspectRatio: false,
                  responsive: true,
                  plugins: {
                    legend: {
                      position: 'top',
                    },
                    tooltip: {
                      enabled: true,
                    },
                  },
                  onClick: (event, elements, chart) => handlePieClick(elements, chart, true),
                }}
              />
            </div>
          ) : (
            <p>Нет данных о клиентских ОС</p>
          )}
        </Col>
        <Col span={12}>
          <h3>Распределение серверных ОС</h3>
          {serverOsChartData.labels.length > 0 ? (
            <div style={{ height: '300px', cursor: 'pointer' }}>
              <Pie
                data={serverOsChartData}
                options={{
                  maintainAspectRatio: false,
                  responsive: true,
                  plugins: {
                    legend: {
                      position: 'top',
                    },
                    tooltip: {
                      enabled: true,
                    },
                  },
                  onClick: (event, elements, chart) => handlePieClick(elements, chart, false),
                }}
              />
            </div>
          ) : (
            <p>Нет данных о серверных ОС</p>
          )}
        </Col>
      </Row>

      {/* Таблица с отключенной пагинацией */}
      {diskData.length > 0 ? (
        <div style={{ marginTop: '16px' }}>
          <h3>Компьютеры с низким объемом диска</h3>
          <Table
            columns={diskColumns}
            dataSource={diskData}
            rowKey={(record) => `${record.hostname}-${record.disk_id}`}
            size="middle"
            locale={{ emptyText: 'Нет данных' }}
            pagination={false}
          />
        </div>
      ) : (
        <p style={{ marginTop: '16px' }}>Нет компьютеров с низким объемом диска.</p>
      )}

      {/* Модальное окно для отображения отфильтрованных компьютеров */}
      <Modal
        title={`Компьютеры с ОС: ${selectedOs ? selectedOs.replace('%', '') : 'Не выбрано'}`}
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
          <p>Ошибка загрузки данных: {computersError.message}</p>
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
            locale={{ emptyText: 'Нет данных' }}
          />
        ) : (
          <p>Нет данных</p>
        )}
      </Modal>

      <Link to="/computers" aria-label="Перейти к списку всех компьютеров" style={{ marginTop: '16px', display: 'block' }}>
        Перейти к списку компьютеров
      </Link>
    </div>
  );
};

export default Dashboard;