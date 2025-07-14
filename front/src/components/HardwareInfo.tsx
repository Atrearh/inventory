// src/components/HardwareInfo.tsx
import { Table, Card, Space } from 'antd';
import { Computer, PhysicalDisk, LogicalDisk, VideoCard } from '../types/schemas';

interface HardwareInfoProps {
  computer: Computer;
}

const HardwareInfo: React.FC<HardwareInfoProps> = ({ computer }) => {
  const physicalDiskColumns = [
    { title: 'Модель', dataIndex: 'model', key: 'model' },
    { title: 'Серийный номер', dataIndex: 'serial', key: 'serial' },
    { title: 'Интерфейс', dataIndex: 'interface', key: 'interface' },
  ];

  const logicalDiskColumns = [
    { title: 'ID', dataIndex: 'device_id', key: 'device_id' },
    { title: 'Метка', dataIndex: 'volume_label', key: 'volume_label' },
    { title: 'Объем', dataIndex: 'total_space', key: 'total_space', render: (val: number) => `${(val / 1024**3).toFixed(2)} ГБ` },
    { title: 'Свободно', dataIndex: 'free_space', key: 'free_space', render: (val: number, rec: LogicalDisk) => `${(val / 1024**3).toFixed(2)} ГБ (${rec.total_space ? (val * 100 / rec.total_space).toFixed(1) : 0}%)`},
  ];

  const videoCardColumns = [
    { title: 'Название', dataIndex: 'name', key: 'name' },
    { title: 'Версия драйвера', dataIndex: 'driver_version', key: 'driver_version' },
  ];

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      {!computer.is_virtual && (
        <Card title="Физические диски">
          <Table
            dataSource={computer.physical_disks}
            columns={physicalDiskColumns}
            rowKey="serial"
            pagination={false}
            size="small"
          />
        </Card>
      )}
      <Card title="Логические диски">
        <Table
          dataSource={computer.logical_disks}
          columns={logicalDiskColumns}
          rowKey="device_id"
          pagination={false}
          size="small"
        />
      </Card>
      {!computer.is_virtual && (
        <Card title="Видеокарты">
          <Table
            dataSource={computer.video_cards}
            columns={videoCardColumns}
            rowKey="name"
            pagination={false}
            size="small"
          />
        </Card>
      )}
    </Space>
  );
};

export default HardwareInfo;