import {
  Button,
  Form,
  Input,
  Table,
  Popconfirm,
  Modal,
  Space,
  Card,
} from "antd";
import { ColumnsType } from "antd/es/table";
import { QueryKey } from "@tanstack/react-query";
import { useMemo, useEffect, useCallback } from "react";
import { register, updateUser, deleteUser } from "../api/api";
import { scanDomains } from "../api/domain.api";
import { UserRead, UserCreate, UserUpdate } from "../types/schemas";
import { useUsers } from "../hooks/useApiQueries";
import { useApiMutation } from "../hooks/useApiMutation";
import { useModalForm } from "../hooks/useModalForm";
import { useAppContext } from "../context/AppContext";
import DomainManagement from "./DomainManagement";
import { useTranslation } from "react-i18next";

interface MutationResponse {
  status: string;
  task_id?: string;
  task_ids?: string[];
}

const AdminPanel: React.FC = () => {
  const { t } = useTranslation();
  const { setPageTitle } = useAppContext();
  const [form] = Form.useForm();
  const {
    isModalOpen,
    editingItem,
    openCreateModal,
    openEditModal,
    handleCancel,
  } = useModalForm<UserRead>({ form });
  const { data: users, isLoading: isUsersLoading } = useUsers();
  const usersQueryKey: QueryKey = ["users"];

  // Встановлення заголовка сторінки
  useEffect(() => {
    setPageTitle(t("admin_panel_title"));
  }, [t, setPageTitle]);

  // Мутації
  const { mutate: registerMutation, isPending: isRegisterLoading } = useApiMutation<
    UserRead,
    UserCreate
  >({
    mutationFn: register,
    successMessage: t("register_success"),
    errorMessage: t("register_error"),
    invalidateQueryKeys: [usersQueryKey],
    onSuccessCallback: handleCancel,
  });

  const { mutate: updateUserMutation, isPending: isUpdateLoading } = useApiMutation<
    UserRead,
    { id: number; data: Partial<UserUpdate> }
  >({
    mutationFn: ({ id, data }) => updateUser(id, data),
    successMessage: t("user_updated"),
    errorMessage: t("update_error"),
    invalidateQueryKeys: [usersQueryKey],
    onSuccessCallback: handleCancel,
  });

  const { mutate: deleteUserMutation } = useApiMutation<void, number>({
    mutationFn: deleteUser,
    successMessage: t("user_deleted"),
    errorMessage: t("delete_error"),
    invalidateQueryKeys: [usersQueryKey],
  });

  // Типізація колонок
  const columns: ColumnsType<UserRead> = useMemo(
    () => [
      {
        title: t("username"),
        dataIndex: "username",
        key: "username",
      },
      {
        title: t("email"),
        dataIndex: "email",
        key: "email",
      },
      {
        title: t("role"),
        dataIndex: "role",
        key: "role",
        render: (role: string | null) => role || "-",
      },
      {
        title: t("actions"),
        key: "actions",
        render: (_, record: UserRead) => (
          <Space size="middle">
            <Button
              type="link"
              onClick={() => openEditModal(record)}
              aria-label={t("edit")}
            >
              {t("edit")}
            </Button>
            <Popconfirm
              title={t("confirm_delete")}
              onConfirm={() => deleteUserMutation(record.id)}
              okText={t("yes", "Yes")}
              cancelText={t("cancel")}
            >
              <Button
                type="link"
                danger
                aria-label={t("delete_user")}
              >
                {t("delete")}
              </Button>
            </Popconfirm>
          </Space>
        ),
      },
    ],
    [t, openEditModal, deleteUserMutation],
  );

  // Обробка форми
  const onFinish = useCallback(
    (values: UserCreate | UserUpdate) => {
      if (editingItem) {
        updateUserMutation({ id: editingItem.id, data: values });
      } else {
        registerMutation(values as UserCreate);
      }
    },
    [editingItem, registerMutation, updateUserMutation],
  );

  return (
    <div>
      <Card
        title={t("admin_panel_title")}
        extra={
          <Button type="primary" onClick={openCreateModal} aria-label={t("new_user")}>
            {t("new_user")}
          </Button>
        }
        style={{ marginBottom: 24 }}
      >
        <Table
          dataSource={users}
          columns={columns}
          rowKey="id"
          loading={isUsersLoading}
          pagination={false}
          aria-label={t("users_table")}
        />
      </Card>

      <Card>
        <DomainManagement />
      </Card>

      <Modal
        title={editingItem ? t("edit_user_title") : t("new_user")}
        open={isModalOpen}
        onCancel={handleCancel}
        footer={[
          <Button key="back" onClick={handleCancel} aria-label={t("cancel")}>
            {t("cancel")}
          </Button>,
          <Button
            key="submit"
            type="primary"
            loading={isRegisterLoading || isUpdateLoading}
            onClick={() => form.submit()}
            aria-label={editingItem ? t("save") : t("create")}
          >
            {editingItem ? t("save") : t("create")}
          </Button>,
        ]}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={onFinish}
          style={{ marginTop: 24 }}
        >
          <Form.Item
            name="username"
            label={t("username")}
            rules={[{ required: true, message: t("enter_username") }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="email"
            label={t("email")}
            rules={[{ required: true, type: "email", message: t("invalid_email") }]}
          >
            <Input />
          </Form.Item>
          {!editingItem && (
            <Form.Item
              name="password"
              label={t("password")}
              rules={[{ required: true, message: t("enter_password") }]}
            >
              <Input.Password />
            </Form.Item>
          )}
          <Form.Item name="role" label={t("role")}>
            <Input placeholder={t("role_placeholder")} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default AdminPanel;