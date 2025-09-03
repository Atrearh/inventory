import { Table, Card, Space } from 'antd';
import { memo } from 'react';
import { useTranslation } from 'react-i18next';
import { Computer, PhysicalDisk, LogicalDisk, VideoCard } from '../types/schemas';

interface HardwareInfoProps {
  computer: Computer;
}

const HardwareInfo: React.FC<HardwareInfoProps> = ({ computer }) => {
  const { t } = useTranslation();

  const physicalDiskColumns = [
    { title: t('model', 'Модель'), dataIndex: 'model', key: 'model' },
    { title: t('serial_number', 'Серийный номер'), dataIndex: 'serial', key: 'serial' },
    { title: t('interface', 'Интерфейс'), dataIndex: 'interface', key: 'interface' },
  ];

  const logicalDiskColumns = [
    { title: t('id', 'ID'), dataIndex: 'device_id', key: 'device_id' },
    { title: t('volume_label', 'Метка'), dataIndex: 'volume_label', key: 'volume_label' },
    {
      title: t('total_space', 'Объем'),
      dataIndex: 'total_space',
      key: 'total_space',
      render: (val: number) => `${(val / 1024 ** 3).toFixed(2)} ${t('gb', 'ГБ')}`,
    },
    {
      title: t('free_space', 'Свободно'),
      dataIndex: 'free_space',
      key: 'free_space',
      render: (val: number, rec: LogicalDisk) =>
        `${(val / 1024 ** 3).toFixed(2)} ${t('gb', 'ГБ')} (${rec.total_space ? (val * 100 / rec.total_space).toFixed(1) : 0}%)`,
    },
  ];

  const videoCardColumns = [
    { title: t('name', 'Название'), dataIndex: 'name', key: 'name' },
    { title: t('driver_version', 'Версия драйвера'), dataIndex: 'driver_version', key: 'driver_version' },
  ];

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      {!computer.is_virtual && (
        <Card title={t('physical_disks', 'Физические диски')}>
          <Table
            dataSource={computer.physical_disks}
            columns={physicalDiskColumns}
            rowKey="serial"
            pagination={false}
            size="small"
          />
        </Card>
      )}
      <Card title={t('logical_disks', 'Логические диски')}>
        <Table
          dataSource={computer.logical_disks}
          columns={logicalDiskColumns}
          rowKey="device_id"
          pagination={false}
          size="small"
        />
      </Card>
      {!computer.is_virtual && (
        <Card title={t('video_cards', 'Видеокарты')}>
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

export default memo(HardwareInfo);