import React, { useState } from 'react';
import { Layout, Menu, Button } from 'antd';
import { Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

const { Sider, Content, Header } = Layout;

const AppLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const location = useLocation();
  const { t, i18n } = useTranslation();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider collapsible collapsed={collapsed} onCollapse={setCollapsed}>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={[
            { key: '/', label: <Link to="/">{t('dashboard')}</Link> },
            { key: '/computers', label: <Link to="/computers">{t('computers')}</Link> },
            { key: '/admin', label: <Link to="/admin">{t('admin')}</Link> },
            { key: '/settings', label: <Link to="/settings">{t('settings')}</Link> },
          ]}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            display: 'flex',
            justifyContent: 'flex-end',
            alignItems: 'center',
            padding: '0 16px',
            background: '#fff',
          }}
        >
          <Button
            size="small"
            style={{ marginRight: 8 }}
            onClick={() => i18n.changeLanguage(i18n.language === 'ua' ? 'en' : 'ua')}
          >
            {i18n.language === 'ua' ? 'EN' : 'UA'}
          </Button>
        </Header>
        <Content style={{ margin: '16px' }}>{children}</Content>
      </Layout>
    </Layout>
  );
};

export default AppLayout;
