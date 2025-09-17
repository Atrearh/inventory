import { Table, Card, Space, Tag } from 'antd';
import { memo } from 'react';
import { useTranslation } from 'react-i18next';
import { ComputerDetail, PhysicalDisk, LogicalDisk, VideoCard } from '../types/schemas';

interface HardwareInfoProps {
  computer: ComputerDetail;
}

const HardwareInfo: React.FC<HardwareInfoProps> = ({ computer }) => {
  const { t } = useTranslation();

  // Сортування даних: спочатку невидалені (removed_on === null), потім за датою видалення (останні актуальні зверху)
  const sortByDeletion = <T extends { removed_on?: string | null }>(data: T[]): T[] => {
    return data.sort((a, b) => {
      if (!a.removed_on && b.removed_on) return -1;
      if (a.removed_on && !b.removed_on) return 1;
      if (a.removed_on && b.removed_on) {
        return (b.removed_on || '').localeCompare(a.removed_on || '');
      }
      return 0;
    });
  };

  const physicalDiskColumns = [
    { title: t('model', 'Модель'), dataIndex: 'model', key: 'model' },
    { title: t('serial_number', 'Серийный номер'), dataIndex: 'serial', key: 'serial' },
    { title: t('interface', 'Интерфейс'), dataIndex: 'interface', key: 'interface' },
    {
      title: t('status', 'Статус'),
      dataIndex: 'removed_on',
      key: 'status',
      render: (removedOn: string | null) =>
        removedOn ? (
          <Tag color="red">
            {t('deleted', 'Видалено')} ({new Date(removedOn).toLocaleDateString()})
          </Tag>
        ) : (
          <Tag color="green">{t('active', 'Активно')}</Tag>
        ),
    },
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
        `${(val / 1024 ** 3).toFixed(2)} ${t('gb', 'ГБ')} (${rec.total_space ? ((val * 100) / rec.total_space).toFixed(1) : 0}%)`,
    },
    {
      title: t('status', 'Статус'),
      dataIndex: 'removed_on',
      key: 'status',
      render: (removedOn: string | null) =>
        removedOn ? (
          <Tag color="red">
            {t('deleted', 'Видалено')} ({new Date(removedOn).toLocaleDateString()})
          </Tag>
        ) : (
          <Tag color="green">{t('active', 'Активно')}</Tag>
        ),
    },
  ];

  const videoCardColumns = [
    { title: t('name', 'Название'), dataIndex: 'Name', key: 'Name' }, // Змінено dataIndex на 'Name' відповідно до типу
    {
      title: t('ram', 'Обсяг пам\'яті'),
      dataIndex: 'AdapterRAM',
      key: 'AdapterRAM',
      render: (val: number | null) => (val ? `${(val / 1024 ** 3).toFixed(2)} ${t('gb', 'ГБ')}` : '-'),
    },
    {
      title: t('status', 'Статус'),
      dataIndex: 'removed_on',
      key: 'status',
      render: (removedOn: string | null) =>
        removedOn ? (
          <Tag color="red">
            {t('deleted', 'Видалено')} ({new Date(removedOn).toLocaleDateString()})
          </Tag>
        ) : (
          <Tag color="green">{t('active', 'Активно')}</Tag>
        ),
    },
  ];

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      {!computer.is_virtual && (
        <Card title={t('physical_disks', 'Физические диски')}>
          <Table
            dataSource={sortByDeletion(computer.physical_disks ?? [])}
            columns={physicalDiskColumns}
            rowKey="serial"
            pagination={computer.physical_disks && computer.physical_disks.length > 5 ? { pageSize: 5 } : false}
            size="small"
          />
        </Card>
      )}
      <Card title={t('logical_disks', 'Логические диски')}>
        <Table
          dataSource={sortByDeletion(computer.logical_disks ?? [])}
          columns={logicalDiskColumns}
          rowKey="device_id"
          pagination={computer.logical_disks && computer.logical_disks.length > 5 ? { pageSize: 5 } : false}
          size="small"
        />
      </Card>
      {!computer.is_virtual && (
        <Card title={t('video_cards', 'Видеокарты')}>
          <Table
            dataSource={sortByDeletion(computer.video_cards ?? [])}
            columns={videoCardColumns}
            rowKey="Name"
            pagination={computer.video_cards && computer.video_cards.length > 5 ? { pageSize: 5 } : false}
            size="small"
          />
        </Card>
      )}
    </Space>
  );
};

export default memo(HardwareInfo);