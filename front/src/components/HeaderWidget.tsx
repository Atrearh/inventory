import { useState, useEffect, useCallback, useMemo } from "react";
import { useTranslation } from "react-i18next";
import {
  Button,
  Space,
  Dropdown,
  MenuProps,
  Badge,
  Typography,
  theme,
  message,
} from "antd";
import { useAppContext } from "../context/AppContext";
import { formatDateInUserTimezone } from "../utils/formatDate";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getTasks } from "../api/tasks.api";
import { handleApiError } from "../utils/apiErrorHandler";
import LanguageAndThemeSwitch from "./LanguageAndThemeSwitch";
import { LogoutOutlined, DownOutlined } from "@ant-design/icons";
import styles from "./HeaderWidget.module.css";
import { ScanTask } from "../types/schemas";

const HeaderWidget: React.FC = () => {
  const { t } = useTranslation();
  const { user, logout, timezone, dark } = useAppContext();
  const queryClient = useQueryClient();
  const [currentTime, setCurrentTime] = useState(new Date());
  const { token } = theme.useToken();

  useEffect(() => {
    let rafId: number;
    const updateTime = () => {
      setCurrentTime(new Date());
      rafId = requestAnimationFrame(updateTime);
    };
    rafId = requestAnimationFrame(updateTime);
    return () => cancelAnimationFrame(rafId);
  }, []);

  const { data = { tasks: [], total: 0 }, isLoading: isTasksLoading } = useQuery<
    { tasks: ScanTask[]; total: number },
    Error
  >({
    queryKey: ["tasks"],
    queryFn: () => getTasks(),
    refetchInterval: 15000,
    enabled: !!user,
  });

  const handleLogout = useCallback(() => {
    logout();
    queryClient.invalidateQueries({ queryKey: ["tasks"] });
  }, [logout, queryClient]);

  const formattedTime = useMemo(
    () =>
      formatDateInUserTimezone(currentTime, timezone, "dd.MM.yyyy HH:mm:ss"),
    [currentTime, timezone],
  );

  const taskMenuItems: MenuProps["items"] = data.tasks.length
    ? data.tasks.map((task: ScanTask) => ({
        key: task.id,
        label: (
          <div>
            <Typography.Text strong>
              {task.name || `Сканування ${task.id}`}
            </Typography.Text>
            <br />
            <Typography.Text type="secondary">
              {t("status", "Статус")}: {task.status} |{" "}
              {formatDateInUserTimezone(task.created_at, timezone, "HH:mm:ss")}
            </Typography.Text>
          </div>
        ),
      }))
    : [
        {
          key: "no-tasks",
          label: t("no_active_tasks", "Немає активних завдань"),
          disabled: true,
        },
      ];

  return (
    <div
      className={styles.container}
      style={{ background: token.colorBgContainer }}
    >
      <Space align="center">
        <Typography.Text style={{ color: token.colorText }}>
          {formattedTime}
        </Typography.Text>
        {user && (
          <>
            <Typography.Text strong style={{ color: token.colorText }}>
              {user.username}
            </Typography.Text>
            <Dropdown
              menu={{ items: taskMenuItems }}
              trigger={["click"]}
              disabled={isTasksLoading}
            >
              <Button size="small" type={dark ? "default" : "primary"}>
                <Badge count={data.tasks.length} size="small">
                  {t("tasks", "Завдання")} <DownOutlined />
                </Badge>
              </Button>
            </Dropdown>
            <LanguageAndThemeSwitch />
            <Button
              size="small"
              icon={<LogoutOutlined />}
              onClick={handleLogout}
              aria-label={t("logout", "Вийти")}
              type={dark ? "default" : "primary"}
            >
              {t("logout", "Вийти")}
            </Button>
          </>
        )}
        {!user && <LanguageAndThemeSwitch />}
      </Space>
    </div>
  );
};

export default HeaderWidget;