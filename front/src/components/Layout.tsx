// front/src/components/Layout.tsx
import React from 'react';
import { Layout, Menu, Button } from 'antd';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const { Content, Sider } = Layout;

const LayoutComponent: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { logout } = useAuth();
  const navigate = useNavigate();

  const menuItems = [
    { key: '1', label: <Link to="/">Статистика</Link> },
    { key: '2', label: <Link to="/computers">Комп'ютери</Link> },
    { key: '3', label: <Link to="/settings">Налаштування</Link> },
    { key: '4', label: <Link to="/admin">Адміністрування</Link> },
  ];

  const handleLogout = async () => {
    try {
      await logout();
      navigate('/login');
    } catch (error) {
      console.error('Помилка виходу:', error);
    }
  };

  return (
    <Layout style={{ padding: 0, minHeight: '100vh' }}>
      <Sider>
        <Menu theme="dark" mode="inline" defaultSelectedKeys={['1']} items={menuItems} />
        <Button
          type="primary"
          style={{ margin: '16px', width: 'calc(100% - 32px)' }}
          onClick={handleLogout}
        >
          Вихід
        </Button>
      </Sider>
      <Layout>
        <Content style={{ padding: 0, background: '#fff' }}>
          {children}
        </Content>
      </Layout>
    </Layout>
  );
};

export default LayoutComponent;