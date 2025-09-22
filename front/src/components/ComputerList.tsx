import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useNavigate, Link } from "react-router-dom";
import { useState, useEffect, useMemo } from "react";
import { notification, Skeleton, Table, Button } from "antd";
import { useExportCSV } from "../hooks/useExportCSV";
import { useComputers, useStatistics } from "../hooks/useApiQueries";
import type { TableProps } from "antd";
import styles from "./ComputerList.module.css";
import { useComputerFilters } from "../hooks/useComputerFilters";
import ComputerFiltersPanel from "./ComputerFiltersPanel";
import ActionPanel from "./ActionPanel";
import { AxiosError } from "axios";
import { useAppContext } from "../context/AppContext";
import { formatDateInUserTimezone } from "../utils/formatDate";
import { getDomains } from "../api/domain.api";
import { ComputerListItem, OperatingSystemRead } from "../types/schemas";

const ComputerListComponent: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { timezone } = useAppContext();
  const { setPageTitle } = useAppContext();
  const [cachedComputers, setCachedComputers] = useState<ComputerListItem[]>([]);
  const [selectedHostnames, setSelectedHostnames] = useState<string[]>([]);

  const { data: domainsData, isLoading: isDomainsLoading } = useQuery({
    queryKey: ["domains"],
    queryFn: getDomains,
  });

  const domainMap = useMemo(() => {
    const map = new Map<number, string>();
    domainsData?.forEach((domain) => {
      map.set(domain.id, domain.name);
    });
    return map;
  }, [domainsData]);

  const {
    filters,
    filteredComputers,
    debouncedSetHostname,
    handleFilterChange,
    clearAllFilters,
    handleTableChange,
  } = useComputerFilters(cachedComputers, domainMap);

  const {
    data: computersData,
    error: computersError,
    isLoading: isComputersLoading,
  } = useComputers({
    ...filters,
    hostname: undefined,
    os_name: undefined,
    check_status: undefined,
    sort_by: undefined,
    sort_order: undefined,
    limit: 1000,
  });

  const {
    data: statsData,
    error: statsError,
    isLoading: isStatsLoading,
  } = useStatistics(["os_distribution"]);

  const { handleExportCSV } = useExportCSV(filters);

  useEffect(() => {
    if (computersData?.data) {
      const uniqueComputers = Array.from(
        new Map(computersData.data.map((comp) => [comp.id, comp])).values(),
      );
      const transformedComputers = uniqueComputers
        .slice(0, 1000)
        .map((computer) => ({
          ...computer,
          last_updated: computer.last_updated || "",
          last_check: computer.last_full_scan || "",
        }));
      setCachedComputers(transformedComputers);
      setPageTitle(
        `${t("computers_list", "Список комп’ютерів")} (${filteredComputers.total || 0})`,
      );
      if (computersData.total > 1000) {
        notification.warning({
          message: t("data_limit", "Обмеження даних"),
          description: t(
            "data_limit_description",
            "Відображається лише перші 1000 комп’ютерів. Використовуйте фільтри для точного пошуку.",
          ),
        });
      }
    }
  }, [computersData, t, filteredComputers.total, setPageTitle]);

  const getCheckStatusColor = (status: string | null | undefined) => {
    switch (status) {
      case "success":
        return "#52c41a"; // Зелений
      case "failed":
      case "unreachable":
        return "#ff4d4f"; // Червоний
      case "partially_successful":
        return "#faad14"; // Жовтий
      case "disabled":
      case "is_deleted":
        return "#8c8c8c"; // Сірий
      default:
        return "#000"; // Чорний
    }
  };

  const getLastScanColor = (scanDate: string | null) => {
    if (!scanDate) return "#000"; // Чорний за замовчуванням
    const date = new Date(scanDate);
    const now = new Date();
    const diffDays = (now.getTime() - date.getTime()) / (1000 * 3600 * 24);
    if (diffDays <= 7) return "#52c41a"; // Зелений для сканувань за останній тиждень
    if (diffDays <= 14) return "#faad14"; // Помаранчевий для 1–2 тижнів
    return "#ff4d4f"; // Червоний для старіших
  };

  const rowSelection = useMemo(
    () => ({
      onChange: (selectedRowKeys: React.Key[], selectedRows: ComputerListItem[]) => {
        setSelectedHostnames(selectedRows.map((row) => row.hostname));
      },
      getCheckboxProps: (record: ComputerListItem) => ({
        disabled: record.check_status === "is_deleted",
        name: record.hostname,
      }),
    }),
    [],
  );

  const columns = useMemo<TableProps<ComputerListItem>["columns"]>(
    () => [
      {
        title: t("hostname", "Ім’я хоста"),
        dataIndex: "hostname",
        key: "hostname",
        sorter: true,
        sortOrder:
          filters.sort_by === "hostname"
            ? filters.sort_order === "asc"
              ? "ascend"
              : "descend"
            : undefined,
        render: (_: string, record: ComputerListItem) => (
          <Link to={`/computer/${record.id}`} className={styles.link}>
            {record.hostname}
          </Link>
        ),
      },
      {
        title: t("ip_addresses", "IP-адреси"),
        dataIndex: "ip_addresses",
        key: "ip_addresses",
        sorter: false,
        render: (_: any, record: ComputerListItem) =>
          record.ip_addresses?.map((ip) => ip.address).join(", ") || "-",
      },
      {
        title: t("os_name", "Операційна система"),
        dataIndex: "os",
        key: "os",
        sorter: true,
        sortOrder:
          filters.sort_by === "os"
            ? filters.sort_order === "asc"
              ? "ascend"
              : "descend"
            : undefined,
        render: (os: OperatingSystemRead | null) => os?.name ?? "-",
      },
      {
        title: t("last_check", "Остання перевірка"),
        dataIndex: "last_full_scan",
        key: "last_full_scan",
        sorter: true,
        sortOrder:
          filters.sort_by === "last_full_scan"
            ? filters.sort_order === "asc"
              ? "ascend"
              : "descend"
            : undefined,
        render: (text: string | null) => (
          <span style={{ color: getLastScanColor(text) }}>
            {text ? formatDateInUserTimezone(text, timezone) : "-"}
          </span>
        ),
      },
      {
        title: t("check_status", "Статус перевірки"),
        dataIndex: "check_status",
        key: "check_status",
        sorter: true,
        sortOrder:
          filters.sort_by === "check_status"
            ? filters.sort_order === "asc"
              ? "ascend"
              : "descend"
            : undefined,
        render: (text: string | null) => {
          const statusMap: Record<string, string> = {
            success: t("status_success", "Успішно"),
            failed: t("status_failed", "Невдало"),
            unreachable: t("status_unreachable", "Недоступно"),
            partially_successful: t(
              "status_partially_successful",
              "Частково успішно",
            ),
            disabled: t("status_disabled", "Відключено"),
            is_deleted: t("status_is_deleted", "Видалено"),
          };
          return (
            <span style={{ color: getCheckStatusColor(text) }}>
              {statusMap[text || ""] || text || "-"}
            </span>
          );
        },
      },
    ],
    [t, filters.sort_by, filters.sort_order, timezone],
  ) as NonNullable<TableProps<ComputerListItem>["columns"]>;

  useEffect(() => {
    const error = computersError || statsError;
    if (error && (error as AxiosError).response?.status === 401) {
      navigate("/login");
    }
  }, [computersError, statsError, navigate]);

  return (
    <div className={styles.container}>
      {isComputersLoading || isStatsLoading || isDomainsLoading ? (
        <Skeleton active paragraph={{ rows: 10 }} />
      ) : (
        <>
          <ComputerFiltersPanel
            filters={filters}
            statsData={statsData}
            isStatsLoading={isStatsLoading}
            domainsData={domainsData}
            isDomainsLoading={isDomainsLoading}
            debouncedSetHostname={debouncedSetHostname}
            debouncedSetOsName={handleFilterChange.bind(null, "os_name")}
            debouncedSetDomain={handleFilterChange.bind(null, "domain")}
            debouncedSetCheckStatus={handleFilterChange.bind(
              null,
              "check_status",
            )}
            handleFilterChange={handleFilterChange}
            clearAllFilters={clearAllFilters}
            handleExportCSV={handleExportCSV} 
          />
          <Table
            rowSelection={rowSelection}
            columns={columns}
            dataSource={filteredComputers.data}
            rowKey="id"
            pagination={false}
            scroll={{ y: 700 }}
            onChange={handleTableChange}
            locale={{ emptyText: t("no_data", "Немає даних для відображення") }}
            size="small"
            showSorterTooltip={false}
          />
          <div className={styles.actionPanel} style={{ marginTop: "16px" }}>
            <ActionPanel hostnames={selectedHostnames} />
          </div>
        </>
      )}
    </div>
  );
};

export default ComputerListComponent;