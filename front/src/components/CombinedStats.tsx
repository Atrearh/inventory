// front/src/components/CombinedStats.tsx
import { Card, Row, Col, Table, Typography } from "antd";
import { Pie } from "react-chartjs-2";
import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
  Legend,
  ChartData,
  ChartOptions,
} from "chart.js";
import { DashboardStats } from "../types/schemas";
import { useNavigate, Link } from "react-router-dom";
import { useAppContext } from "../context/AppContext"; 
import { formatDateInUserTimezone } from "../utils/formatDate";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";
import { memo } from "react";

ChartJS.register(ArcElement, Tooltip, Legend);

const { Title } = Typography;

interface CombinedStatsProps {
  totalComputers: number | null | undefined;
  lastScanTime: string | null;
  clientOsData: DashboardStats["os_stats"]["client_os"];
  serverOsData: DashboardStats["os_stats"]["server_os"];
  softwareData?: DashboardStats["os_stats"]["software_distribution"];
  statusStats: DashboardStats["scan_stats"]["status_stats"];
  lowDiskSpaceCount: number;
  onOsClick: (os: string, isClientOs: boolean) => void;
  onStatusClick: (status: string) => void;
}

const normalizeOsName = (name: string, t: TFunction): string => {
  const nameLower = name.toLowerCase();
  if (
    nameLower.includes("windows 10") &&
    (nameLower.includes("корпоративная") ||
      nameLower.includes("enterprise") ||
      nameLower.includes("ltsc"))
  ) {
    return t("windows_10_enterprise", "Windows 10 Enterprise");
  }
  if (nameLower.includes("hyper-v")) {
    return t("hyper_v_server", "Hyper-V Server");
  }
  return name;
};

