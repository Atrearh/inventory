import { Table } from 'antd';
import { Link } from 'react-router-dom';
import { DashboardStats } from '../types/schemas';

interface LowDiskSpaceProps {
  lowDiskSpace: DashboardStats['disk_stats']['low_disk_space'];
}

const LowDiskSpace: React.FC<LowDiskSpaceProps> = ({ lowDiskSpace }) => {
  // Логування для діагностики даних
  console.log('Дані low_disk_space:', lowDiskSpace);

  const diskColumns = [
    {
      title: 'Hostname',
      dataIndex: 'hostname',
      key: 'hostname',
      render: (hostname: string, record: DashboardStats['disk_stats']['low_disk_space'][0]) => (
        <Link to={`/computers/${record.id}`}>{hostname}</Link>
      ),
    },
    { title: 'Диск', dataIndex: 'disk_id', key: 'disk_id' },
    { title: 'Модель', dataIndex: 'model', key: 'model', render: (value: string) => value || 'Unknown' },
    {
      title: 'Загальний обсяг (ГБ)',
      dataIndex: 'total_space_gb',
      key: 'total_space_gb',
      render: (value: number) => value.toFixed(2),
    },
    {
      title: 'Вільний обсяг (ГБ)',
      dataIndex: 'free_space_gb',
      key: 'free_space_gb',
      render: (value: number) => value.toFixed(2),
    },
  ];

  return (
    <div style={{ marginTop: '16px' }}>
      <h3>Комп'ютери з низьким обсягом диска</h3>
      {lowDiskSpace.length > 0 ? (
        <Table
          columns={diskColumns}
          dataSource={lowDiskSpace}
          rowKey={(record) => `${record.id}-${record.disk_id}`}
          size="middle"
          locale={{ emptyText: 'Немає даних' }}
          pagination={false}
        />
      ) : (
        <p>Немає комп'ютерів з низьким обсягом диска.</p>
      )}
    </div>
  );
};

export default LowDiskSpace;