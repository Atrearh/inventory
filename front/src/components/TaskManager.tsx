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
import { useAppContext } from "../context/AppContext";
import { formatDateInUserTimezone } from "../utils/formatDate";
import { ScanTask, ScanStatus } from "../types/schemas";

const { Title } = Typography;

const TaskManager: React.FC = () => {
  const { t } = useTranslation();
  const { setPageTitle, timezone } = useAppContext();

  useEffect(() => {
    setPageTitle(t("task_management", "Керування завданнями"));
  }, [setPageTitle, t]);

  const queryKey = ["tasks"];

  const { data = { tasks: [], total: 0 }, isLoading, isFetching } = useQuery<
    { tasks: ScanTask[]; total: number },
    Error
  >({
    queryKey,
    queryFn: () => getTasks(100, 0),
    refetchInterval: 5000,
  });

  const { mutate: deleteTaskMutation } = useApiMutation<
    { ok: boolean },
    string
  >({
    mutationFn: deleteTask,
    successMessage: t("task_deleted", "Завдання видалено"),
    errorMessage: t("task_delete_error", "Помилка видалення завдання"),
    invalidateQueryKeys: [queryKey],
  });

  const { mutate: retryTaskMutation } = useApiMutation<ScanTask, string>({
    mutationFn: (taskId) => updateTaskState(taskId, "pending"),
    successMessage: t("task_restarted", "Завдання перезапущено"),
    errorMessage: t("task_restart_error", "Помилка перезапуску завдання"),
    invalidateQueryKeys: [queryKey],
  });

  const getStatusTag = (status: ScanStatus) => {
    switch (status) {
      case "completed":
        return (
          <Tag icon={<CheckCircleOutlined />} color="success">
            {t("completed", "Завершено")}
          </Tag>
        );
      case "failed":
        return (
          <Tag icon={<CloseCircleOutlined />} color="error">
            {t("failed", "Помилка")}
          </Tag>
        );
      case "pending":
      case "running":
        return (
          <Tag icon={<SyncOutlined spin />} color="processing">
            {t(status, status === "pending" ? "Очікування" : "Виконується")}
          </Tag>
        );
      default:
        return <Tag>{status}</Tag>;
    }
  };

  const columns = [
    {
      title: t("name", "Назва"),
      dataIndex: "name",
      key: "name",
      render: (name: string, record: ScanTask) =>
        name || `Сканування ${record.id}`,
    },
    {
      title: t("status", "Статус"),
      dataIndex: "status",
      key: "status",
      render: (status: ScanStatus) => getStatusTag(status),
    },
    {
      title: t("progress", "Прогрес"),
      dataIndex: "progress",
      key: "progress",
      render: (progress: number) => (
        <Progress percent={progress} size="small" />
      ),
    },
    {
      title: t("created_at", "Створено"),
      dataIndex: "created_at",
      key: "created_at",
      render: (date: string) =>
        formatDateInUserTimezone(date, timezone, "dd.MM.yyyy HH:mm:ss"),
    },
    {
      title: t("updated_at", "Оновлено"),
      dataIndex: "updated_at",
      key: "updated_at",
      render: (date: string) =>
        formatDateInUserTimezone(date, timezone, "dd.MM.yyyy HH:mm:ss"),
    },
    {
      title: t("error", "Помилка"),
      dataIndex: "error",
      key: "error",
      render: (error: string) =>
        error ? (
          <Tooltip title={error}>
            <span style={{ color: "red" }}>{t("yes", "Так")}</span>
          </Tooltip>
        ) : (
          t("no", "Ні")
        ),
    },
    {
      title: t("actions", "Дії"),
      key: "actions",
      render: (_: any, record: ScanTask) => (
        <Space>
          {record.status === "failed" && (
            <Tooltip title={t("retry_task", "Перезапустити завдання")}>
              <Button
                icon={<ReloadOutlined />}
                onClick={() => retryTaskMutation(record.id)}
                size="small"
              />
            </Tooltip>
          )}
          <Popconfirm
            title={t("confirm_delete_task", "Ви впевнені, що хочете видалити завдання?")}
            onConfirm={() => deleteTaskMutation(record.id)}
            okText={t("yes", "Так")}
            cancelText={t("no", "Ні")}
          >
            <Tooltip title={t("delete_task", "Видалити завдання")}>
              <Button icon={<DeleteOutlined />} danger size="small" />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: "16px 24px" }}>
      <Table
        dataSource={data.tasks}
        columns={columns}
        rowKey="id"
        loading={isLoading || isFetching}
        pagination={{
          total: data.total,
          showSizeChanger: false,
        }}
        size="middle"
      />
    </div>
  );
};

export default TaskManager;