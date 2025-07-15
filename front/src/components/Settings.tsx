import { useState, useEffect } from 'react';
import { useQuery, useMutation, UseQueryOptions } from '@tanstack/react-query';
import { Form, Input, Button, Select, message, Spin } from 'antd';
import { apiInstance } from '../api/api';
import { useAuth } from '../context/AuthContext';

interface SettingsData {
  ad_server_url?: string;
  domain?: string;
  ad_username?: string;
  ad_password?: string;
  api_url?: string;
  test_hosts?: string;
  log_level?: string;
  scan_max_workers?: number;
  polling_days_threshold?: number;
  winrm_operation_timeout?: number;
  winrm_read_timeout?: number;
  winrm_port?: number;
  winrm_server_cert_validation?: string;
  ping_timeout?: number;
  powershell_encoding?: string;
  json_depth?: number;
  server_port?: number;
  cors_allow_origins?: string;
  allowed_ips?: string;
}

const Settings: React.FC = () => {
  const { isAuthenticated, isLoading: isAuthLoading } = useAuth();
  const [form] = Form.useForm();
  const [messageApi, contextHolder] = message.useMessage();

  const queryOptions: UseQueryOptions<SettingsData, Error, SettingsData, ['settings']> = {
    queryKey: ['settings'],
    queryFn: async () => {
      const response = await apiInstance.get<SettingsData>('/settings');
      console.log('Settings fetched:', response.data);
      return response.data;
    },
    enabled: isAuthenticated && !isAuthLoading,
  };

  const { data, isLoading, error } = useQuery(queryOptions);

  const mutation = useMutation({
    mutationFn: async (values: SettingsData) => {
      const processedValues = {
        ...values,
        cors_allow_origins: values.cors_allow_origins?.trim(),
        allowed_ips: values.allowed_ips?.trim(),
      };
      const response = await apiInstance.post('/settings', processedValues);
      console.log('Settings updated:', response.data);
      return response.data;
    },
    onSuccess: () => {
      messageApi.success('Настройки успешно обновлены. Перезапустите сервер для применения изменений.');
    },
    onError: (error: any) => {
      if (error.response?.status === 401) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login';
      }
      messageApi.error(`Ошибка обновления настроек: ${error.response?.data?.error || error.message}`);
    },
  });

  useEffect(() => {
    if (data) {
      form.setFieldsValue(data);
    }
  }, [data, form]);

  const onFinish = (values: SettingsData) => {
    if (!isAuthenticated) {
      messageApi.error('Пожалуйста, войдите в систему для изменения настроек');
      return;
    }
    mutation.mutate(values);
  };

  if (isAuthLoading) return <div style={{ textAlign: 'center', padding: '50px' }}><Spin size="large" /></div>;
  if (!isAuthenticated) {
    window.location.href = '/login';
    return null;
  }
  if (isLoading) return <div style={{ textAlign: 'center', padding: '50px' }}><Spin size="large" /></div>;
  if (error) {
    if ((error as any).response?.status === 401) {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      window.location.href = '/login';
    }
    return <div>Ошибка загрузки настроек: {(error as any).message}</div>;
  }

  return (
    <>
      {contextHolder}
      <Form
        form={form}
        layout="vertical"
        onFinish={onFinish}
        style={{ maxWidth: 600, margin: '0 auto' }}
      >
        <Form.Item label="AD Server URL" name="ad_server_url">
          <Input />
        </Form.Item>
        <Form.Item label="Domain" name="domain">
          <Input />
        </Form.Item>
        <Form.Item label="AD Username" name="ad_username">
          <Input />
        </Form.Item>
        <Form.Item label="AD Password" name="ad_password" rules={[{ required: false }]}>
          <Input.Password />
        </Form.Item>
        <Form.Item label="API URL" name="api_url">
          <Input />
        </Form.Item>
        <Form.Item label="Test Hosts" name="test_hosts">
          <Input placeholder="Comma-separated list" />
        </Form.Item>
        <Form.Item label="Log Level" name="log_level">
          <Select>
            <Select.Option value="DEBUG">DEBUG</Select.Option>
            <Select.Option value="INFO">INFO</Select.Option>
            <Select.Option value="WARNING">WARNING</Select.Option>
            <Select.Option value="ERROR">ERROR</Select.Option>
            <Select.Option value="CRITICAL">CRITICAL</Select.Option>
          </Select>
        </Form.Item>
        <Form.Item label="Scan Max Workers" name="scan_max_workers">
          <Input type="number" min={1} />
        </Form.Item>
        <Form.Item label="Polling Days Threshold" name="polling_days_threshold">
          <Input type="number" min={1} />
        </Form.Item>
        <Form.Item label="WinRM Operation Timeout" name="winrm_operation_timeout">
          <Input type="number" min={1} />
        </Form.Item>
        <Form.Item label="WinRM Read Timeout" name="winrm_read_timeout">
          <Input type="number" min={1} />
        </Form.Item>
        <Form.Item label="WinRM Port" name="winrm_port">
          <Input type="number" min={1} />
        </Form.Item>
        <Form.Item label="WinRM Server Cert Validation" name="winrm_server_cert_validation">
          <Select>
            <Select.Option value="validate">Validate</Select.Option>
            <Select.Option value="ignore">Ignore</Select.Option>
          </Select>
        </Form.Item>
        <Form.Item label="Ping Timeout" name="ping_timeout">
          <Input type="number" min={1} />
        </Form.Item>
        <Form.Item label="Powershell Encoding" name="powershell_encoding">
          <Input />
        </Form.Item>
        <Form.Item label="JSON Depth" name="json_depth">
          <Input type="number" min={1} />
        </Form.Item>
        <Form.Item label="Server Port" name="server_port">
          <Input type="number" min={1} />
        </Form.Item>
        <Form.Item
          label="CORS Allow Origins"
          name="cors_allow_origins"
          rules={[{ message: 'Введите origins, разделённые запятыми, например: http://localhost:8000,http://localhost:5173' }]}
        >
          <Input placeholder="Enter origins, e.g. http://localhost:8000,http://localhost:5173" />
        </Form.Item>
        <Form.Item
          label="Allowed IPs"
          name="allowed_ips"
          rules={[{ message: 'Введите IP или диапазоны, разделённые запятыми, например: 127.0.0.1,192.168.1.0/24' }]}
        >
          <Input placeholder="Enter IPs or ranges, e.g. 127.0.0.1,192.168.1.0/24" />
        </Form.Item>
        <Form.Item>
          <Button type="primary" htmlType="submit" loading={mutation.isPending} disabled={!isAuthenticated}>
            Сохранить
          </Button>
        </Form.Item>
      </Form>
    </>
  );
};

export default Settings;