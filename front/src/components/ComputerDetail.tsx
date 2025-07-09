import { useQuery } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import { getComputerById, getHistory, startHostScan } from '../api/api';
import { useState } from 'react';
import { Skeleton, Typography, Table, Button, Collapse, message } from 'antd';
import GeneralInfo from './GeneralInfo';
import styles from './ComputerDetail.module.css';
import type { TableProps } from 'antd';
import { differenceInDays } from 'date-fns';
import { Computer, ComponentHistory, Role, Software, PhysicalDisk, LogicalDisk, Processor, VideoCard, IPAddress, MACAddress } from '../types/schemas';
const { Title, Text } = Typography;
const { Panel } = Collapse;

interface SortState {
  key: string;
  sort_order: 'asc' | 'desc';
}

type SectionKey = 'roles' | 'software' | 'history';

const ComputerDetail: React.FC = () => {
  const { computerId } = useParams<{ computerId: string }>();
  const [sort, setSort] = useState<SortState>({ key: '', sort_order: 'asc' });
  const [softwarePage, setSoftwarePage] = useState(1);
  const [historyPage, setHistoryPage] = useState(1);
  const [collapsedSections, setCollapsedSections] = useState<{
    roles: boolean;
    software: boolean;
    history: boolean;
  }>({
    roles: true,
    software: true,
    history: true,
  });

  const computerIdNum = Number(computerId);
  if (isNaN(computerIdNum)) {
    return <div className={styles.error}>Невірний ID комп'ютера</div>;
  }

  const { data: computer, error: compError, isLoading: compLoading } = useQuery({
    queryKey: ['computer', computerIdNum],
    queryFn: () => getComputerById(computerIdNum),
    enabled: !!computerId,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 5 * 60 * 1000,
  });

  const { data: history = [], error: histError, isLoading: histLoading } = useQuery({
    queryKey: ['history', computerIdNum],
    queryFn: () => getHistory(computerIdNum),
    enabled: !!computerId,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 5 * 60 * 1000,
  });

  const handleSort = (key: string) => {
    setSort((prev) => ({
      key,
      sort_order: prev.key === key && prev.sort_order === 'asc' ? 'desc' : 'asc',
    }));
  };

  const isServerOS = computer?.os_name?.toLowerCase().includes('server');
  const isVirtualServer = isServerOS && computer?.is_virtual;
  const currentDate = new Date();

  // Время последней проверки
  const lastCheckDate = computer?.last_updated ? new Date(computer.last_updated) : null;
  const daysDiff = lastCheckDate ? differenceInDays(currentDate, lastCheckDate) : Infinity;
  let lastCheckColor = '';
  if (daysDiff <= 7) lastCheckColor = '#52c41a'; // Зеленый
  else if (daysDiff <= 30) lastCheckColor = '#faad14'; // Желтый
  else lastCheckColor = '#ff4d4f'; // Красный

  // Статистика
  const roleCount = computer?.roles?.length || 0;
  const softwareCount = computer?.software?.length || 0;
  const historyCount = history.length;

  // Групування ролей
  const groupedRoles = computer?.roles?.reduce((acc, role) => {
    const [roleType, ...components] = role.Name.split('-');
    if (!acc[roleType]) acc[roleType] = [];
    if (components.length > 0) acc[roleType].push(components.join('-'));
    return acc;
  }, {} as Record<string, string[]>);

  // Обработчик для запуска сканирования
  const handleScanHost = async () => {
    if (!computer?.hostname) {
        message.error('Hostname не найден');
        return;
    }
    try {
        const response = await startHostScan(computer.hostname);
        message.success(`Сканирование начато, task_id: ${response.task_id}`);
    } catch (error: any) {
        message.error(`Ошибка при запуске сканирования: ${error.response?.data?.error || error.message}`);
        console.error(error);
    }
};

  const roleColumns: TableProps<Role>['columns'] = [
    {
      title: 'Ім’я',
      dataIndex: 'Name',
      key: 'Name',
      sorter: true,
      sortOrder: sort.key === 'Name' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : undefined,
      onHeaderCell: () => ({ onClick: () => handleSort('Name') }),
    },
  ];

  const softwareColumns: TableProps<Software>['columns'] = [
    {
      title: 'Ім’я',
      dataIndex: 'DisplayName',
      key: 'DisplayName',
      sorter: true,
      sortOrder: sort.key === 'DisplayName' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : undefined,
      onHeaderCell: () => ({ onClick: () => handleSort('DisplayName') }),
    },
    {
      title: 'Версія',
      dataIndex: 'DisplayVersion',
      key: 'DisplayVersion',
      render: (value) => value ?? '-',
      sorter: true,
      sortOrder: sort.key === 'DisplayVersion' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : undefined,
      onHeaderCell: () => ({ onClick: () => handleSort('DisplayVersion') }),
    },
    {
      title: 'Дата встановлення',
      dataIndex: 'InstallDate',
      key: 'InstallDate',
      render: (value) => (value ? new Date(value).toLocaleString('uk-UA') : '-'),
      sorter: true,
      sortOrder: sort.key === 'InstallDate' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : undefined,
      onHeaderCell: () => ({ onClick: () => handleSort('InstallDate') }),
    },
    {
      title: 'Нове',
      key: 'isNew',
      render: (_: any, record: Software) => {
        if (record.InstallDate) {
          const installDate = new Date(record.InstallDate);
          const daysDiff = differenceInDays(currentDate, installDate);
          return daysDiff <= 2 ? 'Так' : '-';
        }
        return '-';
      },
      sorter: true,
      sortOrder: sort.key === 'isNew' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : undefined,
      onHeaderCell: () => ({ onClick: () => handleSort('isNew') }),
    },
    {
      title: 'Видалено',
      key: 'isDeleted',
      render: (_: any, record: Software) => (record.removed_on ? 'Так' : '-'),
      sorter: true,
      sortOrder: sort.key === 'isDeleted' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : undefined,
      onHeaderCell: () => ({ onClick: () => handleSort('isDeleted') }),
    },
  ];

  const physicalDiskColumns: TableProps<PhysicalDisk>['columns'] = [
    {
      title: 'Модель',
      dataIndex: 'model',
      key: 'model',
      sorter: true,
      sortOrder: sort.key === 'model' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : undefined,
      onHeaderCell: () => ({ onClick: () => handleSort('model') }),
    },
    {
      title: 'Серийный номер',
      dataIndex: 'serial',
      key: 'serial',
      sorter: true,
      sortOrder: sort.key === 'serial' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : undefined,
      onHeaderCell: () => ({ onClick: () => handleSort('serial') }),
    },
    {
      title: 'Интерфейс',
      dataIndex: 'interface',
      key: 'interface',
      sorter: true,
      sortOrder: sort.key === 'interface' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : undefined,
      onHeaderCell: () => ({ onClick: () => handleSort('interface') }),
    },
  ];

  const logicalDiskColumns: TableProps<LogicalDisk>['columns'] = [
    {
      title: 'ID',
      dataIndex: 'device_id',
      key: 'device_id',
      sorter: true,
      sortOrder: sort.key === 'device_id' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : undefined,
      onHeaderCell: () => ({ onClick: () => handleSort('device_id') }),
    },
    {
      title: 'Метка тома',
      dataIndex: 'volume_label',
      key: 'volume_label',
      sorter: true,
      sortOrder: sort.key === 'volume_label' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : undefined,
      onHeaderCell: () => ({ onClick: () => handleSort('volume_label') }),
    },
    {
      title: 'Обсяг',
      dataIndex: 'total_space',
      key: 'total_space',
      render: (value) => `${value ? (value / (1024 * 1024 * 1024)).toFixed(2) : '-'} ГБ`,
      sorter: true,
      sortOrder: sort.key === 'total_space' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : undefined,
      onHeaderCell: () => ({ onClick: () => handleSort('total_space') }),
    },
    {
      title: 'Вільно',
      dataIndex: 'free_space',
      key: 'free_space',
      render: (value, record) => `${value ? (value / (1024 * 1024 * 1024)).toFixed(2) : '-'} ГБ (${value && record.total_space ? ((value / record.total_space) * 100).toFixed(2) : '0'}%)`,
      sorter: true,
      sortOrder: sort.key === 'free_space' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : undefined,
      onHeaderCell: () => ({ onClick: () => handleSort('free_space') }),
    },
  ];

  const videoCardColumns: TableProps<VideoCard>['columns'] = [
    {
      title: 'Назва',
      dataIndex: 'name',
      key: 'name',
      sorter: true,
      sortOrder: sort.key === 'name' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : undefined,
      onHeaderCell: () => ({ onClick: () => handleSort('name') }),
    },
    {
      title: 'Версія драйвера',
      dataIndex: 'driver_version',
      key: 'driver_version',
      render: (value) => value ?? '-',
      sorter: true,
      sortOrder: sort.key === 'driver_version' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : undefined,
      onHeaderCell: () => ({ onClick: () => handleSort('driver_version') }),
    },
    {
      title: 'Дата виявлення',
      dataIndex: 'detected_on',
      key: 'detected_on',
      render: (value) => (value ? new Date(value).toLocaleString('uk-UA') : '-'),
      sorter: true,
      sortOrder: sort.key === 'detected_on' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : undefined,
      onHeaderCell: () => ({ onClick: () => handleSort('detected_on') }),
    },
    {
      title: 'Дата видалення',
      dataIndex: 'removed_on',
      key: 'removed_on',
      render: (value) => (value ? new Date(value).toLocaleString('uk-UA') : '-'),
      sorter: true,
      sortOrder: sort.key === 'removed_on' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : undefined,
      onHeaderCell: () => ({ onClick: () => handleSort('removed_on') }),
    },
  ];

  const historyColumns: TableProps<ComponentHistory>['columns'] = [
    {
      title: 'Тип компонента',
      dataIndex: 'component_type',
      key: 'component_type',
      sorter: true,
      sortOrder: sort.key === 'component_type' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : undefined,
      onHeaderCell: () => ({ onClick: () => handleSort('component_type') }),
      render: (value) => {
        const typeMap: Record<string, string> = {
          physical_disk: 'Физический диск',
          logical_disk: 'Логический диск',
          processor: 'Процесор',
          video_card: 'Відеокарта',
          ip_address: 'IP-адреса',
          mac_address: 'MAC-адреса',
          software: 'Програмне забезпечення',
        };
        return typeMap[value] || value;
      },
    },
    {
      title: 'Ідентифікатор',
      key: 'identifier',
      render: (_, record) => {
        const data = record.data;
        if (record.component_type === 'physical_disk') return (data as PhysicalDisk).serial || '-';
        if (record.component_type === 'logical_disk') return (data as LogicalDisk).device_id || '-';
        if (record.component_type === 'processor' || record.component_type === 'video_card') return (data as Processor | VideoCard).name || '-';
        if (record.component_type === 'ip_address' || record.component_type === 'mac_address') return (data as IPAddress | MACAddress).address || '-';
        if (record.component_type === 'software') return (data as Software).DisplayName || '-';
        return '-';
      },
      sorter: true,
      sortOrder: sort.key === 'identifier' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : undefined,
      onHeaderCell: () => ({ onClick: () => handleSort('identifier') }),
    },
    {
      title: 'Деталі',
      key: 'details',
      render: (_, record) => {
        const data = record.data;
        if (record.component_type === 'physical_disk') {
          const disk = data as PhysicalDisk;
          return `Модель: ${disk.model || '-'}, Интерфейс: ${disk.interface || '-'}`;
        }
        if (record.component_type === 'logical_disk') {
          const disk = data as LogicalDisk;
          return `Метка: ${disk.volume_label || '-'}, Обсяг: ${(disk.total_space / (1024 * 1024 * 1024)).toFixed(2)} ГБ, Вільно: ${disk.free_space ? (disk.free_space / (1024 * 1024 * 1024)).toFixed(2) : '-'} ГБ`;
        }
        if (record.component_type === 'processor') {
          const processor = data as Processor;
          return `Ядер: ${processor.number_of_cores}, Логічних процесорів: ${processor.number_of_logical_processors}`;
        }
        if (record.component_type === 'video_card') {
          const videoCard = data as VideoCard;
          return `Версія драйвера: ${videoCard.driver_version || '-'}`;
        }
        if (record.component_type === 'ip_address' || record.component_type === 'mac_address') {
          return (data as IPAddress | MACAddress).address || '-';
        }
        if (record.component_type === 'software') {
          const software = data as Software;
          return `Версія: ${software.DisplayVersion || '-'}, Дата встановлення: ${software.InstallDate ? new Date(software.InstallDate).toLocaleString('uk-UA') : '-'}`;
        }
        return '-';
      },
    },
    {
      title: 'Дата виявлення',
      dataIndex: 'detected_on',
      key: 'detected_on',
      render: (value) => (value ? new Date(value).toLocaleString('uk-UA') : '-'),
      sorter: true,
      sortOrder: sort.key === 'detected_on' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : undefined,
      onHeaderCell: () => ({ onClick: () => handleSort('detected_on') }),
    },
    {
      title: 'Дата видалення',
      dataIndex: 'removed_on',
      key: 'removed_on',
      render: (value) => (value ? new Date(value).toLocaleString('uk-UA') : '-'),
      sorter: true,
      sortOrder: sort.key === 'removed_on' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : undefined,
      onHeaderCell: () => ({ onClick: () => handleSort('removed_on') }),
    },
  ];

  const toggleSection = (section: SectionKey) => {
    setCollapsedSections((prev) => ({ ...prev, [section]: !prev[section] }));
  };

  return (
    <div className={styles.container}>
      {compLoading ? (
        <Skeleton active />
      ) : compError ? (
        <div className={styles.error}>Помилка: {(compError as any)?.response?.data?.error || compError.message || 'Невідома помилка'}</div>
      ) : !computer ? (
        <div className={styles.error}>Комп'ютер не знайдено</div>
      ) : (
        <>
          <div style={{ position: 'sticky', top: 0, zIndex: 10, background: '#fff', padding: '8px 0', marginBottom: 16 }}>
            <Button type="primary" onClick={handleScanHost}>
              Сканувати хост
            </Button>
          </div>
          <Title level={2} className={styles.title}>{computer.hostname || 'Завантаження...'}</Title>
          <GeneralInfo computer={computer} lastCheckDate={lastCheckDate} lastCheckColor={lastCheckColor} />
          {!isVirtualServer && (
            <>
              <div>
                <Title level={3} className={styles.subtitle}>Физические диски</Title>
                <Table
                  dataSource={computer.physical_disks || []}
                  columns={physicalDiskColumns}
                  rowKey={(record) => record.serial ?? 'unknown-physical-disk'}
                  pagination={false}
                  locale={{ emptyText: 'Немає даних про физические диски' }}
                  size="small"
                />
              </div>
              <div>
                <Title level={3} className={styles.subtitle}>Відеокарти</Title>
                <Table
                  dataSource={computer.video_cards || []}
                  columns={videoCardColumns}
                  rowKey={(record) => record.name ?? 'unknown-video-card'}
                  pagination={false}
                  locale={{ emptyText: 'Немає даних про відеокарти' }}
                  size="small"
                />
              </div>
            </>
          )}
          <div>
            <Title level={3} className={styles.subtitle}>Логические диски</Title>
            <Table
              dataSource={computer.logical_disks || []}
              columns={logicalDiskColumns}
              rowKey={(record) => record.device_id ?? 'unknown-logical-disk'}
              pagination={false}
              locale={{ emptyText: 'Немає даних про логические диски' }}
              size="small"
            />
          </div>
          {isServerOS && (
            <div>
              <Title level={3} className={styles.subtitle}>Ролі</Title>
              <Button onClick={() => toggleSection('roles')} style={{ marginBottom: 8 }}>
                {collapsedSections.roles ? 'Показати всі ролі' : 'Сховати ролі'}
              </Button>
              <Text>Кількість ролей: {roleCount}</Text>
              {!collapsedSections.roles && groupedRoles && (
                <Collapse>
                  {Object.entries(groupedRoles).map(([roleType, components]) => (
                    <Panel header={roleType} key={roleType}>
                      <ul>
                        {components.map((component, index) => (
                          <li key={`${roleType}-${component}-${index}`}>{component}</li>
                        ))}
                      </ul>
                    </Panel>
                  ))}
                </Collapse>
              )}
            </div>
          )}
          <div>
            <Title level={3} className={styles.subtitle}>Програмне забезпечення</Title>
            <Button onClick={() => toggleSection('software')} style={{ marginBottom: 8 }}>
              {collapsedSections.software ? 'Показати все ПЗ' : 'Сховати ПЗ'}
            </Button>
            <Text>Кількість програм: {softwareCount}</Text>
            {!collapsedSections.software && (
              <>
                {computer.software && computer.software.length > 0 ? (
                  <Table
                    dataSource={computer.software}
                    columns={softwareColumns}
                    rowKey={(record) => `${record.DisplayName}-${record.DisplayVersion || ''}-${record.InstallDate || ''}`}
                    pagination={{ current: softwarePage, pageSize: 10, total: computer.software.length, onChange: setSoftwarePage, showSizeChanger: false, showQuickJumper: false }}
                    locale={{ emptyText: 'Немає даних' }}
                    size="small"
                  />
                ) : <div className={styles.empty}>Немає даних</div>}
              </>
            )}
          </div>
          <div>
            <Title level={3} className={styles.subtitle}>Історія змін</Title>
            <Button onClick={() => toggleSection('history')} style={{ marginBottom: 8 }}>
              {collapsedSections.history ? 'Показати всю історію' : 'Сховати історію'}
            </Button>
            <Text>Кількість змін: {historyCount}, Остання перевірка: {lastCheckDate ? lastCheckDate.toLocaleString('uk-UA') : 'Немає даних'}</Text>
            {!collapsedSections.history && (
              <>
                {history.length > 0 ? (
                  <Table
                    dataSource={history}
                    columns={historyColumns}
                    rowKey={(record) => {
                      const data = record.data;
                      if (record.component_type === 'physical_disk') return `${record.component_type}-${(data as PhysicalDisk).serial || 'unknown'}`;
                      if (record.component_type === 'logical_disk') return `${record.component_type}-${(data as LogicalDisk).device_id || 'unknown'}`;
                      if (record.component_type === 'processor' || record.component_type === 'video_card') return `${record.component_type}-${(data as Processor | VideoCard).name || 'unknown'}`;
                      if (record.component_type === 'ip_address' || record.component_type === 'mac_address') return `${record.component_type}-${(data as IPAddress | MACAddress).address || 'unknown'}`;
                      if (record.component_type === 'software') return `${record.component_type}-${(data as Software).DisplayName || 'unknown'}`;
                      return `${record.component_type}-unknown`;
                    }}
                    pagination={{ current: historyPage, pageSize: 10, total: history.length, onChange: setHistoryPage, showSizeChanger: false, showQuickJumper: false }}
                    locale={{ emptyText: 'Немає даних про історію' }}
                    size="small"
                  />
                ) : <div className={styles.empty}>Немає даних про історію</div>}
              </>
            )}
          </div>
        </>
      )}
    </div>
  );
};

export default ComputerDetail;