import React, { useState, useContext } from 'react';
import { Layout, Menu, Button, Typography } from 'antd';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../context/AuthContext';
import { ThemeContext } from '../context/ThemeContext';
import { usePageTitle } from '../context/PageTitleContext';
import HeaderWidget from './HeaderWidget';
import { MenuFoldOutlined, MenuUnfoldOutlined, DashboardOutlined, DesktopOutlined, SettingOutlined, UserOutlined } from '@ant-design/icons';


const { Sider, Content, Header } = Layout;

const AppLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const location = useLocation();
  const { t } = useTranslation();
  const { logout } = useAuth();
  const { dark } = useContext(ThemeContext);
  const { pageTitle } = usePageTitle();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(false);

  const handleLogout = async () => {
    try {
      await logout();
      navigate('/login');
    } catch (error: any) {
      console.error('Помилка виходу:', error.message);
    }
  };

  React.useEffect(() => {
    document.body.setAttribute('data-theme', dark ? 'dark' : 'light');
  }, [dark]);

  return (
    <Layout style={{ minHeight: '100vh', marginLeft: collapsed ? 80 : 200  }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        trigger={null}
        style={{ position: 'fixed', height: '100vh', left: 0, top: 0, bottom: 0, zIndex: 1000  }}
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
          ]}
          style={{ paddingTop: '56px' }}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            padding: '0 16px',
            background: dark ? '#1f1f1f' : '#fff',
            height: '48px',
            lineHeight: '48px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <Typography.Title level={4} style={{ margin: 0, color: dark ? '#fff' : '#000' }}>
            {pageTitle || t('app_title', 'Inventory Management')}
          </Typography.Title>
          <div style={{ position: 'absolute', top: 0, right: 0 }}>
            <HeaderWidget />
          </div>
        </Header>
        <Content
          style={{
            margin: 0,
            padding: '16px',
            minHeight: 'calc(100vh - 48px)',
          }}
        >
          {children}
        </Content>
      </Layout>
    </Layout>
  );
};

export default AppLayout;