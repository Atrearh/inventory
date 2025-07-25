// src/components/CombinedStats.tsx
import { Card, Row, Col, Table, Typography } from 'antd';
import { Pie } from 'react-chartjs-2';
import { Chart, ActiveElement } from 'chart.js';
import { DashboardStats } from '../types/schemas';
import { useNavigate, Link } from 'react-router-dom';

const { Title } = Typography;

interface CombinedStatsProps {
  totalComputers: number | null | undefined;
  lastScanTime: string | null;
  clientOsData: DashboardStats['os_stats']['client_os'];
  serverOsData: DashboardStats['os_stats']['server_os'];
  statusStats: DashboardStats['scan_stats']['status_stats'];
  lowDiskSpaceCount: number;
  onOsClick: (os: string, isClientOs: boolean) => void;
  onStatusClick: (status: string) => void;
}

// Нормалізація назви ОС для відображення
const normalizeOsName = (name: string): string => {
  const nameLower = name.toLowerCase();
  if (nameLower.includes('windows 10') && (nameLower.includes('корпоративная') || nameLower.includes('enterprise') || nameLower.includes('ltsc'))) {
    return 'Windows 10 Корпоративная';
  }
  if (nameLower.includes('hyper-v')) {
    return 'Hyper-V Server';
  }
  return name;
};

// Переклади статусів перевірки
const statusTranslations: Record<string, string> = {
  success: 'Успішно',
  partially_successful: 'Частково успішно',
  failed: 'Невдало',
  unreachable: 'Недоступно',
  disabled: 'Відключено',
  is_deleted: 'Видалено',
};

const CombinedStats: React.FC<CombinedStatsProps> = ({
  totalComputers,
  lastScanTime,
  clientOsData,
  serverOsData,
  statusStats,
  lowDiskSpaceCount,
  onOsClick,
  onStatusClick,
}) => {
  const navigate = useNavigate();

  // Дані для діаграми клієнтських ОС
  const clientOsChartData = {
    labels: clientOsData && Array.isArray(clientOsData) ? clientOsData.map(os => normalizeOsName(os.category)) : [],
    datasets: [{
      data: clientOsData && Array.isArray(clientOsData) ? clientOsData.map(os => os.count) : [],
      backgroundColor: ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF'],
    }],
  };

  // Дані для діаграми серверних ОС
  const serverOsChartData = {
    labels: serverOsData && Array.isArray(serverOsData) ? serverOsData.map(os => normalizeOsName(os.category)) : [],
    datasets: [{
      data: serverOsData && Array.isArray(serverOsData) ? serverOsData.map(os => os.count) : [],
      backgroundColor: ['#FF9F40', '#FFCD56', '#C9CB3F', '#36A2EB'],
    }],
  };

  // Обробка кліку по діаграмі
  const handlePieClick = (elements: ActiveElement[], chart: Chart, isClientOs: boolean) => {
    if (!elements.length) return;
    const index = elements[0].index;
    const os = chart.data.labels?.[index];
    if (typeof os === 'string') onOsClick(os, isClientOs);
  };

  // Колонки для таблиці статусів
  const statusColumns = [
    {
      title: 'Статус',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <a onClick={() => {
          onStatusClick(status);
          navigate(`/computers?check_status=${encodeURIComponent(status)}`);
        }} style={{ cursor: 'pointer', color: '#1890ff' }}>
          {statusTranslations[status] || status}
        </a>
      ),
    },
    { title: 'Кількість', dataIndex: 'count', key: 'count' },
  ];

  return (
    <div style={{ padding: 0 }}>
      <Card style={{ marginBottom: '16px' }}>
        <Row justify="space-between">
          <Col>
            <strong>Всього комп’ютерів:</strong> {totalComputers ?? '-'}
          </Col>
          <Col>
            <strong>Остання перевірка:</strong>{' '}
            {lastScanTime ? new Date(lastScanTime).toLocaleString('uk-UA') : '-'}
          </Col>
        </Row>
        {lowDiskSpaceCount > 0 && (
          <Row style={{ marginTop: 8 }}>
            <Col>
              <Link to="/?tab=low_disk_space" style={{ color: 'red' }}>
                Увага: {lowDiskSpaceCount} комп’ютерів з низьким залишком вільного місця на диску
              </Link>
            </Col>
          </Row>
        )}
      </Card>

      <Row gutter={[16, 0]}>
        <Col span={12}>
          <Card>
            <Title level={3} style={{ textAlign: 'center' }}>Клієнтські ОС</Title>
            {clientOsChartData.labels.length > 0 ? (
              <div style={{ height: '260px', cursor: 'pointer' }}>
                <Pie
                  data={clientOsChartData}
                  options={{
                    maintainAspectRatio: false,
                    responsive: true,
                    plugins: {
                      legend: { position: 'bottom' },
                      tooltip: { enabled: true },
                    },
                    onClick: (e, el, c) => handlePieClick(el, c, true),
                  }}
                />
              </div>
            ) : (
              <p style={{ textAlign: 'center' }}>Немає даних про клієнтські ОС</p>
            )}
          </Card>
        </Col>

        <Col span={12}>
          <Card>
            <Title level={3} style={{ textAlign: 'center' }}>Серверні ОС</Title>
            {serverOsChartData.labels.length > 0 ? (
              <div style={{ height: '260px', cursor: 'pointer' }}>
                <Pie
                  data={serverOsChartData}
                  options={{
                    maintainAspectRatio: false,
                    responsive: true,
                    plugins: {
                      legend: { position: 'bottom' },
                      tooltip: { enabled: true },
                    },
                    onClick: (e, el, c) => handlePieClick(el, c, false),
                  }}
                />
              </div>
            ) : (
              <p style={{ textAlign: 'center' }}>Немає даних про серверні ОС</p>
            )}
          </Card>
        </Col>
      </Row>

      <Card style={{ marginTop: '16px' }}>
        <Title level={4}>Статуси перевірки</Title>
        <Table
          columns={statusColumns}
          dataSource={statusStats && Array.isArray(statusStats) ? statusStats.filter(stat => stat.count > 0) : []}
          rowKey="status"
          size="small"
          pagination={false}
          locale={{ emptyText: 'Немає даних' }}
        />
      </Card>
    </div>
  );
};

export default CombinedStats;