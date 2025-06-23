// src/App.tsx
import { useState } from 'react';
import { Routes, Route, useNavigate, useSearchParams } from 'react-router-dom';
import { Layout, Menu, Input } from 'antd';
import { Link } from 'react-router-dom';
import Dashboard from './components/Dashboard';
import ComputerList from './components/ComputerList';
import ComputerDetail from './components/ComputerDetail';
import Settings from './components/Settings';
import AdminPanel from './components/AdminPanel';

const { Header, Content, Sider } = Layout;

const App: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [searchQuery, setSearchQuery] = useState(searchParams.get('hostname') || '');
  const navigate = useNavigate();

  const handleSearch = () => {
    if (searchQuery.trim()) {
      setSearchParams({
        ...Object.fromEntries(searchParams),
        hostname: searchQuery,
        page: '1',
      });
      navigate(`/computers`);
    }
  };

  const menuItems = [
    { key: '1', label: <Link to="/">Dashboard</Link> },
    { key: '2', label: <Link to="/computers">Компьютеры</Link> },
    { key: '3', label: <Link to="/settings">Настройки</Link> },
    { key: '4', label: <Link to="/admin">Администрирование</Link> },
  ];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider>
        <Menu theme="dark" mode="inline" defaultSelectedKeys={['1']} items={menuItems} />
      </Sider>
      <Layout>
        <Header style={{ background: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 16px' }}>
          <Input.Search
            placeholder="Поиск по hostname..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onSearch={handleSearch}
            style={{ width: 200 }}
          />
        </Header>
        <Content style={{ padding: 16, background: '#fff' }}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/computers" element={<ComputerList />} />
            <Route path="/computer/:computerId" element={<ComputerDetail />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/admin" element={<AdminPanel />} /> {/* Добавлен маршрут для админки */}
          </Routes>
        </Content>
      </Layout>
    </Layout>
  );
};

export default App;