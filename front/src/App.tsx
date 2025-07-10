import { Routes, Route } from 'react-router-dom';
import { Layout, Menu } from 'antd';
import { Link } from 'react-router-dom';
import Dashboard from './components/Dashboard';
import ComputerList from './components/ComputerList';
import ComputerDetail from './components/ComputerDetail';
import Settings from './components/Settings';
import AdminPanel from './components/AdminPanel';
import NotFound from './components/NotFound';

const { Content, Sider } = Layout;

const App: React.FC = () => { 
  const menuItems = [
    { key: '1', label: <Link to="/">Панель управління</Link> },
    { key: '2', label: <Link to="/computers">Комп'ютери</Link> },
    { key: '3', label: <Link to="/settings">Налаштування</Link> },
    { key: '4', label: <Link to="/admin">Адміністрування</Link> },
  ];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider>
        <Menu theme="dark" mode="inline" defaultSelectedKeys={['1']} items={menuItems} />
      </Sider>
      <Layout>
        <Content style={{ padding: 16, background: '#fff' }}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/computers" element={<ComputerList />} />
            <Route path="/computer/:computerId" element={<ComputerDetail />} />
            <Route path="/computers/:computerId" element={<ComputerDetail />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/admin" element={<AdminPanel />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  );
};

export default App;