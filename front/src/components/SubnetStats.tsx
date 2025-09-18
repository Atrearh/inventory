import { useQuery } from "@tanstack/react-query";
import { getComputers } from "../api/api";
import { ComputersResponse, ComputerListItem } from "../types/schemas";
import { useEffect, useState } from "react";
import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
  Legend,
  ChartData,
  ChartOptions,
} from "chart.js";
import { Pie } from "react-chartjs-2";
import { notification, Table } from "antd";
import { useAppContext } from "../context/AppContext";
import { useTranslation } from "react-i18next";
import { AxiosError } from "axios";

ChartJS.register(ArcElement, Tooltip, Legend);

interface SubnetStatsProps {
  onSubnetClick?: (subnet: string) => void;
  emptyComponent?: React.ReactNode; 
}

const SubnetStats: React.FC<SubnetStatsProps> = ({
  onSubnetClick,
  emptyComponent,
}) => {
  const { t } = useTranslation();
  const { isAuthenticated } = useAppContext();
  const [subnetData, setSubnetData] = useState<
    { subnet: string; count: number }[]
  >([]);

  const {
    data: computersData,
    isLoading,
    error,
    refetch,
  } = useQuery<ComputersResponse, Error>({
    queryKey: ["computersForSubnets"],
    queryFn: () =>
      getComputers({
        page: 1,
        limit: 1000,
        hostname: undefined,
        os_name: undefined,
        check_status: undefined,
        show_disabled: true,
        sort_by: "hostname",
        sort_order: "asc",
        domain: undefined,
      }),
    enabled: isAuthenticated,
    refetchOnWindowFocus: false,
    staleTime: 60 * 60 * 1000,
    retry: 3,
    retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 30000),
  });

  useEffect(() => {
    if (error) {
      console.error(t("error_query", "Query error"), error);
      if (error instanceof AxiosError && error.response?.data) {
        console.error(
          t("error_server_details", "Server error details"),
          JSON.stringify(error.response.data, null, 2),
        );
        notification.error({
          message: t("error_loading_data", "Error loading data"),
          description: t("error_loading_computers", {
            error: JSON.stringify(error.response.data.detail || error.message),
          }),
        });
      } else {
        notification.error({
          message: t("error_loading_data", "Error loading data"),
          description: t("error_loading_computers", { error: error.message }),
        });
      }
      refetch();
    }
    if (!isAuthenticated) {
      return;
    }
    if (computersData?.data && Array.isArray(computersData.data)) {
      const subnetMap = new Map<string, number>();
      computersData.data
        .filter(
          (computer) =>
            computer.check_status !== "disabled" &&
            computer.check_status !== "is_deleted",
        )
        .forEach((computer: ComputerListItem) => {
          const ip = computer.ip_addresses?.[0]?.address;
          let subnet = t("unknown", "Unknown");
          if (ip) {
            const match = ip.match(/^(\d+\.\d+)\.(\d+)\.\d+$/);
            if (match) {
              const baseIp = match[1];
              const thirdOctet = parseInt(match[2] || "0", 10);
              const subnetThirdOctet = thirdOctet - (thirdOctet % 2);
              subnet = `${baseIp}.${subnetThirdOctet}.0/23`;
            }
          }
          subnetMap.set(subnet, (subnetMap.get(subnet) || 0) + 1);
        });
      const subnets = Array.from(subnetMap.entries()).map(
        ([subnet, count]) => ({ subnet, count }),
      );
      setSubnetData(subnets);
    }
  }, [computersData, error, isAuthenticated, refetch, t]);

  if (!isAuthenticated)
    return <div>{t("auth_required", "Authentication required")}</div>;
  if (isLoading) return <div>{t("loading", "Loading...")}</div>;
  if (error)
    return (
      <div style={{ color: "red" }}>
        {t("error", "Error")}: {error.message}
      </div>
    );
  if (
    !computersData ||
    !computersData.data ||
    !Array.isArray(computersData.data) ||
    computersData.data.length === 0
  ) {
    return (
      emptyComponent || (
        <div>{t("no_computer_data", "No computer data available")}</div>
      )
    );
  }

  const totalComputers = subnetData.reduce((sum, item) => sum + item.count, 0);

  const chartData: ChartData<"pie", number[], string> = {
    labels: subnetData.map((item) => item.subnet),
    datasets: [
      {
        label: t("computers_by_subnets", "Computers by subnets"),
        data: subnetData.map((item) => item.count),
        backgroundColor: [
          "#FF6384",
          "#36A2EB",
          "#FFCE56",
          "#4BC0C0",
          "#9966FF",
          "#FF9F40",
        ],
        borderColor: ["#fff"],
        borderWidth: 1,
      },
    ],
  };

  const chartOptions: ChartOptions<"pie"> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: "top" as const,
      },
      tooltip: {
        callbacks: {
          label: (context) => {
            const value = context.raw as number;
            const percentage = totalComputers
              ? ((value / totalComputers) * 100).toFixed(1)
              : "0";
            return `${context.label}: ${value} ${t("os_tooltip_computers", "Computers")} (${percentage} ${t("os_tooltip_percentage", "Percentage")})`;
          },
        },
      },
    },
    onClick: (e, elements, chart) => {
      if (elements.length && onSubnetClick) {
        const index = elements[0].index;
        const subnet = chart.data.labels?.[index];
        if (typeof subnet === "string") {
          onSubnetClick(subnet);
        }
      }
    },
  };

  const subnetColumns = [
    {
      title: t("subnet", "Subnet"),
      dataIndex: "subnet",
      key: "subnet",
      render: (subnet: string) => (
        <a
          style={{ cursor: "pointer", color: "#1890ff" }}
          onClick={() => {
            onSubnetClick && onSubnetClick(subnet);
          }}
        >
          {subnet}
        </a>
      ),
    },
    { title: t("count", "Count"), dataIndex: "count", key: "count" },
  ];

  return (
    <div style={{ padding: 12 }}>
      <h2>{t("computers_by_subnets", "Computers by subnets (/23)")}</h2>
      {subnetData.length > 0 ? (
        <>
          <div style={{ height: 300, marginBottom: 24 }}>
            <Pie data={chartData} options={chartOptions} />
          </div>
          <Table
            columns={subnetColumns}
            dataSource={subnetData}
            rowKey="subnet"
            size="small"
            pagination={false}
            locale={{ emptyText: emptyComponent || t("no_data", "No data") }}
          />
        </>
      ) : (
        emptyComponent || (
          <div>{t("no_subnet_data", "No subnet data available")}</div>
        )
      )}
    </div>
  );
};

export default SubnetStats;
