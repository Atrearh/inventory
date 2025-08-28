import { Button, Form, Input, Table, Popconfirm, message, Modal, Space, Flex } from 'antd';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState, useMemo } from 'react';
import { startScan, register, updateUser, deleteUser } from '../api/api';
import { scanDomains } from '../api/domain.api';
import { UserRead, UserCreate, UserUpdate } from '../types/schemas';
import { useAuth } from '../context/AuthContext';
import { useUsers } from '../hooks/useApiQueries';
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
  const { isAuthenticated } = useAuth();
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [editingUser, setEditingUser] = useState<UserRead | null>(null);

  // Запит для отримання списку користувачів
  const { data: users, refetch: refetchUsers, isLoading: isUsersLoading } = useUsers();

  // Мутація для реєстрації користувача
  const { mutate: registerMutation, isPending: isRegisterLoading } = useMutation<UserRead, Error, UserCreate>({
    mutationFn: register,
    onSuccess: () => {
      message.success('Користувача успішно зареєстровано');
      refetchUsers();
      setIsModalVisible(false);
    },
    onError: (error: any) => message.error(`Помилка реєстрації: ${getErrorMessage(error)}`),
  });

  // Мутація для оновлення користувача
  const { mutate: updateUserMutation, isPending: isUpdateLoading } = useMutation<
    UserRead,
    Error,
    { id: number; data: Partial<UserUpdate> }
  >({
    mutationFn: ({ id, data }) => updateUser(id, data),
    onSuccess: () => {
      message.success('Користувача оновлено');
      refetchUsers();
      setIsModalVisible(false);
    },
    onError: (error: any) => message.error(`Помилка оновлення: ${getErrorMessage(error)}`),
  });

  // Мутація для видалення користувача
  const { mutate: deleteUserMutation } = useMutation<void, Error, number>({
    mutationFn: deleteUser,
    onSuccess: () => {
      message.success('Користувача видалено');
      refetchUsers();
    },
    onError: (error: any) => message.error(`Помилка видалення: ${getErrorMessage(error)}`),
  });

  // Мутація для запуску інвентаризації
  const { mutate: startScanMutation, isPending: isScanLoading } = useMutation<MutationResponse, Error, void>({
    mutationFn: startScan,
    onSuccess: (data) => message.success(`Інвентаризацію запущено, task_id: ${data.task_id}`),
    onError: (error) => message.error(`Помилка: ${getErrorMessage(error)}`),
  });

  // Мутація для запуску сканування всіх доменів
  const { mutate: scanAllDomainsMutation, isPending: isAllDomainsADScanLoading } = useMutation<MutationResponse, Error, void>({
    mutationFn: () => scanDomains(), // Виклик без domainId для сканування всіх доменів
    onSuccess: (data) => message.success(`Сканування всіх доменів запущено, task_ids: ${data.task_ids?.join(', ')}`),
    onError: (error) => message.error(`Помилка сканування всіх доменів: ${getErrorMessage(error)}`),
  });

  // Відкриття модального вікна для створення користувача
  const handleAddNewUser = () => {
    setEditingUser(null);
    form.resetFields();
    setIsModalVisible(true);
  };

  // Відкриття модального вікна для редагування користувача
  const handleEditUser = (record: UserRead) => {
    setEditingUser(record);
    form.setFieldsValue(record);
    setIsModalVisible(true);
  };

  // Закриття модального вікна
  const handleCancel = () => {
    setIsModalVisible(false);
    setEditingUser(null);
    form.resetFields();
  };

  // Обробка відправлення форми
  const onFinish = async (values: any) => {
    try {
      if (editingUser) {
        updateUserMutation({ id: editingUser.id, data: values });
      } else {
        registerMutation(values);
      }
    } catch (error: any) {
      message.error(getErrorMessage(error));
    }
  };

  // Визначення стовпців таблиці
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
            <Button onClick={() => handleEditUser(record)} aria-label={`Редагувати користувача ${record.username}`}>
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
    [deleteUserMutation, handleEditUser]
  );

  return (
    <div style={{ padding: '16px 24px' }}>
      <Flex justify="space-between" align="center" style={{ marginBottom: 24 }}>
        <h1 style={{ marginTop: 0, marginBottom: 0 }}>Адміністрування</h1>
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
      </Flex>

      <Flex justify="space-between" align="center" style={{ marginBottom: 16 }}>
        <h2>Список користувачів</h2>
        <Button type="primary" onClick={handleAddNewUser} aria-label="Додати нового користувача">
          Додати користувача
        </Button>
      </Flex>

      <Table
        dataSource={users}
        columns={columns}
        rowKey="id"
        loading={isUsersLoading}
        pagination={false}
        aria-label="Таблиця користувачів"
      />

      <h2 style={{ marginTop: 32, marginBottom: 16 }}>Керування доменами</h2>
      <DomainManagement />

      <Modal
        title={editingUser ? 'Редагування користувача' : 'Новий користувач'}
        open={isModalVisible}
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
            aria-label={editingUser ? 'Зберегти зміни користувача' : 'Створити користувача'}
          >
            {editingUser ? 'Зберегти' : 'Створити'}
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
          {!editingUser && (
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
