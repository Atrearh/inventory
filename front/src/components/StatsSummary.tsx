import { Card } from 'antd';
import { DashboardStats } from '../types/schemas';

interface StatsSummaryProps {
  totalComputers: number | undefined;
  lastScanTime: string | null;
}

const StatsSummary: React.FC<StatsSummaryProps> = ({ totalComputers, lastScanTime }) => (
  <Card title="Загальна статистика" bordered style={{ marginBottom: 16 }}>
    {totalComputers !== undefined && (
      <p>
        <strong>Всього комп'ютерів:</strong> {totalComputers}
      </p>
    )}
    {lastScanTime && (
      <p>
        <strong>Останнє сканування:</strong>{' '}
        {new Date(lastScanTime).toLocaleString('uk-UA')}
      </p>
    )}
  </Card>
);

export default StatsSummary;