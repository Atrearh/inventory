import { Button, Form, Input, Table, Popconfirm, message } from 'antd';
import { useMutation, useQuery } from '@tanstack/react-query';
import { startScan, startADScan, register, getUsers, updateUser, deleteUser } from '../api/api';
import { UserRead, UserCreate } from '../types/schemas';
import { useAuth } from '../context/AuthContext';

// Интерфейс для ответа API
interface MutationResponse {
  status: string;
  task_id: string;
}

const AdminPanel: React.FC = () => {
  const [form] = Form.useForm();
  const { isAuthenticated } = useAuth();
  const { data: users, refetch: refetchUsers } = useQuery<UserRead[], Error>({
    queryKey: ['users'],
    queryFn: getUsers,
    enabled: isAuthenticated, // Запрос выполняется только если пользователь аутентифицирован
  });

  const { mutate: registerMutation, isPending: isRegisterLoading } = useMutation<UserRead, Error, UserCreate>({
    mutationFn: register,
    onSuccess: () => {
      message.success('Пользователь успешно зарегистрирован');
      form.resetFields();
      refetchUsers();
    },
    onError: (error: any) => message.error(`Ошибка регистрации: ${error.response?.data?.error || error.message}`),
  });

  const { mutate: updateUserMutation, isPending: isUpdateLoading } = useMutation<UserRead, Error, { id: number; data: Partial<UserCreate> }>({
    mutationFn: ({ id, data }) => updateUser(id, data),
    onSuccess: () => {
      message.success('Пользователь обновлен');
      refetchUsers();
    },
    onError: (error: any) => message.error(`Ошибка обновления: ${error.response?.data?.error || error.message}`),
  });

  const { mutate: deleteUserMutation, isPending: isDeleteLoading } = useMutation<void, Error, number>({
    mutationFn: deleteUser,
    onSuccess: () => {
      message.success('Пользователь удален');
      refetchUsers();
    },
    onError: (error: any) => message.error(`Ошибка удаления: ${error.response?.data?.error || error.message}`),
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

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id' },
    { title: 'Имя пользователя', dataIndex: 'username', key: 'username' },
    { title: 'Email', dataIndex: 'email', key: 'email' },
    { title: 'Роль', dataIndex: 'role', key: 'role', render: (role: string | null) => role || 'Не указана' },
    { title: 'Активен', dataIndex: 'is_active', key: 'is_active', render: (active: boolean) => (active ? 'Да' : 'Нет') },
    {
      title: 'Действия',
      key: 'actions',
      render: (_: any, record: UserRead) => (
        <>
          <Button
            onClick={() => {
              form.setFieldsValue({ username: record.username, email: record.email, role: record.role });
              updateUserMutation({ id: record.id, data: { username: record.username, email: record.email, role: record.role } });
            }}
            style={{ marginRight: 8 }}
            disabled={isUpdateLoading}
          >
            Редактировать
          </Button>
          <Popconfirm
            title="Вы уверены, что хотите удалить пользователя?"
            onConfirm={() => deleteUserMutation(record.id)}
            okText="Да"
            cancelText="Нет"
          >
            <Button danger disabled={isDeleteLoading}>Удалить</Button>
          </Popconfirm>
        </>
      ),
    },
  ];

  return (
    <div style={{ padding: 12 }}>
      <h1 style={{ marginTop: 0 }}> Администрирование </h1>
      <Button
        type="primary"
        onClick={() => startScanMutation()}
        loading={isScanLoading}
        style={{ marginRight: '10px', marginBottom: 16 }}
      >
        Запустить инвентаризацию
      </Button>
      <Button
        type="primary"
        onClick={() => startADScanMutation()}
        loading={isADScanLoading}
        style={{ marginBottom: 16 }}
      >
        Опросить АД
      </Button>

      <h3>Регистрация нового пользователя</h3>
      <Form
        form={form}
        layout="vertical"
        onFinish={(values) => registerMutation(values)}
        style={{ maxWidth: 400, marginBottom: 24 }}
      >
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
        <Form.Item
          name="password"
          label="Пароль"
          rules={[{ required: true, message: 'Введите пароль' }]}
        >
          <Input.Password />
        </Form.Item>
        <Form.Item name="role" label="Роль">
          <Input placeholder="Например, user или admin" />
        </Form.Item>
        <Form.Item>
          <Button type="primary" htmlType="submit" loading={isRegisterLoading}>
            Зарегистрировать
          </Button>
        </Form.Item>
      </Form>

      <h3>Список пользователей</h3>
      <Table
        dataSource={users}
        columns={columns}
        rowKey="id"
        loading={!users && isAuthenticated}
        pagination={{ pageSize: 10 }}
      />
    </div>
  );
};

export default AdminPanel;