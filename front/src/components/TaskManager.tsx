import { useQuery } from "@tanstack/react-query";
import {
  Table,
  Button,
  Tag,
  Progress,
  Popconfirm,
  Space,
  Typography,
  Tooltip,
} from "antd";
import {
  ReloadOutlined,
  DeleteOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
} from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import { useEffect } from "react";

import { getTasks, deleteTask, updateTaskState } from "../api/tasks.api";
import { useApiMutation } from "../hooks/useApiMutation";
import { usePageTitle } from "../context/PageTitleContext";
import { useTimezone } from "../context/TimezoneContext";
import { formatDateInUserTimezone } from "../utils/formatDate";
import { ScanTask, ScanStatus } from "../types/schemas";

const { Title } = Typography;

const TaskManager: React.FC = () => {
  const { t } = useTranslation();
  const { setPageTitle } = usePageTitle();
  const { timezone } = useTimezone();

  useEffect(() => {
    setPageTitle(t("task_management"));
  }, [setPageTitle, t]);

  const queryKey = ["tasks"];

  const { data, isLoading, isFetching } = useQuery({
    queryKey,
    queryFn: () => getTasks(100, 0),
    refetchInterval: 5000, // Автоматичне оновлення кожні 5 секунд
  });

  const { mutate: deleteTaskMutation } = useApiMutation<
    { ok: boolean },
    string
  >({
    mutationFn: deleteTask,
    successMessage: t("task_deleted"),
    errorMessage: t("task_delete_error"),
    invalidateQueryKeys: [queryKey],
  });

  const { mutate: retryTaskMutation } = useApiMutation<ScanTask, string>({
    mutationFn: (taskId) => updateTaskState(taskId, "pending"),
    successMessage: t("task_restarted"),
    errorMessage: t("task_restart_error"),
    invalidateQueryKeys: [queryKey],
  });

  const getStatusTag = (status: ScanStatus) => {
    switch (status) {
      case "completed":
        return (
          <Tag icon={<CheckCircleOutlined />} color="success">
            {t("status_completed")}
          </Tag>
        );
      case "running":
        return (
          <Tag icon={<SyncOutlined spin />} color="processing">
            {t("status_running")}
          </Tag>
        );
      case "failed":
        return (
          <Tag icon={<CloseCircleOutlined />} color="error">
            {t("status_failed")}
          </Tag>
        );
      case "pending":
        return <Tag color="default">{t("status_pending")}</Tag>;
      default:
        return <Tag>{status}</Tag>;
    }
  };

  const columns = [
    {
      title: t("id"),
      dataIndex: "id",
      key: "id",
      render: (id: string) => (
        <Tooltip title={id}>
          <code>{id.substring(0, 8)}...</code>
        </Tooltip>
      ),
    },
    {
      title: t("status"),
      dataIndex: "status",
      key: "status",
      render: getStatusTag,
    },
    {
      title: t("progress"),
      key: "progress",
      render: (_: any, record: ScanTask) => (
        <Progress
          percent={Math.round(record.progress ?? 0)}
          size="small"
          status={record.status === "failed" ? "exception" : "normal"}
          format={() => `${record.successful_hosts}/${record.scanned_hosts}`}
        />
      ),
    },
    {
      title: t("created_at"),
      dataIndex: "created_at",
      key: "created_at",
      render: (date: string) => formatDateInUserTimezone(date, timezone),
    },
    {
      title: t("updated_at"),
      dataIndex: "updated_at",
      key: "updated_at",
      render: (date: string) => formatDateInUserTimezone(date, timezone),
    },
    {
      title: t("error"),
      dataIndex: "error",
      key: "error",
      render: (error: string) =>
        error ? (
          <Tooltip title={error}>
            <span style={{ color: "red" }}>{t("yes")}</span>
          </Tooltip>
        ) : (
          t("no")
        ),
    },
    {
      title: t("actions"),
      key: "actions",
      render: (_: any, record: ScanTask) => (
        <Space>
          {record.status === "failed" && (
            <Tooltip title={t("retry_task")}>
              <Button
                icon={<ReloadOutlined />}
                onClick={() => retryTaskMutation(record.id)}
                size="small"
              />
            </Tooltip>
          )}
          <Popconfirm
            title={t("confirm_delete_task")}
            onConfirm={() => deleteTaskMutation(record.id)}
            okText={t("yes")}
            cancelText={t("no")}
          >
            <Tooltip title={t("delete_task")}>
              <Button icon={<DeleteOutlined />} danger size="small" />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const [tasks, total] = data || [[], 0];

  return (
    <div style={{ padding: "16px 24px" }}>
      <Title level={2}>{t("task_management")}</Title>
      <Table
        dataSource={tasks}
        columns={columns}
        rowKey="id"
        loading={isLoading || isFetching}
        pagination={{
          total,
          showSizeChanger: false,
        }}
        size="middle"
      />
    </div>
  );
};

export default TaskManager;