const CombinedStats: React.FC<CombinedStatsProps> = ({
  totalComputers,
  lastScanTime,
  clientOsData,
  serverOsData,
  softwareData,
  statusStats,
  lowDiskSpaceCount,
  onOsClick,
  onStatusClick,
}) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { timezone } = useAppContext();

  const chartColors = {
    clientOs: ["#FF6384", "#36A2EB", "#FFCE56", "#4BC0C0", "#9966FF"],
    serverOs: ["#FF9F40", "#FFCD56", "#C9CB3F", "#36A2EB"],
    software: ["#FF5733", "#33FF57", "#3357FF", "#FF33A1", "#33FFF5"], 
  };

  const clientOsTotal =
    clientOsData && Array.isArray(clientOsData)
      ? clientOsData.reduce((sum, os) => sum + os.count, 0)
      : 0;
  const serverOsTotal =
    serverOsData && Array.isArray(serverOsData)
      ? serverOsData.reduce((sum, os) => sum + os.count, 0)
      : 0;
  const softwareTotal =
    softwareData && Array.isArray(softwareData)
      ? softwareData.reduce((sum, sw) => sum + sw.count, 0)
      : 0;

  const clientOsChartData: ChartData<"pie", number[], string> = {
    labels:
      clientOsData && Array.isArray(clientOsData)
        ? clientOsData.map((os) => normalizeOsName(os.category, t))
        : [],
    datasets: [
      {
        data:
          clientOsData && Array.isArray(clientOsData)
            ? clientOsData.map((os) => os.count)
            : [],
        backgroundColor: chartColors.clientOs,
      },
    ],
  };

  const serverOsChartData: ChartData<"pie", number[], string> = {
    labels:
      serverOsData && Array.isArray(serverOsData)
        ? serverOsData.map((os) => normalizeOsName(os.category, t))
        : [],
    datasets: [
      {
        data:
          serverOsData && Array.isArray(serverOsData)
            ? serverOsData.map((os) => os.count)
            : [],
        backgroundColor: chartColors.serverOs,
      },
    ],
  };

  const softwareChartData: ChartData<"pie", number[], string> = {
    labels:
      softwareData && Array.isArray(softwareData)
        ? softwareData.map((sw) => sw.category)
        : [],
    datasets: [
      {
        data:
          softwareData && Array.isArray(softwareData)
            ? softwareData.map((sw) => sw.count)
            : [],
        backgroundColor: chartColors.software,
      },
    ],
  };

  const chartOptions: ChartOptions<"pie"> = {
    maintainAspectRatio: false,
    responsive: true,
    plugins: {
      legend: { position: "bottom" },
      tooltip: {
        callbacks: {
          label: (context) => {
            const value = context.raw as number;
            const total =
              context.datasetIndex === 0
                ? clientOsTotal
                : context.datasetIndex === 1
                  ? serverOsTotal
                  : softwareTotal;
            const percentage = total ? ((value / total) * 100).toFixed(1) : "0";
            return `${context.label}: ${value} ${t("os_tooltip_computers", "Computers")} (${percentage} ${t("os_tooltip_percentage", "Percentage")})`;
          },
        },
      },
    },
  };

  const handlePieClick = (
    elements: { index: number }[],
    chart: ChartJS<"pie", number[], string>,
    isClientOs: boolean,
  ) => {
    if (!elements.length || !chart.data.labels) return;
    const index = elements[0].index;
    const os = chart.data.labels[index];
    if (typeof os === "string") {
      onOsClick(os, isClientOs);
    }
  };

  const statusColumns = [
    {
      title: t("status", "Status"),
      dataIndex: "status",
      key: "status",
      render: (status: string) => (
        <a
          onClick={() => {
            onStatusClick(status);
            navigate(`/computers?check_status=${encodeURIComponent(status)}`);
          }}
          style={{ cursor: "pointer", color: "#1890ff" }}
        >
          {t(`status_${status}`, status)}
        </a>
      ),
    },
    { title: t("count", "Count"), dataIndex: "count", key: "count" },
  ];

  return (
    <div style={{ padding: 0 }}>
      <Card style={{ marginBottom: "16px" }}>
        <Row justify="space-between">
          <Col>
            <strong>{t("total_computers", "Total Computers")}:</strong>{" "}
            {totalComputers ?? "-"}
          </Col>
          <Col>
            <strong>{t("last_check", "Last Check")}:</strong>{" "}
            {lastScanTime
              ? formatDateInUserTimezone(lastScanTime, timezone)
              : t("no_data", "No data")}
          </Col>
        </Row>
        {lowDiskSpaceCount > 0 && (
          <Row style={{ marginTop: 8 }}>
            <Col>
              <Link to="/?tab=low_disk_space" style={{ color: "red" }}>
                {t("low_disk_space_warning", { count: lowDiskSpaceCount })}
              </Link>
            </Col>
          </Row>
        )}
      </Card>

      <Row gutter={[16, 0]}>
        <Col span={8}>
          <Card>
            <Title level={3} style={{ textAlign: "center" }}>
              {t("client_os", "Client OS")}
            </Title>
            {clientOsChartData.labels && clientOsChartData.labels.length > 0 ? (
              <div style={{ height: "260px", cursor: "pointer" }}>
                <Pie
                  data={clientOsChartData}
                  options={{
                    ...chartOptions,
                    onClick: (e, el, c) =>
                      handlePieClick(
                        el,
                        c as ChartJS<"pie", number[], string>,
                        true,
                      ),
                  }}
                />
              </div>
            ) : (
              <p style={{ textAlign: "center" }}>
                {t("no_client_os_data", "No client OS data")}
              </p>
            )}
          </Card>
        </Col>

        <Col span={8}>
          <Card>
            <Title level={3} style={{ textAlign: "center" }}>
              {t("server_os", "Server OS")}
            </Title>
            {serverOsChartData.labels && serverOsChartData.labels.length > 0 ? (
              <div style={{ height: "260px", cursor: "pointer" }}>
                <Pie
                  data={serverOsChartData}
                  options={{
                    ...chartOptions,
                    onClick: (e, el, c) =>
                      handlePieClick(
                        el,
                        c as ChartJS<"pie", number[], string>,
                        false,
                      ),
                  }}
                />
              </div>
            ) : (
              <p style={{ textAlign: "center" }}>
                {t("no_server_os_data", "No server OS data")}
              </p>
            )}
          </Card>
        </Col>

        <Col span={8}>
          <Card>
            <Title level={3} style={{ textAlign: "center" }}>
              {t("software_distribution", "Software Distribution")}
            </Title>
            {softwareChartData.labels && softwareChartData.labels.length > 0 ? (
              <div style={{ height: "260px", cursor: "pointer" }}>
                <Pie data={softwareChartData} options={{ ...chartOptions }} />
              </div>
            ) : (
              <p style={{ textAlign: "center" }}>
                {t("no_software_data", "No software data")}
              </p>
            )}
          </Card>
        </Col>
      </Row>

      <Card style={{ marginTop: "16px" }}>
        <Title level={4}>{t("check_statuses", "Check Statuses")}</Title>
        <Table
          columns={statusColumns}
          dataSource={
            statusStats && Array.isArray(statusStats)
              ? statusStats.filter((stat) => stat.count > 0)
              : []
          }
          rowKey="status"
          size="small"
          pagination={false}
          locale={{ emptyText: t("no_data", "No data") }}
        />
      </Card>
    </div>
  );
};

export default memo(CombinedStats);
