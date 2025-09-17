// front/src/components/SessionManagement.tsx
import { useQuery } from "@tanstack/react-query";
import { Table, Button, Popconfirm, Tag, Card, Space, Typography } from "antd";
import { useTranslation } from "react-i18next";
import {
  getSessions,
  revokeSession,
  revokeAllOtherSessions,
} from "../api/auth.api";
import { useApiMutation } from "../hooks/useApiMutation";
import { formatDateInUserTimezone } from "../utils/formatDate";
import { useTimezone } from "../context/TimezoneContext";

const { Title, Text } = Typography;

const SessionManagement: React.FC = () => {
  const { t } = useTranslation();
  const { timezone } = useTimezone();
  const queryKey = ["sessions"];

  const { data: sessions, isLoading } = useQuery({
    queryKey,
    queryFn: getSessions,
  });

  const { mutate: revoke, isPending: isRevoking } = useApiMutation<
    void,
    number
  >({
    mutationFn: revokeSession,
    successMessage: t("session_revoked"),
    errorMessage: t("session_revoke_error"),
    invalidateQueryKeys: [queryKey],
  });

  const { mutate: revokeAll, isPending: isRevokingAll } = useApiMutation({
    mutationFn: revokeAllOtherSessions,
    successMessage: t("all_other_sessions_revoked"),
    errorMessage: t("session_revoke_error"),
    invalidateQueryKeys: [queryKey],
  });

  const columns = [
    {
      title: t("login_date"),
      dataIndex: "issued_at",
      key: "issued_at",
      render: (date: string) => formatDateInUserTimezone(date, timezone),
    },
    {
      title: t("session_expires"),
      dataIndex: "expires_at",
      key: "expires_at",
      render: (date: string) => formatDateInUserTimezone(date, timezone),
    },
    {
      title: t("status"),
      dataIndex: "is_current",
      key: "is_current",
      render: (isCurrent: boolean) =>
        isCurrent ? (
          <Tag color="green">{t("current_session")}</Tag>
        ) : (
          <Tag color="default">{t("active")}</Tag>
        ),
    },
    {
      title: t("actions"),
      key: "actions",
      render: (_: any, record: { id: number; is_current: boolean }) =>
        !record.is_current && (
          <Popconfirm
            title={t("confirm_revoke_session")}
            onConfirm={() => revoke(record.id)}
            okText={t("yes")}
            cancelText={t("no")}
          >
            <Button danger loading={isRevoking}>
              {t("revoke")}
            </Button>
          </Popconfirm>
        ),
    },
  ];

  return (
    <Card>
      <Space direction="vertical" style={{ width: "100%" }}>
        <Title level={4}>{t("session_management")}</Title>
        <Text type="secondary">{t("session_management_description")}</Text>
        <Popconfirm
          title={t("confirm_revoke_all_other_sessions")}
          onConfirm={() => revokeAll()}
          okText={t("yes")}
          cancelText={t("no")}
        >
          <Button danger loading={isRevokingAll} style={{ marginBottom: 16 }}>
            {t("revoke_all_other_sessions")}
          </Button>
        </Popconfirm>

        <Table
          columns={columns}
          dataSource={sessions}
          rowKey="id"
          loading={isLoading}
          pagination={false}
        />
      </Space>
    </Card>
  );
};

export default SessionManagement;
