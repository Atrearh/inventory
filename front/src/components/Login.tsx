import React, { useState, useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { ThemeContext } from '../context/ThemeContext';
import { Button, Form, Input, Card } from 'antd';
import { useQueryClient } from '@tanstack/react-query';
import { getStatistics, getComputers, getUsers } from '../api/api';
import { Filters, isServerOs } from '../hooks/useComputerFilters';
import { ITEMS_PER_PAGE } from '../config';
import { useTranslation } from 'react-i18next';
import LanguageAndThemeSwitch from './LanguageAndThemeSwitch';

const Login: React.FC = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const { dark } = useContext(ThemeContext);
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const { t } = useTranslation();

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
    domain: undefined,
  };

  const onFinish = async (values: { email: string; password: string }) => {
    try {
      await login(values.email, values.password);
      console.log('Login successful. Starting prefetching...');
      
      await queryClient.prefetchQuery({
        queryKey: ['statistics'],
        queryFn: () => getStatistics({ metrics: ['total_computers', 'os_distribution', 'low_disk_space_with_volumes', 'last_scan_time', 'status_stats'] }),
      });
      await queryClient.prefetchQuery({
        queryKey: ['computers', defaultFilters],
        queryFn: () => {
          const params: Partial<Filters> = { ...defaultFilters, hostname: undefined, limit: 1000 };
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
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        backgroundColor: dark ? '#1a1a1a' : '#f0f2f5',
      }}
    >
      <Card style={{ width: 400, background: dark ? '#2c2c2c' : '#ffffff', color: dark ? '#d9d9d9' : '#000000' }}>
        <h2 style={{ textAlign: 'center', marginBottom: 24, color: dark ? '#d9d9d9' : '#000000', userSelect: 'none' }}>
          {t('login', 'Вхід')}
        </h2>
        <Form onFinish={onFinish} layout="vertical">
          <Form.Item
            name="email"
            rules={[
              { required: true, message: t('enter_email', 'Введіть email') },
              { type: 'email', message: t('invalid_email', 'Некоректний email') },
            ]}
          >
            <Input placeholder={t('email', 'Email')} />
          </Form.Item>
          <Form.Item
            name="password"
            rules={[
              { required: true, message: t('enter_password', 'Введіть пароль') },
              { min: 6, message: t('password_min_length', 'Пароль має містити щонайменше 6 символів') },
            ]}
          >
            <Input.Password placeholder={t('password', 'Пароль')} />
          </Form.Item>
          {error && <p style={{ color: dark ? '#ff4d4f' : '#ff0000', marginBottom: 16 }}>{error}</p>}
          <Form.Item>
            <Button type="primary" htmlType="submit" block>
              {t('login', 'Вхід')}
            </Button>
          </Form.Item>
          <Form.Item>
            <LanguageAndThemeSwitch />
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
};

export default Login;