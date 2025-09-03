import { Input, Select, Button, Checkbox } from 'antd';
import { useRef } from 'react';
import { InputRef } from 'antd';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { Filters } from '../hooks/useComputerFilters';
import { DashboardStats, DomainRead } from '../types/schemas';
import styles from './ComputerList.module.css';
import { getDomains } from '../api/domain.api';

interface ComputerFiltersPanelProps {
  filters: Filters;
  statsData?: DashboardStats;
  isStatsLoading: boolean;
  debouncedSetHostname: (value: string | undefined) => void;
  handleFilterChange: (key: keyof Filters, value: string | boolean | undefined) => void;
  clearAllFilters: () => void;
}

const ComputerFiltersPanel: React.FC<ComputerFiltersPanelProps> = ({
  filters,
  statsData,
  isStatsLoading,
  debouncedSetHostname,
  handleFilterChange,
  clearAllFilters,
}) => {
  const { t } = useTranslation();
  const inputRef = useRef<InputRef>(null);

  // Запит для отримання доменів
  const { data: domainsData, isLoading: isDomainsLoading } = useQuery({
    queryKey: ['domains'],
    queryFn: getDomains,
  });

  const osOptions = statsData?.os_stats.client_os.map((os) => ({
    label: os.category,
    value: os.category,
  })) || [];

  const domainOptions = domainsData?.map((domain) => ({
    label: domain.name,
    value: domain.name,
  })) || [];

  return (
    <div className={styles.filters}>
      <Input
        ref={inputRef}
        placeholder={t('enter_hostname', 'Фільтр за ім’ям хоста (пошук за початком)')}
        value={filters.hostname}
        onChange={(e) => debouncedSetHostname(e.target.value)}
        className={styles.filterInput}
        allowClear
      />
      <Select
        value={filters.os_name || undefined}
        onChange={(value) => handleFilterChange('os_name', value)}
        className={styles.filterSelect}
        placeholder={t('select_os', 'Оберіть ОС')}
        loading={isStatsLoading}
        showSearch
        optionFilterProp="children"
        options={[{ label: t('all_os', 'Усі ОС'), value: '' }, ...osOptions]}
        allowClear
      />
      <Select
        value={filters.check_status || undefined}
        onChange={(value) => handleFilterChange('check_status', value)}
        className={styles.filterSelect}
        placeholder={t('select_status', 'Усі статуси')}
        options={[
          { label: t('all_statuses', 'Усі статуси'), value: '' },
          { label: t('status_success', 'Успішно'), value: 'success' },
          { label: t('status_failed', 'Невдало'), value: 'failed' },
          { label: t('status_unreachable', 'Недоступно'), value: 'unreachable' },
          { label: t('status_partially_successful', 'Частково успішно'), value: 'partially_successful' },
          ...(filters.show_disabled
            ? [
                { label: t('status_disabled', 'Відключено'), value: 'disabled' },
                { label: t('status_is_deleted', 'Видалено'), value: 'is_deleted' },
              ]
            : []),
        ]}
        allowClear
      />
      <Select
        value={filters.domain || undefined}
        onChange={(value) => handleFilterChange('domain', value)}
        className={styles.filterSelect}
        placeholder={t('select_domain', 'Оберіть домен')}
        showSearch
        optionFilterProp="children"
        options={[{ label: t('all_domains', 'Усі домени'), value: '' }, ...domainOptions]}
        loading={isDomainsLoading}
        allowClear
      />
      <Checkbox
        checked={filters.show_disabled}
        onChange={(e) => handleFilterChange('show_disabled', e.target.checked)}
        style={{ marginLeft: 8 }}
      >
        {t('show_disabled', 'Показувати відключені та видалені')}
      </Checkbox>
      <Button onClick={clearAllFilters} style={{ marginLeft: 8 }}>
        {t('clear_filters', 'Очистити всі фільтри')}
      </Button>
    </div>
  );
};

export default ComputerFiltersPanel;