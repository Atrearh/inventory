import { Routes, Route, Navigate } from 'react-router-dom';
import { Layout, Menu } from 'antd';
import { Link } from 'react-router-dom';
import Dashboard from './components/Dashboard';
import ComputerList from './components/ComputerList';
import ComputerDetail from './components/ComputerDetail';
import Settings from './components/Settings';
import AdminPanel from './components/AdminPanel';
import NotFound from './components/NotFound';
import { useAuth } from './context/AuthContext';
import Login from './components/Login';

const { Content, Sider } = Layout;

const ProtectedRoute: React.FC<{ children: JSX.Element }> = ({ children }) => {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return children;
};

const App: React.FC = () => {
  const { isAuthenticated } = useAuth();

  const menuItems = [
    { key: '1', label: <Link to="/">Статистика</Link> },
    { key: '2', label: <Link to="/computers">Комп'ютери</Link> },
    { key: '3', label: <Link to="/settings">Налаштування</Link> },
    { key: '4', label: <Link to="/admin">Адміністрування</Link> },
  ];

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      {isAuthenticated ? (
        <Route
          path="*"
          element={
            <Layout style={{padding: 0 , minHeight: '100vh' }}>
              <Sider>
                <Menu theme="dark" mode="inline" defaultSelectedKeys={['1']} items={menuItems} />
              </Sider>
              <Layout>
                <Content style={{padding: 0, background: '#fff' }}>
                  <Routes>
                    <Route path="/" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
                    <Route path="/computers" element={<ProtectedRoute><ComputerList /></ProtectedRoute>} />
                    <Route path="/computer/:computerId" element={<ProtectedRoute><ComputerDetail /></ProtectedRoute>} />
                    <Route path="/settings" element={<ProtectedRoute><Settings /></ProtectedRoute>} />
                    <Route path="/admin" element={<ProtectedRoute><AdminPanel /></ProtectedRoute>} />
                    <Route path="*" element={<NotFound />} />
                  </Routes>
                </Content>
              </Layout>
            </Layout>
          }
        />
      ) : (
        <Route path="*" element={<Navigate to="/login" replace />} />
      )}
    </Routes>
  );
};

export default App;