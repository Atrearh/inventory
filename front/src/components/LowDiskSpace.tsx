import { Table, Card, Row, Col } from "antd";
import { Link } from "react-router-dom";
import { DashboardStats } from "../types/schemas";
import { useTranslation } from "react-i18next";

interface LowDiskSpaceProps {
  lowDiskSpace: DashboardStats["disk_stats"]["low_disk_space"];
  emptyComponent?: React.ReactNode;
}

const LowDiskSpace: React.FC<LowDiskSpaceProps> = ({
  lowDiskSpace,
  emptyComponent,
}) => {
  const { t } = useTranslation();

  // Фільтрація комп'ютерів з низьким обсягом диска (менше або дорівнює 1024 ГБ)
  const filteredLowDiskSpace = lowDiskSpace.filter(
    (disk) => disk.free_space_gb !== undefined && disk.free_space_gb <= 1024,
  );

  const diskColumns = [
    {
      title: t("hostname", "Hostname"),
      dataIndex: "hostname",
      key: "hostname",
      render: (
        hostname: string,
        record: DashboardStats["disk_stats"]["low_disk_space"][0],
      ) => (
        <Link to={`/computer/${record.id}`}>
          {hostname || t("unknown", "Unknown")}
        </Link>
      ),
    },
    { title: t("disk_id", "Disk"), dataIndex: "disk_id", key: "disk_id" },
    {
      title: t("model", "Model"),
      dataIndex: "model",
      key: "model",
      render: (value: string) => value || t("unknown", "Unknown"),
    },
    {
      title: t("total_space", "Total Space (GB)"),
      dataIndex: "total_space_gb",
      key: "total_space_gb",
      render: (value: number) =>
        value !== undefined ? value.toFixed(2) : t("not_available", "N/A"),
    },
    {
      title: t("free_space", "Free Space (GB)"),
      dataIndex: "free_space_gb",
      key: "free_space_gb",
      render: (value: number) =>
        value !== undefined ? value.toFixed(2) : t("not_available", "N/A"),
    },
  ];

  if (!lowDiskSpace || lowDiskSpace.length === 0) {
    return (
      emptyComponent || (
        <p style={{ color: "red" }}>
          {t("no_low_disk_data", "No low disk space data")}
        </p>
      )
    );
  }

  return (
    <div style={{ marginTop: "16px" }}>
      <Card>
        <Row gutter={[16, 16]}>
          <Col span={24}>
            <h3>
              {t("low_disk_space_computers", "Computers with Low Disk Space")}
            </h3>
            {filteredLowDiskSpace.length > 0 ? (
              <>
                <Table
                  columns={diskColumns}
                  dataSource={filteredLowDiskSpace}
                  rowKey={(record) => `${record.id}-${record.disk_id}`}
                  size="middle"
                  locale={{
                    emptyText: emptyComponent || t("no_data", "No data"),
                  }}
                  pagination={false}
                />
              </>
            ) : (
              emptyComponent || (
                <p>
                  {t(
                    "no_low_disk_computers",
                    "No computers with low disk space",
                  )}
                </p>
              )
            )}
          </Col>
        </Row>
      </Card>
    </div>
  );
};

export default LowDiskSpace;
