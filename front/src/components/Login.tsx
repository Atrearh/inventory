// front/src/components/Login.tsx
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Button, Form, Input } from 'antd';
import { useQueryClient } from '@tanstack/react-query'; // 👈 1. Імпортуємо useQueryClient
import { getStatistics, getComputers, getUsers } from '../api/api'; // 👈 2. Імпортуємо функції для запитів

const Login: React.FC = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient(); // 👈 3. Отримуємо екземпляр queryClient

  const onFinish = async (values: { email: string; password: string }) => {
    try {
      await login(values.email, values.password); // [cite: 1166]

      // 👇 4. Додаємо логіку попереднього завантаження
      console.log('Login successful. Starting prefetching...');

      // Попереднє завантаження статистики для головної сторінки
      await queryClient.prefetchQuery({
        queryKey: ['statistics'],
        queryFn: () => getStatistics({ metrics: ['total_computers', 'os_distribution', 'low_disk_space_with_volumes', 'last_scan_time', 'status_stats'] }),
      });

      // Попереднє завантаження першої сторінки комп'ютерів
      await queryClient.prefetchQuery({
        queryKey: ['computers', { page: 1, limit: 1000, sort_by: 'hostname', sort_order: 'asc' }],
        queryFn: () =>
          getComputers({
            page: 1,
            limit: 1000,
            sort_by: 'hostname',
            sort_order: 'asc',
            hostname: '',
            os_name: '',
            check_status: '',
            show_disabled: false,
          }),
      });
      
      // Попереднє завантаження списку користувачів для адмін-панелі
      await queryClient.prefetchQuery({
        queryKey: ['users'],
        queryFn: getUsers,
      });

      console.log('Prefetching complete.');
      
      navigate('/'); // [cite: 1167]
    } catch (err: any) {
      setError(err.message);
    }
  };

  return (
    <div style={{ maxWidth: 400, margin: '50px auto' }}>
      <h2>Вхід</h2>
      <Form onFinish={onFinish} layout="vertical">
        <Form.Item
          name="email"
          rules={[{ required: true, message: 'Введіть email' }, { type: 'email', message: 'Невірний формат email' }]}
        >
          <Input placeholder="Email" />
        </Form.Item>
        <Form.Item
          name="password"
          rules={[{ required: true, message: 'Введіть пароль' }, { min: 6, message: 'Пароль має бути не менше 6 символів' }]}
        >
          <Input.Password placeholder="Пароль" />
        </Form.Item>
        {error && <p style={{ color: 'red', marginBottom: 16 }}>{error}</p>}
        <Form.Item>
          <Button type="primary" htmlType="submit" block>
            Увійти
          </Button>
        </Form.Item>
      </Form>
    </div>
  );
};

export default Login;