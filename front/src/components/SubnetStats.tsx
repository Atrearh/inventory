// src/components/SubnetStats.tsx
import { useQuery } from '@tanstack/react-query';
import { getComputers } from '../api/api';
import { ComputersResponse, ComputerListItem } from '../types/schemas';
import { useEffect, useState } from 'react';
import { Chart as ChartJS, ArcElement, Tooltip, Legend, ChartData, ChartOptions } from 'chart.js';
import { Pie } from 'react-chartjs-2';
import { notification, Table } from 'antd';
import { useAuth } from '../context/AuthContext';
import { AxiosError } from 'axios';

ChartJS.register(ArcElement, Tooltip, Legend);

interface SubnetStatsProps {
  onSubnetClick?: (subnet: string) => void;
}

const SubnetStats: React.FC<SubnetStatsProps> = ({ onSubnetClick }) => {
  const { isAuthenticated } = useAuth();
  const [subnetData, setSubnetData] = useState<{ subnet: string; count: number }[]>([]);

  const { data: computersData, isLoading, error, refetch } = useQuery<ComputersResponse, Error>({
    queryKey: ['computersForSubnets'],
    queryFn: () => getComputers({ page: 1, limit: 1000 }),
    enabled: isAuthenticated,
    refetchOnWindowFocus: false,
    staleTime: 60 * 60 * 1000,
    retry: 3,
    retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 30000),
  });

  useEffect(() => {
    if (error) {
      console.error('Query error:', error);
      if (error instanceof AxiosError && error.response?.data) {
        console.error('Server error details:', JSON.stringify(error.response.data, null, 2));
        notification.error({
          message: 'Ошибка загрузки данных',
          description: `Не удалось загрузить данные компьютеров: ${JSON.stringify(error.response.data.detail || error.message)}`,
        });
      } else {
        notification.error({
          message: 'Ошибка загрузки данных',
          description: `Не удалось загрузить данные компьютеров: ${error.message}`,
        });
      }
      console.log('Refetching computers data');
      refetch();
    }
    if (!isAuthenticated) {
      console.log('User is not authenticated');
      return;
    }
    if (computersData?.data && Array.isArray(computersData.data)) {
      const subnetMap = new Map<string, number>();
      computersData.data.forEach((computer: ComputerListItem) => {
        const ip = computer.ip_addresses?.[0]?.address;
        let subnet = 'Неизвестно';
        if (ip) {
          const match = ip.match(/^(\d+\.\d+)\.(\d+)\.\d+$/);
          if (match) {
            const baseIp = match[1];
            const thirdOctet = parseInt(match[2] || '0', 10);
            const subnetThirdOctet = thirdOctet - (thirdOctet % 2);
            subnet = `${baseIp}.${subnetThirdOctet}.0/23`;
          }
        }
        subnetMap.set(subnet, (subnetMap.get(subnet) || 0) + 1);
      });
      const subnets = Array.from(subnetMap.entries()).map(([subnet, count]) => ({ subnet, count }));
      console.log('Calculated subnet data:', subnets);
      setSubnetData(subnets);
    } else {
      console.log('No valid data received:', computersData);
    }
  }, [computersData, error, isAuthenticated, refetch]);

  if (!isAuthenticated) return <div>Требуется аутентификация</div>;
  if (isLoading) return <div>Загрузка...</div>;
  if (error) return <div style={{ color: 'red' }}>Ошибка: {error.message}</div>;
  if (!computersData || !computersData.data || !Array.isArray(computersData.data) || computersData.data.length === 0) {
    return <div>Нет данных о компьютерах для подсетей</div>;
  }

  const chartData: ChartData<'pie', number[], string> = {
    labels: subnetData.map((item) => item.subnet),
    datasets: [
      {
        label: 'Компьютеры по подсетям',
        data: subnetData.map((item) => item.count),
        backgroundColor: ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40'],
        borderColor: ['#fff'],
        borderWidth: 1,
      },
    ],
  };

  const chartOptions: ChartOptions<'pie'> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top' as const,
      },
      tooltip: {
        enabled: true,
      },
    },
    onClick: (e, elements, chart) => {
      if (elements.length && onSubnetClick) {
        const index = elements[0].index;
        const subnet = chart.data.labels?.[index];
        if (typeof subnet === 'string') {
          console.log('Clicked subnet:', subnet);
          onSubnetClick(subnet);
        }
      }
    },
  };

  const subnetColumns = [
    {
      title: 'Подсеть',
      dataIndex: 'subnet',
      key: 'subnet',
      render: (subnet: string) => (
        <a
          style={{ cursor: 'pointer', color: '#1890ff' }}
          onClick={() => {
            console.log('Clicked subnet in table:', subnet);
            onSubnetClick && onSubnetClick(subnet);
          }}
        >
          {subnet}
        </a>
      ),
    },
    { title: 'Количество компьютеров', dataIndex: 'count', key: 'count' },
  ];

  return (
    <div style={{ padding: 12 }}>
      <h2>Распределение компьютеров по подсетям (/23)</h2>
      {subnetData.length > 0 ? (
        <>
          <div style={{ height: 300, marginBottom: 24 }}>
            <Pie data={chartData} options={chartOptions} />
          </div>
          <Table
            columns={subnetColumns}
            dataSource={subnetData}
            rowKey="subnet"
            size="small"
            pagination={false}
            locale={{ emptyText: 'Нет данных' }}
          />
        </>
      ) : (
        <div>Нет данных о подсетях</div>
      )}
    </div>
  );
};

export default SubnetStats;