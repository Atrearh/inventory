// src/components/ComputerDetail.tsx
import { useQuery } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import { getComputers, getHistory } from '../api/api';
import { Computer, ChangeLog, Role, Software, Disk } from '../types/schemas';
import { useState, useEffect } from 'react';
import { CSVLink } from 'react-csv';
import { Skeleton, notification, Typography, Table } from 'antd';
import GeneralInfo from './GeneralInfo';
import styles from './ComputerDetail.module.css';
import type { TableProps } from 'antd';

const { Title } = Typography;

interface SortState {
  key: string;
  sort_order: 'asc' | 'desc';
}

const ComputerDetail: React.FC = () => {
  const { computerId } = useParams<{ computerId: string }>();
  const [sort, setSort] = useState<SortState>({ key: '', sort_order: 'asc' });
  const [softwarePage, setSoftwarePage] = useState(1);
  const [historyPage, setHistoryPage] = useState(1);

  const { data: computerData, error: compError, isLoading: compLoading } = useQuery({
    queryKey: ['computers', computerId],
    queryFn: async () => getComputers({ id: computerId }),
    enabled: !!computerId,
  });

  const computer = computerData?.data?.[0] || null;

  const { data: history = [], error: histError, isLoading: histLoading } = useQuery({
    queryKey: ['history', computerId],
    queryFn: () => getHistory(Number(computerId)),
    enabled: !!computerId,
  });

  useEffect(() => {
    if (compError) {
      notification.error({
        message: 'Ошибка загрузки данных компьютера',
        description: compError.message,
      });
    }
    if (histError) {
      notification.error({
        message: 'Ошибка загрузки истории изменений',
        description: histError.message,
      });
    }
  }, [compError, histError]);

  const handleSort = (key: string) => {
    setSort((prev) => ({
      key,
      sort_order: prev.key === key && prev.sort_order === 'asc' ? 'desc' : 'asc',
    }));
  };

  const softwareCsvData = computer?.software?.map((item: Software) => ({
    DisplayName: item?.DisplayName ?? '',
    DisplayVersion: item?.DisplayVersion ?? '',
    InstallDate: item?.InstallDate ? new Date(item.InstallDate).toLocaleString('ru-RU') : '',
  })) || [];

  const historyCsvData = history.map((item: ChangeLog) => ({
    Field: item?.field ?? '',
    OldValue: item?.old_value ?? '',
    NewValue: item?.new_value ?? '',
    ChangedAt: item?.changed_at ? new Date(item.changed_at).toLocaleString('ru-RU') : '',
  }));

  if (compLoading || histLoading) {
    return <Skeleton active paragraph={{ rows: 10 }} />;
  }
  if (compError || histError) {
    return <div className={styles.error}>Ошибка: {(compError || histError)?.message}</div>;
  }
  if (!computer) {
    return <div className={styles.empty}>Компьютер не найден</div>;
  }

  const roleColumns: TableProps<Role>['columns'] = [
    {
      title: 'Имя',
      dataIndex: 'Name',
      key: 'Name',
      sorter: true,
      sortOrder: sort.key === 'Name' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : null,
      onHeaderCell: () => ({
        onClick: () => handleSort('Name'),
      }),
    },
  ];

  const softwareColumns: TableProps<Software>['columns'] = [
    {
      title: 'Имя',
      dataIndex: 'DisplayName',
      key: 'DisplayName',
      sorter: true,
      sortOrder: sort.key === 'DisplayName' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : null,
      onHeaderCell: () => ({
        onClick: () => handleSort('DisplayName'),
      }),
    },
    {
      title: 'Версия',
      dataIndex: 'DisplayVersion',
      key: 'DisplayVersion',
      render: (value) => value ?? '-',
      sorter: true,
      sortOrder: sort.key === 'DisplayVersion' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : null,
      onHeaderCell: () => ({
        onClick: () => handleSort('DisplayVersion'),
      }),
    },
    {
      title: 'Дата установки',
      dataIndex: 'InstallDate',
      key: 'InstallDate',
      render: (value) => (value ? new Date(value).toLocaleString('ru-RU') : '-'),
      sorter: true,
      sortOrder: sort.key === 'InstallDate' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : null,
      onHeaderCell: () => ({
        onClick: () => handleSort('InstallDate'),
      }),
    },
  ];

  const diskColumns: TableProps<Disk>['columns'] = [
    {
      title: 'ID',
      dataIndex: 'DeviceID',
      key: 'DeviceID',
      sorter: true,
      sortOrder: sort.key === 'DeviceID' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : null,
      onHeaderCell: () => ({
        onClick: () => handleSort('DeviceID'),
      }),
    },
    {
      title: 'Объем',
      dataIndex: 'TotalSpace',
      key: 'TotalSpace',
      render: (value) => `${value ?? '-'} MB`,
      sorter: true,
      sortOrder: sort.key === 'TotalSpace' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : null,
      onHeaderCell: () => ({
        onClick: () => handleSort('TotalSpace'),
      }),
    },
    {
      title: 'Свободно',
      dataIndex: 'FreeSpace',
      key: 'FreeSpace',
      render: (value, record) =>
        `${value ?? '-'} MB (${value && record.TotalSpace ? ((value / record.TotalSpace) * 100).toFixed(2) : '0'}%)`,
      sorter: true,
      sortOrder: sort.key === 'FreeSpace' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : null,
      onHeaderCell: () => ({
        onClick: () => handleSort('FreeSpace'),
      }),
    },
  ];

  const historyColumns: TableProps<ChangeLog>['columns'] = [
    {
      title: 'Поле',
      dataIndex: 'field',
      key: 'field',
      sorter: true,
      sortOrder: sort.key === 'field' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : null,
      onHeaderCell: () => ({
        onClick: () => handleSort('field'),
      }),
    },
    {
      title: 'Старое',
      dataIndex: 'old_value',
      key: 'old_value',
      render: (value) => value ?? '-',
      sorter: true,
      sortOrder: sort.key === 'old_value' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : null,
      onHeaderCell: () => ({
        onClick: () => handleSort('old_value'),
      }),
    },
    {
      title: 'Новое',
      dataIndex: 'new_value',
      key: 'new_value',
      render: (value) => value ?? '-',
      sorter: true,
      sortOrder: sort.key === 'new_value' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : null,
      onHeaderCell: () => ({
        onClick: () => handleSort('new_value'),
      }),
    },
    {
      title: 'Дата',
      dataIndex: 'changed_at',
      key: 'changed_at',
      render: (value) => (value ? new Date(value).toLocaleString('ru-RU') : '-'),
      sorter: true,
      sortOrder: sort.key === 'changed_at' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : null,
      onHeaderCell: () => ({
        onClick: () => handleSort('changed_at'),
      }),
    },
  ];

  return (
    <div className={styles.container}>
      <Title level={2} className={styles.title}>{computer.hostname}</Title>

      <GeneralInfo computer={computer} />

      <Title level={3} className={styles.subtitle}>Роли</Title>
      <Table
        dataSource={computer.roles || []}
        columns={roleColumns}
        rowKey="Name"
        pagination={false}
        locale={{ emptyText: 'Нет ролей' }}
        size="small"
      />

      <Title level={3} className={styles.subtitle}>Программное обеспечение</Title>
      {computer.software && computer.software.length > 0 ? (
        <>
          <CSVLink
            data={softwareCsvData}
            filename={`software_${computerId}.csv`}
            className={styles.csvLink}
            aria-label="Экспорт программного обеспечения в CSV"
          >
            Экспорт ПО в CSV
          </CSVLink>
          <Table
            dataSource={computer.software}
            columns={softwareColumns}
            rowKey="DisplayName"
            pagination={{
              current: softwarePage,
              pageSize: 10,
              total: computer.software.length,
              onChange: setSoftwarePage,
              showSizeChanger: false,
              showQuickJumper: false,
            }}
            locale={{ emptyText: 'Нет данных' }}
            size="small"
          />
        </>
      ) : (
        <div className={styles.empty}>Нет данных</div>
      )}

      <Title level={3} className={styles.subtitle}>Диски</Title>
      <Table
        dataSource={computer.disks || []}
        columns={diskColumns}
        rowKey="DeviceID"
        pagination={false}
        locale={{ emptyText: 'Нет данных о дисках' }}
        size="small"
      />

      <Title level={3} className={styles.subtitle}>История изменений</Title>
      {history.length > 0 ? (
        <>
          <CSVLink
            data={historyCsvData}
            filename={`history_${computerId}.csv`}
            className={styles.csvLink}
            aria-label="Экспорт истории изменений в CSV"
          >
            Экспорт истории в CSV
          </CSVLink>
          <Table
            dataSource={history}
            columns={historyColumns}
            rowKey="id"
            pagination={{
              current: historyPage,
              pageSize: 10,
              total: history.length,
              onChange: setHistoryPage,
              showSizeChanger: false,
              showQuickJumper: false,
            }}
            locale={{ emptyText: 'Нет данных об истории' }}
            size="small"
          />
        </>
      ) : (
        <div className={styles.empty}>Нет данных об истории</div>
      )}
    </div>
  );
};

export default ComputerDetail;