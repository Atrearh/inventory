import { useEffect } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Form, Select, Button, message, Spin, Card, Typography } from 'antd';
import { apiInstance } from '../api/api';
import { useTimezone } from '../context/TimezoneContext';

const { Title } = Typography;
const availableTimezones = Intl.supportedValuesOf('timeZone');

const Settings: React.FC = () => {
  const [form] = Form.useForm();
  const { timezone, setTimezone, isLoading: isTimezoneLoading } = useTimezone();

  const { data, isLoading, error } = useQuery({
    queryKey: ['settings'],
    queryFn: async () => {
      const response = await apiInstance.get('/settings');
      return response.data;
    },
    enabled: !isTimezoneLoading,
  });

  const mutation = useMutation({
    mutationFn: async (values: { timezone: string }) => {
      return await apiInstance.post('/settings', values);
    },
    onSuccess: (data) => {
      message.success('Налаштування часового поясу оновлено!');
      if (data.data.timezone) {
        setTimezone(data.data.timezone);
      }
    },
    onError: (error: any) => {
      message.error(`Помилка оновлення: ${error.message}`);
    },
  });

  useEffect(() => {
    if (data?.timezone) {
      form.setFieldsValue({ timezone: data.timezone });
    } else {
      form.setFieldsValue({ timezone });
    }
  }, [data, timezone, form]);

  if (isLoading || isTimezoneLoading) {
    return <div style={{ padding: 50, textAlign: 'center' }}><Spin size="large" /></div>;
  }
  if (error) {
    return <div>Помилка завантаження налаштувань: {error.message}</div>;
  }

  return (
    <div style={{ padding: '24px' }}>
      <Title level={2}>Налаштування</Title>
      <Card>
        <Form
          form={form}
          layout="vertical"
          onFinish={(values) => mutation.mutate(values)}
          style={{ maxWidth: 400 }}
        >
          <Form.Item
            label="Часовий пояс"
            name="timezone"
            rules={[{ required: true, message: 'Будь ласка, оберіть часовий пояс' }]}
            tooltip="Усі дати та час у системі будуть відображатися відповідно до цього налаштування."
          >
            <Select
              showSearch
              placeholder="Оберіть часовий пояс"
              optionFilterProp="children"
              filterOption={(input, option) => (option?.label ?? '').toLowerCase().includes(input.toLowerCase())}
              options={availableTimezones.map(tz => ({ value: tz, label: tz }))}
            />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={mutation.isPending}>
              Зберегти
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
};

export default Settings;