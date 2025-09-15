import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import { getComputerById, getHistory, executeScript } from '../api/api';
import { Skeleton, Typography, Tabs, Card, Table, Space, Button, Modal, notification } from 'antd';
import GeneralInfo from './GeneralInfo';
import ActionPanel from './ActionPanel';
import HardwareInfo from './HardwareInfo';
import styles from './ComputerDetail.module.css';
import { differenceInDays } from 'date-fns';
import { ComponentHistory, Software } from '../types/schemas';
import { useAuth } from '../context/AuthContext';
import { useTimezone } from '../context/TimezoneContext';
import { formatDateInUserTimezone } from '../utils/formatDate';
import { useTranslation } from 'react-i18next';
import { handleApiError } from '../utils/apiErrorHandler';
import { useErrorHandler } from '../hooks/useErrorHandler';
import { useState } from 'react';

const { Title } = Typography;

const ComputerDetail: React.FC = () => {
  const { t } = useTranslation();
  const { computerId } = useParams<{ computerId: string }>();
  const computerIdNum = Number(computerId);
  const { isAuthenticated } = useAuth();
  const { timezone } = useTimezone();
  const queryClient = useQueryClient();
  const handleError = useErrorHandler();
  const [isLoading, setIsLoading] = useState(false);

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

  const handleUninstall = async (hostname: string, programName: string) => {
    Modal.confirm({
      title: t('confirm_uninstall', 'Видалити програму {programName}?'),
      okButtonProps: { loading: isLoading },
      onOk: async () => {
        setIsLoading(true);
        try {
          const response = await executeScript(hostname, 'uninstall_program.ps1', { ProgramName: programName });
          if (!response.Success) {
            throw new Error(response.Errors?.join(", ") || response.error || 'Unknown error');
          }
          queryClient.invalidateQueries({ queryKey: ['computer', computerIdNum] });
          notification.success({
            message: t('success'),
            description: t('program_uninstalled', { programName }),
          });
        } catch (error) {
          handleError(error, t('failed_to_uninstall', { programName }));
        } finally {
          setIsLoading(false);
        }
      },
    });
  };

  if (isNaN(computerIdNum)) {
    return <div className={styles.error}>{t('invalid_computer_id')}</div>;
  }

  if (compLoading) {
    return <Skeleton active />;
  }

  if (compError) {
    return <div className={styles.error}>{t('error')}: {handleApiError(compError).message}</div>;
  }

  if (!computer) {
    return <div className={styles.error}>{t('computer_not_found')}</div>;
  }

  const lastCheckDate = computer.last_updated ? new Date(computer.last_updated) : null;
  const daysDiff = lastCheckDate ? differenceInDays(new Date(), lastCheckDate) : Infinity;
  const lastCheckColor = daysDiff <= 7 ? '#52c41a' : daysDiff <= 30 ? '#faad14' : '#ff4d4f';

  const softwareColumns = [
    {
      title: t('name'),
      dataIndex: 'DisplayName',
      key: 'DisplayName',
      sorter: (a: Software, b: Software) => a.DisplayName.localeCompare(b.DisplayName),
    },
    { title: t('version'), dataIndex: 'DisplayVersion', key: 'DisplayVersion' },
    {
      title: t('install_date'),
      dataIndex: 'InstallDate',
      key: 'InstallDate',
      render: (val: string) => formatDateInUserTimezone(val, timezone, 'dd.MM.yyyy'),
      sorter: (a: Software, b: Software) => new Date(a.InstallDate || 0).getTime() - new Date(b.InstallDate || 0).getTime(),
    },
    {
      title: t('actions'),
      key: 'actions',
      render: (_: any, record: Software) => (
        <Button
          type="primary"
          danger
          onClick={() => handleUninstall(computer.hostname, record.DisplayName)}
        >
          {t('delete')}
        </Button>
      ),
    },
  ];

  const historyColumns = [
    { title: t('component_type'), dataIndex: 'component_type', key: 'component_type' },
    { title: t('details'), key: 'details', render: (_: any, rec: ComponentHistory) => JSON.stringify(rec.data) },
    {
      title: t('detected_on'),
      dataIndex: 'detected_on',
      key: 'detected_on',
      render: (val: string) => formatDateInUserTimezone(val, timezone),
    },
    {
      title: t('removed_on'),
      dataIndex: 'removed_on',
      key: 'removed_on',
      render: (val: string) => formatDateInUserTimezone(val, timezone),
    },
  ];

  const tabItems = [
    {
      key: '1',
      label: t('overview'),
      children: (
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <Card>
            <GeneralInfo computer={computer} lastCheckDate={lastCheckDate} lastCheckColor={lastCheckColor} />
          </Card>
          <Card title={t('actions')}>
            <ActionPanel hostname={computer.hostname} />
          </Card>
        </Space>
      ),
    },
    {
      key: '2',
      label: t('hardware'),
      children: <HardwareInfo computer={computer} />,
    },
    {
      key: '3',
      label: t('software'),
      children: (
        <Card>
          <Table
            dataSource={computer.software}
            columns={softwareColumns}
            rowKey={(rec) => `${rec.DisplayName}-${rec.DisplayVersion}`}
            pagination={{ pageSize: 15 }}
            locale={{ emptyText: t('no_data') }}
          />
        </Card>
      ),
    },
    {
      key: '4',
      label: t('history'),
      children: (
        <Card>
          <Table
            dataSource={history}
            columns={historyColumns}
            rowKey={(rec) => `${rec.component_type}-${rec.detected_on || ''}-${rec.removed_on || ''}`}
            loading={histLoading}
            pagination={{ pageSize: 15 }}
            locale={{ emptyText: t('no_data') }}
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