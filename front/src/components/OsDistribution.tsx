// src/components/OsDistribution.tsx
import { Row, Col } from 'antd';
import { Pie } from 'react-chartjs-2';
import { Chart, ActiveElement } from 'chart.js';
import { DashboardStats } from '../types/schemas';

interface OsDistributionProps {
  clientOsData: DashboardStats['os_stats']['client_os'];
  serverOsData: DashboardStats['os_stats']['server_os'];
  onOsClick: (os: string, isClientOs: boolean) => void;
}

const OsDistribution: React.FC<OsDistributionProps> = ({ clientOsData, serverOsData, onOsClick }) => {
  const clientOsChartData = {
    labels: clientOsData.map(os => os.category) || [],
    datasets: [
      {
        data: clientOsData.map(os => os.count) || [],
        backgroundColor: ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF'],
      },
    ],
  };

  const serverOsChartData = {
    labels: serverOsData.map(os => os.category) || [],
    datasets: [
      {
        data: serverOsData.map(os => os.count) || [],
        backgroundColor: ['#FF9F40', '#FFCD56', '#C9CB3F', '#36A2EB'],
      },
    ],
  };

  const handlePieClick = (elements: ActiveElement[], chart: Chart, isClientOs: boolean) => {
    if (!elements.length) return;
    const index = elements[0].index;
    const os = chart.data.labels?.[index];
    if (typeof os === 'string') {
      onOsClick(os, isClientOs);
    }
  };

  return (
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
                plugins: {
                  legend: { position: 'top' },
                  tooltip: { enabled: true },
                },
                onClick: (event, elements, chart) => handlePieClick(elements, chart, true),
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
                plugins: {
                  legend: { position: 'top' },
                  tooltip: { enabled: true },
                },
                onClick: (event, elements, chart) => handlePieClick(elements, chart, false),
              }}
            />
          </div>
        ) : (
          <p>Немає даних про серверні ОС</p>
        )}
      </Col>
    </Row>
  );
};

export default OsDistribution;