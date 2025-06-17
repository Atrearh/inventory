// src/components/ComputerDetail.tsx
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import { getComputers, getHistory } from '../api/api';
import { Computer, ChangeLog, Role, Software, Disk } from '../types/schemas';
import { useState, useEffect } from 'react';
import { CSVLink } from 'react-csv';
import { Skeleton, notification, Typography, Table, Button } from 'antd';
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
    const queryClient = useQueryClient();
    const [sort, setSort] = useState<SortState>({ key: '', sort_order: 'asc' });
    const [softwarePage, setSoftwarePage] = useState(1);
    const [historyPage, setHistoryPage] = useState(1);

    const computerIdNum = Number(computerId);
    if (isNaN(computerIdNum)) {
        return <div className={styles.error}>Неверный ID компьютера</div>;
    }

    const { data: computerData, error: compError, isLoading: compLoading } = useQuery({
        queryKey: ['computers', computerIdNum],
        queryFn: async () => {
            const response = await getComputers({ id: String(computerIdNum) });
            const uniqueComputer = response.data?.length > 1 
                ? response.data.find((c: Computer) => Number(c.id) === computerIdNum) || response.data[0]
                : response.data?.[0] || null;
            return { data: uniqueComputer ? [uniqueComputer] : [] };
        },
        enabled: !!computerId && !isNaN(computerIdNum),
        refetchOnWindowFocus: false,
        refetchOnReconnect: false,
        staleTime: 5 * 60 * 1000,
    });

    const computer = computerData?.data?.[0] || null;

    const { data: history = [], error: histError, isLoading: histLoading } = useQuery({
        queryKey: ['history', computerIdNum],
        queryFn: async () => await getHistory(computerIdNum),
        enabled: !!computerId && !isNaN(computerIdNum),
        refetchOnWindowFocus: false,
        refetchOnReconnect: false,
        staleTime: 5 * 60 * 1000,
    });

    useEffect(() => {
        return () => {
            queryClient.invalidateQueries({ queryKey: ['computers'] });
            queryClient.invalidateQueries({ queryKey: ['history'] });
        };
    }, [computerId, queryClient]);

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

    const clearCache = () => {
        queryClient.invalidateQueries({ queryKey: ['computers'] });
        queryClient.invalidateQueries({ queryKey: ['history'] });
        notification.success({ message: 'Кэш очищен' });
    };

    const handleSort = (key: string) => {
        setSort((prev) => ({
            key,
            sort_order: prev.key === key && prev.sort_order === 'asc' ? 'desc' : 'asc',
        }));
    };

    const softwareCsvData = computer?.software?.map((item: Software) => ({
        Name: item?.name ?? '',
        Version: item?.version ?? '',
        InstallDate: item?.install_date ? new Date(item.install_date).toLocaleString('ru-RU') : '',
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
            dataIndex: 'name',
            key: 'name',
            sorter: true,
            sortOrder: sort.key === 'name' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : null,
            onHeaderCell: () => ({
                onClick: () => handleSort('name'),
            }),
        },
    ];

    const softwareColumns: TableProps<Software>['columns'] = [
        {
            title: 'Имя',
            dataIndex: 'name',
            key: 'name',
            sorter: true,
            sortOrder: sort.key === 'name' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : null,
            onHeaderCell: () => ({
                onClick: () => handleSort('name'),
            }),
        },
        {
            title: 'Версия',
            dataIndex: 'version',
            key: 'version',
            render: (value) => value ?? '-',
            sorter: true,
            sortOrder: sort.key === 'version' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : null,
            onHeaderCell: () => ({
                onClick: () => handleSort('version'),
            }),
        },
        {
            title: 'Дата установки',
            dataIndex: 'install_date',
            key: 'install_date',
            render: (value) => (value ? new Date(value).toLocaleString('ru-RU') : '-'),
            sorter: true,
            sortOrder: sort.key === 'install_date' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : null,
            onHeaderCell: () => ({
                onClick: () => handleSort('install_date'),
            }),
        },
    ];

    const diskColumns: TableProps<Disk>['columns'] = [
        {
            title: 'ID',
            dataIndex: 'device_id',
            key: 'device_id',
            sorter: true,
            sortOrder: sort.key === 'device_id' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : null,
            onHeaderCell: () => ({
                onClick: () => handleSort('device_id'),
            }),
        },
        {
            title: 'Объем',
            dataIndex: 'total_space',
            key: 'total_space',
            render: (value) => `${value ?? '-'} MB`,
            sorter: true,
            sortOrder: sort.key === 'total_space' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : null,
            onHeaderCell: () => ({
                onClick: () => handleSort('total_space'),
            }),
        },
        {
            title: 'Свободно',
            dataIndex: 'free_space',
            key: 'free_space',
            render: (value, record) =>
                `${value ?? '-'} MB (${value && record.total_space ? ((value / record.total_space) * 100).toFixed(2) : '0'}%)`,
            sorter: true,
            sortOrder: sort.key === 'free_space' ? (sort.sort_order === 'asc' ? 'ascend' : 'descend') : null,
            onHeaderCell: () => ({
                onClick: () => handleSort('free_space'),
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
            <Button onClick={clearCache}>Очистить кэш</Button>
            <GeneralInfo computer={computer} />
            <Title level={3} className={styles.subtitle}>Роли</Title>
            <Table
                dataSource={computer.roles ? [...new Map(computer.roles.map(item => [item.Name, item])).values()] : []}
                columns={roleColumns}
                rowKey="name"
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
                        dataSource={computer.software ? [...new Map(computer.software.map(item => [item.name, item])).values()] : []}
                        columns={softwareColumns}
                        rowKey="name"
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
                dataSource={computer.disks ? [...new Map(computer.disks.map(item => [item.device_id, item])).values()] : []}
                columns={diskColumns}
                rowKey="device_id"
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