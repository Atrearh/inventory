import { useQuery } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import { getComputerById, getHistory } from '../api/api';
import { Skeleton, Typography, Tabs, Card, Table, Space } from 'antd';
import GeneralInfo from './GeneralInfo';
import ActionPanel from './ActionPanel';
import HardwareInfo from './HardwareInfo';
import styles from './ComputerDetail.module.css';
import { differenceInDays } from 'date-fns';
import { ComponentHistory, Software } from '../types/schemas';
import { useAuth } from '../context/AuthContext';
import { useTimezone } from '../context/TimezoneContext'; 
import { formatDateInUserTimezone } from '../utils/formatDate';

const { Title } = Typography;

const ComputerDetail: React.FC = () => {
  const { computerId } = useParams<{ computerId: string }>();
  const computerIdNum = Number(computerId);
  const { isAuthenticated } = useAuth();
  const { timezone } = useTimezone();

  const { data: computer, error: compError, isLoading: compLoading } = useQuery({
    queryKey: ['computer', computerIdNum],
    queryFn: () => getComputerById(computerIdNum),
    enabled: !isNaN(computerIdNum) && isAuthenticated,
  });

  const { data: history = [], error: histError, isLoading: histLoading } = useQuery({
    queryKey: ['history', computerIdNum],
    queryFn: () => getHistory(computerIdNum),
    enabled: !isNaN(computerIdNum) && isAuthenticated,
  });

  if (isNaN(computerIdNum)) {
    return <div className={styles.error}>Неверный ID компьютера</div>;
  }

  if (compLoading) {
    return <Skeleton active />;
  }

  if (compError) {
    return <div className={styles.error}>Ошибка: {compError.message}</div>;
  }

  if (!computer) {
    return <div className={styles.error}>Компьютер не найден</div>;
  }

  const lastCheckDate = computer.last_updated ? new Date(computer.last_updated) : null;
  const daysDiff = lastCheckDate ? differenceInDays(new Date(), lastCheckDate) : Infinity;
  const lastCheckColor = daysDiff <= 7 ? '#52c41a' : daysDiff <= 30 ? '#faad14' : '#ff4d4f';

  const softwareColumns = [
    {
      title: 'Назва',
      dataIndex: 'DisplayName',
      key: 'DisplayName',
      sorter: (a: Software, b: Software) => a.DisplayName.localeCompare(b.DisplayName),
    },
    { title: 'Версия', dataIndex: 'DisplayVersion', key: 'DisplayVersion' },
    {
      title: 'Дата установки',
      dataIndex: 'InstallDate',
      key: 'InstallDate',
      render: (val: string) => formatDateInUserTimezone(val, timezone, 'dd.MM.yyyy'),
      sorter: (a: Software, b: Software) => new Date(a.InstallDate || 0).getTime() - new Date(b.InstallDate || 0).getTime(),
    },
  ];

  const historyColumns = [
    { title: 'Тип компонента', dataIndex: 'component_type', key: 'component_type' },
    { title: 'Детали', key: 'details', render: (_: any, rec: ComponentHistory) => JSON.stringify(rec.data) },
    {
      title: 'Дата обнаружения',
      dataIndex: 'detected_on',
      key: 'detected_on',
      render: (val: string) => formatDateInUserTimezone(val, timezone),
    },
    {
      title: 'Дата удаления',
      dataIndex: 'removed_on',
      key: 'removed_on',
      render: (val: string) => formatDateInUserTimezone(val, timezone),
    },
  ];

  const tabItems = [
    {
      key: '1',
      label: 'Обзор',
      children: (
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <Card title="Общая информация">
            <GeneralInfo computer={computer} lastCheckDate={lastCheckDate} lastCheckColor={lastCheckColor} />
          </Card>
          <Card title="Действия">
            <ActionPanel hostname={computer.hostname} />
          </Card>
        </Space>
      ),
    },
    {
      key: '2',
      label: 'Оборудование',
      children: <HardwareInfo computer={computer} />,
    },
    {
      key: '3',
      label: 'Программы',
      children: (
        <Card>
          <Table
            dataSource={computer.software}
            columns={softwareColumns}
            rowKey={(rec) => `${rec.DisplayName}-${rec.DisplayVersion}`}
            pagination={{ pageSize: 15 }}
          />
        </Card>
      ),
    },
    {
      key: '4',
      label: 'История',
      children: (
        <Card>
          <Table
            dataSource={history}
            columns={historyColumns}
            rowKey={(rec) => `${rec.component_type}-${rec.detected_on || ''}-${rec.removed_on || ''}`} // Уникальный ключ без индекса
            loading={histLoading}
            pagination={{ pageSize: 15 }}
          />
        </Card>
      ),
    },
  ];

  return (
    <div className={styles.container}>
      <Title level={2} className={styles.title}>
        {computer.hostname}
      </Title>
      <Tabs defaultActiveKey="1" items={tabItems} />
    </div>
  ); 
};

export default ComputerDetail; 