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
    } catch (err) {
      setError('Неверные учетные данные');
    }
  };

  return (
    <div style={{ maxWidth: 400, margin: '50px auto' }}>
      <h2>Вход</h2>
      <Form onFinish={onFinish}>
        <Form.Item
          name="email"
          rules={[{ required: true, message: 'Введите email' }]}
        >
          <Input placeholder="Email" />
        </Form.Item>
        <Form.Item
          name="password"
          rules={[{ required: true, message: 'Введите пароль' }]}
        >
          <Input.Password placeholder="Пароль" />
        </Form.Item>
        {error && <p style={{ color: 'red' }}>{error}</p>}
        <Form.Item>
          <Button type="primary" htmlType="submit">
            Войти
          </Button>
        </Form.Item>
      </Form>
    </div>
  );
};

export default Login;