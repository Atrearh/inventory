import { Table } from 'antd';
import type { TableProps } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { SorterResult } from 'antd/es/table/interface';
import { AxiosError } from 'axios';
import { handleApiError } from '../utils/apiErrorHandler';
import { notification } from 'antd';
import { useTranslation } from 'react-i18next';

// Типізуємо props
interface ReusableTableProps<T extends { id: number }> {
  queryKey: string[];
  fetchData: (params: any) => Promise<{ data: T[]; total: number }>;
  columns: TableProps<T>['columns'];
  filters: Record<string, any>; // Об'єкт з фільтрами
  onTableChange: (pagination: any, filters: any, sorter: SorterResult<T> | SorterResult<T>[]) => void;
}

const ReusableTable = <T extends { id: number }>({
  queryKey,
  fetchData,
  columns,
  filters,
  onTableChange,
}: ReusableTableProps<T>) => {
  const { t } = useTranslation();

  const { data, isLoading, error } = useQuery({
    queryKey: [...queryKey, filters], // Ключ запиту залежить від фільтрів
    queryFn: () => fetchData(filters),
    //keepPreviousData: true, // Для плавної зміни сторінок
  });

  if (error) {
    const apiError = handleApiError(error as AxiosError, t('error_loading_data'));
    notification.error({ message: apiError.message });
    return <div>{apiError.message}</div>;
  }

  return (
    <Table
      loading={isLoading}
      dataSource={data?.data}
      columns={columns}
      rowKey="id"
      pagination={{
        current: filters.page,
        pageSize: filters.limit,
        total: data?.total || 0,
        showSizeChanger: true,
        showQuickJumper: true,
      }}
      onChange={onTableChange}
      locale={{ emptyText: t('no_data', 'Немає даних для відображення') }}
      size="small"
    />
  );
};

export default ReusableTable;