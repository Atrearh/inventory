// src/components/ComputerDetail.tsx
import { useQuery } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import { getComputerById, getHistory } from '../api/api';
import { Computer, ChangeLog, Role, Software, Disk } from '../types/schemas';
import { useState } from 'react';
import { Skeleton, Typography, Table, Button, Collapse } from 'antd';
import GeneralInfo from './GeneralInfo';
import styles from './ComputerDetail.module.css';
import type { TableProps } from 'antd';
import { differenceInDays } from 'date-fns';

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

  const historyCsvData = history.map((item: ChangeLog) => ({
    Field: item?.field ?? '',
    OldValue: item?.old_value ?? '',
    NewValue: item?.new_value ?? '',
    ChangedAt: item?.changed_at ? new Date(item.changed_at).toLocaleString('uk-UA') : '',
  }));

  if (compLoading || histLoading) {
    return <Skeleton active paragraph={{ rows: 10 }} />;
  }
  if (compError || histError) {
    return <div className={styles.error}>Помилка: {(compError || histError)?.message}</div>;
  }
  if (!computer) {
    return <div className={styles.empty}>Комп'ютер не знайдено</div>;
  }

  const isServerOS = computer.os_name?.toLowerCase().includes('server');
  const currentDate = new Date('2025-06-20T09:08:00+03:00'); // Текущая дата и время

  // Статистика
  const roleCount = computer.roles?.length || 0;
  const softwareCount = computer.software?.length || 0;
  const historyCount = history.length;
  const lastCheck = history.length > 0
    ? new Date(Math.max(...history.map((h) => new Date(h.changed_at).getTime()))).toLocaleString('uk-UA')
    : 'Немає даних';

  // Групування ролей
  const groupedRoles = computer.roles?.reduce((acc, role) => {
    const [roleType, ...components] = role.Name.split('-');
    if (!acc[roleType]) acc[roleType] = [];
    if (components.length > 0) acc[roleType].push(components.join('-'));
    return acc;
  }, {} as Record<string, string[]>);

  const roleColumns: TableProps<Role>['columns'] = [
    {
      title: 'Ім’я',
      dataIndex: 'Name',
      key: 'Name',
      sorter: true,
      sortOrder: sort.key === 'Name' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : null,
      onHeaderCell: () => ({ onClick: () => handleSort('Name') }),
    },
  ];

  const softwareColumns: TableProps<Software>['columns'] = [
    {
      title: 'Ім’я',
      dataIndex: 'DisplayName',
      key: 'DisplayName',
      sorter: true,
      sortOrder: sort.key === 'DisplayName' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : null,
      onHeaderCell: () => ({ onClick: () => handleSort('DisplayName') }),
    },
    {
      title: 'Версія',
      dataIndex: 'DisplayVersion',
      key: 'DisplayVersion',
      render: (value) => value ?? '-',
      sorter: true,
      sortOrder: sort.key === 'DisplayVersion' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : null,
      onHeaderCell: () => ({ onClick: () => handleSort('DisplayVersion') }),
    },
    {
      title: 'Дата встановлення',
      dataIndex: 'InstallDate',
      key: 'InstallDate',
      render: (value) => (value ? new Date(value).toLocaleString('uk-UA') : '-'),
      sorter: true,
      sortOrder: sort.key === 'InstallDate' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : null,
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
      sortOrder: sort.key === 'isNew' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : null,
      onHeaderCell: () => ({ onClick: () => handleSort('isNew') }),
    },
    {
      title: 'Видалено',
      key: 'isDeleted',
      render: (_: any, record: Software) => (record.is_deleted ? 'Так' : '-'),
      sorter: true,
      sortOrder: sort.key === 'isDeleted' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : null,
      onHeaderCell: () => ({ onClick: () => handleSort('isDeleted') }),
    },
  ];

  const diskColumns: TableProps<Disk>['columns'] = [
    {
      title: 'ID',
      dataIndex: 'DeviceID',
      key: 'DeviceID',
      sorter: true,
      sortOrder: sort.key === 'DeviceID' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : null,
      onHeaderCell: () => ({ onClick: () => handleSort('DeviceID') }),
    },
    {
      title: 'Обсяг',
      dataIndex: 'TotalSpace',
      key: 'TotalSpace',
      render: (value) => `${value ?? '-'} MB`,
      sorter: true,
      sortOrder: sort.key === 'TotalSpace' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : null,
      onHeaderCell: () => ({ onClick: () => handleSort('TotalSpace') }),
    },
    {
      title: 'Вільно',
      dataIndex: 'FreeSpace',
      key: 'FreeSpace',
      render: (value, record) => `${value ?? '-'} MB (${value && record.TotalSpace ? ((value / record.TotalSpace) * 100).toFixed(2) : '0'}%)`,
      sorter: true,
      sortOrder: sort.key === 'FreeSpace' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : null,
      onHeaderCell: () => ({ onClick: () => handleSort('FreeSpace') }),
    },
  ];

  const historyColumns: TableProps<ChangeLog>['columns'] = [
    {
      title: 'Поле',
      dataIndex: 'field',
      key: 'field',
      sorter: true,
      sortOrder: sort.key === 'field' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : null,
      onHeaderCell: () => ({ onClick: () => handleSort('field') }),
    },
    {
      title: 'Старе',
      dataIndex: 'old_value',
      key: 'old_value',
      render: (value) => value ?? '-',
      sorter: true,
      sortOrder: sort.key === 'old_value' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : null,
      onHeaderCell: () => ({ onClick: () => handleSort('old_value') }),
    },
    {
      title: 'Нове',
      dataIndex: 'new_value',
      key: 'new_value',
      render: (value) => value ?? '-',
      sorter: true,
      sortOrder: sort.key === 'new_value' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : null,
      onHeaderCell: () => ({ onClick: () => handleSort('new_value') }),
    },
    {
      title: 'Дата',
      dataIndex: 'changed_at',
      key: 'changed_at',
      render: (value) => (value ? new Date(value).toLocaleString('uk-UA') : '-'),
      sorter: true,
      sortOrder: sort.key === 'changed_at' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : null,
      onHeaderCell: () => ({ onClick: () => handleSort('changed_at') }),
    },
  ];

  const toggleSection = (section: SectionKey) => {
    setCollapsedSections((prev) => ({ ...prev, [section]: !prev[section] }));
  };

  return (
    <div className={styles.container}>
      <Title level={2} className={styles.title}>{computer.hostname}</Title>
      <GeneralInfo computer={computer} />
      <div>
        <Title level={3} className={styles.subtitle}>Диски</Title>
        <Table
          dataSource={computer.disks || []}
          columns={diskColumns}
          rowKey={(record) => record.DeviceID}
          pagination={false}
          locale={{ emptyText: 'Немає даних про диски' }}
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
                rowKey={(record) => `${record.DisplayName}-${record.DisplayVersion}-${record.InstallDate || ''}`}
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
        <Text>Кількість змін: {historyCount}, Остання перевірка: {lastCheck}</Text>
        {!collapsedSections.history && (
          <>
            {history.length > 0 ? (
              <Table
                dataSource={history}
                columns={historyColumns}
                rowKey="id"
                pagination={{ current: historyPage, pageSize: 10, total: history.length, onChange: setHistoryPage, showSizeChanger: false, showQuickJumper: false }}
                locale={{ emptyText: 'Немає даних про історію' }}
                size="small"
              />
            ) : <div className={styles.empty}>Немає даних про історію</div>}
          </>
        )}
      </div>
    </div>
  );
};

export default ComputerDetail;