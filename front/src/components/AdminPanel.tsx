import { Button, Form, Input, Table, Popconfirm, Modal, Space, Card } from 'antd';
import { QueryKey } from '@tanstack/react-query';
import { useMemo, useEffect } from 'react';
import { startScan, register, updateUser, deleteUser } from '../api/api';
import { scanDomains } from '../api/domain.api';
import { UserRead, UserCreate, UserUpdate } from '../types/schemas';
import { useUsers } from '../hooks/useApiQueries';
import { useApiMutation } from '../hooks/useApiMutation'; // Імпортуємо хук
import { useModalForm } from '../hooks/useModalForm';
import DomainManagement from './DomainManagement';
import { usePageTitle } from '../context/PageTitleContext';
import { useTranslation } from 'react-i18next';

interface MutationResponse {
  status: string;
  task_id?: string;
  task_ids?: string[];
}

const AdminPanel: React.FC = () => {
  const { t } = useTranslation();
  const { setPageTitle } = usePageTitle();
  const [form] = Form.useForm();
  const { isModalOpen, editingItem, openCreateModal, openEditModal, handleCancel } = useModalForm<UserRead>({ form });
  const { data: users, refetch: refetchUsers, isLoading: isUsersLoading } = useUsers();
  const usersQueryKey: QueryKey = ['users']; // Визначаємо queryKey для інвалідування

  // Мутації з використанням useApiMutation
  const { mutate: registerMutation, isPending: isRegisterLoading } = useApiMutation<UserRead, UserCreate>({
    mutationFn: register,
    successMessage: t('register_success'),
    errorMessage: t('register_error'),
    invalidateQueryKeys: [usersQueryKey],
    onSuccessCallback: handleCancel,
  });

  const { mutate: updateUserMutation, isPending: isUpdateLoading } = useApiMutation<
    UserRead,
    { id: number; data: Partial<UserUpdate> }
  >({
    mutationFn: ({ id, data }) => updateUser(id, data),
    successMessage: t('user_updated'),
    errorMessage: t('update_error'),
    invalidateQueryKeys: [usersQueryKey],
    onSuccessCallback: handleCancel,
  });

  const { mutate: deleteUserMutation } = useApiMutation<void, number>({
    mutationFn: deleteUser,
    successMessage: t('user_deleted'),
    errorMessage: t('delete_error'),
    invalidateQueryKeys: [usersQueryKey],
  });

  const { mutate: startScanMutation, isPending: isScanLoading } = useApiMutation<MutationResponse, void>({
    mutationFn: startScan,
    successMessage: t('scan_started'), // task_id обробляється в mutationFn
    errorMessage: t('scan_error'),
  });

const { mutate: scanAllDomainsMutation, isPending: isAllDomainsADScanLoading } = useApiMutation<MutationResponse, void>({
  mutationFn: () => scanDomains(), // Викликаємо scanDomains без параметрів
  successMessage: t('scan_all_domains_started findebug: true'), // Додаємо findbugs
  errorMessage: t('scan_all_domains_error'),
});

  // Обробка відправлення форми
  const onFinish = async (values: any) => {
    if (editingItem) {
      updateUserMutation({ id: editingItem.id, data: values });
    } else {
      registerMutation(values);
    }
  };

  useEffect(() => {
    setPageTitle(t('admin'));
  }, [setPageTitle, t]);

  // Визначення стовпців таблиці
  const columns = useMemo(
    () => [
      { title: t('username'), dataIndex: 'username', key: 'username' },
      { title: t('email'), dataIndex: 'email', key: 'email' },
      {
        title: t('actions'),
        key: 'actions',
        render: (_: any, record: UserRead) => (
          <Space>
            <Button onClick={() => openEditModal(record)} aria-label={t('edit_user', { username: record.username })}>
              {t('edit')}
            </Button>
            <Popconfirm
              title={t('confirm_delete')}
              onConfirm={() => deleteUserMutation(record.id)}
              okText={t('yes')}
              cancelText={t('no')}
            >
              <Button danger aria-label={t('delete_user', { username: record.username })}>
                {t('delete')}
              </Button>
            </Popconfirm>
          </Space>
        ),
      },
    ],
    [deleteUserMutation, openEditModal, t]
  );

  return (
    <div style={{ padding: '16px 24px' }}>
      <Card title={t('global_actions')} style={{ marginBottom: 24 }}>
        <Space>
          <Button
            onClick={() => startScanMutation()}
            loading={isScanLoading}
            disabled={isScanLoading || isAllDomainsADScanLoading}
            aria-label={t('start_inventory')}
          >
            {t('start_inventory')}
          </Button>
          <Button
            onClick={() => scanAllDomainsMutation()}
            loading={isAllDomainsADScanLoading}
            disabled={isScanLoading || isAllDomainsADScanLoading}
            aria-label={t('scan_all_domains')}
          >
            {t('scan_all_domains')}
          </Button>
        </Space>
      </Card>

      <Card
        title={t('user_management')}
        extra={
          <Button type="primary" onClick={openCreateModal} aria-label={t('add_user')}>
            {t('add_user')}
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
          aria-label={t('users_table')}
        />
      </Card>

      <Card>
        <DomainManagement />
      </Card>

      <Modal
        title={editingItem ? t('edit_user_title') : t('new_user')}
        open={isModalOpen}
        onCancel={handleCancel}
        footer={[
          <Button key="back" onClick={handleCancel} aria-label={t('cancel')}>
            {t('cancel')}
          </Button>,
          <Button
            key="submit"
            type="primary"
            loading={isRegisterLoading || isUpdateLoading}
            onClick={() => form.submit()}
            aria-label={editingItem ? t('save_user_changes') : t('create_user')}
          >
            {editingItem ? t('save') : t('create')}
          </Button>,
        ]}
      >
        <Form form={form} layout="vertical" onFinish={onFinish} style={{ marginTop: 24 }}>
          <Form.Item
            name="username"
            label={t('username')}
            rules={[{ required: true, message: t('enter_username') }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="email"
            label={t('email')}
            rules={[{ required: true, type: 'email', message: t('invalid_email') }]}
          >
            <Input />
          </Form.Item>
          {!editingItem && (
            <Form.Item
              name="password"
              label={t('password')}
              rules={[{ required: true, message: t('enter_password') }]}
            >
              <Input.Password />
            </Form.Item>
          )}
          <Form.Item name="role" label={t('role')}>
            <Input placeholder={t('role_placeholder')} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default AdminPanel;