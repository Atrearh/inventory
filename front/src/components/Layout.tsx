import React, { useState, useContext } from 'react';
import { Layout, Menu, Button } from 'antd';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../context/AuthContext';
import { ThemeContext } from '../context/ThemeContext';
import HeaderWidget from './HeaderWidget';
import { MenuFoldOutlined, MenuUnfoldOutlined, DashboardOutlined, DesktopOutlined, SettingOutlined, UserOutlined } from '@ant-design/icons';
import './Layout.css';

const { Sider, Content, Header } = Layout;

const AppLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const location = useLocation();
  const { t } = useTranslation();
  const { logout } = useAuth();
  const { dark } = useContext(ThemeContext);
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(false);

  // Функція для розлогінювання
  const handleLogout = async () => {
    try {
      await logout();
      navigate('/login');
    } catch (error: any) {
      console.error('Помилка виходу:', error.message);
    }
  };

  // Встановлюємо атрибут data-theme на body
  React.useEffect(() => {
    document.body.setAttribute('data-theme', dark ? 'dark' : 'light');
  }, [dark]);

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        trigger={null}
        style={{ position: 'relative' }}
      >
        <Button
          type="text"
          icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
          onClick={() => setCollapsed(!collapsed)}
          style={{
            color: '#fff',
            width: '100%',
            textAlign: 'left',
            padding: '16px',
            borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
            position: 'absolute',
            top: 0,
            zIndex: 1000,
          }}
          aria-label={collapsed ? t('expand_menu') : t('collapse_menu')}
        >
          {!collapsed && (collapsed ? t('expand_menu') : t('collapse_menu'))}
        </Button>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={[
            {
              key: '/',
              icon: <DashboardOutlined />,
              label: <Link to="/">{t('dashboard')}</Link>,
            },
            {
              key: '/computers',
              icon: <DesktopOutlined />,
              label: <Link to="/computers">{t('computers')}</Link>,
            },
            {
              key: '/admin',
              icon: <UserOutlined />,
              label: <Link to="/admin">{t('admin')}</Link>,
            },
            {
              key: '/settings',
              icon: <SettingOutlined />,
              label: <Link to="/settings">{t('settings')}</Link>,
            },
            {
              key: 'logout',

              label: (
                <Button
                  type="text"
                  onClick={handleLogout}
                  style={{ color: '#fff', width: '100%', textAlign: 'left' }}
                >
                  {!collapsed && t('logout')}
                </Button>
              ),
            },
          ]}
          style={{ paddingTop: '56px' }}
        />
      </Sider>
      <Layout>
        <Header style={{ padding: 0, background: dark ? '#1f1f1f' : '#fff', display: 'flex', justifyContent: 'flex-end' }}>
          <HeaderWidget />
        </Header>
        <Content
          style={{
            margin: 0,
            padding: '16px',
            minHeight: 'calc(100vh - 64px)',
          }}
        >
          {children}
        </Content>
      </Layout>
    </Layout>
  );
};

export default AppLayout;