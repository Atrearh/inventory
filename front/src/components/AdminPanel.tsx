import { Button, Form, Input, Table, Popconfirm, message, Modal, Space, Flex } from 'antd';
import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';
import { startScan, startADScan, register, updateUser, deleteUser } from '../api/api';
import { UserRead, UserCreate, UserUpdate } from '../types/schemas';
import { useAuth } from '../context/AuthContext';
import { useUsers } from '../hooks/useApiQueries'; // Новий імпорт
import DomainManagement from './DomainManagement';  // Новий імпорт для керування доменами

interface MutationResponse {
  status: string;
  task_id: string;
}

const AdminPanel: React.FC = () => {
  const [form] = Form.useForm();
  const { isAuthenticated } = useAuth();
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [editingUser, setEditingUser] = useState<UserRead | null>(null);

  const { data: users, refetch: refetchUsers, isLoading: isUsersLoading } = useUsers();

  const { mutate: registerMutation, isPending: isRegisterLoading } = useMutation<UserRead, Error, UserCreate>({
    mutationFn: register,
    onSuccess: () => {
      message.success('Пользователь успешно зарегистрирован');
      refetchUsers();
      setIsModalVisible(false);
    },
    onError: (error: any) => message.error(`Ошибка регистрации: ${error.response?.data?.detail || error.message}`),
  });

  const { mutate: updateUserMutation, isPending: isUpdateLoading } = useMutation<UserRead, Error, { id: number; data: Partial<UserUpdate> }>({
    mutationFn: ({ id, data }) => updateUser(id, data),
    onSuccess: () => {
      message.success('Пользователь обновлен');
      refetchUsers();
      setIsModalVisible(false);
    },
    onError: (error: any) => message.error(`Ошибка обновления: ${error.response?.data?.detail || error.message}`),
  });

  const { mutate: deleteUserMutation } = useMutation<void, Error, number>({
    mutationFn: deleteUser,
    onSuccess: () => {
      message.success('Пользователь удален');
      refetchUsers();
    },
    onError: (error: any) => message.error(`Ошибка удаления: ${error.response?.data?.detail || error.message}`),
  });

  const { mutate: startScanMutation, isPending: isScanLoading } = useMutation<MutationResponse, Error, void>({
    mutationFn: startScan,
    onSuccess: (data) => message.success(`Инвентаризация запущена, task_id: ${data.task_id}`),
    onError: (error) => message.error(`Ошибка: ${error.message}`),
  });

  const { mutate: startADScanMutation, isPending: isADScanLoading } = useMutation<MutationResponse, Error, void>({
    mutationFn: startADScan,
    onSuccess: (data) => message.success(`Сканирование AD запущено, task_id: ${data.task_id}`),
    onError: (error) => message.error(`Ошибка: ${error.message}`),
  });

  const handleAddNewUser = () => {
    setEditingUser(null);
    form.resetFields();
    setIsModalVisible(true);
  };

  const handleEditUser = (record: UserRead) => {
    setEditingUser(record);
    form.setFieldsValue(record);
    setIsModalVisible(true);
  };

  const handleCancel = () => {
    setIsModalVisible(false);
  };

  const onFinish = (values: UserCreate) => {
    if (editingUser) {
      updateUserMutation({ id: editingUser.id, data: values });
    } else {
      registerMutation(values);
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 50 },
    { title: 'Имя пользователя', dataIndex: 'username', key: 'username' },
    { title: 'Email', dataIndex: 'email', key: 'email' },
    { title: 'Роль', dataIndex: 'role', key: 'role', render: (role: string | null) => role || 'user' },
    { title: 'Активен', dataIndex: 'is_active', key: 'is_active', render: (active: boolean) => (active ? 'Да' : 'Нет') },
    {
      title: 'Действия',
      key: 'actions',
      render: (_: any, record: UserRead) => (
        <Space size="middle">
          <Button onClick={() => handleEditUser(record)}>Редактировать</Button>
          <Popconfirm
            title="Вы уверены, что хотите удалить?"
            onConfirm={() => deleteUserMutation(record.id)}
            okText="Да"
            cancelText="Нет"
          >
            <Button danger>Удалить</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: '16px 24px' }}>
      <Flex justify="space-between" align="center" style={{ marginBottom: 24 }}>
        <h1 style={{ marginTop: 0, marginBottom: 0 }}>Администрирование</h1>
        <Space>
          <Button onClick={() => startScanMutation()} loading={isScanLoading}>
            Запустить инвентаризацию
          </Button>
          <Button onClick={() => startADScanMutation()} loading={isADScanLoading}>
            Опросить АД
          </Button>
        </Space>
      </Flex>

      <Flex justify="space-between" align="center" style={{ marginBottom: 16 }}>
        <h2>Список пользователей</h2>
        <Button type="primary" onClick={handleAddNewUser}>
          Добавить пользователя
        </Button>
      </Flex>

      <Table
        dataSource={users}
        columns={columns}
        rowKey="id"
        loading={isUsersLoading}
        pagination={{ pageSize: 10 }}
      />

      <h2 style={{ marginTop: 32, marginBottom: 16 }}>Керування доменами</h2>  {/* Новий заголовок для секції доменів */}
      <DomainManagement />  {/* Додаємо компонент для керування доменами */}

      <Modal
        title={editingUser ? 'Редактирование пользователя' : 'Новый пользователь'}
        open={isModalVisible}
        onCancel={handleCancel}
        footer={[
          <Button key="back" onClick={handleCancel}>
            Отмена
          </Button>,
          <Button
            key="submit"
            type="primary"
            loading={isRegisterLoading || isUpdateLoading}
            onClick={() => form.submit()}
          >
            {editingUser ? 'Сохранить' : 'Создать'}
          </Button>,
        ]}
      >
        <Form form={form} layout="vertical" onFinish={onFinish} style={{ marginTop: 24 }}>
          <Form.Item
            name="username"
            label="Имя пользователя"
            rules={[{ required: true, message: 'Введите имя пользователя' }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="email"
            label="Email"
            rules={[{ required: true, type: 'email', message: 'Введите корректный email' }]}
          >
            <Input />
          </Form.Item>
          {!editingUser && (
            <Form.Item
              name="password"
              label="Пароль"
              rules={[{ required: true, message: 'Введите пароль' }]}
            >
              <Input.Password />
            </Form.Item>
          )}
          <Form.Item name="role" label="Роль">
            <Input placeholder="Например, user или admin" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default AdminPanel;