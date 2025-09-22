import { Input, Select, Button, Checkbox } from "antd";
import { useRef } from "react";
import { InputRef } from "antd";
import { useTranslation } from "react-i18next";
import { Filters } from "../hooks/useComputerFilters";
import { DashboardStats, DomainRead } from "../types/schemas";
import styles from "./ComputerList.module.css";

interface ComputerFiltersPanelProps {
  filters: Filters;
  statsData?: DashboardStats;
  isStatsLoading: boolean;
  domainsData?: DomainRead[];
  isDomainsLoading: boolean;
  debouncedSetHostname: (value: string | undefined) => void;
  debouncedSetOsName: (value: string | undefined) => void;
  debouncedSetDomain: (value: string | undefined) => void;
  debouncedSetCheckStatus: (value: string | undefined) => void;
  handleFilterChange: (
    key: keyof Filters,
    value: string | boolean | undefined,
  ) => void;
  clearAllFilters: () => void;
  handleExportCSV: () => void; // Додаємо пропс
}

const CHECK_STATUS_OPTIONS = [
  { labelKey: "all_statuses", value: "", defaultLabel: "Усі статуси" },
  { labelKey: "status_success", value: "success", defaultLabel: "Успішно" },
  { labelKey: "status_failed", value: "failed", defaultLabel: "Невдало" },
  {
    labelKey: "status_unreachable",
    value: "unreachable",
    defaultLabel: "Недоступно",
  },
  {
    labelKey: "status_partially_successful",
    value: "partially_successful",
    defaultLabel: "Частково успішно",
  },
  {
    labelKey: "status_disabled",
    value: "disabled",
    defaultLabel: "Відключено",
  },
  {
    labelKey: "status_is_deleted",
    value: "is_deleted",
    defaultLabel: "Видалено",
  },
];

const ComputerFiltersPanel: React.FC<ComputerFiltersPanelProps> = ({
  filters,
  statsData,
  isStatsLoading,
  domainsData,
  isDomainsLoading,
  debouncedSetHostname,
  debouncedSetOsName,
  debouncedSetDomain,
  debouncedSetCheckStatus,
  handleFilterChange,
  clearAllFilters,
  handleExportCSV, // Додаємо пропс
}) => {
  const { t } = useTranslation();
  const inputRef = useRef<InputRef>(null);

  const osOptions: { label: string; value: string }[] =
    statsData?.os_stats?.client_os?.map((os) => ({
      label: os.category,
      value: os.category,
    })) || [];

  const domainOptions: { label: string; value: string }[] =
    domainsData?.map((domain) => ({
      label: domain.name,
      value: domain.name,
    })) || [];

  return (
    <div className={styles.filters}>
      <Input
        ref={inputRef}
        placeholder={t(
          "enter_hostname",
          "Фільтр за ім’ям хоста (пошук за початком)",
        )}
        value={filters.hostname}
        onChange={(e) => debouncedSetHostname(e.target.value)}
        className={styles.filterInput}
        allowClear
      />
      <Select
        value={filters.os_name || undefined}
        onChange={(value) => debouncedSetOsName(value)}
        className={styles.filterSelect}
        placeholder={t("select_os", "Оберіть ОС")}
        loading={isStatsLoading}
        showSearch
        optionFilterProp="children"
        options={[{ label: t("all_os", "Усі ОС"), value: "" }, ...osOptions]}
        allowClear
      />
      <Select
        value={filters.check_status || undefined}
        onChange={(value) => debouncedSetCheckStatus(value)}
        className={styles.filterSelect}
        placeholder={t("select_status", "Усі статуси")}
        options={CHECK_STATUS_OPTIONS.map((opt) => ({
          label: t(opt.labelKey, opt.defaultLabel),
          value: opt.value,
        }))}
        allowClear
      />
      <Select
        value={filters.domain || undefined}
        onChange={(value) => debouncedSetDomain(value)}
        className={styles.filterSelect}
        placeholder={t("select_domain", "Оберіть домен")}
        showSearch
        optionFilterProp="children"
        options={[
          { label: t("all_domains", "Усі домени"), value: "" },
          ...domainOptions,
        ]}
        loading={isDomainsLoading}
        allowClear
      />
      <Checkbox
        checked={filters.show_disabled}
        onChange={(e) => handleFilterChange("show_disabled", e.target.checked)}
        style={{ marginLeft: 8 }}
      >
        {t("show_disabled", "Показувати відключені та видалені")}
      </Checkbox>
      <Button onClick={clearAllFilters} style={{ marginLeft: 8 }}>
        {t("clear_filters", "Очистити всі фільтри")}
      </Button>
      <Button
        type="primary"
        onClick={handleExportCSV}
        className={styles.csvButton}
        style={{ marginLeft: 8 }}
      >
        {t("export_csv", "Експорт у CSV")}
      </Button>
    </div>
  );
};

export default ComputerFiltersPanel;
