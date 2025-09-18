import { useStatistics } from "../hooks/useApiQueries";
import { useLocation, useNavigate } from "react-router-dom";
import { useEffect } from "react";
import { notification, Empty, Button } from "antd";
import CombinedStats from "./CombinedStats";
import LowDiskSpace from "./LowDiskSpace";
import SubnetStats from "./SubnetStats";
import DashboardMenu from "./DashboardMenu";
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from "chart.js";
import { AxiosError } from "axios";
import { startHostScan } from "../api/api";
import { useTranslation } from "react-i18next";
import { usePageTitle } from "../context/PageTitleContext";

ChartJS.register(ArcElement, Tooltip, Legend);

const Dashboard: React.FC = () => {
  const { setPageTitle } = usePageTitle();
  const location = useLocation();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const params = new URLSearchParams(location.search);
  const activeTab = params.get("tab") || "summary";

  useEffect(() => {
    setPageTitle(t("statistics", "Статистика"));
  }, [setPageTitle, t]);

  const {
    data,
    error: statsError,
    isLoading,
  } = useStatistics([
    "total_computers",
    "os_distribution",
    "low_disk_space_with_volumes",
    "last_scan_time",
    "status_stats",
  ]);

  const handleOsClick = (os: string) => {
    const newParams = new URLSearchParams();
    if (os !== "Unknown" && os !== "Other Servers") {
      newParams.set("os_name", os);
    } else if (os === "Other Servers") {
      newParams.set("server_filter", "server");
    }
    newParams.set("page", "1");
    newParams.set("limit", "10");
    navigate(`/computers?${newParams.toString()}`);
  };

  const handleSubnetClick = (subnet: string) => {
    const newParams = new URLSearchParams();
    newParams.set("ip_range", subnet === "Невідомо" ? "none" : subnet);
    newParams.set("page", "1");
    newParams.set("limit", "10");
    navigate(`/computers?${newParams.toString()}`);
  };

  const handleStartScan = async () => {
    try {
      const response = await startHostScan("");
      notification.success({
        message: t("scan_started", "Сканування розпочато"),
        description: `Task ID: ${response.task_id}`,
      });
    } catch (error) {
      notification.error({
        message: t("scan_error", "Помилка сканування"),
        description: (error as Error).message,
      });
    }
  };

  useEffect(() => {
    if (statsError) {
      const errorMessage =
        statsError instanceof AxiosError && statsError.response?.data
          ? JSON.stringify(
              statsError.response.data.detail || statsError.message,
            )
          : statsError.message;
      notification.error({
        message: t("error_loading_stats", "Помилка завантаження статистики"),
        description: errorMessage,
      });
    }
  }, [statsError, t]);

  const renderEmptyState = () => (
    <Empty
      description={t("no_data", "Немає даних")}
      image={Empty.PRESENTED_IMAGE_SIMPLE}
    >
      <Button type="primary" onClick={handleStartScan}>
        {t("start_scan", "Розпочати сканування")}
      </Button>
    </Empty>
  );

  if (isLoading) return <div>{t("loading", "Завантаження...")}</div>;
  if (statsError)
    return (
      <div style={{ color: "red" }}>
        {t("error_loading_stats", "Помилка завантаження статистики")}:{" "}
        {statsError.message}
      </div>
    );
  if (!data || data.total_computers === 0) return renderEmptyState();

  const handleTabChange = (tab: string) => {
    navigate(`?tab=${tab}`, { replace: true });
  };

  return (
    <div style={{ padding: 2 }}>
      <DashboardMenu activeTab={activeTab} onTabChange={handleTabChange} />
      {activeTab === "summary" && (
        <CombinedStats
          totalComputers={data.total_computers}
          lastScanTime={data.scan_stats?.last_scan_time}
          clientOsData={data.os_stats?.client_os || []}
          serverOsData={data.os_stats?.server_os || []}
          statusStats={data.scan_stats?.status_stats || []}
          lowDiskSpaceCount={data.disk_stats?.low_disk_space?.length || 0}
          onOsClick={handleOsClick}
          onStatusClick={(status: string) =>
            navigate(
              `/computers?check_status=${encodeURIComponent(status)}&page=1&limit=10`,
            )
          }
        />
      )}
      {activeTab === "low_disk_space" && (
        <LowDiskSpace
          lowDiskSpace={data.disk_stats?.low_disk_space || []}
          emptyComponent={renderEmptyState()}
        />
      )}
      {activeTab === "subnets" && (
        <SubnetStats
          onSubnetClick={handleSubnetClick}
          emptyComponent={renderEmptyState()}
        />
      )}
    </div>
  );
};

export default Dashboard;
