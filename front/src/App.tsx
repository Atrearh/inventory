import { Routes, Route, Navigate } from 'react-router-dom';
import { Suspense, lazy, useContext } from 'react';
import { useAuth } from './context/AuthContext';
import { ThemeContext } from './context/ThemeContext';
import Login from './components/Login';
import NotFound from './components/NotFound';
import Layout from './components/Layout';
import { useTranslation } from 'react-i18next';
import { ConfigProvider, theme as antdTheme } from 'antd';

const Dashboard = lazy(() => import('./components/Dashboard'));
const ComputerList = lazy(() => import('./components/ComputerList'));
const ComputerDetail = lazy(() => import('./components/ComputerDetail'));
const Settings = lazy(() => import('./components/Settings'));
const AdminPanel = lazy(() => import('./components/AdminPanel'));

const ProtectedRoute: React.FC<{ children: JSX.Element }> = ({ children }) => {
  const { t } = useTranslation();
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <div>{t('loading')}</div>;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return children;
};

const App: React.FC = () => {
  const { isAuthenticated, isLoading } = useAuth();
  const { t } = useTranslation();
  const { dark } = useContext(ThemeContext);

  if (isLoading) return <div>{t('loading')}</div>;

  return (
    <ConfigProvider
      theme={{
        algorithm: dark ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
        token: !dark
          ? {
              colorBgBase: '#f5f5f5', // фон трохи сіріший
              colorBgContainer: '#fafafa', // фон карток/контейнерів
              colorBorder: '#d9d9d9', // приглушені рамки
              colorText: '#333', // не чисто чорний, а темно-сірий
            }
          : {},
      }}
    >
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="*"
          element={
            isAuthenticated ? (
              <Suspense fallback={<div>{t('loading')}</div>}>
                <Layout>
                  <Routes>
                    <Route path="/" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
                    <Route path="/computers" element={<ProtectedRoute><ComputerList /></ProtectedRoute>} />
                    <Route path="/computer/:computerId" element={<ProtectedRoute><ComputerDetail /></ProtectedRoute>} />
                    <Route path="/settings" element={<ProtectedRoute><Settings /></ProtectedRoute>} />
                    <Route path="/admin" element={<ProtectedRoute><AdminPanel /></ProtectedRoute>} />
                    <Route path="*" element={<NotFound />} />
                  </Routes>
                </Layout>
              </Suspense>
            ) : (
              <Navigate to="/login" replace />
            )
          }
        />
      </Routes>
    </ConfigProvider>
  );
};

export default App;