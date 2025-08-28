import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Button, Form, Input } from 'antd';

const Login: React.FC = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  const onFinish = async (values: { email: string; password: string }) => {
    try {
      await login(values.email, values.password);
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