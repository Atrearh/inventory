// src/components/StatusStats.tsx
import { Table } from 'antd';
import { DashboardStats } from '../types/schemas';

interface StatusStatsProps {
  statusStats: DashboardStats['scan_stats']['status_stats'];
}

const StatusStats: React.FC<StatusStatsProps> = ({ statusStats }) => {
  const statusColumns = [
    { title: 'Статус', dataIndex: 'status', key: 'status' },
    { title: 'Кількість', dataIndex: 'count', key: 'count' },
  ];

  return (
    <div style={{ marginTop: '16px' }}>
      <h3>Статистика статусів комп'ютерів</h3>
      <Table
        columns={statusColumns}
        dataSource={statusStats}
        rowKey="status"
        size="middle"
        locale={{ emptyText: 'Немає даних' }}
        pagination={false}
      />
    </div>
  );
};

export default StatusStats;