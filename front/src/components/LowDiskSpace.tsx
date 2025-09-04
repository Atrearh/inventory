// front/src/components/LowDiskSpace.tsx
import { Table } from 'antd';
import { Link } from 'react-router-dom';
import { DashboardStats } from '../types/schemas';

interface LowDiskSpaceProps {
  lowDiskSpace: DashboardStats['disk_stats']['low_disk_space'];
  emptyComponent?: React.ReactNode; // Додаємо проп для порожнього стану
}

const LowDiskSpace: React.FC<LowDiskSpaceProps> = ({ lowDiskSpace, emptyComponent }) => {

  // Фільтрація комп'ютерів з низьким обсягом диска (менше або дорівнює 1024 ГБ)
  const filteredLowDiskSpace = lowDiskSpace.filter(
    (disk) => disk.free_space_gb !== undefined && disk.free_space_gb <= 1024
  );

  const diskColumns = [
    {
      title: 'Hostname',
      dataIndex: 'hostname',
      key: 'hostname',
      render: (hostname: string, record: DashboardStats['disk_stats']['low_disk_space'][0]) => (
        <Link to={`/computer/${record.id}`}>{hostname || 'Невідомо'}</Link>
      ),
    },
    { title: 'Диск', dataIndex: 'disk_id', key: 'disk_id' },
    { title: 'Модель', dataIndex: 'model', key: 'model', render: (value: string) => value || 'Unknown' },
    {
      title: 'Загальний обсяг (ГБ)',
      dataIndex: 'total_space_gb',
      key: 'total_space_gb',
      render: (value: number) => (value !== undefined ? value.toFixed(2) : 'Н/Д'),
    },
    {
      title: 'Вільний обсяг (ГБ)',
      dataIndex: 'free_space_gb',
      key: 'free_space_gb',
      render: (value: number) => (value !== undefined ? value.toFixed(2) : 'Н/Д'),
    },
  ];

  if (!lowDiskSpace || lowDiskSpace.length === 0) {
    return emptyComponent || <p style={{ color: 'red' }}>Дані про низький обсяг диска відсутні</p>;
  }

  return (
    <div style={{ marginTop: '16px' }}>
      <h3>Комп'ютери з низьким обсягом диска</h3>
      {filteredLowDiskSpace.length > 0 ? (
        <Table
          columns={diskColumns}
          dataSource={filteredLowDiskSpace}
          rowKey={(record) => `${record.id}-${record.disk_id}`}
          size="middle"
          locale={{ emptyText: emptyComponent || 'Немає даних' }}
          pagination={false}
        />
      ) : (
        emptyComponent || <p>Немає комп'ютерів з низьким обсягом диска.</p>
      )}
    </div>
  );
};

export default LowDiskSpace;