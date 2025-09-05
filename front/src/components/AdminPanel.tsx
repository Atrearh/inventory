import { Button, Form, Input, Table, Popconfirm, message, Modal, Space, Card } from 'antd';
import { useMutation } from '@tanstack/react-query';
import { useMemo, useEffect } from 'react';
import { startScan, register, updateUser, deleteUser } from '../api/api';
import { scanDomains } from '../api/domain.api';
import { UserRead, UserCreate, UserUpdate } from '../types/schemas';
import { useUsers } from '../hooks/useApiQueries';
import { useModalForm } from '../hooks/useModalForm'; 
import DomainManagement from './DomainManagement';
import { usePageTitle } from '../context/PageTitleContext';
import { useTranslation } from 'react-i18next';
import type { TFunction } from 'i18next';

// Утилітна функція для уніфікованої обробки помилок
const getErrorMessage = (error: Error | any, t: TFunction): string =>
  error.response?.data?.detail || error.message || t('error');

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

  // Мутації
  const { mutate: registerMutation, isPending: isRegisterLoading } = useMutation<UserRead, Error, UserCreate>({
    mutationFn: register,
    onSuccess: () => {
      message.success(t('register_success'));
      refetchUsers();
      handleCancel();
    },
    onError: (error: any) => message.error(`${t('register_error')}: ${getErrorMessage(error, t)}`),
  });

  const { mutate: updateUserMutation, isPending: isUpdateLoading } = useMutation<
    UserRead,
    Error,
    { id: number; data: Partial<UserUpdate> }
  >({
    mutationFn: ({ id, data }) => updateUser(id, data),
    onSuccess: () => {
      message.success(t('user_updated'));
      refetchUsers();
      handleCancel();
    },
    onError: (error: any) => message.error(`${t('update_error')}: ${getErrorMessage(error, t)}`),
  });

  const { mutate: deleteUserMutation } = useMutation<void, Error, number>({
    mutationFn: deleteUser,
    onSuccess: () => {
      message.success(t('user_deleted'));
      refetchUsers();
    },
    onError: (error: any) => message.error(`${t('delete_error')}: ${getErrorMessage(error, t)}`),
  });

  const { mutate: startScanMutation, isPending: isScanLoading } = useMutation<MutationResponse, Error, void>({
    mutationFn: startScan,
    onSuccess: (data) => message.success(t('scan_started', { task_id: data.task_id })),
    onError: (error) => message.error(`${t('scan_error')}: ${getErrorMessage(error, t)}`),
  });

  const { mutate: scanAllDomainsMutation, isPending: isAllDomainsADScanLoading } = useMutation<MutationResponse, Error, void>({
    mutationFn: () => scanDomains(),
    onSuccess: (data) => message.success(t('scan_all_domains_started', { task_ids: data.task_ids?.join(', ') })),
    onError: (error) => message.error(`${t('scan_all_domains_error')}: ${getErrorMessage(error, t)}`),
  });

  // Обробка відправлення форми
  const onFinish = async (values: any) => {
    try {
      if (editingItem) {
        updateUserMutation({ id: editingItem.id, data: values });
      } else {
        registerMutation(values);
      }
    } catch (error: any) {
      message.error(getErrorMessage(error, t));
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