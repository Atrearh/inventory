// src/components/AdminPanel.tsx
import { Button, Form, Input, Table, Popconfirm, message, Modal, Space, Flex, Card, Typography } from 'antd';
import { useMutation } from '@tanstack/react-query';
import { useState, useMemo } from 'react';
import { startScan, register, updateUser, deleteUser } from '../api/api';
import { scanDomains } from '../api/domain.api';
import { UserRead, UserCreate, UserUpdate } from '../types/schemas';
import { useAuth } from '../context/AuthContext';
import { useUsers } from '../hooks/useApiQueries';
import { useModalForm } from '../hooks/useModalForm'; // Додано
import DomainManagement from './DomainManagement';

// Утилітна функція для уніфікованої обробки помилок
const getErrorMessage = (error: Error | any): string =>
  error.response?.data?.detail || error.message || 'Невідома помилка';

interface MutationResponse {
  status: string;
  task_id?: string;
  task_ids?: string[];
}

const AdminPanel: React.FC = () => {
  const [form] = Form.useForm();
  const { isModalOpen, editingItem, openCreateModal, openEditModal, handleCancel } = useModalForm<UserRead>({ form });
  const { data: users, refetch: refetchUsers, isLoading: isUsersLoading } = useUsers();

  // Мутації (без змін)
  const { mutate: registerMutation, isPending: isRegisterLoading } = useMutation<UserRead, Error, UserCreate>({
    mutationFn: register,
    onSuccess: () => {
      message.success('Користувача успішно зареєстровано');
      refetchUsers();
      handleCancel();
    },
    onError: (error: any) => message.error(`Помилка реєстрації: ${getErrorMessage(error)}`),
  });

  const { mutate: updateUserMutation, isPending: isUpdateLoading } = useMutation<
    UserRead,
    Error,
    { id: number; data: Partial<UserUpdate> }
  >({
    mutationFn: ({ id, data }) => updateUser(id, data),
    onSuccess: () => {
      message.success('Користувача оновлено');
      refetchUsers();
      handleCancel();
    },
    onError: (error: any) => message.error(`Помилка оновлення: ${getErrorMessage(error)}`),
  });

  const { mutate: deleteUserMutation } = useMutation<void, Error, number>({
    mutationFn: deleteUser,
    onSuccess: () => {
      message.success('Користувача видалено');
      refetchUsers();
    },
    onError: (error: any) => message.error(`Помилка видалення: ${getErrorMessage(error)}`),
  });

  const { mutate: startScanMutation, isPending: isScanLoading } = useMutation<MutationResponse, Error, void>({
    mutationFn: startScan,
    onSuccess: (data) => message.success(`Інвентаризацію запущено, task_id: ${data.task_id}`),
    onError: (error) => message.error(`Помилка: ${getErrorMessage(error)}`),
  });

  const { mutate: scanAllDomainsMutation, isPending: isAllDomainsADScanLoading } = useMutation<MutationResponse, Error, void>({
    mutationFn: () => scanDomains(),
    onSuccess: (data) => message.success(`Сканування всіх доменів запущено, task_ids: ${data.task_ids?.join(', ')}`),
    onError: (error) => message.error(`Помилка сканування всіх доменів: ${getErrorMessage(error)}`),
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
      message.error(getErrorMessage(error));
    }
  };

  // Визначення стовпців таблиці (без змін)
  const columns = useMemo(
    () => [
      { title: 'ID', dataIndex: 'id', key: 'id' },
      { title: "Ім'я користувача", dataIndex: 'username', key: 'username' },
      { title: 'Email', dataIndex: 'email', key: 'email' },
      { title: 'Роль', dataIndex: 'role', key: 'role' },
      {
        title: 'Дії',
        key: 'actions',
        render: (_: any, record: UserRead) => (
          <Space>
            <Button onClick={() => openEditModal(record)} aria-label={`Редагувати користувача ${record.username}`}>
              Редагувати
            </Button>
            <Popconfirm
              title="Впевнені, що хочете видалити?"
              onConfirm={() => deleteUserMutation(record.id)}
              okText="Так"
              cancelText="Ні"
            >
              <Button danger aria-label={`Видалити користувача ${record.username}`}>
                Видалити
              </Button>
            </Popconfirm>
          </Space>
        ),
      },
    ],
    [deleteUserMutation, openEditModal]
  );

  return (
    <div style={{ padding: '16px 24px' }}>
      <Typography.Title level={1}>Адміністрування</Typography.Title>

      <Card title="Глобальні дії" style={{ marginBottom: 24 }}>
        <Space>
          <Button
            onClick={() => startScanMutation()}
            loading={isScanLoading}
            disabled={isScanLoading || isAllDomainsADScanLoading}
            aria-label="Запустити інвентаризацію"
          >
            Запустити інвентаризацію
          </Button>
          <Button
            onClick={() => scanAllDomainsMutation()}
            loading={isAllDomainsADScanLoading}
            disabled={isScanLoading || isAllDomainsADScanLoading}
            aria-label="Опитати всі домени"
          >
            Опитати всі домени
          </Button>
        </Space>
      </Card>

      <Card
        title="Керування користувачами"
        extra={
          <Button type="primary" onClick={openCreateModal} aria-label="Додати нового користувача">
            Додати користувача
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
          aria-label="Таблиця користувачів"
        />
      </Card>

      <Card title="Керування доменами">
        <DomainManagement />
      </Card>

      <Modal
        title={editingItem ? 'Редагування користувача' : 'Новий користувач'}
        open={isModalOpen}
        onCancel={handleCancel}
        footer={[
          <Button key="back" onClick={handleCancel} aria-label="Скасувати">
            Відміна
          </Button>,
          <Button
            key="submit"
            type="primary"
            loading={isRegisterLoading || isUpdateLoading}
            onClick={() => form.submit()}
            aria-label={editingItem ? 'Зберегти зміни користувача' : 'Створити користувача'}
          >
            {editingItem ? 'Зберегти' : 'Створити'}
          </Button>,
        ]}
      >
        <Form form={form} layout="vertical" onFinish={onFinish} style={{ marginTop: 24 }}>
          <Form.Item
            name="username"
            label="Ім’я користувача"
            rules={[{ required: true, message: 'Введіть ім’я користувача' }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="email"
            label="Email"
            rules={[{ required: true, type: 'email', message: 'Введіть коректний email' }]}
          >
            <Input />
          </Form.Item>
          {!editingItem && (
            <Form.Item
              name="password"
              label="Пароль"
              rules={[{ required: true, message: 'Введіть пароль' }]}
            >
              <Input.Password />
            </Form.Item>
          )}
          <Form.Item name="role" label="Роль">
            <Input placeholder="Наприклад, user або admin" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default AdminPanel;