import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Button, Form, Input } from 'antd';
import { useQueryClient } from '@tanstack/react-query';
import { getStatistics, getComputers, getUsers } from '../api/api';
import { Filters, isServerOs } from '../hooks/useComputerFilters'; // Додано isServerOs
import { ITEMS_PER_PAGE } from '../config'; // Додано для консистентності
import { useTranslation } from 'react-i18next';

const Login: React.FC = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const { t } = useTranslation();

  // Дефолтні фільтри для консистентності з useComputerFilters
  const defaultFilters: Filters = {
    hostname: undefined,
    os_name: undefined,
    check_status: undefined,
    show_disabled: false,
    sort_by: 'hostname',
    sort_order: 'asc',
    page: 1,
    limit: ITEMS_PER_PAGE,
    server_filter: undefined,
    ip_range: undefined,
  };

  const onFinish = async (values: { email: string; password: string }) => {
    try {
      await login(values.email, values.password);

      console.log('Login successful. Starting prefetching...');

      // Попереднє завантаження статистики
      await queryClient.prefetchQuery({
        queryKey: ['statistics'],
        queryFn: () =>
          getStatistics({
            metrics: [
              'total_computers',
              'os_distribution',
              'low_disk_space_with_volumes',
              'last_scan_time',
              'status_stats',
            ],
          }),
      });

      // Попереднє завантаження комп'ютерів з уніфікованим ключем
      await queryClient.prefetchQuery({
        queryKey: ['computers', defaultFilters],
        queryFn: () => {
          const params: Partial<Filters> = {
            ...defaultFilters,
            hostname: undefined, // Вимикаємо серверну фільтрацію по hostname
            limit: 1000,
          };
          if (params.os_name && params.os_name.toLowerCase() === 'unknown') {
            params.os_name = 'unknown';
          } else if (params.os_name && isServerOs(params.os_name)) {
            params.server_filter = 'server';
          } else {
            params.server_filter = undefined;
          }
          return getComputers(params as Filters);
        },
      });

      // Попереднє завантаження користувачів
      await queryClient.prefetchQuery({
        queryKey: ['users'],
        queryFn: getUsers,
      });

      console.log('Prefetching complete.');
      navigate('/');
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
          rules={[
            { required: true, message: 'Введіть email' },
            { type: 'email', message: 'Невірний формат email' },
          ]}
        >
          <Input placeholder="Email" />
        </Form.Item>
        <Form.Item
          name="password"
          rules={[
            { required: true, message: 'Введіть пароль' },
            { min: 6, message: 'Пароль має бути не менше 6 символів' },
          ]}
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