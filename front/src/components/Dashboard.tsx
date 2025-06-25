import { useQuery } from '@tanstack/react-query';
import { getStatistics, getComputers } from '../api/api';
import { DashboardStats, ComputerList } from '../types/schemas';
import { Link } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { Table, Row, Col, Modal } from 'antd';
import { Pie } from 'react-chartjs-2';
import { Chart as ChartJS, ArcElement, Tooltip, Legend, Chart } from 'chart.js';
import type { ChartEvent, ActiveElement } from 'chart.js';

ChartJS.register(ArcElement, Tooltip, Legend);

const Dashboard: React.FC = () => {
  const [selectedOs, setSelectedOs] = useState<string | null>(null);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [filteredComputers, setFilteredComputers] = useState<ComputerList[]>([]);

  // Запит статистики для дашборду
  const { data, error: statsError, isLoading } = useQuery<DashboardStats, Error>({
    queryKey: ['statistics'],
    queryFn: () =>
      getStatistics({
        metrics: ['total_computers', 'os_distribution', 'low_disk_space_with_volumes', 'last_scan_time', 'status_stats'],
      }),
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });

  // Запит відфільтрованого списку комп'ютерів за os_name
  const {
    data: computersData,
    isLoading: isComputersLoading,
    error: computersError,
  } = useQuery<{ data: ComputerList[]; total: number }, Error>({
    queryKey: ['computers', selectedOs],
    queryFn: () => {
      console.log('Надсилання запиту getComputers з os_name:', selectedOs);
      return getComputers({
        os_name: selectedOs || undefined,
        page: 1,
        limit: 100,
      });
    },
    enabled: !!selectedOs,
  });

  // Логування попередження про низький обсяг диска
  useEffect(() => {
    if (data?.disk_stats?.low_disk_space?.length) {
      console.warn(`${data.disk_stats.low_disk_space.length} комп'ютерів мають низький обсяг диска.`);
    }
  }, [data?.disk_stats?.low_disk_space?.length]);

  // Оновлення списку комп'ютерів та відкриття модального вікна
  useEffect(() => {
    if (computersData?.data) {
      console.log('Отримано дані компютерів:', computersData.data);
      setFilteredComputers(computersData.data);
      setIsModalVisible(true);
    }
  }, [computersData]);

  if (isLoading) return <div>Завантаження...</div>;
  if (statsError) return <div>Помилка: {statsError.message}</div>;
  if (!data) return <div>Дані недоступні</div>;

  // Дані для діаграми розподілу клієнтських ОС
  const clientOsChartData = {
    labels: data.os_stats.client_os.map(os => os.category) || [],
    datasets: [
      {
        data: data.os_stats.client_os.map(os => os.count) || [],
        backgroundColor: ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF'],
      },
    ],
  };

  // Дані для діаграми розподілу серверних ОС
  const serverOsChartData = {
    labels: data.os_stats.server_os.map(os => os.category) || [],
    datasets: [
      {
        data: data.os_stats.server_os.map(os => os.count) || [],
        backgroundColor: ['#FF9F40', '#FFCD56', '#C9CB3F', '#36A2EB'],
      },
    ],
  };

  // Колонки для таблиці дисків
  const diskColumns = [
    { title: 'Hostname', dataIndex: 'hostname', key: 'hostname' },
    { title: 'Диск', dataIndex: 'disk_id', key: 'disk_id' },
    { title: 'Загальний обсяг (ГБ)', dataIndex: 'total_space_gb', key: 'total_space_gb', render: (value: number) => value.toFixed(2) },
    { title: 'Вільний обсяг (ГБ)', dataIndex: 'free_space_gb', key: 'free_space_gb', render: (value: number) => value.toFixed(2) },
  ];

  // Колонки для таблиці комп'ютерів у модальному вікні
  const computerColumns = [
    { title: 'Hostname', dataIndex: 'hostname', key: 'hostname' },
    { title: 'IP', dataIndex: 'ip', key: 'ip' },
    { title: 'Версія ОС', dataIndex: 'os_version', key: 'OS_version' },
    { title: 'Статус', dataIndex: 'check_status', key: 'check_status' },
  ];

  const diskData = data.disk_stats.low_disk_space || [];

  // Мапінг міток ОС для відповідності os_name у базі даних
  const osMapping: Record<string, string> = {
    'Windows 10': 'Windows 10%',
    'Windows 11': 'Windows 11%',
    'Windows Server 2016': 'Windows Server 2016%',
    'Windows Server 2019': 'Windows Server 2019%',
    'Windows Server 2022': 'Windows Server 2022%',
    'Ubuntu': 'Ubuntu%',
    'CentOS': 'CentOS%',
    'Debian': 'Debian%',
  };

  // Обробник кліку по діаграмі
  const handlePieClick = (
    event: ChartEvent,
    elements: ActiveElement[],
    chart: Chart<'pie', number[], string>,
    isClientOs: boolean
  ) => {
    // Обробка кліку поза активними елементами
    if (!elements || elements.length === 0) {
      console.log('Клік поза активними елементами діаграми');
      return;
    }
    const index = elements[0].index;
    const os = chart.data.labels?.[index];
    if (typeof os === 'string') {
      const mappedOs = osMapping[os] || os; // Застосовуємо мапінг або використовуємо вихідне значення
      console.log(`Вибрано ОС: ${os}, mappedOs: ${mappedOs}, isClientOs: ${isClientOs}`);
      setSelectedOs(mappedOs);
      setIsModalVisible(true);
    } else {
      console.error('Мітка ОС не є рядком:', os);
    }
  };

  return (
    <div style={{ padding: 16 }}>
      {/* Заголовок і статистика в одному рядку */}
      <Row gutter={[16, 16]} align="middle">
        <Col>
          <h2 style={{ margin: 0 }}>Статистика інвентаризації</h2>
        </Col>
        <Col>
          <div style={{ background: '#f0f2f5', padding: 8, borderRadius: 8 }}>
            {data.total_computers !== undefined && (
              <span>
                <strong>Усього комп'ютерів:</strong> {data.total_computers}{' '}
              </span>
            )}
            {data.scan_stats.last_scan_time && (
              <span>
                <strong>Останнє сканування:</strong> {new Date(data.scan_stats.last_scan_time).toLocaleString('uk-UA')}
              </span>
            )}
          </div>
        </Col>
      </Row>

      {/* Попередження про низький обсяг диска */}
      {data.disk_stats.low_disk_space?.length > 0 && (
        <div style={{ color: 'red', margin: '1rem 0' }}>
          Увага: {data.disk_stats.low_disk_space.length} комп'ютерів із обсягом диска менше 10%.
        </div>
      )}

      {/* Діаграми в одному рядку */}
      <Row gutter={[16, 16]}>
        <Col span={12}>
          <h3>Розподіл клієнтських ОС</h3>
          {clientOsChartData.labels.length > 0 ? (
            <div style={{ height: '300px', cursor: 'pointer' }}>
              <Pie
                data={clientOsChartData}
                options={{
                  maintainAspectRatio: false,
                  responsive: true,
                  onClick: (event: ChartEvent, elements: ActiveElement[], chart: Chart<'pie', number[], string>) =>
                    handlePieClick(event, elements, chart, true),
                }}
              />
            </div>
          ) : (
            <p>Немає даних про клієнтські ОС</p>
          )}
        </Col>
        <Col span={12}>
          <h3>Розподіл серверних ОС</h3>
          {serverOsChartData.labels.length > 0 ? (
            <div style={{ height: '300px', cursor: 'pointer' }}>
              <Pie
                data={serverOsChartData}
                options={{
                  maintainAspectRatio: false,
                  responsive: true,
                  onClick: (event: ChartEvent, elements: ActiveElement[], chart: Chart<'pie', number[], string>) =>
                    handlePieClick(event, elements, chart, false),
                }}
              />
            </div>
          ) : (
            <p>Немає даних про серверні ОС</p>
          )}
        </Col>
      </Row>

      {/* Таблиця з відключеною пагінацією */}
      {diskData.length > 0 ? (
        <div style={{ marginTop: '16px' }}>
          <h3>Комп'ютери з обсягом диска менше 10%</h3>
          <Table
            columns={diskColumns}
            dataSource={diskData}
            rowKey={(record) => `${record.hostname}-${record.disk_id}`}
            size="middle"
            locale={{ emptyText: 'Немає даних' }}
            pagination={false}
          />
        </div>
      ) : (
        <p style={{ marginTop: '16px' }}>Немає комп'ютерів із низьким обсягом диска.</p>
      )}

      {/* Модальне вікно для відображення відфільтрованих комп'ютерів */}
      <Modal
        title={`Комп'ютери з ОС: ${selectedOs ? selectedOs.replace('%', '') : ''}`}
        open={isModalVisible}
        onCancel={() => {
          setIsModalVisible(false);
          setSelectedOs(null);
        }}
        footer={null}
        width={800}
      >
        {isComputersLoading ? (
          <div>Завантаження...</div>
        ) : computersError ? (
          <p>Помилка завантаження даних: {computersError.message}</p>
        ) : filteredComputers.length > 0 ? (
          <Table
            columns={computerColumns}
            dataSource={filteredComputers}
            rowKey="id"
            size="small"
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