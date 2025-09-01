// src/components/ComputerFiltersPanel.tsx
import { Input, Select, Button, Checkbox } from 'antd';
import { useRef } from 'react';
import { InputRef } from 'antd';
import { Filters } from '../hooks/useComputerFilters';
import { DashboardStats } from '../types/schemas';
import styles from './ComputerList.module.css';

interface ComputerFiltersPanelProps {
  filters: Filters;
  statsData?: DashboardStats;
  isStatsLoading: boolean;
  debouncedSetHostname: (value: string) => void;
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
  const inputRef = useRef<InputRef>(null);

  return (
    <div className={styles.filters}>
      <Input
        ref={inputRef}
        placeholder="Фільтр за ім’ям хоста (пошук за початком)"
        defaultValue={filters.hostname}
        onChange={(e) => debouncedSetHostname(e.target.value)}
        className={styles.filterInput}
        allowClear
      />
      <Select
        value={filters.os_name || ''}
        onChange={(value) => handleFilterChange('os_name', value)}
        className={styles.filterSelect}
        placeholder="Оберіть ОС"
        loading={isStatsLoading}
        showSearch
        optionFilterProp="children"
      >
        <Select.Option value="">Усі ОС</Select.Option>
        {[...new Set([...(statsData?.os_stats.client_os.map((item) => item.category) || []), ...(statsData?.os_stats.server_os.map((item) => item.category) || [])])].map(
          (os: string) => (
            <Select.Option key={os} value={os}>
              {os}
            </Select.Option>
          )
        )}
      </Select>
      <Select
        value={filters.check_status || ''}
        onChange={(value) => handleFilterChange('check_status', value)}
        className={styles.filterSelect}
        placeholder="Усі статуси"
      >
        <Select.Option value="">Усі статуси</Select.Option>
        <Select.Option value="success">Успішно</Select.Option>
        <Select.Option value="failed">Невдало</Select.Option>
        <Select.Option value="unreachable">Недоступно</Select.Option>
        <Select.Option value="partially_successful">Частково успішно</Select.Option>
        {filters.show_disabled && <Select.Option value="disabled">Відключено</Select.Option>}
        {filters.show_disabled && <Select.Option value="is_deleted">Видалено</Select.Option>}
      </Select>
      <Checkbox
        checked={filters.show_disabled}
        onChange={(e) => handleFilterChange('show_disabled', e.target.checked)}
        style={{ marginLeft: 8 }}
      >
        Показувати відключені та видалені
      </Checkbox>
      <Button onClick={clearAllFilters} style={{ marginLeft: 8 }}>
        Очистити всі фільтри
      </Button>
    </div>
  );
};

export default ComputerFiltersPanel;